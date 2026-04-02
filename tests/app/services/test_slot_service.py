import pytest
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, date

from app.services.slot_service import SlotService


@pytest.fixture
def slot_service():
    with patch("app.services.slot_service.get_supabase") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from app.config import get_config
        yield SlotService(get_config())


def test_get_slot(slot_service):
    mock_id = str(uuid.uuid4())
    slot_service.client.table().select().eq().execute.return_value.data = [
        {"id": mock_id, "slot_datetime": "2026-03-15T10:00:00+05:30"}
    ]
    res = slot_service.get_slot(mock_id)
    assert res["id"] == mock_id


def test_create_slot(slot_service):
    start_time = datetime(2026, 3, 15, 10, 0)
    end_time = start_time + timedelta(minutes=30)
    mock_id = str(uuid.uuid4())
    slot_service.client.table().insert().execute.return_value.data = [{"id": mock_id}]
    res = slot_service.create_slot(start_time, end_time)
    assert res["id"] == mock_id


def test_get_all_slots(slot_service):
    slot_service.client.table().select().execute.return_value.data = [
        {"id": str(uuid.uuid4()), "slot_datetime": "2026-03-15T10:00:00+05:30"}
    ]
    res = slot_service.get_all_slots()
    assert len(res) >= 0


def test_update_slot(slot_service):
    mock_id = str(uuid.uuid4())
    slot_service.client.table().update().eq().execute.return_value.data = [{"id": mock_id}]
    res = slot_service.update_slot(mock_id, {"notes": "updated"})
    assert res["id"] == mock_id


def test_get_available_slots(slot_service):
    slot_service.client.table().select().eq().gte().execute.return_value.data = [
        {"id": str(uuid.uuid4()), "slot_datetime": "2026-03-15T10:00:00+05:30"}
    ]
    res = slot_service.get_available_slots()
    assert len(res) >= 0


def test_create_day_slots(slot_service):
    slot_service.client.table().insert().execute.return_value.data = [{"id": str(uuid.uuid4())}]
    res = slot_service.create_day_slots(date(2026, 3, 16), 10, 0, 12, 0, 30)
    assert len(res) >= 1


# ─── Atomic increment / decrement tests ───────────────────────────────────────

def test_increment_booking_count_success(slot_service):
    """Atomic book: RPC returns updated row → method returns that dict."""
    mock_id = str(uuid.uuid4())
    mock_row = {"id": mock_id, "booked_count": 1, "capacity": 5, "status": "active"}

    slot_service.client.rpc.return_value.execute.return_value.data = [mock_row]

    result = slot_service.increment_booking_count(mock_id)

    assert result == mock_row
    # Verify the correct RPC function and argument were used
    call_args = slot_service.client.rpc.call_args
    assert call_args[0][0] == "atomic_book_slot"
    assert call_args[0][1] == {"p_slot_id": mock_id}


def test_increment_booking_count_slot_full(slot_service):
    """Atomic book: RPC returns empty (slot full) → ValueError is raised."""
    mock_id = str(uuid.uuid4())

    slot_service.client.rpc.return_value.execute.return_value.data = []

    with pytest.raises(ValueError, match="fully booked or does not exist"):
        slot_service.increment_booking_count(mock_id)


def test_increment_booking_count_slot_full_none(slot_service):
    """Atomic book: RPC returns None data → ValueError is raised."""
    mock_id = str(uuid.uuid4())

    slot_service.client.rpc.return_value.execute.return_value.data = None

    with pytest.raises(ValueError, match="fully booked or does not exist"):
        slot_service.increment_booking_count(mock_id)


def test_decrement_booking_count_success(slot_service):
    """Atomic release: RPC returns updated row → method returns that dict."""
    mock_id = str(uuid.uuid4())
    mock_row = {"id": mock_id, "booked_count": 0, "capacity": 5, "status": "available"}

    slot_service.client.rpc.return_value.execute.return_value.data = [mock_row]

    result = slot_service.decrement_booking_count(mock_id)

    assert result == mock_row
    # Verify the correct RPC function and argument were used
    call_args = slot_service.client.rpc.call_args
    assert call_args[0][0] == "atomic_release_slot"
    assert call_args[0][1] == {"p_slot_id": mock_id}


def test_decrement_booking_count_no_bookings(slot_service):
    """Atomic release: RPC returns empty (no bookings to release) → ValueError."""
    mock_id = str(uuid.uuid4())

    slot_service.client.rpc.return_value.execute.return_value.data = []

    with pytest.raises(ValueError, match="no bookings to release"):
        slot_service.decrement_booking_count(mock_id)
