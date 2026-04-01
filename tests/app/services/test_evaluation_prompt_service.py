import pytest
from unittest.mock import MagicMock
from app.services.evaluation_prompt_service import EvaluationPromptService

@pytest.fixture
def prompt_service(mock_container_services):
    from app.config import get_config
    service = EvaluationPromptService(get_config())
    service.client = MagicMock()
    return service

def test_get_active_prompt_exists(prompt_service):
    mock_response = MagicMock()
    mock_response.data = [{"prompt_template": "My template"}]
    query = prompt_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = mock_response
    
    result = prompt_service.get_active_prompt()
    assert result == "My template"

def test_get_active_prompt_seed(prompt_service):
    # Mock empty response
    mock_response = MagicMock()
    mock_response.data = []
    query = prompt_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = mock_response
    
    # Mock insert (seed)
    mock_insert = MagicMock()
    prompt_service.client.table.return_value.insert.return_value.execute.return_value = mock_insert
    
    result = prompt_service.get_active_prompt()
    assert "expert technical interview evaluator" in result
    assert prompt_service.client.table.return_value.insert.called

def test_update_prompt(prompt_service):
    # Mock exists
    mock_check = MagicMock()
    mock_check.data = [{"id": "p1"}]
    query_check = prompt_service.client.table.return_value.select.return_value
    query_check.eq.return_value = query_check
    query_check.execute.return_value = mock_check
    
    # Mock update
    mock_update = MagicMock()
    query_update = prompt_service.client.table.return_value.update.return_value
    query_update.eq.return_value = query_update
    query_update.execute.return_value = mock_update
    
    assert prompt_service.update_prompt("New template") is True
    assert prompt_service.client.table.return_value.update.called
