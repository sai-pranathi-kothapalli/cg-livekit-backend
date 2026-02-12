"""
Booking and scheduling related Pydantic schemas.
Moved from app.api.main without changes.
"""

from typing import Dict, List, Optional, Any

from pydantic import BaseModel, EmailStr


class ScheduleInterviewRequest(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    datetime: str  # ISO datetime string
    applicationUrl: Optional[str] = None
    applicationText: Optional[str] = None


class ScheduleInterviewResponse(BaseModel):
    ok: bool
    interviewUrl: str
    emailSent: bool = False
    emailError: Optional[str] = None


class BookingResponse(BaseModel):
    token: str
    name: str
    email: str
    phone: Optional[str] = None
    scheduled_at: str
    slot_id: Optional[str] = None
    slot: Optional[dict] = None  # Include slot data if available
    created_at: str
    application_text: Optional[str] = None
    application_url: Optional[str] = None
    application_form_submitted: Optional[bool] = None  # True/False when booking has user_id; must be True to attend
    token_usage: Optional[Dict[str, int]] = None


class PaginatedCandidatesResponse(BaseModel):
    """Paginated response for candidates list"""

    items: List[BookingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


__all__ = [
    "ScheduleInterviewRequest",
    "ScheduleInterviewResponse",
    "BookingResponse",
    "PaginatedCandidatesResponse",
]

