from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status

from app.schemas.student_status import (
    AssignmentResponse,
    SelectSlotRequest,
    MyInterviewResponse,
)
from app.schemas.slots import SlotResponse
from app.schemas.bookings import (
    ScheduleInterviewResponse,
    BookingResponse,
)
from app.schemas.interviews import (
    EvaluationResponse,
    RoundEvaluationResponse,
)
from app.services.container import (
    assignment_service,
    booking_service,
    email_service,
    slot_service,
    user_service,
    evaluation_service,
    transcript_storage_service,
)
from app.utils.logger import get_logger
import asyncio

logger = get_logger(__name__)
from app.utils.datetime_utils import get_now_ist, parse_datetime_safe
from app.utils.url_helper import get_frontend_url
from app.utils.auth_dependencies import get_current_student

# Student-facing endpoints
router = APIRouter(tags=["Student"])


@router.get("/application-form")
async def get_application_form_compat():
    """
    Backwards-compatibility shim for legacy application-form endpoint.

    The dedicated student application form feature has been removed in favor of
    simple resume upload, but some frontend code still calls this endpoint.
    We return `null` instead of 404 so the UI can treat it as "no form data".
    """
    return None


@router.post("/application-form/upload")
async def upload_application_form_compat(file: UploadFile = File(...)):
    """
    Backwards-compatibility shim for legacy application-form PDF upload.

    We no longer persist a structured application form; resume upload is handled
    separately. This endpoint now just validates that a file was provided and
    returns a success flag so existing frontend flows don't break.
    """
    try:
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided",
            )

        # Read the file once to consume the upload; result is ignored.
        await file.read()

        return {
            "success": True,
            "form": None,
            "extraction_error": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Compatibility upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process uploaded file.",
        )


@router.get("/my-assignments", response_model=List[AssignmentResponse])
async def get_my_assignments(current_student: dict = Depends(get_current_student)):
    """
    Get all slot assignments for the current student.
    Returns only assigned (not yet selected) slots.
    """
    try:
        student_id = current_student['id']
        assignments = assignment_service.get_user_assignments(student_id, status='assigned')
        
        # Format response
        result = []
        for assignment in assignments:
            slot_data = assignment.get('interview_slots')
            if slot_data:
                # Handle nested slot data
                if isinstance(slot_data, dict):
                    slot = SlotResponse(**slot_data)
                elif isinstance(slot_data, list) and len(slot_data) > 0:
                    slot = SlotResponse(**slot_data[0])
                else:
                    continue
                
                result.append(AssignmentResponse(
                    id=assignment['id'],
                    user_id=assignment['user_id'],
                    slot_id=assignment['slot_id'],
                    status=assignment['status'],
                    assigned_at=assignment['assigned_at'],
                    selected_at=assignment.get('selected_at'),
                    slot=slot
                ))
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to fetch assignments: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.post("/select-slot", response_model=ScheduleInterviewResponse)
async def select_slot(
    request: SelectSlotRequest,
    http_request: Request,
    current_student: dict = Depends(get_current_student)
):
    """
    Select a slot for the authenticated student. 
    Accepts slot_id and optional prompt. Creates a booking and cancel other assignments.
    """
    try:
        student_email = current_student['email']
        auth_user_id = current_student['id']
        
        # Get enrolled_user for fallback name/phone
        enrolled_user = user_service.get_user_by_email(student_email)
        
        print("JWT USER:", auth_user_id)
        slot_id = request.slot_id
        prompt = request.prompt
        
        # REMOVED: Application form check (feature deprecated)
        # application_form = application_form_service.get_form_by_user_id(auth_user_id) ...

        # 3. Get slot details and verify availability
        slot = slot_service.get_slot(slot_id)
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")
            
        if slot['status'] != 'active':
            raise HTTPException(status_code=400, detail="Slot is not available")
            
        if slot['current_bookings'] >= slot['max_capacity']:
            raise HTTPException(status_code=400, detail="Slot is full")

        # 4. Check for existing assignment for this slot
        assignments = assignment_service.get_user_assignments(auth_user_id, status='assigned')
        assignment = next((a for a in assignments if a['slot_id'] == slot_id), None)
        
        # If no assignment exists but slot is public/available, we can create one or allow it?
        # Current logic seems to prefer assignments. If none found, we'll try to create a virtual one.
        if not assignment:
            logger.info(f"[API] Student {auth_user_id} selecting slot directly: {slot_id}")
            try:
                new_assignments = assignment_service.assign_slots_to_user(auth_user_id, [slot_id])
                if new_assignments:
                    assignment = new_assignments[0]
                else:
                    raise HTTPException(status_code=500, detail="Failed to create slot assignment")
            except Exception as e:
                logger.error(f"[API] Failed to create assignment: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to create slot assignment")

        # 5. Parse slot datetime
        slot_datetime_str = slot.get('slot_datetime') or slot.get('start_time')
        scheduled_at = parse_datetime_safe(slot_datetime_str)

        # 6. Create booking
        token = booking_service.create_booking(
            name=current_student.get('name', enrolled_user.get('name', 'Student') if enrolled_user else 'Student'),
            email=student_email,
            scheduled_at=scheduled_at,
            phone=current_student.get('phone', enrolled_user.get('phone', '') if enrolled_user else ''),
            application_text=None, # Form removed
            application_url=None,
            slot_id=slot_id,
            user_id=auth_user_id, # Use Auth ID for the booking record
            assignment_id=assignment['id'],
            application_form_id=None, # Form removed
            prompt=prompt # Include the prompt from the request
        )

        # 7. Update status: mark assignment used, cancel others, increment count
        assignment_service.select_slot_for_user(auth_user_id, assignment['id'])
        assignment_service.cancel_other_assignments(auth_user_id, assignment['id'])
        slot_service.increment_booking_count(slot_id)
        user_service.update_user(auth_user_id, interview_status='slot_selected')

        # 8. Generate interview URL and send email
        base_url = get_frontend_url(http_request)
        interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"
        
        async def send_email_bg():
            try:
                await email_service.send_interview_email(
                    to_email=student_email,
                    name=enrolled_user.get('name', 'Student') if enrolled_user else 'Student',
                    interview_url=interview_url,
                    scheduled_at=scheduled_at,
                )
            except Exception as e:
                logger.warning(f"[API] ⚠️ Failed to send interview email: {e}")
        
        asyncio.create_task(send_email_bg())
        
        return ScheduleInterviewResponse(
            ok=True,
            interviewUrl=interview_url,
            emailSent=True, # We've queued it
            emailError=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to select slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@router.get("/my-interview", response_model=MyInterviewResponse)
async def get_my_interview(http_request: Request, current_student: dict = Depends(get_current_student)):
    """
    Get student's interview status across all stages (enrolled/scheduled/completed).
    """
    try:
        student_id = current_student['id']
        student_email = current_student['email']
        
        # Get enrolled_user for legacy data fallback
        enrolled_user = user_service.get_user_by_email(student_email)
        
        # Get current time
        now = get_now_ist()
        logger.info(f"[API] Current IST time: {now.isoformat()}")
        
        logger.info(f"[API] Checking bookings by email: {student_email}")
        email_bookings = booking_service.get_bookings_by_email(student_email)
        logger.info(f"[API] Found {len(email_bookings)} bookings by email: {student_email}")
        
        # Use student_id (auth ID) as primary, but fallback to enrolled_user_id for legacy cleanup
        user_id = student_id
        legacy_user_id = enrolled_user['id'] if enrolled_user else None
        
        user_id_bookings = booking_service.get_bookings_by_user_id(user_id)
        if legacy_user_id and legacy_user_id != user_id:
            legacy_bookings = booking_service.get_bookings_by_user_id(legacy_user_id)
            user_id_bookings.extend(legacy_bookings)
            
        logger.info(f"[API] Found {len(user_id_bookings)} total bookings by user IDs")
        seen_tokens = set()
        all_bookings_data = []
        for booking in email_bookings + user_id_bookings:
            token = booking.get('token')
            if token and token not in seen_tokens:
                seen_tokens.add(token)
                slot = slot_service.get_slot(booking['slot_id']) if booking.get('slot_id') else None
                booking['slot'] = slot
                booking['interview_slots'] = slot
                all_bookings_data.append(booking)
        for booking in email_bookings:
            if not booking.get('user_id') and user_id and booking.get('token'):
                try:
                    booking_service.update_booking(booking['token'], user_id=user_id)
                    booking['user_id'] = user_id
                    logger.info(f"[API] ✅ Updated booking {booking['token']} with user_id: {user_id}")
                except Exception as e:
                    logger.warning(f"[API] Failed to update booking {booking.get('token')}: {e}")
        if not enrolled_user:
            logger.warning(f"[API] No enrolled_user for email {student_email}, using email-based bookings only")
        class MockResult:
            def __init__(self, data):
                self.data = data
        all_bookings = MockResult(all_bookings_data)
        logger.info(f"[API] Total unique bookings found: {len(all_bookings_data)}")
        completed_tokens = set()
        if all_bookings.data:
            booking_tokens = [b.get('token') for b in all_bookings.data if b.get('token')]
            if booking_tokens:
                try:
                    evaluation_tokens = evaluation_service.get_booking_tokens_with_evaluations(booking_tokens)
                    transcript_tokens = transcript_storage_service.get_booking_tokens_with_transcripts(booking_tokens)
                    completed_status_tokens = {b.get('token') for b in all_bookings.data if b.get('status') == 'completed'}
                    completed_tokens = evaluation_tokens | transcript_tokens | completed_status_tokens
                    logger.info(f"[API] Completed: {len(completed_tokens)} (evals: {len(evaluation_tokens)}, transcripts: {len(transcript_tokens)}, status: {len(completed_status_tokens)})")
                except Exception as e:
                    logger.warning(f"[API] Failed to fetch completion evidence: {e}")
        
        # Separate upcoming, missed, and completed interviews
        upcoming_bookings = []
        missed_bookings = []
        completed_bookings = []
        
        if all_bookings.data:
            for booking in all_bookings.data:
                try:
                    # Parse the stored datetime - handle UTC or IST format properly
                    scheduled_at_str = booking['scheduled_at']
                    scheduled_at = parse_datetime_safe(scheduled_at_str)
                    booking_token = booking.get('token')
                    booking_status = booking.get('status', 'scheduled')
                    
                    # Get interview duration from slot if available, otherwise default to 30 minutes
                    duration_minutes = 30  # Default duration
                    slot_data = booking.get('interview_slots')
                    if slot_data:
                        if slot_data.get('duration_minutes'):
                            duration_minutes = slot_data['duration_minutes']
                        elif slot_data.get('end_time') and slot_data.get('slot_datetime'):
                            # Calculate duration from slot start and end times
                            try:
                                slot_start_str = slot_data.get('slot_datetime', '')
                                slot_end_str = slot_data.get('end_time', '')
                                if slot_start_str and slot_end_str:
                                    slot_start = parse_datetime_safe(slot_start_str)
                                    slot_end = parse_datetime_safe(slot_end_str)
                                    duration_minutes = int((slot_end - slot_start).total_seconds() / 60)
                            except (ValueError, TypeError) as e:
                                logger.warning(f"[API] Failed to calculate duration from slot times: {e}")
                                pass  # Use default duration if calculation fails
                    
                    # Calculate interview end time
                    interview_end_time = scheduled_at + timedelta(minutes=duration_minutes)
                    
                    # Check if interview window has passed (end time, not start time)
                    time_diff = (interview_end_time - now).total_seconds() / 60  # minutes
                    
                    if interview_end_time < now:
                        # Interview window has passed - check if it was completed
                        # Mark as completed if:
                        # 1. Booking status is 'completed', OR
                        # 2. There's an evaluation record (interview was actually conducted), OR
                        # 3. There's a transcript (interview was conducted)
                        is_completed = (
                            booking_status == 'completed' or 
                            booking_token in completed_tokens or
                            booking.get('status') == 'completed'
                        )
                        
                        if is_completed:
                            completed_bookings.append(booking)
                        else:
                            # Interview window passed but not completed = missed
                            missed_bookings.append(booking)
                    else:
                        # Interview window hasn't passed yet = upcoming
                        upcoming_bookings.append(booking)
                except (ValueError, KeyError, TypeError) as e:
                    pass
        
        # Build upcoming interviews list
        upcoming = []
        for booking in sorted(upcoming_bookings, key=lambda x: x.get('scheduled_at', '')):
            slot_data = booking.get('interview_slots')
            base_url = get_frontend_url(http_request)
            interview_url = f"{base_url}/interview/{booking['token']}" if base_url else f"/interview/{booking['token']}"
            
            upcoming.append({
                'booking': {
                    'token': booking['token'],
                    'scheduled_at': booking['scheduled_at'],
                    'interview_url': interview_url,
                    'name': booking.get('name'),
                    'email': booking.get('email'),
                },
                'slot': slot_data if slot_data else None,
            })
        
        # Build missed interviews list
        missed = []
        for booking in sorted(missed_bookings, key=lambda x: x.get('scheduled_at', ''), reverse=True):
            slot_data = booking.get('interview_slots')
            base_url = get_frontend_url(http_request)
            interview_url = f"{base_url}/interview/{booking['token']}" if base_url else f"/interview/{booking['token']}"
            
            missed.append({
                'booking': {
                    'token': booking['token'],
                    'scheduled_at': booking['scheduled_at'],
                    'interview_url': interview_url,
                    'name': booking.get('name'),
                    'email': booking.get('email'),
                    'status': booking.get('status', 'scheduled'),
                },
                'slot': slot_data if slot_data else None,
            })
        
        # Build completed interviews list
        completed = []
        for booking in sorted(completed_bookings, key=lambda x: x.get('scheduled_at', ''), reverse=True):
            slot_data = booking.get('interview_slots')
            base_url = get_frontend_url(http_request)
            evaluation_url = f"{base_url}/evaluation/{booking['token']}" if base_url else f"/evaluation/{booking['token']}"
            
            completed.append({
                'booking': {
                    'token': booking['token'],
                    'scheduled_at': booking['scheduled_at'],
                    'evaluation_url': evaluation_url,
                    'name': booking.get('name'),
                    'email': booking.get('email'),
                    'status': booking.get('status', 'completed'),
                },
                'slot': slot_data if slot_data else None,
            })
        
        return MyInterviewResponse(
            upcoming=upcoming,
            missed=missed,
            completed=completed
        )
        
    except Exception as e:
        error_msg = f"Failed to fetch interview status: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
