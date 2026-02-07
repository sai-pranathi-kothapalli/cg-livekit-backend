"""
History-Managed LLM Wrapper

Wraps LLM chat to manage conversation history with intelligent truncation.
"""

import asyncio
import re
import threading
import uuid
from typing import Any, Callable, AsyncContextManager, List, Dict, Optional
from livekit import rtc

from app.utils.logger import get_logger


# Decoder-level: block wrap-up language so model cannot end the interview on its own
WRAPUP_REPLACEMENT = "Let me ask you one more question."
WRAPUP_PHRASES = (
    "thank you for your time",
    "thanks for your time",
    "that's all from my side",
    "that is all from my side",
    "that's all for today",
    "that is all for today",
    "we're done",
    "we are done",
    "we are done here",
    "interview is over",
    "interview is complete",
    "that concludes",
    "wish you all the best",
    "all the best",
    "good luck",
    "best of luck",
    "you may leave",
    "you can go now",
    "that will be all",
    "no more questions",
    "that's all the questions",
    "thank you, that's all",
)


def _contains_wrapup(text: str) -> bool:
    if not text or not text.strip():
        return False
    lower = text.lower().strip()
    return any(phrase in lower for phrase in WRAPUP_PHRASES)


def _block_wrapup_at_decoder(text: str) -> str:
    """Strip wrap-up sentences and replace with a neutral continuation. Used at decoder level."""
    if not text or not text.strip():
        return text
    lower = text.lower()
    # Find earliest start of any wrap-up phrase
    earliest = len(text)
    for phrase in WRAPUP_PHRASES:
        idx = lower.find(phrase)
        if idx != -1:
            # Truncate at sentence boundary before this phrase if possible
            before = text[:idx]
            last_period = before.rfind(".")
            last_newline = before.rfind("\n")
            cut = max(last_period, last_newline)
            if cut != -1:
                idx = cut + 1
            earliest = min(earliest, idx)
    if earliest == 0:
        return WRAPUP_REPLACEMENT
    if earliest < len(text):
        out = text[:earliest].rstrip()
        if not out.endswith(".") and not out.endswith("?"):
            out += "."
        return out + " " + WRAPUP_REPLACEMENT
    return text


def _strip_system_context_from_transcript(text: str) -> str:
    """
    Remove echoed time-context / rule text from agent response so it does not
    appear in the user-facing transcript (TIME REMAINING, RULE:, etc.).
    """
    if not text or not text.strip():
        return text
    # Remove leading block: from "TIME REMAINING" up to (but not including) actual reply
    # Actual reply usually starts with Okay, Great, So, Hello, or a question (What/How/Why...)
    leading_system = re.compile(
        r"^\s*TIME REMAINING:.*?"
        r"(?=Okay|Great|So(?:\s|,)|Alright|Hello|Hi\s|Sure|Well|Right|Now,|"
        r"What\s+(?:year|have|did|are|is)|How\s+(?:did|have|are)|Why\s+|"
        r"Thank you|Thanks for|I see\.|Good\.|Perfect\.)",
        re.IGNORECASE | re.DOTALL,
    )
    text = leading_system.sub("", text)
    # Remove any remaining lines that are purely system context (model may add newlines)
    lines = text.split("\n")
    filtered = []
    skip_phrases = (
        "time remaining:",
        "current: minute",
        "rule: only when",
        "do not conclude or say goodbye until",
        "until you receive end_interview",
        "keep asking one question from the question bank",
        "you must not conclude",
        "you must still ask",
        "you must not stop",
        "do not let the model decide to end",
        "say we still have time and ask another question",
        "when time remaining is 2 or less",
        "when time remaining is 5 minutes or less",
        "(same as the timer on top left",
    )
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            filtered.append(line)
            continue
        line_lower = line_stripped.lower()
        if any(phrase in line_lower for phrase in skip_phrases):
            continue
        filtered.append(line)
    text = "\n".join(filtered)
    return text.strip()

# Thread-local storage to track greeting state
_thread_local = threading.local()

# Thread-local for token usage logging (set per LLM call, read by timing wrapper when stream ends)
_token_log_local = threading.local()


def _estimate_tokens(text: str) -> int:
    """Rough estimate: ~3 chars per token."""
    return (len(text or "") // 3)


def _chat_ctx_to_input_tokens_estimate(chat_ctx: Any) -> int:
    """
    Estimate input tokens from LiveKit ChatContext (when agent passes chat_ctx, not messages).
    Used so timing wrapper can log total_estimate = input + output.
    """
    try:
        if chat_ctx is None:
            return 0
        items = getattr(chat_ctx, "items", None)
        if not items:
            return 0
        total_chars = 0
        for item in items:
            x = getattr(item, "item", item)
            if hasattr(x, "content"):
                c = x.content
                if isinstance(c, str):
                    total_chars += len(c)
                elif isinstance(c, (list, tuple)):
                    for part in c:
                        if hasattr(part, "text"):
                            total_chars += len(part.text or "")
                        elif isinstance(part, str):
                            total_chars += len(part)
            elif hasattr(x, "text"):
                total_chars += len(x.text or "")
        return total_chars // 3 if total_chars else 0
    except Exception:
        return 0


def _set_last_llm_input_tokens_estimate(estimate: int) -> None:
    _token_log_local.last_input_tokens_estimate = estimate


def get_last_llm_input_tokens_estimate() -> int:
    """Get last input token estimate (for logging total in timing wrapper)."""
    return getattr(_token_log_local, "last_input_tokens_estimate", 0)

# Import conversation history manager
try:
    from app.services.conversation_history_manager import ConversationHistoryManager
except ImportError:
    # Fallback: try importing from agent services
    import sys
    from pathlib import Path
    agent_path = Path(__file__).parent.parent.parent.parent / "Livekit-agent-backend" / "services"
    if agent_path.exists() and str(agent_path) not in sys.path:
        sys.path.insert(0, str(agent_path))
    try:
        from conversation_history_manager import ConversationHistoryManager
    except ImportError:
        # Last resort: create a simple stub
        logger.warning("[WARN] conversation_history_manager not found, creating minimal stub")
        class ConversationHistoryManager:
            def __init__(self, *args, **kwargs):
                self._messages = []
            def add_message(self, role, content):
                self._messages.append({"role": role, "content": content})
            def get_messages_for_llm(self):
                return self._messages
            def clear(self):
                self._messages = []
            def get_total_tokens(self):
                return sum(len(msg.get("content", "")) // 3 for msg in self._messages)

logger = get_logger(__name__)


def set_skip_transcript(value: bool):
    """Set flag to skip transcript sending (e.g., for greeting)"""
    _thread_local.skip_transcript = value


def get_skip_transcript() -> bool:
    """Get flag to skip transcript sending"""
    return getattr(_thread_local, 'skip_transcript', False)


class HistoryManagedLLMWrapper:
    """
    Wraps LLM chat to manage conversation history.
    
    Intercepts messages, manages history with truncation,
    and ensures context window limits are respected.
    """
    
    def __init__(
        self,
        original_chat: Callable[..., AsyncContextManager],
        transcript_service: Any,  # TranscriptForwardingService
        session_id: str = None,  # [OK] NEW: Session ID
        action_type: str = "interview",  # [OK] NEW: Action type
        max_conversation_tokens: int = 4000,
        max_messages: int = 20,
        min_messages_to_keep: int = 6,
        recent_messages_to_keep_full: int = 6,
        max_summary_chars: int = 800,
        use_gemini_for_summary: bool = False,
        gemini_api_key: Optional[str] = None,
        gemini_model: str = "gemini-1.5-flash",
    ):
        """
        Initialize history-managed LLM wrapper.
        
        Args:
            original_chat: Original LLM chat method
            transcript_service: Transcript forwarding service
            session_id: Unique session identifier (auto-generated if not provided)
            action_type: Type of conversation (e.g., "interview", "chat")
            max_conversation_tokens: Max tokens for conversation (excluding system)
            max_messages: Maximum messages to keep
            min_messages_to_keep: Minimum messages to always keep
            recent_messages_to_keep_full: Last N messages sent in full; older as summary (reduces LLM cost)
            max_summary_chars: Max characters for the "earlier conversation" summary string
            use_gemini_for_summary: If True, use Gemini 1.5 to summarize older messages
            gemini_api_key: Google API key for Gemini summarization
            gemini_model: Model for summarization (e.g. gemini-1.5-flash)
        """
        self._original_chat = original_chat
        self._transcript_service = transcript_service
        
        # [OK] Generate session_id if not provided
        if session_id is None:
            session_id = f"session_{uuid.uuid4()}"
        
        self._session_id = session_id
        
        # [OK] FIXED: Pass session_id and cost-reduction params to ConversationHistoryManager
        self._history_manager = ConversationHistoryManager(
            session_id=session_id,
            action_type=action_type,
            max_conversation_tokens=max_conversation_tokens,
            max_messages=max_messages,
            min_messages_to_keep=min_messages_to_keep,
            recent_messages_to_keep_full=recent_messages_to_keep_full,
            max_summary_chars=max_summary_chars,
            use_gemini_for_summary=use_gemini_for_summary,
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
        )
        logger.info(f"HistoryManagedLLMWrapper initialized for session {session_id}")
    
    def __call__(self, *args, **kwargs) -> "HistoryManagedContextWrapper":
        """
        Call wrapper - intercepts LLM chat calls.
        
        Intercepts messages parameter to manage history before
        passing to original LLM chat.
        """
        _set_last_llm_input_tokens_estimate(0)  # reset so timing wrapper doesn't use stale value
        # Extract messages from kwargs or args
        messages = kwargs.get('messages', None)
        if messages is None and len(args) > 0:
            # Try to get messages from first positional arg
            if isinstance(args[0], (list, tuple)):
                messages = args[0]
        
        # Manage conversation history
        if messages and isinstance(messages, (list, tuple)):
            # Separate system messages from conversation messages
            system_messages = []
            incoming_conversation = []
            
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    
                    if role == 'system':
                        # Keep system messages as-is
                        system_messages.append(msg)
                    elif role in ('user', 'assistant') and content:
                        # Track conversation messages
                        incoming_conversation.append((role, content))
            
            # Sync history with incoming messages (use full list for sync, not summary+recent)
            # Strategy: Intelligently merge new messages instead of clearing/rebuilding
            if incoming_conversation:
                current_history = self._history_manager.get_full_message_list_for_sync()
                current_content = [(msg['role'], msg['content']) for msg in current_history]
                
                # Check if incoming has fewer messages (Agent truncated) - rebuild to stay in sync
                if len(incoming_conversation) < len(current_content):
                    logger.debug(
                        f"🔄 Incoming conversation shorter ({len(incoming_conversation)} < {len(current_content)}), "
                        f"rebuilding history to stay in sync"
                    )
                    self._history_manager.clear()
                    for role, content in incoming_conversation:
                        self._history_manager.add_message(role, content)
                else:
                    # Add only new messages (ones not in current history)
                    new_messages = [
                        (role, content) for role, content in incoming_conversation
                        if (role, content) not in current_content
                    ]
                    
                    if new_messages:
                        logger.debug(
                            f"➕ Adding {len(new_messages)} new messages to history "
                            f"(current: {len(current_content)}, incoming: {len(incoming_conversation)})"
                        )
                        for role, content in new_messages:
                            self._history_manager.add_message(role, content)
                    elif len(incoming_conversation) > len(current_content):
                        # Incoming has more messages but none are new - rebuild to sync
                        logger.debug(
                            f"🔄 Rebuilding history to sync with Agent "
                            f"(current: {len(current_content)}, incoming: {len(incoming_conversation)})"
                        )
                        self._history_manager.clear()
                        for role, content in incoming_conversation:
                            self._history_manager.add_message(role, content)
            
            # Get managed conversation history (already truncated if needed)
            managed_conversation = self._history_manager.get_messages_for_llm()
            
            # Combine: system messages first, then managed conversation history
            managed_messages = system_messages + managed_conversation
            
            # Update kwargs/args
            if 'messages' in kwargs:
                kwargs['messages'] = managed_messages
            elif len(args) > 0:
                # Replace first arg
                args = (managed_messages,) + args[1:]
            
            # Estimate input/context tokens for logging (and for timing wrapper to log total)
            input_tokens_estimate = sum(
                _estimate_tokens(m.get("content", "")) for m in managed_messages
            )
            _set_last_llm_input_tokens_estimate(input_tokens_estimate)
            logger.info(
                f"📊 [TOKENS] input_estimate={input_tokens_estimate} context_estimate={input_tokens_estimate} "
                f"(messages={len(managed_messages)}, history managed: {len(incoming_conversation)}→{len(managed_conversation)})"
            )
            logger.info(
                f"📊 History managed: {len(incoming_conversation)} incoming → "
                f"{len(managed_conversation)} managed messages "
                f"({self._history_manager.get_total_tokens()} tokens), "
                f"{len(system_messages)} system messages"
            )
        else:
            # Agent passed chat_ctx (LiveKit) instead of messages — still set input estimate for token logging
            chat_ctx = kwargs.get("chat_ctx")
            if chat_ctx is not None:
                input_tokens_estimate = _chat_ctx_to_input_tokens_estimate(chat_ctx)
                _set_last_llm_input_tokens_estimate(input_tokens_estimate)
                logger.info(
                    f"📊 [TOKENS] input_estimate={input_tokens_estimate} (from chat_ctx, no message list)"
                )
        
        # Get original context manager with error handling
        try:
            original_cm = self._original_chat(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"[ERR] LLM chat call failed: {e}",
                exc_info=True
            )
            if messages:
                logger.error(
                    f"   Context: {len(managed_messages)} total messages, "
                    f"{self._history_manager.get_total_tokens()} conversation tokens, "
                    f"{len(system_messages)} system messages"
                )
            raise
        
        # Check thread-local flag for skipping transcript (e.g., greeting)
        skip_transcript = get_skip_transcript()
        
        # Wrap with history-aware context manager
        return HistoryManagedContextWrapper(
            original_cm,
            self._transcript_service,
            self._history_manager,
            skip_transcript=skip_transcript
        )


class HistoryManagedContextWrapper:
    """
    Context manager wrapper that tracks assistant responses
    and updates conversation history.
    """
    
    def __init__(
        self,
        original_cm: AsyncContextManager,
        transcript_service: Any,
        history_manager: ConversationHistoryManager,
        skip_transcript: bool = False  # NEW: Flag to skip transcript sending
    ):
        self._cm = original_cm
        self._transcript_service = transcript_service
        self._history_manager = history_manager
        self._skip_transcript = skip_transcript  # NEW: Skip transcript for greeting
        self._accumulated_text = ""
        self._last_sent_length = 0
        self._last_sent_text = ""  # Avoid sending same transcript twice (e.g. gate replacement)
        self._entered = False
        self._forwarded = False
        self._conversation_id = None
        # Decoder-level wrap-up block
        self._wrapup_replacement_yielded = False
        self._consuming_rest_after_wrapup = False
    
    async def __aenter__(self):
        """Enter the original context manager"""
        self._accumulated_text = ""
        self._last_sent_length = 0
        self._last_sent_text = ""
        self._forwarded = False
        self._conversation_id = id(self)
        self._wrapup_replacement_yielded = False
        self._consuming_rest_after_wrapup = False
        
        logger.debug(f"[DEBUG] History-managed wrapper entering (conversation_id: {self._conversation_id})")
        result = await self._cm.__aenter__()
        self._entered = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit and update history with assistant response"""
        try:
            result = await self._cm.__aexit__(exc_type, exc_val, exc_tb)
            
            # Forward transcript (don't add to history here - Agent will include it in next call)
            # Skip if flag is set (e.g., for initial greeting)
            # Only send if not already forwarded (StopAsyncIteration may have already sent it)
            if self._accumulated_text and not self._forwarded and not self._skip_transcript:
                has_unsent_text = len(self._accumulated_text) > self._last_sent_length
                if has_unsent_text:
                    logger.debug(
                        f"[OK] Assistant response completed: "
                        f"{len(self._accumulated_text)} chars ({len(self._accumulated_text) - self._last_sent_length} unsent)"
                    )
                    
                    # Forward transcript (strip echoed system context so it doesn't show in UI)
                    try:
                        to_send = _strip_system_context_from_transcript(self._accumulated_text)
                        if to_send and to_send != self._last_sent_text:
                            await self._transcript_service.send_transcript(to_send)
                            self._last_sent_text = to_send
                        self._last_sent_length = len(self._accumulated_text)
                    except Exception as e:
                        logger.error(f"Failed to send transcript: {e}", exc_info=True)
                
                self._forwarded = True  # Mark as forwarded even if no unsent text
            elif self._skip_transcript:
                logger.debug("⏭️  Skipping transcript (greeting or flagged)")
            
            return result
        except Exception as e:
            logger.error(f"[WARN]  Error in history wrapper __aexit__: {e}", exc_info=True)
            raise
    
    def __aiter__(self):
        """Return self as async iterator"""
        return self
    
    async def __anext__(self):
        """Iterate and accumulate assistant response with error recovery. Block wrap-up at decoder level."""
        max_retries = 3
        retry_count = 0
        
        # If we already detected wrap-up, consume and discard rest of stream, then forward sanitized transcript
        if self._consuming_rest_after_wrapup:
            try:
                while True:
                    await self._cm.__anext__()
            except StopAsyncIteration:
                if self._accumulated_text and not self._forwarded and not self._skip_transcript:
                    has_unsent = len(self._accumulated_text) > self._last_sent_length
                    if has_unsent:
                        try:
                            to_send = _strip_system_context_from_transcript(self._accumulated_text)
                            if to_send and to_send != self._last_sent_text:
                                await self._transcript_service.send_transcript(to_send)
                            self._last_sent_length = len(self._accumulated_text)
                        except Exception as e:
                            logger.error("Failed to send transcript after wrap-up block: %s", e)
                    self._forwarded = True
                raise
        
        while retry_count < max_retries:
            try:
                chunk = await self._cm.__anext__()
                
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
                    
                    # Decoder-level: block wrap-up language — replace with continuation and consume rest
                    if _contains_wrapup(self._accumulated_text) and not self._wrapup_replacement_yielded:
                        self._accumulated_text = _block_wrapup_at_decoder(self._accumulated_text)
                        self._wrapup_replacement_yielded = True
                        self._consuming_rest_after_wrapup = True
                        logger.info("[DECODER] Wrap-up language blocked; replacing with: %s", WRAPUP_REPLACEMENT)
                        # Yield a chunk that TTS will speak (replacement only)
                        class _Chunk:
                            def __init__(self):
                                self.content = WRAPUP_REPLACEMENT
                                self.text = WRAPUP_REPLACEMENT
                        return _Chunk()
                    
                    # Send incremental transcript (skip if flag is set)
                    if not self._skip_transcript:
                        new_chars = len(self._accumulated_text) - self._last_sent_length
                        should_send = (
                            self._last_sent_length == 0 or
                            (len(self._accumulated_text) <= 50 and new_chars >= 1) or
                            new_chars >= 5
                        )
                        
                        if should_send:
                            try:
                                to_send = _strip_system_context_from_transcript(self._accumulated_text)
                                if to_send and to_send != self._last_sent_text:
                                    await self._transcript_service.send_transcript(to_send)
                                    self._last_sent_text = to_send
                                self._last_sent_length = len(self._accumulated_text)
                            except Exception as e:
                                logger.warning(f"[WARN] Incremental transcript send failed: {e}")
                
                # Reset retry count on successful chunk
                retry_count = 0
                return chunk
                
            except StopAsyncIteration:
                # Normal end of stream - forward final transcript (skip if flag is set)
                # Only send if we haven't already forwarded and there's unsent text
                if self._accumulated_text and not self._forwarded and not self._skip_transcript:
                    has_unsent_text = len(self._accumulated_text) > self._last_sent_length
                    if has_unsent_text:
                        logger.debug(
                            f"[OK] Final assistant response: "
                            f"{len(self._accumulated_text)} chars"
                        )
                        try:
                            to_send = _strip_system_context_from_transcript(self._accumulated_text)
                            if to_send and to_send != self._last_sent_text:
                                await self._transcript_service.send_transcript(to_send)
                                self._last_sent_text = to_send
                            self._last_sent_length = len(self._accumulated_text)
                            self._forwarded = True  # Mark as forwarded to prevent duplicate
                        except Exception as e:
                            logger.error(f"Failed to send final transcript: {e}", exc_info=True)
                    else:
                        # Already sent everything incrementally, just mark as forwarded
                        self._forwarded = True
                raise
                
            except Exception as e:
                retry_count += 1
                error_type = type(e).__name__
                error_msg = str(e)
                
                # Check if it's a recoverable error
                is_recoverable = (
                    "timeout" in error_msg.lower() or
                    "connection" in error_msg.lower() or
                    "503" in error_msg or
                    "502" in error_msg or
                    "429" in error_msg or  # Rate limit
                    "context" in error_msg.lower() or
                    "token" in error_msg.lower()
                )
                
                if retry_count < max_retries and is_recoverable:
                    wait_time = retry_count * 2  # Exponential backoff: 2s, 4s, 6s
                    logger.warning(
                        f"[WARN]  LLM chunk error (retry {retry_count}/{max_retries}): {error_type}: {error_msg}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Non-recoverable or max retries reached
                    logger.error(
                        f"[ERR] LLM chunk error (non-recoverable or max retries): {error_type}: {error_msg}",
                        exc_info=True
                    )
                    # End gracefully instead of crashing to keep session alive
                    logger.warning("🔄 Ending LLM stream gracefully to keep session alive")
                    raise StopAsyncIteration
    
    def __getattr__(self, name: str) -> Any:
        """Proxy any other attributes to the original context manager"""
        return getattr(self._cm, name)

