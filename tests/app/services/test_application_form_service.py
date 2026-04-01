import pytest
from unittest.mock import MagicMock
from app.services.application_form_service import ApplicationFormService

@pytest.fixture
def form_service(mock_container_services):
    from app.config import get_config
    service = ApplicationFormService(get_config())
    service.client = MagicMock()
    return service

def test_submit_form(form_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "f1", "user_id": "u1", "form_data": {"name": "Test"}}]
    form_service.client.table.return_value.insert.return_value.execute.return_value = mock_response
    
    result = form_service.submit_form("u1", {"name": "Test"})
    assert result["id"] == "f1"
    assert result["name"] == "Test" # Check mapping

def test_get_form_by_user_id(form_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "f1", "user_id": "u1", "form_data": {"phone": "123"}}]
    query = form_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = form_service.get_form_by_user_id("u1")
    assert result["phone"] == "123"

def test_create_or_update_form_update(form_service):
    # Mock existing
    mock_get = MagicMock()
    mock_get.data = [{"id": "f1", "user_id": "u1", "form_data": {}}]
    query_get = form_service.client.table.return_value.select.return_value
    query_get.eq.return_value = query_get
    query_get.execute.return_value = mock_get
    
    # Mock update
    mock_update = MagicMock()
    mock_update.data = [{"id": "f1", "user_id": "u1", "form_data": {"city": "New York"}}]
    query_update = form_service.client.table.return_value.update.return_value
    query_update.eq.return_value = query_update
    query_update.execute.return_value = mock_update
    
    result = form_service.create_or_update_form("u1", {"city": "New York"})
    assert result["city"] == "New York"
