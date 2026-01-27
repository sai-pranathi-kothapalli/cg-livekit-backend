"""
Transcript Forwarding Service

Handles forwarding of agent responses to frontend via LiveKit data channel
with proper error handling and text accumulation.
"""

import json
import asyncio
from typing import Any, Callable, AsyncContextManager

from livekit import rtc

from app.utils.logger import get_logger

logger = get_logger(__name__)


class TranscriptForwardingService:
    """
    Service for forwarding agent transcripts to frontend.
    
    Wraps LLM chat method to capture streaming responses and
    publish them via LiveKit data channel.
    """
    
    DATA_CHANNEL_TOPIC = "lk-chat"
    
    def __init__(self, room: rtc.Room):
        """
        Initialize transcript forwarding service.
        
        Args:
            room: LiveKit room instance for data channel publishing
        """
        self.room = room
        self._last_sent_text = ""  # Track last sent text to prevent duplicates
        logger.debug("TranscriptForwardingService initialized")
    
    async def send_transcript(self, text: str, transcript_type: str = "agentTranscript", max_retries: int = 2) -> None:
        """
        Send transcript text to frontend via data channel with retry mechanism.
        
        Args:
            text: Transcript text to send
            transcript_type: Type of transcript ("agentTranscript" for agent, "userTranscript" for candidate)
            max_retries: Maximum number of retry attempts (default: 2)
        """
        if not text or not text.strip():
            logger.debug("Empty transcript, skipping...")
            return
        
        # Prevent duplicate sends (if same text is sent again, skip)
        if text == self._last_sent_text:
            logger.debug(f"⏭️  Skipping duplicate transcript ({len(text)} chars)")
            return
        
        # Check if room is connected
        if not self.room.isconnected():
            logger.warning(f"⚠️  Room not connected, cannot send transcript. Room state: {self.room.connection_state}")
            return
        
        # Log connection status and participant info for debugging
        local_participant = self.room.local_participant
        remote_participants = list(self.room.remote_participants.values())
        logger.info(
            f"📡 Sending transcript - Room connected: {self.room.isconnected()}, "
            f"Local participant: {local_participant.identity if local_participant else 'None'}, "
            f"Remote participants: {len(remote_participants)}"
        )
        
        # Format message for LiveKit data channel
        # Frontend expects: { "message": "text content", "type": "agentTranscript" or "userTranscript" }
        # Using agentTranscript/userTranscript type helps LiveKit's useSessionMessages recognize it
        payload = json.dumps({
            "message": text,
            "type": transcript_type,  # Mark as agent or user transcript for proper recognition
        }).encode('utf-8')
        
        # Retry mechanism with exponential backoff
        for attempt in range(max_retries):
            try:
                # Publish via data channel
                # Using local_participant because from agent's perspective, agent is local
                # Frontend will see this as coming from remote participant (the agent)
                # Using reliable=False for faster delivery (lower latency)
                await self.room.local_participant.publish_data(
                    payload,
                    topic=self.DATA_CHANNEL_TOPIC,
                    reliable=False,  # Faster delivery, lower latency
                )
                
                if attempt > 0:
                    logger.info(f"✅ Transcript sent successfully on retry attempt {attempt + 1}")
                else:
                    logger.info(f"📝 Transcript sent to frontend ({len(text)} chars, topic='{self.DATA_CHANNEL_TOPIC}'): {text[:100]}...")
                
                # Update last sent text to prevent duplicates
                self._last_sent_text = text
                return  # Success - exit retry loop
                
            except Exception as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 0.05s, 0.1s
                    delay = 0.05 * (2 ** attempt)
                    logger.warning(
                        f"⚠️  Transcript send failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Final attempt failed
                    logger.error(
                        f"❌ Failed to send transcript after {max_retries} attempts: "
                        f"{type(e).__name__}: {e}",
                        exc_info=True
                    )
                    # Note: STT transcripts from OpenAI will still be available as fallback
                    logger.info("💡 Note: STT transcripts from OpenAI are still available as fallback")
    
    def wrap_llm_chat(
        self,
        original_chat: Callable[..., AsyncContextManager]
    ) -> Callable[..., "ContextManagerWrapper"]:
        """
        Wrap LLM chat method to capture and forward transcripts.
        
        Args:
            original_chat: Original LLM chat method
            
        Returns:
            Wrapped chat method that forwards transcripts
        """
        def chat_wrapper(*args, **kwargs):
            """Wrapper function that returns a context manager wrapper"""
            logger.info("🔍 LLM chat called - setting up transcript wrapper...")
            logger.debug(f"   Chat args: {len(args)} positional, {len(kwargs)} keyword")
            
            # Get the original context manager
            original_cm = original_chat(*args, **kwargs)
            
            wrapper = ContextManagerWrapper(original_cm, self)
            logger.debug("✅ Transcript wrapper created for this LLM chat call")
            return wrapper
        
        return chat_wrapper


class ContextManagerWrapper:
    """
    Wraps LLM chat context manager to capture streaming chunks
    and forward accumulated text to frontend.
    """
    
    def __init__(
        self,
        original_cm: AsyncContextManager,
        transcript_service: TranscriptForwardingService
    ):
        """
        Initialize context manager wrapper.
        
        Args:
            original_cm: Original async context manager from LLM
            transcript_service: Service for sending transcripts
        """
        self._cm = original_cm
        self._transcript_service = transcript_service
        self._accumulated_text = ""
        self._last_sent_length = 0  # Track how much we've already sent
        self._entered = False
        self._forwarded = False
        self._conversation_id = None  # Track which conversation this is
    
    async def __aenter__(self):
        """Enter the original context manager"""
        # Reset state for new conversation turn
        self._accumulated_text = ""
        self._last_sent_length = 0
        self._forwarded = False
        self._conversation_id = id(self)  # Unique ID for this conversation turn
        
        logger.info(f"🔍 Transcript wrapper __aenter__ called - LLM chat starting (conversation_id: {self._conversation_id})")
        result = await self._cm.__aenter__()
        self._entered = True
        logger.info(f"✅ Transcript wrapper entered - ready to capture chunks (conversation_id: {self._conversation_id})")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit and forward accumulated text"""
        try:
            result = await self._cm.__aexit__(exc_type, exc_val, exc_tb)
            
            # Forward any remaining accumulated text
            if self._accumulated_text and not self._forwarded:
                try:
                    logger.info(
                        f"📤 Forwarding final accumulated transcript "
                        f"({len(self._accumulated_text)} chars)..."
                    )
                    await self._transcript_service.send_transcript(self._accumulated_text)
                    self._last_sent_length = len(self._accumulated_text)
                except Exception as e:
                    logger.error(f"Failed to send transcript in __aexit__: {e}", exc_info=True)
                self._forwarded = True
            
            return result
            
        except Exception as e:
            logger.error(f"⚠️  Error in __aexit__: {type(e).__name__}: {e}", exc_info=True)
            raise
    
    def __aiter__(self):
        """Return self as async iterator"""
        return self
    
    async def __anext__(self):
        """Iterate over original context manager and accumulate text"""
        try:
            chunk = await self._cm.__anext__()
            logger.debug(f"📦 Received LLM chunk: {type(chunk).__name__}")
            
            # Extract text from chunk
            chunk_text = ""
            if hasattr(chunk, 'content'):
                chunk_text = chunk.content
            elif hasattr(chunk, 'text'):
                chunk_text = chunk.text
            elif isinstance(chunk, str):
                chunk_text = chunk
            elif hasattr(chunk, 'delta') and hasattr(chunk.delta, 'content'):
                chunk_text = chunk.delta.content
            
            # Accumulate text
            if chunk_text:
                self._accumulated_text += chunk_text
                
                # Optimized batching for minimal latency:
                # - First 50 chars: send every character immediately for instant feedback
                # - After 50 chars: send every 5 chars for balance between speed and efficiency
                new_chars = len(self._accumulated_text) - self._last_sent_length
                
                # Priority 1 & 2: Send first character immediately, then optimize batching
                should_send = (
                    self._last_sent_length == 0 or  # First chunk - send immediately (even 1 char)
                    (len(self._accumulated_text) <= 50 and new_chars >= 1) or  # First 50 chars: send every character
                    new_chars >= 5  # After 50 chars: send every 5 chars (reduced from 10)
                )
                
                if should_send:
                    try:
                        # Send current accumulated text (full text so far)
                        await self._transcript_service.send_transcript(self._accumulated_text)
                        self._last_sent_length = len(self._accumulated_text)
                        logger.info(f"📤 Sent incremental transcript ({len(self._accumulated_text)} chars, {new_chars} new chars): {self._accumulated_text[:80]}...")
                    except Exception as e:
                        # Error is already logged in send_transcript with retry mechanism
                        logger.warning(f"⚠️ Incremental transcript send failed: {e}")
            
            return chunk
            
        except StopAsyncIteration:
            # Forward final accumulated text if any remains (check if there's unsent text)
            has_unsent_text = (
                self._accumulated_text and 
                len(self._accumulated_text) > self._last_sent_length
            )
            if has_unsent_text and not self._forwarded:
                try:
                    logger.info(
                        f"📤 Forwarding final transcript "
                        f"({len(self._accumulated_text)} chars, {len(self._accumulated_text) - self._last_sent_length} new)..."
                    )
                    await self._transcript_service.send_transcript(self._accumulated_text)
                    self._last_sent_length = len(self._accumulated_text)
                except Exception as e:
                    logger.error(f"Failed to send final transcript: {e}", exc_info=True)
                self._forwarded = True
            raise
    
    def __getattr__(self, name: str) -> Any:
        """Proxy any other attributes to the original context manager"""
        return getattr(self._cm, name)

