import pytest
from unittest.mock import MagicMock
from app.services.system_instructions_service import SystemInstructionsService

@pytest.fixture
def sys_service(mock_container_services):
    from app.config import get_config
    service = SystemInstructionsService(get_config())
    service.client = MagicMock()
    return service

def test_get_system_instructions(sys_service):
    mock_response = MagicMock()
    mock_response.data = [{"instructions": "You are a bot"}]
    query = sys_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = sys_service.get_system_instructions()
    assert result["instructions"] == "You are a bot"

def test_update_system_instructions(sys_service):
    # Mock no existing
    mock_check = MagicMock()
    mock_check.data = []
    
    query = sys_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_check
    
    # Mock insert
    mock_insert = MagicMock()
    sys_service.client.table.return_value.insert.return_value.execute.return_value = mock_insert
    
    result = sys_service.update_system_instructions("New bot rules")
    assert result["instructions"] == "New bot rules"
    assert sys_service.client.table.return_value.insert.called
