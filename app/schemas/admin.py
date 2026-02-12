"""
Admin-related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from typing import List, Optional

from pydantic import BaseModel, EmailStr

from app.schemas.bookings import BookingResponse


class JobDescriptionRequest(BaseModel):
    context: str  # Full interview/agent context (admin-editable in Job Description section)


class JobDescriptionResponse(BaseModel):
    context: str


class CandidateRegistrationRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str
    datetime: str


class BulkRegistrationResponse(BaseModel):
    success: bool
    total: int
    successful: int
    failed: int
    errors: Optional[List[str]] = None


class ManagerRegistrationRequest(BaseModel):
    name: str
    email: EmailStr


class ManagerResponse(BaseModel):
    id: str
    username: Optional[str] = None
    email: str
    name: Optional[str] = None
    role: str = "manager"
    created_at: Optional[str] = None
    temp_password: Optional[str] = None


class SystemInstructionsRequest(BaseModel):
    instructions: str


class SystemInstructionsResponse(BaseModel):
    instructions: str


__all__ = [
    "JobDescriptionRequest",
    "JobDescriptionResponse",
    "CandidateRegistrationRequest",
    "BulkRegistrationResponse",
    "ManagerRegistrationRequest",
    "ManagerResponse",
    "SystemInstructionsRequest",
    "SystemInstructionsResponse",
]

