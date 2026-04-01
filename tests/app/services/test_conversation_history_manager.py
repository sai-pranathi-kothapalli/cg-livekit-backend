import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from app.services.conversation_history_manager import ConversationHistoryManager, Message, _build_summary_from_messages

def test_message_creation():
    m = Message(role="user", content="Hello", tokens=2)
    assert m.role == "user"
    assert m.content == "Hello"
    assert isinstance(m.timestamp, datetime)

def test_build_summary_from_messages():
    msgs = [
        Message(role="user", content="Hello", tokens=2),
        Message(role="assistant", content="Hi there", tokens=3)
    ]
    summary = _build_summary_from_messages(msgs, max_chars=100)
    assert "[User]: Hello" in summary
    assert "[Assistant]: Hi there" in summary

def test_manager_add_and_truncate():
    manager = ConversationHistoryManager(
        session_id="s1",
        max_messages=3,
        min_messages_to_keep=2
    )
    manager.add_message("user", "m1")
    manager.add_message("assistant", "m2")
    manager.add_message("user", "m3")
    assert len(manager.messages) == 3
    
    manager.add_message("assistant", "m4")
    # Should truncate first message
    assert len(manager.messages) == 3
    assert manager.messages[0].content == "m2"

def test_get_messages_for_llm_no_summary():
    manager = ConversationHistoryManager(
        session_id="s1",
        recent_messages_to_keep_full=4
    )
    for i in range(3):
        manager.add_message("user", f"msg {i}")
    
    msgs = manager.get_messages_for_llm()
    assert len(msgs) == 3
    assert msgs[0]["role"] == "user"

def test_get_messages_for_llm_with_summary():
    manager = ConversationHistoryManager(
        session_id="s1",
        recent_messages_to_keep_full=2,
        use_gemini_for_summary=False
    )
    # Add 4 messages. Last 2 full, first 2 summarized.
    manager.add_message("user", "old 1")
    manager.add_message("assistant", "old 2")
    manager.add_message("user", "new 1")
    manager.add_message("assistant", "new 2")
    
    msgs = manager.get_messages_for_llm()
    assert len(msgs) == 3 # 1 summary + 2 full
    assert msgs[0]["role"] == "system"
    assert "Summary" in msgs[0]["content"]
    assert msgs[1]["content"] == "new 1"
    assert msgs[2]["content"] == "new 2"

@patch("httpx.Client")
def test_summarize_with_gemini(mock_client_class):
    mock_client = mock_client_class.return_value.__enter__.return_value
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "AI generated summary"}]}}]
    }
    mock_client.post.return_value = mock_response
    
    manager = ConversationHistoryManager(
        session_id="s1",
        recent_messages_to_keep_full=1,
        use_gemini_for_summary=True,
        gemini_api_key="fake-key"
    )
    manager.add_message("user", "long text 1")
    manager.add_message("assistant", "long response 1")
    manager.add_message("user", "latest")
    
    msgs = manager.get_messages_for_llm()
    assert msgs[0]["content"].find("AI generated summary") != -1
