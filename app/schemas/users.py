"""
Enrolled users and related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from typing import List, Optional, Any

from pydantic import BaseModel, EmailStr, Field, field_validator
from app.utils.sanitize import sanitize_email, sanitize_name, sanitize_phone, sanitize_string


class EnrollUserRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Candidate's full name.", example="Jane Doe")
    email: EmailStr = Field(..., example="jane@example.com")
    phone: Optional[str] = Field(None, example="1234567890")
    notes: Optional[str] = Field(None, example="Highly recommended candidate")
    slot_ids: List[str] = Field(default=[], description="List of slot IDs to assign (minimum 10 recommended).", example=["bc7d68f3-982b-4dbe-95bb-8d5621ac88cc"])

    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        return sanitize_name(v)

    @field_validator('email')
    @classmethod
    def clean_email(cls, v):
        return sanitize_email(v)

    @field_validator('phone')
    @classmethod
    def clean_phone(cls, v):
        return sanitize_phone(v or "")

    @field_validator('notes')
    @classmethod
    def clean_notes(cls, v):
        if v:
            return sanitize_string(v, max_length=2000)
        return v


class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(None, example="Jane X. Doe")
    email: Optional[EmailStr] = Field(None, example="jane.new@example.com")
    phone: Optional[str] = Field(None, example="0987654321")
    status: Optional[str] = Field(None, example="inactive")
    notes: Optional[str] = Field(None, example="Updated notes")

    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        if v:
            return sanitize_name(v)
        return v

    @field_validator('email')
    @classmethod
    def clean_email(cls, v):
        if v:
            return sanitize_email(v)
        return v

    @field_validator('phone')
    @classmethod
    def clean_phone(cls, v):
        if v:
            return sanitize_phone(v)
        return v

    @field_validator('notes')
    @classmethod
    def clean_notes(cls, v):
        if v:
            return sanitize_string(v, max_length=2000)
        return v


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None  # Optional for MongoDB docs that may not have it
    email_sent: Optional[bool] = None  # True if email was sent successfully
    email_error: Optional[str] = None  # Error message if email failed
    temporary_password: Optional[str] = None  # Temporary password (for testing - remove in production)


class InterviewSummary(BaseModel):
    token: str
    scheduled_at: str
    status: str
    overall_score: Optional[float] = None
    overall_feedback: Optional[str] = None
    evaluation_url: Optional[str] = None
    interview_url: Optional[str] = None


class UserDetailResponse(UserResponse):
    interviews: List[InterviewSummary] = []
    # Aggregated progress/feedback summary across interviews (when available)
    overall_analysis: Optional[str] = None


class BulkEnrollResponse(BaseModel):
    success: bool
    total: int
    successful: int
    failed: int
    errors: Optional[List[str]] = None


class ScheduleInterviewForUserRequest(BaseModel):
    user_id: str = Field(..., example="f36caeef-761e-447d-9d59-db94597261a7")
    slot_id: str = Field(..., example="bc7d68f3-982b-4dbe-95bb-8d5621ac88cc")
    prompt: Optional[str] = Field(None, example="Discuss distributed systems architecture.")


class BulkScheduleInterviewResponse(BaseModel):
    success: bool
    total: int
    successful: int
    failed: int
    errors: Optional[List[str]] = None


class BulkScheduleItem(BaseModel):
    email: EmailStr = Field(..., example="candidate1@example.com")
    datetime: str = Field(..., example="2026-02-14T18:00:00+05:30")  # ISO format string


class BulkScheduleRequest(BaseModel):
    prompt: Optional[str] = Field(None, example="Focus on leadership skills and team management.")
    candidates: List[BulkScheduleItem] = Field(..., example=[{"email": "c1@example.com", "datetime": "2026-02-14T10:00:00+05:30"}])

    @field_validator('prompt')
    @classmethod
    def clean_prompt(cls, v):
        if v:
            from app.utils.sanitize import sanitize_for_llm
            return sanitize_for_llm(v, max_length=5000)
        return v


__all__ = [
    "EnrollUserRequest",
    "UpdateUserRequest",
    "UserResponse",
    "InterviewSummary",
    "UserDetailResponse",
    "BulkEnrollResponse",
    "ScheduleInterviewForUserRequest",
    "ScheduleInterviewForUserRequest",
    "BulkScheduleInterviewResponse",
    "BulkScheduleItem",
    "BulkScheduleRequest",
]

