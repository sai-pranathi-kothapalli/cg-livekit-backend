import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.evaluation_service import EvaluationService

@pytest.fixture
def evaluation_service(mock_container_services):
    from app.config import get_config
    service = EvaluationService(get_config())
    service.client = MagicMock()
    return service

def test_create_evaluation_new(evaluation_service):
    # Mock check exists -> None
    mock_check = MagicMock()
    mock_check.data = []
    
    # Mock insert
    mock_insert = MagicMock()
    mock_insert.data = [{"id": "eval-1"}]
    
    query = evaluation_service.client.table.return_value.select.return_value
    query.eq.return_value = query
    query.execute.return_value = mock_check
    
    evaluation_service.client.table.return_value.insert.return_value.execute.return_value = mock_insert
    
    eval_id = evaluation_service.create_evaluation("tok123", "room1", overall_score=8.5)
    assert eval_id == "eval-1"

@pytest.mark.asyncio
async def test_evaluate_answer_ai(evaluation_service):
    # Mock HTTPX response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": '{"score": 9, "technical_depth": 8, "communication": 9, "feedback": "Great!"}'}]}}]
    }
    
    # Mock store_answer_evaluation
    with patch.object(evaluation_service, "store_answer_evaluation", new_callable=AsyncMock) as mock_store:
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            
            # Ensure API key is "set"
            evaluation_service.config.gemini_llm.api_key = "fake-key"
            
            result = await evaluation_service.evaluate_answer("tok123", "What is Python?", "A language.")
            assert result["score"] == 9
            assert mock_store.called

def test_fix_json_string(evaluation_service):
    bad_json = '{"key": "value with "quotes" inside"}'
    fixed = evaluation_service._fix_json_string(bad_json)
    assert "key" in fixed

def test_extract_scores_from_malformed_json(evaluation_service):
    content = 'Some text... "overall_score": 8.5, "communication_quality": 7.0 ...'
    extracted = evaluation_service._extract_scores_from_malformed_json(content)
    assert extracted["overall_score"] == 8.5
    assert extracted["communication_quality"] == 7.0

@pytest.mark.asyncio
async def test_store_answer_evaluation(evaluation_service):
    mock_select = MagicMock()
    mock_select.data = [{"rounds_data": []}]
    mock_update = MagicMock()
    
    query_select = evaluation_service.client.table.return_value.select.return_value
    query_select.eq.return_value = query_select
    query_select.execute.return_value = mock_select
    
    query_update = evaluation_service.client.table.return_value.update.return_value
    query_update.eq.return_value = query_update
    query_update.execute.return_value = mock_update
    
    await evaluation_service.store_answer_evaluation("tok123", {"score": 10})
    assert evaluation_service.client.table.return_value.update.called
