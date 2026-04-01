import pytest
from unittest.mock import MagicMock, patch
from app.services.booking_service import BookingService
from datetime import datetime
import uuid

@pytest.fixture
def booking_service():
    with patch("app.services.booking_service.get_supabase") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from app.config import get_config
        yield BookingService(get_config())

def test_create_booking(booking_service):
    scheduled_at = datetime(2026, 3, 15, 10, 0)
    slot_id = str(uuid.uuid4())
    token = booking_service.create_booking(
        name="Test User",
        email="test@example.com",
        scheduled_at=scheduled_at,
        phone="1234567890",
        slot_id=slot_id
    )
    assert len(token) == 32
    assert booking_service.client.table.called

def test_get_booking(booking_service):
    mock_data = [{"token": "t1", "scheduled_at": "2026-03-15T10:00:00+05:30"}]
    booking_service.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = mock_data
    res = booking_service.get_booking("t1")
    assert res["token"] == "t1"

def test_get_all_bookings(booking_service):
    mock_data = [{"token": "t1", "created_at": "2026-03-15T10:00:00+05:30"}]
    booking_service.client.table.return_value.select.return_value.order.return_value.execute.return_value.data = mock_data
    res = booking_service.get_all_bookings()
    assert len(res) == 1

def test_update_booking_status(booking_service):
    booking_service.client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "b1"}]
    assert booking_service.update_booking_status("t1", "completed") is True

def test_get_bookings_by_email(booking_service):
    mock_data = [{"token": "t1", "email": "test@e.com"}]
    booking_service.client.table.return_value.select.return_value.ilike.return_value.execute.return_value.data = mock_data
    res = booking_service.get_bookings_by_email("test@e.com")
    assert len(res) == 1

def test_delete_bookings_by_user_id(booking_service):
    booking_service.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"token": "t1"}]
    res = booking_service.delete_bookings_by_user_id("u1")
    assert res == ["t1"]
