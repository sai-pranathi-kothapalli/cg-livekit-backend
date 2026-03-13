import pytest
from unittest.mock import MagicMock
from datetime import datetime, date
from app.services.slot_service import SlotService

@pytest.fixture
def slot_service(mock_container_services):
    from app.config import get_config
    service = SlotService(get_config())
    service.client = MagicMock()
    return service

def test_create_slot(slot_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "slot-1", "slot_datetime": "2026-02-14T10:00:00+05:30", "capacity": 1}]
    slot_service.client.table.return_value.insert.return_value.execute.return_value = mock_response
    
    dt = datetime(2026, 2, 14, 10, 0)
    result = slot_service.create_slot(start_time=dt, end_time=dt, max_bookings=5)
    
    assert result["id"] == "slot-1"
    assert "max_capacity" in result # Mapped from capacity

def test_get_slot(slot_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "slot-1", "slot_datetime": "2026-02-14T10:00:00+05:30"}]
    query = slot_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = slot_service.get_slot("slot-1")
    assert result["id"] == "slot-1"

def test_get_all_slots(slot_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "s1", "slot_datetime": "2026-02-14T10:00:00+05:30"}]
    query = slot_service.client.table.return_value.select.return_value
    query.gte.return_value = query
    query.order.return_value = query
    query.execute.return_value = mock_response
    
    result = slot_service.get_all_slots(include_past=False)
    assert len(result) == 1

def test_create_day_slots(slot_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "new-slot", "slot_datetime": "..."}]
    slot_service.client.table.return_value.insert.return_value.execute.return_value = mock_response
    
    test_date = date(2026, 2, 15)
    slots, errors = slot_service.create_day_slots(
        date=test_date,
        start_hour=9,
        start_minute=0,
        end_hour=11,
        end_minute=0,
        interval_minutes=30
    )
    
    assert len(slots) == 4 # 9:00, 9:30, 10:00, 10:30
    assert len(errors) == 0

def test_increment_booking_count(slot_service):
    # Mock find
    mock_find = MagicMock()
    mock_find.data = [{"id": "slot-1", "booked_count": 0, "capacity": 2}]
    
    # Mock update
    mock_update = MagicMock()
    mock_update.data = [{"id": "slot-1", "booked_count": 1}]
    
    query_find = slot_service.client.table.return_value.select.return_value
    query_find.eq.return_value = query_find
    query_find.execute.return_value = mock_find
    
    query_update = slot_service.client.table.return_value.update.return_value
    query_update.eq.return_value = query_update
    query_update.execute.return_value = mock_update
    
    assert slot_service.increment_booking_count("slot-1") is True
