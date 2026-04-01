import pytest
from pydantic import ValidationError
from app.schemas.student_status import (
    AssignmentResponse,
    SelectSlotRequest,
    MyInterviewResponse
)

def test_assignment_response():
    slot = {
        "id": "slot-1",
        "slot_datetime": "2026-02-15T10:00:00+05:30",
        "max_capacity": 10,
        "current_bookings": 0,
        "status": "active",
        "created_at": "2026-02-14T10:00:00Z"
    }
    valid_data = {
        "id": "asgn-1",
        "user_id": "user-1",
        "slot_id": "slot-1",
        "status": "pending",
        "assigned_at": "2026-02-14T11:00:00Z",
        "slot": slot
    }
    model = AssignmentResponse(**valid_data)
    assert model.id == "asgn-1"
    assert model.slot.id == "slot-1"
    
    with pytest.raises(ValidationError):
        AssignmentResponse(id="asgn-1")

def test_select_slot_request():
    valid_data = {"slot_id": "slot-1", "prompt": "Focus on React"}
    model = SelectSlotRequest(**valid_data)
    assert model.slot_id == "slot-1"
    
    minimal_data = {"slot_id": "slot-2"}
    model2 = SelectSlotRequest(**minimal_data)
    assert model2.prompt is None

def test_my_interview_response():
    valid_data = {
        "upcoming": [{"id": "int-1"}],
        "missed": [],
        "completed": [{"id": "int-2"}]
    }
    model = MyInterviewResponse(**valid_data)
    assert len(model.upcoming) == 1
    assert len(model.completed) == 1
    
    empty_model = MyInterviewResponse()
    assert empty_model.upcoming == []
