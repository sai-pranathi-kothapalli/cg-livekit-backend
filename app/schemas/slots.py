"""
Interview slots management related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from app.utils.sanitize import sanitize_string


class CreateSlotRequest(BaseModel):
    slot_datetime: str = Field(..., example="2026-02-15T10:00:00+05:30")  # ISO format datetime string
    max_capacity: int = Field(default=30, example=10)  # Default 30, but admin can change
    duration_minutes: int = Field(default=30, example=60)  # Interview duration in minutes (default 30)
    batch: Optional[str] = Field(None, example="PFS-106")
    location: Optional[str] = Field(None, example="vijayawada")
    notes: Optional[str] = Field(None, example="Morning interview slot")

    @field_validator('notes')
    @classmethod
    def clean_notes(cls, v):
        if v:
            return sanitize_string(v, max_length=2000)
        return v


class UpdateSlotRequest(BaseModel):
    slot_datetime: Optional[str] = Field(None, example="2026-02-15T11:00:00+05:30")
    max_capacity: Optional[int] = Field(None, example=20)
    status: Optional[str] = Field(None, example="cancelled")
    batch: Optional[str] = Field(None, example="PFS-107")
    location: Optional[str] = Field(None, example="nellore")
    notes: Optional[str] = Field(None, example="Rescheduled due to availability")

    @field_validator('notes')
    @classmethod
    def clean_notes(cls, v):
        if v:
            return sanitize_string(v, max_length=2000)
        return v


class SlotResponse(BaseModel):
    id: str
    slot_datetime: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None  # Interview duration in minutes
    max_capacity: int
    current_bookings: int
    status: str
    batch: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None  # Optional for MongoDB docs that may not have it
    created_by: Optional[str] = None


class CreateDaySlotsRequest(BaseModel):
    date: str = Field(..., example="2026-02-16")  # YYYY-MM-DD
    start_time: str = Field(..., example="09:00")  # HH:MM (24-hour)
    end_time: str = Field(..., example="17:00")  # HH:MM (24-hour)
    interval_minutes: int = Field(default=30, example=60)
    duration_minutes: int = Field(default=30, example=45)
    max_capacity: int = Field(default=30, example=5)
    batch: Optional[str] = Field(None, example="PFS-106")
    location: Optional[str] = Field(None, example="vijayawada")
    notes: Optional[str] = Field(None, example="Back-to-back testing slots")


class CreateDaySlotsResponse(BaseModel):
    success: bool
    created_count: int
    slots: List[SlotResponse]
    errors: Optional[List[str]] = None


__all__ = [
    "CreateSlotRequest",
    "UpdateSlotRequest",
    "SlotResponse",
    "CreateDaySlotsRequest",
    "CreateDaySlotsResponse",
]

