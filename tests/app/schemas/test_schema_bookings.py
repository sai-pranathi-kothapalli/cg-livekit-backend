import pytest
from pydantic import ValidationError
from app.schemas.bookings import (
    ScheduleInterviewRequest,
    ScheduleInterviewResponse,
    BookingResponse,
    PaginatedCandidatesResponse
)

def test_schedule_interview_request():
    valid_data = {
        "name": "Tester",
        "email": "test@example.com",
        "datetime": "2026-02-14T17:00:00+05:30"
    }
    model = ScheduleInterviewRequest(**valid_data)
    assert model.name == "Tester"
    
    with pytest.raises(ValidationError):
        ScheduleInterviewRequest(name="T", email="not-email", datetime="now")

def test_booking_response():
    valid_data = {
        "token": "tok-1",
        "name": "Alice",
        "email": "alice@example.com",
        "scheduled_at": "2026-02-14T17:00:00+05:30",
        "created_at": "2026-02-13T10:00:00Z"
    }
    model = BookingResponse(**valid_data)
    assert model.token == "tok-1"
    assert model.application_form_submitted is None # Optional

def test_paginated_candidates_response():
    booking = {
        "token": "tok-1",
        "name": "Alice",
        "email": "alice@example.com",
        "scheduled_at": "2026-02-14T17:00:00+05:30",
        "created_at": "2026-02-13T10:00:00Z"
    }
    valid_data = {
        "items": [booking],
        "total": 1,
        "page": 1,
        "page_size": 10,
        "total_pages": 1,
        "has_next": False,
        "has_prev": False
    }
    model = PaginatedCandidatesResponse(**valid_data)
    assert len(model.items) == 1
    assert model.total == 1
