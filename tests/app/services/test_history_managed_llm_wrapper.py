import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.history_managed_llm_wrapper import (
    HistoryManagedLLMWrapper,
    _contains_wrapup,
    _block_wrapup_at_decoder,
    _strip_system_context_from_transcript,
    increment_questions_asked,
    get_questions_asked,
    reset_questions_asked
)

def test_question_counter():
    reset_questions_asked()
    assert get_questions_asked() == 0
    increment_questions_asked()
    assert get_questions_asked() == 1
    reset_questions_asked()
    assert get_questions_asked() == 0

def test_contains_wrapup():
    assert _contains_wrapup("This concludes the interview") is True
    assert _contains_wrapup("Hello world") is False

def test_block_wrapup_at_decoder():
    text = "Here is a question. This concludes the interview."
    blocked = _block_wrapup_at_decoder(text)
    assert "concludes" not in blocked
    assert "Here is a question" in blocked

def test_strip_system_context():
    text = "TIME REMAINING: 5 minutes. Okay, tell me about yourself."
    stripped = _strip_system_context_from_transcript(text)
    assert "TIME REMAINING" not in stripped
    assert "Okay, tell me about yourself" in stripped

@pytest.mark.asyncio
async def test_history_wrapper_call():
    mock_chat = MagicMock()
    mock_transcript_service = MagicMock()
    
    wrapper = HistoryManagedLLMWrapper(
        original_chat=mock_chat,
        transcript_service=mock_transcript_service,
        session_id="test_session"
    )
    
    messages = [
        {"role": "system", "content": "Instructions"},
        {"role": "user", "content": "Hello"}
    ]
    
    # Mock the context manager returned by original_chat
    mock_cm = AsyncMock()
    mock_chat.return_value = mock_cm
    
    wrapper(messages=messages)
    
    # Verify history manager was updated
    assert len(wrapper._history_manager.get_full_message_list_for_sync()) > 0
    
    # Verify original chat was called with managed messages
    mock_chat.assert_called_once()
    args, kwargs = mock_chat.call_args
    assert any(m['role'] == 'system' for m in kwargs['messages'])
    assert any(m['role'] == 'user' for m in kwargs['messages'])
