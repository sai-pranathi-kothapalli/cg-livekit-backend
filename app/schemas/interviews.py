"""
Interview and evaluation related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, field_validator
from app.utils.sanitize import sanitize_string, sanitize_code

from app.schemas.bookings import BookingResponse


class RoundEvaluationResponse(BaseModel):
    round_number: int
    round_name: str
    questions_asked: int
    average_rating: Optional[float] = None
    time_spent_minutes: Optional[float] = None
    time_target_minutes: Optional[int] = None
    topics_covered: List[str] = []
    performance_summary: Optional[str] = None
    response_ratings: List[float] = []


class EvaluationResponse(BaseModel):
    booking: BookingResponse
    candidate: Dict[str, Any]
    interview_metrics: Optional[Dict[str, Any]] = None
    rounds: List[RoundEvaluationResponse] = []
    overall_score: Optional[float] = None
    strengths: List[str] = []
    areas_for_improvement: List[str] = []
    transcript: List[Dict[str, Any]] = []
    communication_quality: Optional[float] = None
    technical_knowledge: Optional[float] = None
    problem_solving: Optional[float] = None
    coding_score: Optional[float] = None
    confidence_level: Optional[float] = None
    overall_feedback: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None


class ConnectionDetailsRequest(BaseModel):
    room_config: Optional[dict] = Field(None, example={"audio": True, "video": False})
    token: Optional[str] = Field(None, example="XyeNodpGCy0H3HFEneHUTrw4kL35q39Z")


class ConnectionDetailsResponse(BaseModel):
    serverUrl: str
    roomName: str
    participantName: str
    participantToken: str


class CodeAnalysisRequest(BaseModel):
    question: str
    code: str
    language: str

    @field_validator('question')
    @classmethod
    def clean_question(cls, v):
        return sanitize_string(v, max_length=2000)

    @field_validator('code')
    @classmethod
    def clean_code(cls, v):
        return sanitize_code(v)

    @field_validator('language')
    @classmethod
    def clean_language(cls, v):
        return sanitize_string(v, max_length=50)


class CodeAnalysisResponse(BaseModel):
    feedback: str


class SessionStateResponse(BaseModel):
    transcript: List[Dict[str, Any]]
    interview_state: Optional[Dict[str, Any]] = None
    remaining_minutes: Optional[int] = None
    scheduled_at: Optional[str] = None


__all__ = [
    "RoundEvaluationResponse",
    "EvaluationResponse",
    "ConnectionDetailsRequest",
    "ConnectionDetailsResponse",
    "CodeAnalysisRequest",
    "CodeAnalysisResponse",
    "SessionStateResponse",
]

