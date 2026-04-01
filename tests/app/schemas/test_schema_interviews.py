import pytest
from pydantic import ValidationError
from app.schemas.interviews import (
    RoundEvaluationResponse,
    EvaluationResponse,
    ConnectionDetailsRequest,
    ConnectionDetailsResponse,
    CodeAnalysisRequest,
    CodeAnalysisResponse
)

def test_round_evaluation_response():
    valid_data = {
        "round_number": 1,
        "round_name": "Technical",
        "questions_asked": 3,
        "average_rating": 8.5,
        "topics_covered": ["Python", "FastAPI"]
    }
    model = RoundEvaluationResponse(**valid_data)
    assert model.round_name == "Technical"
    assert model.average_rating == 8.5
    
    with pytest.raises(ValidationError):
        RoundEvaluationResponse(round_number=1)

def test_evaluation_response():
    booking = {
        "token": "tok-1",
        "name": "Alice",
        "email": "alice@example.com",
        "scheduled_at": "2026-02-14T17:00:00+05:30",
        "created_at": "2026-02-13T10:00:00Z"
    }
    valid_data = {
        "booking": booking,
        "candidate": {"name": "Alice"},
        "rounds": [],
        "overall_score": 9.0,
        "strengths": ["Communication"],
        "areas_for_improvement": ["None"]
    }
    model = EvaluationResponse(**valid_data)
    assert model.booking.token == "tok-1"
    assert model.overall_score == 9.0

def test_connection_details_request():
    valid_data = {"token": "test-token"}
    model = ConnectionDetailsRequest(**valid_data)
    assert model.token == "test-token"
    
    empty_data = {}
    model2 = ConnectionDetailsRequest(**empty_data)
    assert model2.token is None

def test_code_analysis_request():
    valid_data = {
        "question": "Reverse a string",
        "code": "s[::-1]",
        "language": "python"
    }
    model = CodeAnalysisRequest(**valid_data)
    assert model.language == "python"
