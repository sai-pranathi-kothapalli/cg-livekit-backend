import pytest
from pydantic import ValidationError
from app.schemas.slots import (
    CreateSlotRequest,
    UpdateSlotRequest,
    SlotResponse,
    CreateDaySlotsRequest,
    CreateDaySlotsResponse
)

def test_create_slot_request():
    valid_data = {
        "slot_datetime": "2026-02-15T10:00:00+05:30",
        "max_capacity": 10,
        "duration_minutes": 30
    }
    model = CreateSlotRequest(**valid_data)
    assert model.max_capacity == 10
    
    with pytest.raises(ValidationError):
        CreateSlotRequest()

def test_slot_response():
    valid_data = {
        "id": "slot-1",
        "slot_datetime": "2026-02-15T10:00:00+05:30",
        "max_capacity": 10,
        "current_bookings": 0,
        "status": "active",
        "created_at": "2026-02-14T10:00:00Z"
    }
    model = SlotResponse(**valid_data)
    assert model.id == "slot-1"
    assert model.status == "active"

def test_create_day_slots_request():
    valid_data = {
        "date": "2026-02-16",
        "start_time": "09:00",
        "end_time": "17:00",
        "interval_minutes": 30,
        "max_capacity": 5
    }
    model = CreateDaySlotsRequest(**valid_data)
    assert model.date == "2026-02-16"
    assert model.duration_minutes == 30 # Default
