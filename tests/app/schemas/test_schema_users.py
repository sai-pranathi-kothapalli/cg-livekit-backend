import pytest
from pydantic import ValidationError
from app.schemas.users import (
    EnrollUserRequest,
    UpdateUserRequest,
    UserResponse,
    InterviewSummary,
    UserDetailResponse,
    BulkEnrollResponse,
    ScheduleInterviewForUserRequest,
    BulkScheduleInterviewResponse,
    BulkScheduleItem,
    BulkScheduleRequest
)

def test_enroll_user_request():
    valid_data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "slot_ids": ["slot-1", "slot-2"]
    }
    model = EnrollUserRequest(**valid_data)
    assert model.name == "Jane Doe"
    
    with pytest.raises(ValidationError):
        EnrollUserRequest(name="J", email="jane@example.com") # min_length 2

def test_user_response():
    valid_data = {
        "id": "u1",
        "name": "Jane",
        "email": "jane@example.com",
        "status": "enrolled",
        "created_at": "2026-02-14T10:00:00Z"
    }
    model = UserResponse(**valid_data)
    assert model.id == "u1"
    assert model.email_sent is None

def test_user_detail_response():
    user = {
        "id": "u1",
        "name": "Jane",
        "email": "jane@example.com",
        "status": "enrolled",
        "created_at": "2026-02-14T10:00:00Z"
    }
    summary = {
        "token": "tok-1",
        "scheduled_at": "2026-02-15T10:00:00Z",
        "status": "completed"
    }
    valid_data = {
        **user,
        "interviews": [summary],
        "overall_analysis": "Good candidate"
    }
    model = UserDetailResponse(**valid_data)
    assert model.name == "Jane"
    assert len(model.interviews) == 1

def test_bulk_schedule_request():
    item = {"email": "c1@example.com", "datetime": "2026-02-14T10:00:00+05:30"}
    valid_data = {
        "prompt": "Test prompt",
        "candidates": [item]
    }
    model = BulkScheduleRequest(**valid_data)
    assert model.prompt == "Test prompt"
    assert len(model.candidates) == 1
