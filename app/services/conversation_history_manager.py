"""
Conversation History Manager

Manages conversation history with intelligent truncation to prevent
context window overflow while maintaining conversation continuity.

Cost-reduction strategy: send last N messages in full, and older history
as a single summarized/compressed string to reduce LLM tokens per turn.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from app.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@dataclass
class Message:
    """Represents a single conversation message"""
    role: str  # "user" or "assistant"
    content: str
    tokens: int  # Estimated token count
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


def _build_summary_from_messages(messages: List[Message], max_chars: int) -> str:
    """
    Build a single summary string from older messages (truncated concatenation).
    No LLM call; just "[User]: ... [Assistant]: ..." with a character limit.
    """
    if not messages:
        return ""
    parts = []
    total = 0
    for m in messages:
        line = f"[{m.role.capitalize()}]: {m.content.strip()}\n"
        if total + len(line) > max_chars:
            remaining = max_chars - total - 20  # leave room for "... [truncated]"
            if remaining > 0 and m.content:
                parts.append(f"[{m.role.capitalize()}]: {m.content.strip()[:remaining]}...\n")
            break
        parts.append(line)
        total += len(line)
    return "".join(parts).strip()


def _summarize_with_gemini_sync(
    messages: List[Message],
    max_chars: int,
    api_key: str,
    model: str = "gemini-1.5-flash",
) -> str:
    """
    Use Gemini 1.5 to summarize older conversation (sync). Falls back to truncated
    concatenation on failure or if httpx unavailable.
    """
    if not messages or not api_key or not HTTPX_AVAILABLE:
        return _build_summary_from_messages(messages, max_chars)
    text = "\n".join(
        f"[{m.role.capitalize()}]: {m.content.strip()}" for m in messages
    )
    if not text.strip():
        return ""
    prompt = (
        "Summarize this interview conversation in 2-4 concise sentences. "
        "Include topics discussed and key points. Output only the summary, no preamble.\n\n"
        + text
    )
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                url,
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 256},
                },
            )
            r.raise_for_status()
            data = r.json()
        usage = data.get("usageMetadata") or {}
        inp = usage.get("promptTokenCount") or usage.get("prompt_token_count")
        out = usage.get("candidatesTokenCount") or usage.get("candidates_token_count")
        tot = usage.get("totalTokenCount") or usage.get("total_token_count")
        if inp is not None or out is not None or tot is not None:
            logger.info(
                "📊 [SUMMARY TOKENS] input=%s output=%s total=%s (Gemini history summary)",
                inp or "—", out or "—", tot or "—",
            )
        content = ""
        if "candidates" in data and len(data["candidates"]) > 0:
            cand = data["candidates"][0]
            if "content" in cand and "parts" in cand["content"] and cand["content"]["parts"]:
                content = cand["content"]["parts"][0].get("text", "").strip()
        if content:
            return content[:max_chars] if len(content) > max_chars else content
    except Exception as e:
        logger.debug("Gemini summary failed, using truncated concatenation: %s", e)
    return _build_summary_from_messages(messages, max_chars)


class ConversationHistoryManager:
    """
    Manages conversation history with sliding window truncation.

    When history is long, returns:
    - One system message with "Summary of earlier conversation: ..." (older messages, truncated)
    - Last recent_messages_to_keep_full messages in full

    This reduces LLM cost by sending only recent turns in full and compressing older context.
    """
    
    def __init__(
        self,
        session_id: str,
        action_type: str = "interview",
        max_conversation_tokens: int = 4000,
        max_messages: int = 20,
        min_messages_to_keep: int = 6,
        system_instructions_tokens: int = 3500,
        recent_messages_to_keep_full: int = 6,
        max_summary_chars: int = 800,
        use_gemini_for_summary: bool = False,
        gemini_api_key: Optional[str] = None,
        gemini_model: str = "gemini-1.5-flash",
    ):
        """
        Initialize conversation history manager.

        Args:
            recent_messages_to_keep_full: Number of most recent messages to send in full (e.g. 6 = last 3 turns).
            max_summary_chars: Max characters for the "older history" summary string (~260 tokens at 3 chars/token).
            use_gemini_for_summary: If True and gemini_api_key set, use Gemini to summarize older messages.
            gemini_api_key: Google API key for Gemini (only used when use_gemini_for_summary=True).
            gemini_model: Model name for summarization (e.g. gemini-1.5-flash).
        """
        self.session_id = session_id
        self.action_type = action_type
        self.max_conversation_tokens = max_conversation_tokens
        self.max_messages = max_messages
        self.min_messages_to_keep = min_messages_to_keep
        self.system_instructions_tokens = system_instructions_tokens
        self.recent_messages_to_keep_full = max(2, recent_messages_to_keep_full)  # at least 2 (one pair)
        self.max_summary_chars = max(200, max_summary_chars)
        self.use_gemini_for_summary = use_gemini_for_summary and bool(gemini_api_key)
        self.gemini_api_key = gemini_api_key or ""
        self.gemini_model = gemini_model or "gemini-1.5-flash"
        
        # Track conversation history in memory
        self.messages: List[Message] = []
        self.total_tokens = 0
        
        logger.info(
            f"[OK] ConversationHistoryManager initialized for session {session_id}: "
            f"max_tokens={max_conversation_tokens}, max_messages={max_messages}, "
            f"recent_full={self.recent_messages_to_keep_full}, max_summary_chars={self.max_summary_chars}, "
            f"use_gemini_summary={self.use_gemini_for_summary}"
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (~3 characters per token)"""
        if not text:
            return 0
        return len(text) // 3
    
    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to conversation history.
        """
        tokens = self._estimate_tokens(content)
        message = Message(role=role, content=content, tokens=tokens)
        
        self.messages.append(message)
        self.total_tokens += tokens
        
        # Truncate if needed
        self._truncate_if_needed()
    
    def _truncate_if_needed(self) -> None:
        """
        Truncate old messages if history exceeds limits.
        """
        while len(self.messages) > self.max_messages or (self.total_tokens > self.max_conversation_tokens and len(self.messages) > self.min_messages_to_keep):
            removed = self.messages.pop(0)
            self.total_tokens -= removed.tokens
            logger.debug(f"Truncated message from history: {removed.role}")

    def get_full_message_list_for_sync(self) -> List[Dict[str, str]]:
        """
        Get all messages as list of dicts (no summary). Use for sync with incoming
        conversation only; do not use for LLM input.
        """
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """
        Get messages formatted for LLM API.

        Cost-reduction: if we have more than recent_messages_to_keep_full messages,
        older messages are returned as a single "Summary of earlier conversation" system message,
        and only the last recent_messages_to_keep_full messages are sent in full.
        """
        if not self.messages:
            return []
        n = self.recent_messages_to_keep_full
        if len(self.messages) <= n:
            return [{"role": m.role, "content": m.content} for m in self.messages]
        older = self.messages[:-n]
        recent = self.messages[-n:]
        if self.use_gemini_for_summary and self.gemini_api_key:
            summary_text = _summarize_with_gemini_sync(
                older, self.max_summary_chars, self.gemini_api_key, self.gemini_model
            )
        else:
            summary_text = _build_summary_from_messages(older, self.max_summary_chars)
        if not summary_text.strip():
            return [{"role": m.role, "content": m.content} for m in recent]
        summary_message = {
            "role": "system",
            "content": f"Summary of earlier conversation (use for context only; respond based on the most recent messages below):\n\n{summary_text}",
        }
        result = [summary_message] + [{"role": m.role, "content": m.content} for m in recent]
        logger.debug(
            f"History for LLM: 1 summary message ({len(summary_text)} chars) + {len(recent)} recent messages "
            f"(reduced from {len(self.messages)} full messages)"
        )
        return result

    def clear(self) -> None:
        """Clear conversation history"""
        self.messages = []
        self.total_tokens = 0

    def close(self) -> None:
        """Clean up resources"""
        pass
