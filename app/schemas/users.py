"""
Enrolled users and related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from typing import List, Optional

from pydantic import BaseModel, EmailStr


class EnrollUserRequest(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    notes: Optional[str] = None
    slot_ids: List[str] = []  # List of slot IDs to assign to the user (min 10 slots in next 2 days)


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


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
    user_id: str
    slot_id: str
    prompt: Optional[str] = None  # Custom prompt for the AI interviewer


class BulkScheduleInterviewResponse(BaseModel):
    success: bool
    total: int
    successful: int
    failed: int
    errors: Optional[List[str]] = None


__all__ = [
    "EnrollUserRequest",
    "UpdateUserRequest",
    "UserResponse",
    "InterviewSummary",
    "UserDetailResponse",
    "BulkEnrollResponse",
    "ScheduleInterviewForUserRequest",
    "BulkScheduleInterviewResponse",
]

