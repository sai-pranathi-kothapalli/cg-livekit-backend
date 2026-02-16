"""
Interview slots management related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CreateSlotRequest(BaseModel):
    slot_datetime: str = Field(..., example="2026-02-15T10:00:00+05:30")  # ISO format datetime string
    max_capacity: int = Field(default=30, example=10)  # Default 30, but admin can change
    duration_minutes: int = Field(default=45, example=60)  # Interview duration in minutes (default 45)
    notes: Optional[str] = Field(None, example="Morning interview slot")


class UpdateSlotRequest(BaseModel):
    slot_datetime: Optional[str] = Field(None, example="2026-02-15T11:00:00+05:30")
    max_capacity: Optional[int] = Field(None, example=20)
    status: Optional[str] = Field(None, example="cancelled")
    notes: Optional[str] = Field(None, example="Rescheduled due to availability")


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
    date: str = Field(..., example="2026-02-16")  # YYYY-MM-DD
    start_time: str = Field(..., example="09:00")  # HH:MM (24-hour)
    end_time: str = Field(..., example="17:00")  # HH:MM (24-hour)
    interval_minutes: int = Field(default=45, example=60)
    duration_minutes: int = Field(default=45, example=45)
    max_capacity: int = Field(default=30, example=5)
    notes: Optional[str] = Field(None, example="Back-to-back testing slots")


class CreateDaySlotsResponse(BaseModel):
    slots: List[SlotResponse]


__all__ = [
    "CreateSlotRequest",
    "UpdateSlotRequest",
    "SlotResponse",
    "CreateDaySlotsRequest",
    "CreateDaySlotsResponse",
]

