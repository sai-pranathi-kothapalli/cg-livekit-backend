"""
Transcript Storage Service

Saves interview transcripts to MongoDB.
One MongoDB document per interview: { booking_token, room_name, messages: [...], created_at, updated_at }.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import Config
from app.db.mongo import get_database
from app.utils.logger import get_logger
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class TranscriptStorageService:
    """Service for storing interview transcripts in MongoDB. One document per interview."""

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
        """
        Append one message to the interview's transcript document.
        Uses upsert: one document per booking_token with a messages array.
        """
        try:
            if timestamp is None:
                timestamp = get_now_ist()
            now_iso = get_now_ist().isoformat()
            message_entry = {
                "role": role,
                "content": content,
                "message_index": message_index,
                "timestamp": timestamp.isoformat(),
            }
            result = self.col.update_one(
                {"booking_token": booking_token},
                {
                    "$push": {"messages": message_entry},
                    "$set": {"updated_at": now_iso, "room_name": room_name},
                    "$setOnInsert": {"booking_token": booking_token, "created_at": now_iso},
                },
                upsert=True,
            )
            if result.upserted_id or result.modified_count:
                logger.debug(f"✅ Saved transcript message {message_index} for booking {booking_token}")
                return True
            return True  # matched, push applied
        except Exception as e:
            logger.error(f"❌ Error saving transcript message: {e}", exc_info=True)
            return False

    def save_transcript_batch(
        self,
        booking_token: str,
        room_name: str,
        messages: List[Dict[str, Any]],
    ) -> bool:
        """
        Set or append messages for one interview (one document per interview).
        If a document exists, appends new messages; otherwise creates one with all messages.
        """
        try:
            if not messages:
                return False
            now_iso = get_now_ist().isoformat()
            entries = []
            for msg in messages:
                ts = msg.get("timestamp")
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                elif ts is None:
                    ts = get_now_ist()
                entries.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "message_index": msg.get("index", len(entries)),
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                })
            self.col.update_one(
                {"booking_token": booking_token},
                {
                    "$push": {"messages": {"$each": entries}},
                    "$set": {"updated_at": now_iso, "room_name": room_name},
                    "$setOnInsert": {"booking_token": booking_token, "created_at": now_iso},
                },
                upsert=True,
            )
            logger.info(f"✅ Saved batch of {len(entries)} transcript messages for booking {booking_token}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving transcript batch: {e}", exc_info=True)
            return False

    def get_transcript(self, booking_token: str) -> List[Dict[str, Any]]:
        """
        Return list of messages for this interview.
        Supports: (1) one doc per interview with "messages" array; (2) legacy one doc per message.
        """
        try:
            # New format: one document with "messages" array
            doc = self.col.find_one({"booking_token": booking_token})
            if not doc:
                return []
            if "messages" in doc and isinstance(doc["messages"], list):
                out = []
                for m in doc["messages"]:
                    out.append({
                        "role": m.get("role") or m.get("message_role"),
                        "content": m.get("content") or m.get("message_content", ""),
                        "timestamp": m.get("timestamp"),
                        "index": m.get("message_index", m.get("index")),
                    })
                return out
            # Legacy: single-message document (old schema)
            if "message_role" in doc:
                return [{
                    "role": doc.get("message_role"),
                    "content": doc.get("message_content", ""),
                    "timestamp": doc.get("timestamp"),
                    "index": doc.get("message_index"),
                }]
            # Legacy: multiple docs, one per message
            cursor = self.col.find({"booking_token": booking_token}).sort("message_index", 1)
            out = []
            for row in cursor:
                out.append({
                    "role": row.get("message_role"),
                    "content": row.get("message_content", ""),
                    "timestamp": row.get("timestamp"),
                    "index": row.get("message_index"),
                })
            return out
        except Exception as e:
            logger.error(f"❌ Error fetching transcript: {e}", exc_info=True)
            return []

    def get_booking_tokens_with_transcripts(self, tokens: List[str]) -> set:
        """Return set of booking_tokens that have at least one transcript (one doc or messages array)."""
        try:
            # New format: doc has "messages" with length > 0
            cursor = self.col.find(
                {"booking_token": {"$in": tokens}, "messages.0": {"$exists": True}},
                {"booking_token": 1},
            )
            out = {doc["booking_token"] for doc in cursor}
            # Legacy: docs with message_role (one doc per message)
            if len(out) < len(tokens):
                legacy = self.col.distinct("booking_token", {"booking_token": {"$in": tokens}})
                out.update(legacy)
            return out
        except Exception as e:
            logger.error(f"Error fetching transcript tokens: {e}")
            return set()

    def delete_by_booking_tokens(self, tokens: List[str]) -> int:
        """Delete transcript documents for the given booking tokens. Returns count deleted."""
        if not tokens:
            return 0
        try:
            r = self.col.delete_many({"booking_token": {"$in": tokens}})
            if r.deleted_count > 0:
                logger.info(f"[TranscriptStorage] Deleted {r.deleted_count} transcript(s) for {len(tokens)} token(s)")
            return r.deleted_count
        except Exception as e:
            logger.error(f"Error deleting transcripts by tokens: {e}")
            return 0
