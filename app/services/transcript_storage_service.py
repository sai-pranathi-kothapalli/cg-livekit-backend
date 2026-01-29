"""
Transcript Storage Service

Saves interview transcripts to the database for evaluation purposes.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from supabase import Client
from app.config import Config
from app.utils.logger import get_logger
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class TranscriptStorageService:
    """
    Service for storing interview transcripts in the database.
    """
    
    def __init__(self, config: Config):
        self.config = config
        from supabase import create_client
        self.supabase: Client = create_client(
            config.supabase.url,
            config.supabase.service_role_key
        )
    
    def save_transcript_message(
        self,
        booking_token: str,
        room_name: str,
        role: str,
        content: str,
        message_index: int,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Save a single transcript message to the database.
        
        Args:
            booking_token: Interview booking token
            room_name: LiveKit room name (session identifier)
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            message_index: Order of message in conversation
            timestamp: Message timestamp (defaults to now)
        
        Returns:
            True if saved successfully, False otherwise
        """
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
            
            result = self.supabase.table('interview_transcripts').insert(transcript_data).execute()
            
            if result.data:
                logger.debug(f"✅ Saved transcript message {message_index} for booking {booking_token}")
                return True
            else:
                logger.warning(f"⚠️  Failed to save transcript message for booking {booking_token}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error saving transcript message: {e}", exc_info=True)
            return False
    
    def save_transcript_batch(
        self,
        booking_token: str,
        room_name: str,
        messages: List[Dict[str, Any]]
    ) -> bool:
        """
        Save multiple transcript messages in a batch.
        
        Args:
            booking_token: Interview booking token
            room_name: LiveKit room name
            messages: List of message dicts with keys: role, content, index, timestamp (optional)
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            transcript_data = []
            for msg in messages:
                timestamp = msg.get('timestamp')
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                elif timestamp is None:
                    timestamp = get_now_ist()
                
                transcript_data.append({
                    "booking_token": booking_token,
                    "room_name": room_name,
                    "message_role": msg['role'],
                    "message_content": msg['content'],
                    "message_index": msg.get('index', 0),
                    "timestamp": timestamp.isoformat(),
                })
            
            if transcript_data:
                result = self.supabase.table('interview_transcripts').insert(transcript_data).execute()
                
                if result.data:
                    logger.info(f"✅ Saved {len(transcript_data)} transcript messages for booking {booking_token}")
                    return True
                else:
                    logger.warning(f"⚠️  Failed to save transcript batch for booking {booking_token}")
                    return False
            else:
                logger.warning("⚠️  No transcript messages to save")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error saving transcript batch: {e}", exc_info=True)
            return False
    
    def get_transcript(self, booking_token: str) -> List[Dict[str, Any]]:
        """
        Retrieve full transcript for a booking.
        
        Args:
            booking_token: Interview booking token
        
        Returns:
            List of transcript messages ordered by message_index
        """
        try:
            result = self.supabase.table('interview_transcripts')\
                .select("*")\
                .eq("booking_token", booking_token)\
                .order("message_index", desc=False)\
                .execute()
            
            if result.data:
                # Format the response
                transcripts = []
                for row in result.data:
                    transcripts.append({
                        "role": row.get("message_role"),
                        "content": row.get("message_content"),
                        "timestamp": row.get("timestamp"),
                        "index": row.get("message_index"),
                    })
                return transcripts
            return []
            
        except Exception as e:
            logger.error(f"❌ Error fetching transcript: {e}", exc_info=True)
            return []
