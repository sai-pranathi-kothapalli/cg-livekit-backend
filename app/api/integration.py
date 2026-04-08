from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from typing import List, Optional
from app.utils.integration_auth import IntegrationAuth
from app.utils.sanitize import sanitize_string, sanitize_email, sanitize_name

# Import services — adjust these imports based on your container/dependency injection pattern
from app.services.container import (
    integration_auth,
    user_service,
    slot_service,
    booking_service,
    evaluation_service,
)

router = APIRouter(tags=["Integration"])


# ============================================================
# Schemas
# ============================================================

class StudentInput(BaseModel):
    student_id: str  # UUID from LMS
    email: str
    name: str
    batch: str
    location: str

    @field_validator('email')
    @classmethod
    def clean_email(cls, v):
        return sanitize_email(v)

    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        return sanitize_name(v)

    @field_validator('batch', 'location')
    @classmethod
    def clean_text(cls, v):
        return sanitize_string(v, max_length=255)


class EnrollStudentsRequest(BaseModel):
    batch: str
    location: str
    students: List[StudentInput]

    @field_validator('batch', 'location')
    @classmethod
    def clean_text(cls, v):
        return sanitize_string(v, max_length=255)


class ScheduleInterviewRequest(BaseModel):
    batch: str
    location: str
    student_ids: Optional[List[str]] = None  # Array of external student UUIDs
    date: str  # "2026-04-07"
    window_start: str  # "08:00"
    window_end: str  # "20:00"
    interview_duration: int  # minutes
    curriculum_topics: Optional[str] = None
    capacity: Optional[int] = 30
    student_id: Optional[str] = None

    @field_validator('batch', 'location', 'student_id')
    @classmethod
    def clean_text(cls, v):
        return sanitize_string(v, max_length=255)

    @field_validator('curriculum_topics')
    @classmethod
    def clean_topics(cls, v):
        if v:
            return sanitize_string(v, max_length=5000)
        return v

    @field_validator('interview_duration')
    @classmethod
    def valid_duration(cls, v):
        if v < 5 or v > 120:
            raise ValueError("interview_duration must be between 5 and 120 minutes")
        return v

    @field_validator('capacity')
    @classmethod
    def valid_capacity(cls, v):
        if v and (v < 1 or v > 200):
            raise ValueError("capacity must be between 1 and 200")
        return v


class BookSlotRequest(BaseModel):
    external_student_id: str  # External UUID from LMS
    batch: str
    slot_id: str  # UUID of the slot to book

    @field_validator('batch')
    @classmethod
    def clean_batch(cls, v):
        return sanitize_string(v, max_length=255)


class BookSlotResponse(BaseModel):
    slotId: str
    bookingToken: str
    interviewLink: str
    scheduledAt: Optional[str]
    slotTime: Optional[str]
    endTime: Optional[str]
    date: Optional[str]
    durationMinutes: Optional[int]


class RegisterWebhookRequest(BaseModel):
    target_url: str
    events: Optional[List[str]] = ["EVALUATION_COMPLETED"]
    secret: Optional[str] = None
    batch_filter: Optional[str] = None
    name: Optional[str] = "LMS Webhook"


# ============================================================
# Endpoints
# ============================================================

@router.get("/health")
async def integration_health(api_key_info: dict = Depends(integration_auth.verify_key)):
    """Health check — validates API key is working."""
    return {
        "status": "ok",
        "authenticated_as": api_key_info.get("key_name"),
    }


@router.post("/enroll-students")
async def enroll_students(
    request: EnrollStudentsRequest,
    api_key_info: dict = Depends(integration_auth.verify_key)
):
    """
    Bulk enroll students from LMS.
    Idempotent — enrolling the same student_id twice returns 'already_existed'.
    """
    try:
        results = await user_service.enroll_integration_students(
            batch=request.batch,
            location=request.location,
            students=[s.model_dump() for s in request.students]
        )

        return {
            "success": True,
            "batch": request.batch,
            "results": results,
            "summary": {
                "created": len(results.get("created", [])),
                "already_existed": len(results.get("already_existed", [])),
                "failed": len(results.get("failed", [])),
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {str(e)}")


@router.get("/students")
async def get_students_by_batch(
    batch: str = Query(..., description="Batch code, e.g. PFS-106"),
    api_key_info: dict = Depends(integration_auth.verify_key)
):
    """
    Get all enrolled students for a batch.
    LMS uses this to verify enrollment sync and cross-check student lists.
    """
    try:
        from app.utils.sanitize import sanitize_string
        batch = sanitize_string(batch, max_length=255)

        students = user_service.get_students_by_batch(batch)

        formatted = []
        for s in students:
            formatted.append({
                "student_id": s.get("external_student_id"),
                "email": s.get("email"),
                "name": s.get("name"),
                "batch": s.get("batch"),
                "location": s.get("location"),
                "status": s.get("status"),
                "enrolled_at": s.get("created_at"),
            })

        return {
            "success": True,
            "batch": batch,
            "total": len(formatted),
            "students": formatted,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch students: {str(e)}")


@router.post("/schedule-interview")
async def schedule_interview(
    request: ScheduleInterviewRequest,
    api_key_info: dict = Depends(integration_auth.verify_key)
):
    """
    Create interview slots for a batch within a time window.
    Generates 30-min slots from window_start to window_end.
    If student_ids provided, validate all are enrolled.
    """
    # If student_ids provided, validate all are enrolled
    enrollment_check = None
    if request.student_ids and len(request.student_ids) > 0:
        enrolled = []
        not_enrolled = []

        for sid in request.student_ids:
            student = user_service.resolve_external_student_id(sid)
            if student:
                enrolled.append(sid)
            else:
                not_enrolled.append(sid)

        enrollment_check = {
            "total_students": len(request.student_ids),
            "enrolled": len(enrolled),
            "not_enrolled": not_enrolled,
        }

        # If any students aren't enrolled, warn but don't block
        if not_enrolled:
            import logging
            logging.getLogger(__name__).warning(
                f"Schedule interview for {request.batch}: "
                f"{len(not_enrolled)} student(s) not enrolled: {not_enrolled[:5]}"
            )

    try:
        slots = await slot_service.create_window_slots(
            batch=request.batch,
            location=request.location,
            date=request.date,
            window_start=request.window_start,
            window_end=request.window_end,
            interview_duration=request.interview_duration,
            curriculum_topics=request.curriculum_topics,
            capacity=request.capacity or 30,
            student_id=request.student_id,
            created_by=api_key_info.get("id"),
        )

        # Format response to match what LMS expects
        formatted_slots = []
        for slot in slots:
            formatted_slots.append({
                "slot_id": slot.get("id"),
                "slot_time": slot.get("start_time"),
                "end_time": slot.get("end_time"),
                "duration_minutes": slot.get("duration_minutes"),
                "capacity": slot.get("capacity"),
                "booked": slot.get("booked_count", 0),
            })

        response = {
            "success": True,
            "batch": request.batch,
            "date": request.date,
            "total_slots": len(formatted_slots),
            "slots": formatted_slots,
        }

        # Include enrollment check if student_ids were provided
        if enrollment_check:
            response["student_validation"] = enrollment_check

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule creation failed: {str(e)}")


@router.get("/slots")
async def get_slots_by_batch(
    batch: str = Query(..., description="Batch code, e.g. PFS-106"),
    api_key_info: dict = Depends(integration_auth.verify_key)
):
    """
    Get all slots for a batch with current availability.
    LMS uses this to show the slot booking grid to students.
    """
    try:
        batch = sanitize_string(batch, max_length=255)
        slots = slot_service.get_slots_by_batch(batch)

        formatted = []
        for slot in slots:
            formatted.append({
                "slot_id": slot.get("id"),
                "slot_time": slot.get("start_time"),
                "slot_datetime": slot.get("slot_datetime"),
                "end_time": slot.get("end_time"),
                "duration_minutes": slot.get("duration_minutes"),
                "capacity": slot.get("capacity"),
                "booked": slot.get("booked_count", 0),
                "available": slot.get("available", 0),
                "status": slot.get("status"),
            })

        return {
            "success": True,
            "batch": batch,
            "total_slots": len(formatted),
            "slots": formatted,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch slots: {str(e)}")


@router.post("/book-slot", response_model=BookSlotResponse)
async def book_slot(
    request: BookSlotRequest,
    api_key_info: dict = Depends(integration_auth.verify_key)
):
    """
    Book a student into a slot. Returns the interview link.
    
    Uses external student_id from LMS — resolves to internal user automatically.
    Atomic slot reservation — no overbooking possible.
    """
    try:
        result = await booking_service.create_integration_booking(
            external_student_id=request.external_student_id,
            batch=request.batch,
            slot_id=request.slot_id,
            user_service=user_service,
        )

        return result.get("data", result)

    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Booking failed: {str(e)}")


@router.get("/evaluation/{booking_token}")
async def get_evaluation(
    booking_token: str,
    api_key_info: dict = Depends(integration_auth.verify_key)
):
    """
    Get evaluation results for a completed interview.
    Includes scores, feedback, transcript, student_id, batch.
    """
    try:
        from app.utils.sanitize import sanitize_uuid
        booking_token = sanitize_uuid(booking_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        evaluation = evaluation_service.get_evaluation_with_context(booking_token)

        if not evaluation:
            raise HTTPException(status_code=404, detail="Evaluation not found for this booking token")

        return {
            "success": True,
            **evaluation,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch evaluation: {str(e)}")


@router.post("/register-webhook")
async def register_webhook(
    request: RegisterWebhookRequest,
    api_key_info: dict = Depends(integration_auth.verify_key)
):
    """
    Register a webhook URL to receive evaluation results.
    AI Interview will POST to this URL when a student completes an interview.
    """
    try:
        from app.db.supabase import get_supabase
        supabase_client = get_supabase()

        result = supabase_client.table('webhooks_registry').insert({
            'name': request.name,
            'target_url': request.target_url,
            'events': request.events,
            'secret': request.secret,
            'batch_filter': request.batch_filter,
            'active': True,
        }).execute()

        if not result.data:
            raise Exception("Failed to register webhook")

        webhook = result.data[0]

        return {
            "success": True,
            "webhook_id": webhook.get("id"),
            "target_url": request.target_url,
            "events": request.events,
            "message": "Webhook registered. You will receive POST requests at this URL when events occur."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook registration failed: {str(e)}")


@router.get("/evaluation-by-student")
async def get_evaluation_by_student(
    student_id: str = Query(..., description="External student ID from LMS"),
    batch: str = Query(..., description="Batch code"),
    api_key_info: dict = Depends(integration_auth.verify_key)
):
    """
    Get evaluation results for a student in a specific batch.
    Uses the new student_id and batch columns in the evaluations table for direct lookup.
    """
    try:
        from app.db.supabase import get_supabase
        supabase = get_supabase()
        
        # Search directly in evaluations table using the new columns
        res = supabase.table("evaluations").select("booking_token").eq("student_id", student_id).eq("batch", batch).order("created_at", desc=True).limit(1).execute()
        
        if not res.data:
            raise HTTPException(
                status_code=404, 
                detail=f"No interview result found for student '{student_id}' in batch '{batch}'. "
                       f"The interview may not have been completed yet."
            )
            
        booking_token = res.data[0].get("booking_token")
        
        # Use service to get enriched evaluation context
        evaluation = evaluation_service.get_evaluation_with_context(booking_token)
        
        if not evaluation:
            raise HTTPException(status_code=404, detail="Evaluation details missing for found record")

        return {
            "success": True,
            **evaluation,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search evaluation: {str(e)}")
