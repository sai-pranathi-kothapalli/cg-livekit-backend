import pytest
from unittest.mock import MagicMock
from app.services.assignment_service import AssignmentService

@pytest.fixture
def assign_service(mock_container_services):
    from app.config import get_config
    service = AssignmentService(get_config())
    service.client = MagicMock()
    return service

def test_assign_slots(assign_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "a1", "slot_id": "s1"}]
    assign_service.client.table.return_value.insert.return_value.execute.return_value = mock_response
    
    result = assign_service.assign_slots_to_user("u1", ["s1", "s2"])
    # It calls insert for each slot
    assert len(result) == 2
    assert result[0]["slot_id"] == "s1"

def test_get_user_assignments(assign_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "a1", "status": "assigned"}]
    query = assign_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = assign_service.get_user_assignments("u1", status="assigned")
    assert len(result) == 1

def test_select_slot_for_user(assign_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "a1", "status": "selected"}]
    query = assign_service.client.table.return_value.update.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    assert assign_service.select_slot_for_user("u1", "a1") is True

def test_cancel_other_assignments(assign_service):
    mock_response = MagicMock()
    query = assign_service.client.table.return_value.update.return_value
    query.eq.return_value = query
    query.neq.return_value = query
    query.execute.return_value = mock_response
    
    assert assign_service.cancel_other_assignments("u1", "a1") is True
