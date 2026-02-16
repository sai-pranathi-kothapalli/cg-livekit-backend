"""
Admin-related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.bookings import BookingResponse


class JobDescriptionRequest(BaseModel):
    context: str = Field(..., example="We are looking for a Senior Software Engineer with 5+ years of experience in Python and FastAPI...")


class JobDescriptionResponse(BaseModel):
    context: str


class CandidateRegistrationRequest(BaseModel):
    name: str = Field(..., example="Alice Smith")
    email: EmailStr = Field(..., example="alice@example.com")
    phone: str = Field(..., example="9876543210")
    datetime: str = Field(..., example="2026-02-20T10:00:00+05:30")


class BulkRegistrationResponse(BaseModel):
    success: bool
    total: int
    successful: int
    failed: int
    errors: Optional[List[str]] = None


class ManagerRegistrationRequest(BaseModel):
    name: str = Field(..., example="Bob Johnson")
    email: EmailStr = Field(..., example="bob@example.com")


class ManagerResponse(BaseModel):
    id: str
    username: Optional[str] = None
    email: str
    name: Optional[str] = None
    role: str = "manager"
    created_at: Optional[str] = None
    temp_password: Optional[str] = None


class SystemInstructionsRequest(BaseModel):
    instructions: str = Field(..., example="Your task is to conduct a professional technical interview. Start by introducing yourself...")


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

