"""
Transcript Storage Service

Saves interview transcripts to MongoDB.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import Config
from app.db.mongo import get_database
from app.utils.logger import get_logger
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class TranscriptStorageService:
    """Service for storing interview transcripts in MongoDB."""

    def __init__(self, config: Config):
        self.config = config
        self.db = get_database(config)
        self.col = self.db["interview_transcripts"]

    def save_transcript_message(
        self,
        booking_token: str,
        room_name: str,
        role: str,
        content: str,
        message_index: int,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        try:
            if timestamp is None:
                timestamp = get_now_ist()
            transcript_data = {
                "booking_token": booking_token,
                "room_name": room_name,
                "message_role": role,
                "message_content": content,
                "message_index": message_index,
                "timestamp": timestamp.isoformat(),
            }
            self.col.insert_one(transcript_data)
            logger.debug(f"✅ Saved transcript message {message_index} for booking {booking_token}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving transcript message: {e}", exc_info=True)
            return False

    def save_transcript_batch(
        self,
        booking_token: str,
        room_name: str,
        messages: List[Dict[str, Any]],
    ) -> bool:
        try:
            transcript_data = []
            for msg in messages:
                timestamp = msg.get("timestamp")
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                elif timestamp is None:
                    timestamp = get_now_ist()
                transcript_data.append({
                    "booking_token": booking_token,
                    "room_name": room_name,
                    "message_role": msg["role"],
                    "message_content": msg["content"],
                    "message_index": msg.get("index", 0),
                    "timestamp": timestamp.isoformat(),
                })
            if transcript_data:
                self.col.insert_many(transcript_data)
                logger.info(f"✅ Saved {len(transcript_data)} transcript messages for booking {booking_token}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error saving transcript batch: {e}", exc_info=True)
            return False

    def get_transcript(self, booking_token: str) -> List[Dict[str, Any]]:
        try:
            cursor = self.col.find({"booking_token": booking_token}).sort("message_index", 1)
            out = []
            for row in cursor:
                out.append({
                    "role": row.get("message_role"),
                    "content": row.get("message_content"),
                    "timestamp": row.get("timestamp"),
                    "index": row.get("message_index"),
                })
            return out
        except Exception as e:
            logger.error(f"❌ Error fetching transcript: {e}", exc_info=True)
            return []

    def get_booking_tokens_with_transcripts(self, tokens: List[str]) -> set:
        """Return set of booking_tokens that have at least one transcript message."""
        try:
            out = self.col.distinct("booking_token", {"booking_token": {"$in": tokens}})
            return set(out)
        except Exception as e:
            logger.error(f"Error fetching transcript tokens: {e}")
            return set()
