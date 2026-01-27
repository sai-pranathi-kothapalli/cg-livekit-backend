"""
Conversation History Manager

Manages conversation history with intelligent truncation to prevent
context window overflow while maintaining conversation continuity.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from app.utils.logger import get_logger

logger = get_logger(__name__)


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


class ConversationHistoryManager:
    """
    Manages conversation history with sliding window truncation.
    """
    
    def __init__(
        self,
        session_id: str,
        action_type: str = "interview",
        max_conversation_tokens: int = 4000,
        max_messages: int = 20,
        min_messages_to_keep: int = 6,
        system_instructions_tokens: int = 3500
    ):
        """
        Initialize conversation history manager.
        """
        self.session_id = session_id
        self.action_type = action_type
        self.max_conversation_tokens = max_conversation_tokens
        self.max_messages = max_messages
        self.min_messages_to_keep = min_messages_to_keep
        self.system_instructions_tokens = system_instructions_tokens
        
        # Track conversation history in memory
        self.messages: List[Message] = []
        self.total_tokens = 0
        
        logger.info(
            f"[OK] ConversationHistoryManager initialized for session {session_id}: "
            f"max_tokens={max_conversation_tokens}, "
            f"max_messages={max_messages}"
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

    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """
        Get messages formatted for LLM API.
        """
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def clear(self) -> None:
        """Clear conversation history"""
        self.messages = []
        self.total_tokens = 0

    def close(self) -> None:
        """Clean up resources"""
        pass
