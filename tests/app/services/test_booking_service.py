import pytest
from unittest.mock import MagicMock
from datetime import datetime
from app.services.booking_service import BookingService

@pytest.fixture
def booking_service(mock_container_services):
    from app.config import get_config
    service = BookingService(get_config())
    service.client = MagicMock()
    return service

def test_create_booking(booking_service):
    mock_response = MagicMock()
    booking_service.client.table.return_value.insert.return_value.execute.return_value = mock_response
    
    token = booking_service.create_booking(
        name="Alice",
        email="alice@example.com",
        scheduled_at=datetime.now(),
        slot_id="slot-1"
    )
    
    assert len(token) == 32
    assert isinstance(token, str)

def test_get_booking(booking_service):
    mock_response = MagicMock()
    mock_booking = {"token": "tok123", "name": "Alice", "scheduled_at": "2026-02-14T10:00:00+05:30"}
    mock_response.data = [mock_booking]
    query = booking_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = booking_service.get_booking("tok123")
    assert result["name"] == "Alice"
    assert result["token"] == "tok123"

def test_update_booking_status(booking_service):
    mock_response = MagicMock()
    mock_response.data = [{"token": "tok123", "status": "completed"}]
    query = booking_service.client.table.return_value.update.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    assert booking_service.update_booking_status("tok123", "completed") is True

def test_delete_bookings_by_user_id(booking_service):
    # Mock find tokens
    mock_find = MagicMock()
    mock_find.data = [{"token": "tok1"}, {"token": "tok2"}]
    
    query_find = booking_service.client.table.return_value.select.return_value
    query_find.eq.return_value = query_find
    query_find.execute.return_value = mock_find
    
    query_delete = booking_service.client.table.return_value.delete.return_value
    query_delete.eq.return_value = query_delete
    query_delete.execute.return_value = MagicMock()
    
    tokens = booking_service.delete_bookings_by_user_id("user-1")
    assert tokens == ["tok1", "tok2"]

def test_upload_application_to_storage(booking_service):
    mock_storage = MagicMock()
    # Correct mocking for storage
    booking_service.client.storage.from_.return_value = mock_storage
    mock_storage.upload.return_value = MagicMock()
    mock_storage.get_public_url.return_value = "http://example.com/file.pdf"
    
    url = booking_service.upload_application_to_storage(b"content", "file.pdf")
    assert url == "http://example.com/file.pdf"
