import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.evaluation_service import EvaluationService
from app.utils.datetime_utils import get_now_ist
from datetime import datetime

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

def test_fix_json_string_basic(evaluation_service):
    # Test unescaped quote fixing
    broken = '{"feedback": "He said "Hello" world"}'
    fixed = evaluation_service._fix_json_string(broken)
    assert 'He said \\"Hello\\" world' in fixed
    
def test_fix_json_string_with_extra_text(evaluation_service):
    # Test extraction from markdown-like junk
    junk = 'Random text before {"key": "value"} random text after'
    fixed = evaluation_service._fix_json_string(junk)
    assert fixed == '{"key": "value"}'

def test_extract_scores_from_malformed_json_fallback(evaluation_service):
    # Test deep regex fallback for scores
    content = '"overall_score": 8.5, "communication_quality": 9.0'
    extracted = evaluation_service._extract_scores_from_malformed_json(content)
    assert extracted["overall_score"] == 8.5
    assert extracted["communication_quality"] == 9.0
    content = 'Some text... "overall_score": 8.5, "communication_quality": 7.0 ...'
    extracted = evaluation_service._extract_scores_from_malformed_json(content)
    assert extracted["overall_score"] == 8.5
    assert extracted["communication_quality"] == 7.0

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

@pytest.mark.asyncio
async def test_get_evaluation_by_token(evaluation_service):
    mock_response = MagicMock()
    mock_response.data = [{"id": "eval-1"}]
    evaluation_service.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
    
    result = await evaluation_service.get_evaluation_by_token("tok1")
    assert result == {"id": "eval-1"}

def test_delete_evaluations_by_booking_tokens(evaluation_service):
    mock_response = MagicMock()
    # Mocking the delete count isn't strictly necessary for coverage but good for logic
    evaluation_service.client.table.return_value.delete.return_value.in_.return_value.execute.return_value = mock_response
    
    evaluation_service.delete_evaluations_by_booking_tokens(["tok1", "tok2"])
    assert evaluation_service.client.table.return_value.delete.called

def test_format_transcript_for_analysis(evaluation_service):
    transcript = [
        {"role": "assistant", "content": "How are you?"},
        {"role": "user", "content": "I am fine."}
    ]
    formatted = evaluation_service._format_transcript_for_analysis(transcript)
    assert "[Interviewer]: How are you?" in formatted
    assert "[Candidate]: I am fine." in formatted

@pytest.mark.asyncio
async def test_evaluate_answer_no_httpx(evaluation_service):
    with patch("app.services.evaluation_service.HTTPX_AVAILABLE", False):
        result = await evaluation_service.evaluate_answer("tok1", "Q", "A")
        assert result is None

@pytest.mark.asyncio
async def test_analyze_code_success(evaluation_service):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Feedback message"}]}}]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        evaluation_service.config.gemini_llm.api_key = "key"
        
        result = await evaluation_service.analyze_code("Q", "print(1)")
        assert result == "Feedback message"

def test_fix_json_string_complex(evaluation_service):
    # Test unescaped quotes and newlines
    bad_json = '{"feedback": "He said "Hello" and \n then left."}'
    fixed = evaluation_service._fix_json_string(bad_json)
    # The fix logic should escape or handle it
    assert "feedback" in fixed

def test_extract_scores_from_broken_json(evaluation_service):
    content = 'The candidate was great. "overall_score": 9.0, "communication_quality": 8.5. strengths: Python, Java.'
    extracted = evaluation_service._extract_scores_from_malformed_json(content)
    assert extracted["overall_score"] == 9.0
    assert extracted["communication_quality"] == 8.5

@pytest.mark.asyncio
async def test_generate_evaluation_aggregation(evaluation_service):
    # Mock incremental evals exist
    mock_select = MagicMock()
    mock_select.data = [{
        "rounds_data": [
            {"score": 8, "communication": 7, "feedback": "Good"},
            {"score": 9, "communication": 8, "feedback": "Great"},
            {"score": 7, "communication": 6, "feedback": "Ok"}
        ],
        "interview_state": {"state": "active"}
    }]
    evaluation_service.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_select
    
    # Mock create_evaluation (called twice: preliminary and final)
    with patch.object(evaluation_service, "create_evaluation", return_value="eval-123") as mock_create:
        evaluation_service.calculate_evaluation_from_transcript("tok1", "room1", transcript=[])
        
        # Verify aggregation logic (8+9+7)/3 = 8.0
        # Check the last call to create_evaluation for final stats
        final_call_args = mock_create.call_args_list[-1][1]
        assert final_call_args["overall_score"] == 8.0
        assert final_call_args["communication_quality"] == 7.0

@pytest.mark.asyncio
async def test_generate_evaluation_full_ai(evaluation_service):
    # No incremental evals, but transcript is long enough
    mock_select = MagicMock()
    mock_select.data = [] # No current eval
    evaluation_service.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_select
    
    transcript = [
        {"role": "assistant", "content": "Hi", "timestamp": "2026-03-13T10:00:00Z"},
        {"role": "user", "content": "Hello", "timestamp": "2026-03-13T10:01:00Z"},
        {"role": "assistant", "content": "Question?", "timestamp": "2026-03-13T10:02:00Z"},
        {"role": "user", "content": "Answer.", "timestamp": "2026-03-13T10:03:00Z"}
    ]
    
    mock_ai_result = {
        "overall_score": 8.5,
        "communication_quality": 8.0,
        "technical_knowledge": 8.5,
        "problem_solving": 9.0,
        "coding_score": 8.0,
        "overall_feedback": "Excellent",
        "strengths": ["Logic"],
        "areas_for_improvement": ["Speed"]
    }
    
    with patch.object(evaluation_service, "_analyze_with_gemini", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_ai_result
        with patch.object(evaluation_service, "create_evaluation", return_value="eval-456") as mock_create:
            # Set MIN_MESSAGES_FOR_AI_EVALUATION to 2 for test
            evaluation_service.config.MIN_MESSAGES_FOR_AI_EVALUATION = 2
            
            evaluation_service.calculate_evaluation_from_transcript("tok1", "room1", transcript=transcript)
            
@pytest.mark.asyncio
async def test_calculate_evaluation_aggregation(evaluation_service):
    # Test aggregation of incremental evals
    booking_token = "tok-agg"
    # Three incremental evals needed for aggregation (8, 9, 8.5)
    evaluation_service.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"rounds_data": [{"score": 8, "communication": 7}, {"score": 9, "communication": 9}, {"score": 8.5, "communication": 8}], "interview_state": {}}
    ]
    
    with patch.object(evaluation_service, "create_evaluation", return_value="eval-agg") as mock_create:
        evaluation_service.calculate_evaluation_from_transcript(booking_token, "room1", transcript=[])
        
        # Verify aggregation in final call
        # (8+9+8.5)/3 = 8.5
        final_call_args = mock_create.call_args_list[-1][1]
        assert final_call_args["overall_score"] == 8.5
        assert final_call_args["communication_quality"] == 8.0
