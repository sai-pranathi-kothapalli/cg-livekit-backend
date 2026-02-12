from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status

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
    BulkRegistrationResponse,
)
from app.api.main import (  # type: ignore
    booking_service,
    email_service,
    system_instructions_service,
    logger,
    get_current_admin,
    get_supabase,
    validate_scheduled_time,
    get_frontend_url,
    IST,
)

router = APIRouter()


@router.get("/api/admin/job-description", response_model=JobDescriptionResponse)
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


@router.put("/api/admin/job-description", response_model=JobDescriptionResponse)
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


@router.post("/api/admin/managers", response_model=ManagerResponse)
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


@router.get("/api/admin/managers", response_model=List[ManagerResponse])
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


@router.delete("/api/admin/managers/{manager_id}")
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


@router.get("/api/admin/system-instructions", response_model=SystemInstructionsResponse)
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


@router.put("/api/admin/system-instructions", response_model=SystemInstructionsResponse)
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


@router.post("/api/admin/register-candidate", response_model=ScheduleInterviewResponse)
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


@router.post("/api/admin/bulk-register", response_model=BulkRegistrationResponse)
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


@router.get("/api/admin/gemini-usage", response_model=List[BookingResponse])
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


@router.get("/api/admin/candidates", response_model=PaginatedCandidatesResponse)
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
        ascending = sort_order == "asc"
        query = query.order(sort_field, ascending=ascending)

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


