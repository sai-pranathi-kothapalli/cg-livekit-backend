import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch
from livekit import rtc
from app.services.transcript_service import TranscriptForwardingService

class MockRoom:
    def __init__(self):
        self.local_participant = AsyncMock()
        self.remote_participants = {}
    def isconnected(self):
        return True
    @property
    def connection_state(self):
        return "connected"

@pytest.fixture
def room():
    return MockRoom()

@pytest.fixture
def trans_service(room):
    # Using real class with mock room
    return TranscriptForwardingService(room)

@pytest.mark.asyncio
async def test_send_transcript(trans_service):
    await trans_service.send_transcript("Hello world")
    
    # Verify mock_room.local_participant.publish_data called
    publish_mock = trans_service.room.local_participant.publish_data
    assert publish_mock.called
    args, kwargs = publish_mock.call_args
    payload = json.loads(args[0].decode('utf-8'))
    assert payload["message"] == "Hello world"
    assert payload["type"] == "agentTranscript"

@pytest.mark.asyncio
async def test_wrap_llm_chat(trans_service):
    # Mock LLM chat context manager
    def mock_chat(*args, **kwargs):
        class CM:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): pass
            def __aiter__(self): return self
            async def __anext__(self):
                # Yield two chunks
                if not hasattr(self, '_yielded'):
                    self._yielded = 1
                    return MagicMock(content="Hello ")
                if self._yielded == 1:
                    self._yielded = 2
                    return MagicMock(content="world")
                raise StopAsyncIteration
        return CM()
        
    wrapped_chat = trans_service.wrap_llm_chat(mock_chat)
    
    # Use wrapped chat
    async with wrapped_chat() as stream:
        async for chunk in stream:
            pass
            
    # Verify that transcript service was used to send accumulation
    # "Hello " and "Hello world" should have been sent (based on batching logic)
    assert trans_service.room.local_participant.publish_data.called
