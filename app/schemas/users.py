"""
Enrolled users and related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from typing import List, Optional, Any

from pydantic import BaseModel, EmailStr, Field


class EnrollUserRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Candidate's full name.", example="Jane Doe")
    email: EmailStr = Field(..., example="jane@example.com")
    phone: Optional[str] = Field(None, example="1234567890")
    notes: Optional[str] = Field(None, example="Highly recommended candidate")
    slot_ids: List[str] = Field(default=[], description="List of slot IDs to assign (minimum 10 recommended).", example=["bc7d68f3-982b-4dbe-95bb-8d5621ac88cc"])


class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(None, example="Jane X. Doe")
    email: Optional[EmailStr] = Field(None, example="jane.new@example.com")
    phone: Optional[str] = Field(None, example="0987654321")
    status: Optional[str] = Field(None, example="inactive")
    notes: Optional[str] = Field(None, example="Updated notes")


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

