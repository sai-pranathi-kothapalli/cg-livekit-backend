from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.slots import (
    CreateSlotRequest,
    UpdateSlotRequest,
    SlotResponse,
    CreateDaySlotsRequest,
    CreateDaySlotsResponse,
)
from app.services.container import (
    slot_service,
)
from app.utils.logger import get_logger
from app.utils.auth_dependencies import get_current_admin
from app.utils.datetime_utils import to_ist

logger = get_logger(__name__)

# Slot management (admin + public availability)
router = APIRouter(tags=["Slots"])


@router.post("/admin/slots", response_model=SlotResponse)
async def create_slot(
    request: CreateSlotRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Create a new interview slot.
    """
    try:
        # Parse datetime and ensure it's in IST
        try:
            # Parse the datetime string (may come with or without timezone)
            slot_datetime_str = request.slot_datetime.replace('Z', '+00:00')
            slot_datetime = datetime.fromisoformat(slot_datetime_str)

            # Convert to IST timezone (or assume already IST if naive)
            start_time = to_ist(slot_datetime)

            logger.info(f"[API] Slot creation - Input: {request.slot_datetime}, Parsed: {slot_datetime}, IST: {start_time}")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid datetime format. Use ISO format. Error: {str(e)}"
            )

        # Validate capacity
        if request.max_capacity < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max capacity must be at least 1"
            )

        # Validate duration
        if request.duration_minutes < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration must be at least 1 minute"
            )
        if request.duration_minutes > 120:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration cannot exceed 120 minutes (2 hours)"
            )

        # Use provided duration (default 45 minutes if not specified)
        duration_minutes = request.duration_minutes or 45
        end_time = start_time + timedelta(minutes=duration_minutes)

        # Avoid duplicate: a slot already exists at this datetime
        slot_datetime_iso = start_time.isoformat()
        existing = slot_service.get_slot_by_datetime(slot_datetime_iso)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A slot already exists at this date and time. Edit the existing slot or choose a different time."
            )

        logger.info(f"[API] Creating slot with duration: {duration_minutes} minutes (from request: {request.duration_minutes})")

        slot = slot_service.create_slot(
            start_time=start_time,
            end_time=end_time,
            max_bookings=request.max_capacity,
            notes=request.notes,
            duration_minutes=duration_minutes,
        )

        logger.info(f"[API] Slot created: id={slot.get('id')}, duration_minutes={slot.get('duration_minutes')}, stored_duration={slot.get('duration_minutes')}")

        slot_dict = dict(slot)
        slot_dict.setdefault('updated_at', None)
        return SlotResponse(**slot_dict)

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to create slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/admin/slots", response_model=List[SlotResponse])
async def get_all_slots(
    slot_status: Optional[str] = None,
    include_past: bool = False,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Get all interview slots.
    """
    try:
        slots = slot_service.get_all_slots(status=slot_status, include_past=include_past)
        out: List[SlotResponse] = []
        for slot in slots:
            d = dict(slot)
            d.setdefault("updated_at", None)
            # Ensure datetime fields are strings for SlotResponse (Supabase/Mongo may return datetime)
            for key in ("slot_datetime", "start_time", "end_time", "created_at", "updated_at"):
                if key in d and d[key] is not None and hasattr(d[key], "isoformat"):
                    d[key] = d[key].isoformat()
            out.append(SlotResponse(**d))
        return out
    except Exception as e:
        error_msg = f"Failed to fetch slots: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/admin/slots/{slot_id}", response_model=SlotResponse)
async def get_slot(
    slot_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Get an interview slot by ID.
    """
    try:
        slot = slot_service.get_slot(slot_id)
        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slot not found"
            )
        return SlotResponse(**slot)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to fetch slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.put("/admin/slots/{slot_id}", response_model=SlotResponse)
async def update_slot(
    slot_id: str,
    request: UpdateSlotRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Update an interview slot.
    """
    try:
        updates: dict = {}
        if request.slot_datetime is not None:
            try:
                # Parse and convert to IST
                slot_datetime_str = request.slot_datetime.replace('Z', '+00:00')
                slot_datetime = datetime.fromisoformat(slot_datetime_str)
                updates['slot_datetime'] = to_ist(slot_datetime)
                updates['start_time'] = to_ist(slot_datetime)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid datetime format. Use ISO format. Error: {str(e)}"
                )
        if request.max_capacity is not None:
            if request.max_capacity < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Max capacity must be at least 1"
                )
            updates['max_capacity'] = request.max_capacity
        if request.status is not None:
            updates['status'] = request.status
        if request.notes is not None:
            updates['notes'] = request.notes

        slot = slot_service.update_slot(slot_id, updates)
        return SlotResponse(**slot)

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to update slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.delete("/admin/slots/{slot_id}")
async def delete_slot(
    slot_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Delete an interview slot.
    """
    try:
        slot_service.delete_slot(slot_id)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to delete slot: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/available", response_model=List[SlotResponse])
async def get_available_slots():
    """
    Get available slots for students (public endpoint, no auth required).
    """
    try:
        slots = slot_service.get_available_slots()
        return [SlotResponse(**slot) for slot in slots]
    except Exception as e:
        error_msg = f"Failed to fetch available slots: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.post("/admin/slots/create-day", response_model=CreateDaySlotsResponse)
async def create_day_slots(
    request: CreateDaySlotsRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Create multiple slots for a single day based on start time, end time, and interval.
    """
    try:
        # Parse date
        try:
            selected_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Expected YYYY-MM-DD"
            )

        # Parse start/end times
        try:
            start_hour, start_minute = map(int, request.start_time.split(":"))
            end_hour, end_minute = map(int, request.end_time.split(":"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid time format. Expected HH:MM (24-hour)"
            )

        if request.interval_minutes < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Interval must be at least 5 minutes"
            )

        created_slots, errors = slot_service.create_day_slots(
            date=selected_date,
            start_hour=start_hour,
            start_minute=start_minute,
            end_hour=end_hour,
            end_minute=end_minute,
            interval_minutes=request.interval_minutes,
            max_capacity=request.max_capacity,
            notes=request.notes,
        )

        return CreateDaySlotsResponse(
            success=len(errors) == 0,
            created_count=len(created_slots),
            slots=[SlotResponse(**slot) for slot in created_slots],
            errors=errors or None,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to create day slots: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


