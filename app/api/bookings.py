from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.schemas.bookings import (
    ScheduleInterviewRequest,
    ScheduleInterviewResponse,
    BookingResponse,
)
from app.services.container import (
    booking_service,
    email_service,
    slot_service,
)
from app.utils.logger import get_logger
from app.config import get_config
from app.utils.auth_dependencies import get_optional_student
from app.utils.datetime_utils import IST, validate_scheduled_time
from app.utils.url_helper import get_frontend_url

logger = get_logger(__name__)
config = get_config()

# Public interview booking endpoints
router = APIRouter(tags=["Bookings"])


@router.post("/schedule-interview", response_model=ScheduleInterviewResponse)
async def schedule_interview(request: ScheduleInterviewRequest, http_request: Request):
    """
    Schedule an interview.

    Creates a booking in the database and sends confirmation email.
    """
    try:
        logger.info(f"[API] Received schedule request: {request.email} at {request.datetime}")

        # Validate required fields
        if not request.name or not request.email or not request.datetime:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: name, email, datetime"
            )

        # Parse datetime
        try:
            # Try parsing with timezone info first
            if 'Z' in request.datetime or '+' in request.datetime or request.datetime.count('-') > 2:
                # Has timezone info
                scheduled_at = datetime.fromisoformat(request.datetime.replace('Z', '+00:00'))
            else:
                # No timezone info - treat as local time in IST
                naive_dt = datetime.fromisoformat(request.datetime)
                # Assume it's in IST (UTC+5:30)
                scheduled_at = naive_dt.replace(tzinfo=IST)
        except ValueError:
            try:
                # Fallback: try parsing as-is
                scheduled_at = datetime.fromisoformat(request.datetime)
                # If still naive, assume IST and convert to UTC
                if scheduled_at.tzinfo is None:
                    scheduled_at = scheduled_at.replace(tzinfo=IST)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid datetime format. Expected ISO format."
                )

        # Validate scheduled time is at least 5 minutes in the future
        validate_scheduled_time(scheduled_at)

        # Create booking
        try:
            token = booking_service.create_booking(
                name=request.name,
                email=request.email,
                scheduled_at=scheduled_at,
                phone=request.phone or '',
                application_text=request.applicationText,
                application_url=request.applicationUrl,
            )
        except Exception as e:
            logger.error(f"[API] Failed to create booking: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create booking: {str(e)}"
            )

        # Generate interview URL - use request origin dynamically
        base_url = get_frontend_url(http_request)
        interview_url = f"{base_url}/interview/{token}" if base_url else f"/interview/{token}"

        # Send email (non-blocking)
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

        logger.info(f"[API] ✅ Interview scheduled: {interview_url}")

        return ScheduleInterviewResponse(
            ok=True,
            interviewUrl=interview_url,
            emailSent=email_sent,
            emailError=email_error,
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


@router.get("/booking/{token}", response_model=BookingResponse)
async def get_booking(
    token: str,
    current_student: Optional[dict] = Depends(get_optional_student)
):
    """
    Get booking details by token.

    When REQUIRE_LOGIN_FOR_INTERVIEW=true: requires student authentication and verifies ownership.
    When REQUIRE_LOGIN_FOR_INTERVIEW=false: anyone with the token can get booking details.
    """
    try:
        # Optional: Require student authentication (configurable)
        if config.REQUIRE_LOGIN_FOR_INTERVIEW:
            if not current_student:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to access interview. Please log in as a student."
                )

        booking = booking_service.get_booking(token)

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )

        # Optional: Verify that the booking belongs to the logged-in student (only when login required)
        if config.REQUIRE_LOGIN_FOR_INTERVIEW and current_student:
            booking_user_id = booking.get('user_id')
            if booking_user_id:
                # Verify that the booking belongs to the logged-in student
                auth_user_id = current_student.get('id')
                if booking_user_id != auth_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have permission to access this interview"
                    )
            else:
                # If booking has no user_id, allow access (for backward compatibility)
                logger.warning(f"[API] ⚠️  Booking {token} has no user_id - allowing access for backward compatibility")

        # Include slot data if booking has slot_id
        booking_dict = dict(booking)
        # Application form feature has been removed; keep field for compatibility but always None
        booking_dict['application_form_submitted'] = None
        slot_id = booking_dict.get('slot_id')
        if slot_id:
            try:
                slot = slot_service.get_slot(slot_id)
                if slot:
                    booking_dict['slot'] = slot
            except Exception as e:
                logger.warning(f"[API] Failed to fetch slot {slot_id}: {e}")

        return BookingResponse(**booking_dict)

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to fetch booking: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


