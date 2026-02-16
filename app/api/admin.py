from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status

from app.schemas.bookings import (
    BookingResponse,
    PaginatedCandidatesResponse,
    ScheduleInterviewResponse,
)
from app.schemas.admin import (
    JobDescriptionRequest,
    JobDescriptionResponse,
    ManagerRegistrationRequest,
    ManagerResponse,
    SystemInstructionsRequest,
    SystemInstructionsResponse,
    CandidateRegistrationRequest,
    CandidateRegistrationRequest,
    BulkRegistrationResponse,
)
from app.schemas.users import (
    ScheduleInterviewForUserRequest,
    ScheduleInterviewForUserRequest,
    BulkScheduleInterviewResponse,
    BulkScheduleRequest,
)
from app.utils.url_helper import get_frontend_url
import pandas as pd
from io import BytesIO

from app.services.container import (
    booking_service,
    email_service,
    system_instructions_service,
    user_service,
    slot_service,
    auth_service,
)
from app.utils.logger import get_logger
from app.utils.auth_dependencies import get_current_admin
from app.db.supabase import get_supabase
from app.utils.datetime_utils import (
    IST,
    get_now_ist,
    to_ist,
    parse_datetime_safe,
    validate_scheduled_time
)
import asyncio

logger = get_logger(__name__)

# Admin-only management and configuration endpoints
router = APIRouter(tags=["Admin"])


@router.get("/job-description", response_model=JobDescriptionResponse)
async def get_job_description(current_admin: dict = Depends(get_current_admin)):
    """
    Get current job description / system instructions from database.
    Requires admin authentication.
    """
    try:
        data = system_instructions_service.get_system_instructions()
        return JobDescriptionResponse(context=data.get("instructions", ""))
    except Exception as e:
        logger.error(f"[API] Error fetching system instructions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch system instructions: {str(e)}"
        )


@router.put("/job-description", response_model=JobDescriptionResponse)
async def update_job_description(jd: JobDescriptionRequest, current_admin: dict = Depends(get_current_admin)):
    """
    Update job description / system instructions in database.
    Requires admin authentication.
    """
    try:
        ctx_len = len(jd.context or "")
        logger.info(f"[API] Updating system instructions (received length={ctx_len})")

        # Save to database
        updated = system_instructions_service.update_system_instructions(instructions=jd.context)

        logger.info(f"[API] ✅ System instructions saved to database")
        return JobDescriptionResponse(context=updated.get("instructions", ""))
    except Exception as e:
        logger.error(f"[API] Error updating system instructions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update system instructions: {str(e)}"
        )


@router.post("/managers", response_model=ManagerResponse)
async def enroll_manager(
    request: ManagerRegistrationRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Enroll a new manager. Auto-generates a temporary password.
    Requires admin authentication.
    """
    try:
        logger.info(f"[API] Enrolling manager: {request.email}")
        # Reuse auth_service via app.api.main imports if needed; here result is built upstream.
        from app.api.main import auth_service  # local import to avoid cycles

        result = auth_service.register_manager(
            name=request.name,
            email=request.email,
        )
        return ManagerResponse(**result)
    except Exception as e:
        logger.error(f"[API] Error enrolling manager: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/managers", response_model=List[ManagerResponse])
async def list_managers(current_admin: dict = Depends(get_current_admin)):
    """
    List all managers.
    Requires admin authentication.
    """
    try:
        client = get_supabase()
        response = client.table("users").select("*").eq("role", "manager").order("created_at", desc=True).execute()
        managers: List[ManagerResponse] = []
        for m in (response.data or []):
            managers.append(ManagerResponse(
                id=m["id"],
                username=m.get("username", ""),
                email=m.get("email", ""),
                name=m.get("name"),
                phone=m.get("phone"),
                role="manager",
                created_at=m.get("created_at"),
            ))
        return managers
    except Exception as e:
        logger.error(f"[API] Error listing managers: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list managers: {str(e)}"
        )


@router.delete("/managers/{manager_id}")
async def delete_manager(manager_id: str, current_admin: dict = Depends(get_current_admin)):
    """
    Delete a manager by ID.
    Requires admin authentication.
    """
    try:
        client = get_supabase()
        client.table("users").delete().eq("id", manager_id).eq("role", "manager").execute()
        return {"success": True, "message": f"Manager {manager_id} deleted"}
    except Exception as e:
        logger.error(f"[API] Error deleting manager: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete manager: {str(e)}"
        )


@router.get("/system-instructions", response_model=SystemInstructionsResponse)
async def get_system_instructions(current_admin: dict = Depends(get_current_admin)):
    """
    Get current system instructions.
    Requires admin authentication.
    """
    try:
        data = system_instructions_service.get_system_instructions()
        return SystemInstructionsResponse(instructions=data.get("instructions", ""))
    except Exception as e:
        logger.error(f"[API] Error fetching system instructions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch system instructions: {str(e)}"
        )


@router.put("/system-instructions", response_model=SystemInstructionsResponse)
async def update_system_instructions(
    request: SystemInstructionsRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Update system instructions.
    Requires admin authentication.
    """
    try:
        updated = system_instructions_service.update_system_instructions(instructions=request.instructions)
        logger.info(f"[API] ✅ System instructions updated (length={len(request.instructions)})")
        return SystemInstructionsResponse(instructions=updated.get("instructions", ""))
    except Exception as e:
        logger.error(f"[API] Error updating system instructions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update system instructions: {str(e)}"
        )


@router.post("/register-candidate", response_model=ScheduleInterviewResponse)
async def register_candidate(
    request: CandidateRegistrationRequest,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Register a single candidate and schedule interview.
    Requires admin authentication.
    """
    try:
        logger.info(f"[API] Registering candidate: {request.email}")

        # Parse datetime
        try:
            if 'Z' in request.datetime or '+' in request.datetime or request.datetime.count('-') > 2:
                scheduled_at = datetime.fromisoformat(request.datetime.replace('Z', '+00:00'))
            else:
                naive_dt = datetime.fromisoformat(request.datetime)
                scheduled_at = naive_dt.replace(tzinfo=IST)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid datetime format. Expected ISO format."
            )

        # Validate scheduled time is at least 5 minutes in the future
        validate_scheduled_time(scheduled_at)

        # Create booking
        token = booking_service.create_booking(
            name=request.name,
            email=request.email,
            scheduled_at=scheduled_at,
            phone=request.phone,
            application_text=None,
            application_url=None,
        )

        # Generate interview URL - use request origin dynamically
        base_url = get_frontend_url(http_request)
        interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"

        # Send email
        email_sent = False
        email_error: Optional[str] = None
        try:
            email_sent, email_error = await email_service.send_interview_email(
                to_email=request.email,
                name=request.name,
                interview_url=interview_url,
                scheduled_at=scheduled_at,
            )
        except Exception as e:
            email_error = str(e)
            logger.warning(f"[API] Email sending failed: {email_error}")

        logger.info(f"[API] ✅ Candidate registered: {interview_url}")

        return ScheduleInterviewResponse(
            ok=True,
            interviewUrl=interview_url,
            emailSent=email_sent,
            emailError=email_error,
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to register candidate: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.post("/bulk-register", response_model=BulkRegistrationResponse)
async def bulk_register_candidates(
    file: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Bulk register candidates from an Excel file.
    Requires admin authentication.
    """
    try:
        if not file.filename.lower().endswith((".xlsx", ".xls")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only Excel files (.xlsx, .xls) are supported"
            )

        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty"
            )

        import pandas as pd
        from io import BytesIO

        df = pd.read_excel(BytesIO(content))
        # Expect columns: name, email, phone, datetime
        required_cols = {"name", "email", "phone", "datetime"}
        if not required_cols.issubset(set(df.columns.str.lower())):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Excel must contain columns: {', '.join(required_cols)}"
            )

        total = len(df)
        successful = 0
        failed = 0
        errors: List[str] = []

        for idx, row in df.iterrows():
            try:
                name = str(row.get("name") or "").strip()
                email = str(row.get("email") or "").strip()
                phone = str(row.get("phone") or "").strip()
                dt_str = str(row.get("datetime") or "").strip()

                if not name or not email or not dt_str:
                    failed += 1
                    errors.append(f"Row {idx + 2}: Missing required fields")
                    continue

                try:
                    scheduled_at = datetime.fromisoformat(dt_str)
                    if scheduled_at.tzinfo is None:
                        scheduled_at = scheduled_at.replace(tzinfo=IST)
                except Exception:
                    failed += 1
                    errors.append(f"Row {idx + 2}: Invalid datetime format")
                    continue

                validate_scheduled_time(scheduled_at)

                token = booking_service.create_booking(
                    name=name,
                    email=email,
                    scheduled_at=scheduled_at,
                    phone=phone,
                    application_text=None,
                    application_url=None,
                )

                base_url = ""  # In bulk mode we don't know the exact origin; frontend can derive link from token
                interview_url = f"/interview/{token}"

                try:
                    await email_service.send_interview_email(
                        to_email=email,
                        name=name,
                        interview_url=interview_url,
                        scheduled_at=scheduled_at,
                    )
                except Exception as e:
                    logger.warning(f"[API] Bulk email send failed for {email}: {e}")

                successful += 1
            except Exception as e:
                failed += 1
                errors.append(f"Row {idx + 2}: {str(e)}")

        return BulkRegistrationResponse(
            success=failed == 0,
            total=total,
            successful=successful,
            failed=failed,
            errors=errors or None,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to bulk register: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/gemini-usage", response_model=List[BookingResponse])
async def get_gemini_usage_report(
    current_admin: dict = Depends(get_current_admin),
):
    """
    Get all interviews with token usage for reporting.
    """
    try:
        # Fetch all bookings from Supabase
        bookings = booking_service.get_all_bookings()

        candidates: List[BookingResponse] = []
        for booking in bookings:
            candidates.append(BookingResponse(
                token=booking.get('token', ''),
                name=booking.get('name', ''),
                email=booking.get('email', ''),
                phone=booking.get('phone', ''),
                scheduled_at=str(booking.get('scheduled_at', '')),
                created_at=str(booking.get('created_at', '')),
                application_text=booking.get('application_text'),
                application_url=booking.get('application_url'),
                token_usage=booking.get('token_usage'),
                slot_id=booking.get('slot_id'),
                application_form_submitted=booking.get('application_form_submitted')
            ))

        return candidates
    except Exception as e:
        logger.error(f"[API] Error fetching usage report: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/candidates", response_model=PaginatedCandidatesResponse)
async def get_all_candidates(
    current_admin: dict = Depends(get_current_admin),
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """
    Get paginated list of registered candidates.
    Requires admin authentication.

    Args:
        page: Page number (1-indexed, default 1)
        page_size: Items per page (default 20, max 100)
        search: Search by name or email (optional)
        status_filter: Filter by status (optional)
        sort_by: Sort field (created_at, scheduled_at, name, email)
        sort_order: Sort order (asc or desc)
    """
    try:
        # Validate pagination params
        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        # Build query params for service
        offset = (page - 1) * page_size

        # Use Supabase directly for now for flexibility
        client = get_supabase()
        query = client.table("interview_bookings").select("*", count="exact")

        if search:
            search = search.strip()
            query = query.or_(
                f"name.ilike.%{search}%,email.ilike.%{search}%"
            )

        if status_filter:
            query = query.eq("status", status_filter)

        # Sorting
        sort_field = sort_by if sort_by in ["created_at", "scheduled_at", "name", "email"] else "created_at"
        is_asc = sort_order == "asc"
        query = query.order(sort_field, desc=not is_asc)

        # Pagination range (Supabase uses 0-based index)
        query = query.range(offset, offset + page_size - 1)

        response = query.execute()
        rows = response.data or []
        total = response.count or 0

        items: List[BookingResponse] = []
        for row in rows:
            items.append(BookingResponse(
                token=row.get("token", ""),
                name=row.get("name", ""),
                email=row.get("email", ""),
                phone=row.get("phone"),
                scheduled_at=str(row.get("scheduled_at", "")),
                created_at=str(row.get("created_at", "")),
                application_text=row.get("application_text"),
                application_url=row.get("application_url"),
                application_form_submitted=row.get("application_form_submitted"),
                slot_id=row.get("slot_id"),
                slot=row.get("slot"),
                token_usage=row.get("token_usage"),
            ))

        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1

        return PaginatedCandidatesResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )
    except Exception as e:
        logger.error(f"[API] Error fetching candidates: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch candidates: {str(e)}"
        )


@router.post("/schedule-interview", response_model=ScheduleInterviewResponse)
async def schedule_interview_for_user(
    request: ScheduleInterviewForUserRequest,
    http_request: Request,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Schedule an interview for an enrolled user using a predefined slot.
    Returns interview link immediately and processes email in background.
    """
    try:
        logger.info(f"[API] Scheduling interview for user_id: {request.user_id} with slot_id: {request.slot_id}")
        
        # Get the enrolled user
        user = user_service.get_user(request.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get the slot and validate it exists
        slot = slot_service.get_slot(request.slot_id)
        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview slot not found"
            )
        
        # Check if slot is active and has available capacity
        if slot['status'] != 'active':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slot is not available. Status: {slot['status']}"
            )
        
        if slot['current_bookings'] >= slot['max_capacity']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slot is full. Capacity: {slot['current_bookings']}/{slot['max_capacity']}"
            )
        
        # Parse slot datetime - handle UTC or IST format properly
        try:
            slot_datetime_str = slot.get('slot_datetime') or slot.get('start_time')
            if not slot_datetime_str:
                raise ValueError("No start time found for slot")
            
            # Use parse_datetime_safe to handle both UTC and IST formats
            scheduled_at = parse_datetime_safe(slot_datetime_str)
            logger.info(f"[API] Parsed slot datetime: {slot_datetime_str} -> {scheduled_at.isoformat()} (IST)")
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid slot datetime format: {str(e)}"
            )
        
        # Create booking with slot_id reference
        try:
            # Resolve actual user_id from users table (if registered) to avoid FK violation
            # interview_bookings.user_id references users.id, but request.user_id is from enrolled_users
            auth_user = auth_service.get_user_by_email(user['email'])
            booking_user_id = auth_user['id'] if auth_user else None
            
            token = booking_service.create_booking(
                name=user['name'],
                email=user['email'],
                scheduled_at=scheduled_at,
                phone=user.get('phone', ''),
                application_text=None,
                application_url=None,
                slot_id=request.slot_id,
                user_id=booking_user_id,
                prompt=request.prompt,
            )
            logger.info(f"[API] ✅ Booking created successfully: token={token}, user_id={request.user_id}")
        except Exception as e:
            logger.error(f"[API] Failed to create booking: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create booking: {str(e)}"
            )
        
        # Increment slot booking count
        try:
            success = slot_service.increment_booking_count(request.slot_id)
            if success:
                logger.info(f"[API] ✅ Incremented booking count for slot {request.slot_id}")
            else:
                logger.warning(f"[API] ⚠️ Failed to increment booking count - slot may be full")
                # This shouldn't happen as we checked above, but handle it gracefully
        except Exception as e:
            logger.warning(f"[API] ⚠️ Failed to increment slot booking count: {str(e)}")
            # Don't fail the request if slot update fails, but log it
        
        # Update user status to 'interviewed'
        try:
            user_service.update_user(request.user_id, status='interviewed')
        except Exception as e:
            logger.warning(f"[API] Failed to update user status: {str(e)}")
        
        # Generate interview URL - use request origin dynamically
        base_url = get_frontend_url(http_request)
        interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"
        
        # Send email and update status in background (non-blocking)
        async def send_email_and_update_bg():
            try:
                # Send email with timeout
                email_sent, email_error = await asyncio.wait_for(
                    email_service.send_interview_email(
                        to_email=user['email'],
                        name=user['name'],
                        interview_url=interview_url,
                        scheduled_at=scheduled_at,
                    ),
                    timeout=10.0
                )
                if email_sent:
                    logger.info(f"[API] ✅ Interview email sent to {user['email']}")
                else:
                    logger.warning(f"[API] ⚠️ Interview email failed for {user['email']}: {email_error}")
            except asyncio.TimeoutError:
                logger.warning(f"[API] ⚠️ Interview email timed out for {user['email']}")
            except Exception as e:
                logger.error(f"[API] ❌ Exception sending interview email: {str(e)}", exc_info=True)
        
        # Schedule background task
        asyncio.create_task(send_email_and_update_bg())
        await asyncio.sleep(0.1)  # Small delay to ensure task is scheduled
        
        logger.info(f"[API] ✅ Interview scheduled: {interview_url}")
        
        # Return immediately with interview URL
        return ScheduleInterviewResponse(
            ok=True,
            interviewUrl=interview_url,
            emailSent=False,  # Email is sent in background
            emailError=None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to schedule interview: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.post("/schedule-interview/bulk", response_model=BulkScheduleInterviewResponse)
async def bulk_schedule_interviews(
    http_request: Request,
    file: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Bulk schedule interviews from Excel file.
    Expected format: email, datetime columns.
    Optional prompt applies to all scheduled interviews.
    """
    try:
        logger.info(f"[API] Bulk scheduling from file: {file.filename}")
        
        # Read Excel file
        try:
            contents = await file.read()
            # Simple check for csv based on extension, though usually Excel is used here
            filename = file.filename.lower()
            if filename.endswith('.csv'):
                df = pd.read_csv(BytesIO(contents))
            else:
                df = pd.read_excel(BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read file: {str(e)}"
            )
        
        # Validate columns
        required_columns = ['email', 'datetime']
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing columns: {', '.join(missing)}"
            )
            
        # Convert DF to list of dicts for common processing
        candidates = []
        for _, row in df.iterrows():
            candidates.append({
                "email": str(row['email']).lower().strip(),
                "datetime": str(row['datetime']).strip()
            })
            
        return await _process_bulk_schedule_data(http_request, candidates, prompt)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Bulk file error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule-interview/bulk-json", response_model=BulkScheduleInterviewResponse)
async def bulk_schedule_interviews_json(
    request: BulkScheduleRequest,
    http_request: Request, # Added http_request to pass to _process_bulk_schedule_data
    current_admin: dict = Depends(get_current_admin)
):
    """
    Bulk schedule interviews from JSON body.
    """
    try:
        logger.info(f"[API] Bulk scheduling from JSON: {len(request.candidates)} candidates")
        
        candidates = []
        for c in request.candidates:
            candidates.append({
                "email": c.email.lower().strip(),
                "datetime": c.datetime.strip()
            })
            
        return await _process_bulk_schedule_data(http_request, candidates, request.prompt)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Bulk JSON error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _process_bulk_schedule_data(http_request: Request, candidates: List[dict], prompt: Optional[str]) -> BulkScheduleInterviewResponse:
    """
    Common logic to process a list of candidate dicts: {'email': ..., 'datetime': ...}
    """
    total = len(candidates)
    successful = 0
    failed = 0
    errors = []
    
    # Give background tasks a moment to start
    await asyncio.sleep(0.1)
    
    for idx, item in enumerate(candidates):
        row_num = idx + 1
        try:
            email = item['email']
            datetime_str = item['datetime']
            
            if not email or not datetime_str:
                raise ValueError("email and datetime are required")
            
            # Get user
            user = user_service.get_user_by_email(email)
            if not user:
                raise ValueError(f"User with email {email} not found")
            
            # Parse datetime
            try:
                # Handle pandas datetime objects if they somehow made it here
                if isinstance(item['datetime'], pd.Timestamp):
                    scheduled_at = item['datetime'].to_pydatetime()
                    scheduled_at = to_ist(scheduled_at)
                else:
                    # Attempt flexible parsing for string
                    if 'T' in datetime_str:
                        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                    else:
                        dt = parse_datetime_safe(datetime_str)
                    scheduled_at = to_ist(dt)
            except Exception as e:
                raise ValueError(f"Invalid datetime format: {datetime_str}")
                
            # Validate scheduled time
            now = get_now_ist()
            if scheduled_at <= now:
                raise ValueError(f"Scheduled time must be in the future (Time in IST: {scheduled_at.strftime('%Y-%m-%d %H:%M:%S')})")
            
            # Create booking
            auth_user = auth_service.get_user_by_email(user['email'])
            booking_user_id = auth_user['id'] if auth_user else None
            
            token = booking_service.create_booking(
                name=user.get('name', 'Student'),
                email=email,
                scheduled_at=scheduled_at,
                phone=user.get('phone', ''),
                user_id=booking_user_id,
                prompt=prompt
            )
            
            # Generate interview URL
            base_url = get_frontend_url(http_request)
            interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"
            
            # Helper for background email
            async def send_email_wrapper(t_email, t_name, t_url, t_time):
                try:
                    await email_service.send_interview_email(
                        to_email=t_email,
                        name=t_name,
                        interview_url=t_url,
                        scheduled_at=t_time
                    )
                except Exception as e:
                    logger.warning(f"[API] ⚠️ Bulk interview email failed for {t_email}: {e}")
            
            # Schedule email
            asyncio.create_task(send_email_wrapper(email, user.get('name', 'Student'), interview_url, scheduled_at))
            
            successful += 1
            logger.info(f"[API] ✅ Scheduled interview {idx + 1}/{total}: {email}")

        except Exception as e:
            failed += 1
            errors.append(f"Row {row_num} ({item.get('email', '?')}): {str(e)}")
            
    return BulkScheduleInterviewResponse(
        success=True,
        total=total,
        successful=successful,
        failed=failed,
        errors=errors
    )