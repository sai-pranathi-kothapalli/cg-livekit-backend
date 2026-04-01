import pytest
from unittest.mock import MagicMock
from app.services.transcript_storage_service import TranscriptStorageService

@pytest.fixture
def storage_service(mock_container_services):
    from app.config import get_config
    service = TranscriptStorageService(get_config())
    service.client = MagicMock()
    return service

def test_save_transcript_message_new(storage_service):
    # Mock check exists -> None
    mock_check = MagicMock()
    mock_check.data = []
    
    query = storage_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_check
    
    mock_insert = MagicMock()
    storage_service.client.table.return_value.insert.return_value.execute.return_value = mock_insert
    
    success = storage_service.save_transcript_message("tok123", "room1", "assistant", "Hello", 0)
    assert success is True
    assert storage_service.client.table.return_value.insert.called

def test_save_transcript_message_existing(storage_service):
    # Mock existing
    mock_check = MagicMock()
    mock_check.data = [{"id": "t1", "transcript": []}]
    
    query_select = storage_service.client.table.return_value.select.return_value
    query_select.eq.return_value = query_select
    query_select.execute.return_value = mock_check
    
    # Mock update
    mock_update = MagicMock()
    query_update = storage_service.client.table.return_value.update.return_value
    query_update.eq.return_value = query_update
    query_update.execute.return_value = mock_update
    
    success = storage_service.save_transcript_message("tok123", "room1", "user", "Hi", 1)
    assert success is True
    assert storage_service.client.table.return_value.update.called

def test_get_transcript(storage_service):
    mock_response = MagicMock()
    mock_response.data = [{"transcript": [{"role": "assistant", "content": "Hello", "message_index": 0}]}]
    query = storage_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_response
    
    result = storage_service.get_transcript("tok123")
    assert len(result) == 1
    assert result[0]["role"] == "assistant"
