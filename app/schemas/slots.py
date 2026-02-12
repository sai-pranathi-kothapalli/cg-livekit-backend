"""
Interview slots management related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class CreateSlotRequest(BaseModel):
    slot_datetime: str  # ISO format datetime string
    max_capacity: int = 30  # Default 30, but admin can change
    duration_minutes: int = 45  # Interview duration in minutes (default 45)
    notes: Optional[str] = None


class UpdateSlotRequest(BaseModel):
    slot_datetime: Optional[str] = None
    max_capacity: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class SlotResponse(BaseModel):
    id: str
    slot_datetime: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None  # Interview duration in minutes
    max_capacity: int
    current_bookings: int
    status: str
    notes: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None  # Optional for MongoDB docs that may not have it
    created_by: Optional[str] = None


class CreateDaySlotsRequest(BaseModel):
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM (24-hour)
    end_time: str  # HH:MM (24-hour)
    duration_minutes: int = 45
    max_capacity: int = 30
    notes: Optional[str] = None


class CreateDaySlotsResponse(BaseModel):
    slots: List[SlotResponse]


__all__ = [
    "CreateSlotRequest",
    "UpdateSlotRequest",
    "SlotResponse",
    "CreateDaySlotsRequest",
    "CreateDaySlotsResponse",
]

