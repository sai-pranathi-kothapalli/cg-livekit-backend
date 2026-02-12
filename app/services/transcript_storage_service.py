"""
Transcript Storage Service

Saves interview transcripts to Supabase.
One Supabase row per interview: { booking_token, transcript: [...], created_at, updated_at }.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class TranscriptStorageService:
    """Service for storing interview transcripts in Supabase. One row per interview."""

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

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
        Append one message to the interview's transcript.
        Uses upsert: one row per booking_token with a transcript JSONB array.
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
            
            # Check if transcript exists
            response = self.client.table("transcripts").select("id, transcript").eq("booking_token", booking_token).execute()
            
            if response.data:
                # Append to existing transcript
                existing = response.data[0]
                transcript = existing.get("transcript", [])
                transcript.append(message_entry)
                
                self.client.table("transcripts").update({
                    "transcript": transcript,
                    "updated_at": now_iso
                }).eq("booking_token", booking_token).execute()
            else:
                # Create new transcript
                self.client.table("transcripts").insert({
                    "id": str(uuid.uuid4()),
                    "booking_token": booking_token,
                    "transcript": [message_entry],
                    "created_at": now_iso,
                    "updated_at": now_iso
                }).execute()
            
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
        """
        Set or append messages for one interview.
        If a transcript exists, appends new messages; otherwise creates one with all messages.
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
            
            # Check if transcript exists
            response = self.client.table("transcripts").select("id, transcript").eq("booking_token", booking_token).execute()
            
            if response.data:
                # Append to existing
                existing = response.data[0]
                transcript = existing.get("transcript", [])
                transcript.extend(entries)
                
                self.client.table("transcripts").update({
                    "transcript": transcript,
                    "updated_at": now_iso
                }).eq("booking_token", booking_token).execute()
            else:
                # Create new
                self.client.table("transcripts").insert({
                    "id": str(uuid.uuid4()),
                    "booking_token": booking_token,
                    "transcript": entries,
                    "created_at": now_iso,
                    "updated_at": now_iso
                }).execute()
            
            logger.info(f"✅ Saved batch of {len(entries)} transcript messages for booking {booking_token}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving transcript batch: {e}", exc_info=True)
            return False

    def get_transcript(self, booking_token: str) -> List[Dict[str, Any]]:
        """
        Return list of messages for this interview.
        """
        try:
            response = self.client.table("transcripts").select("transcript").eq("booking_token", booking_token).execute()
            
            if not response.data:
                return []
            
            transcript = response.data[0].get("transcript", [])
            
            # Normalize format
            out = []
            for m in transcript:
                out.append({
                    "role": m.get("role"),
                    "content": m.get("content", ""),
                    "timestamp": m.get("timestamp"),
                    "index": m.get("message_index"),
                })
            return out
        except Exception as e:
            logger.error(f"❌ Error fetching transcript: {e}", exc_info=True)
            return []

    def get_booking_tokens_with_transcripts(self, tokens: List[str]) -> set:
        """Return set of booking_tokens that have at least one transcript."""
        try:
            response = self.client.table("transcripts").select("booking_token").in_("booking_token", tokens).execute()
            return {row["booking_token"] for row in (response.data or [])}
        except Exception as e:
            logger.error(f"Error fetching transcript tokens: {e}")
            return set()

    def delete_by_booking_tokens(self, tokens: List[str]) -> int:
        """Delete transcript documents for the given booking tokens. Returns count deleted."""
        if not tokens:
            return 0
        try:
            response = self.client.table("transcripts").delete().in_("booking_token", tokens).execute()
            count = len(response.data) if response.data else 0
            if count > 0:
                logger.info(f"[TranscriptStorage] Deleted {count} transcript(s) for {len(tokens)} token(s)")
            return count
        except Exception as e:
            logger.error(f"Error deleting transcripts by tokens: {e}")
            return 0
