"""
Booking Service

Handles interview booking operations with Supabase.
"""

import time
import random
import string
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist, parse_datetime_safe

logger = get_logger(__name__)


class BookingService:
    """Service for managing interview bookings using Supabase"""

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

    def create_booking(
        self,
        name: str,
        email: str,
        scheduled_at: datetime,
        phone: Optional[str] = None,
        application_text: Optional[str] = None,
        application_url: Optional[str] = None,
        slot_id: Optional[str] = None,
        user_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        application_form_id: Optional[str] = None,
        prompt: Optional[str] = None,  # NEW: Per-interview prompt
    ) -> str:
        """Create a new interview booking in Supabase."""
        try:
            token = "".join(random.choices(string.ascii_letters + string.digits, k=32))
            booking_data = {
                "id": str(uuid.uuid4()),
                "token": token,
                "name": name,
                "email": email,
                "phone": phone,
                "scheduled_at": scheduled_at.isoformat(),
                "application_text": application_text,
                "application_url": application_url,
                "prompt": prompt,  # NEW
                "slot_id": slot_id,
                "user_id": user_id,
                "assignment_id": assignment_id,
                "application_form_id": application_form_id,
                "status": "scheduled",
                "created_at": get_now_ist().isoformat(),
            }
            self.client.table("interview_bookings").insert(booking_data).execute()
            return token
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            raise AgentError(f"Failed to create booking: {str(e)}", "BookingService")

    def get_booking(self, token: str) -> Optional[Dict[str, Any]]:
        """Fetch a booking by token from Supabase."""
        try:
            response = self.client.table("interview_bookings").select("*").eq("token", token).execute()
            if not response.data:
                return None
            booking = response.data[0]
            if booking and booking.get("scheduled_at"):
                try:
                    scheduled_at_ist = parse_datetime_safe(booking["scheduled_at"])
                    booking["scheduled_at"] = scheduled_at_ist.isoformat()
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not convert scheduled_at for booking {token}: {e}")
            return booking
        except Exception as e:
            logger.error(f"Error fetching booking: {e}")
            return None

    def _normalize_booking(self, booking: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize booking datetime fields."""
        for field in ["scheduled_at", "created_at"]:
            if booking and booking.get(field):
                try:
                    dt_ist = parse_datetime_safe(booking[field])
                    booking[field] = dt_ist.isoformat()
                except (ValueError, TypeError):
                    pass
        return booking

    def get_all_bookings(self) -> List[Dict[str, Any]]:
        """Fetch all bookings from Supabase."""
        try:
            response = self.client.table("interview_bookings").select("*").order("created_at", desc=True).execute()
            return [self._normalize_booking(b) for b in (response.data or [])]
        except Exception as e:
            logger.error(f"Error fetching all bookings: {e}")
            return []

    def get_user_bookings(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch all bookings for a specific user from Supabase."""
        try:
            response = self.client.table("interview_bookings").select("*").eq("user_id", user_id).order("scheduled_at", desc=True).execute()
            return [self._normalize_booking(b) for b in (response.data or [])]
        except Exception as e:
            logger.error(f"Error fetching user bookings for {user_id}: {e}")
            return []

    def update_booking_status(self, token: str, status: str) -> bool:
        """Update booking status in Supabase."""
        try:
            response = self.client.table("interview_bookings").update({"status": status}).eq("token", token).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating booking status: {e}")
            return False

    def update_booking(self, token: str, **kwargs) -> bool:
        """Update booking fields by token."""
        try:
            response = self.client.table("interview_bookings").update(kwargs).eq("token", token).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating booking: {e}")
            return False

    def get_bookings_by_email(self, email: str) -> List[Dict[str, Any]]:
        """Get bookings matching email (case-insensitive)."""
        try:
            response = self.client.table("interview_bookings").select("*").ilike("email", email).execute()
            return [self._normalize_booking(b) for b in (response.data or [])]
        except Exception as e:
            logger.error(f"Error fetching bookings by email: {e}")
            return []

    def get_bookings_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        """Get bookings for a user_id."""
        try:
            response = self.client.table("interview_bookings").select("*").eq("user_id", user_id).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching bookings by user_id: {e}")
            return []

    def delete_bookings_by_user_id(self, user_id: str) -> List[str]:
        """Delete all bookings for a user_id. Returns list of booking tokens that were deleted."""
        try:
            # First get the tokens
            response = self.client.table("interview_bookings").select("token").eq("user_id", user_id).execute()
            tokens = [b["token"] for b in (response.data or []) if b.get("token")]
            
            if tokens:
                self.client.table("interview_bookings").delete().eq("user_id", user_id).execute()
                logger.info(f"[BookingService] Deleted {len(tokens)} booking(s) for user_id={user_id}")
            return tokens
        except Exception as e:
            logger.error(f"Error deleting bookings by user_id: {e}")
            return []

    def upload_application_to_storage(self, file_content: bytes, filename: str) -> str:
        """Upload an application file to Supabase Storage and return the file URL."""
        try:
            unique_filename = f"{int(time.time())}_{filename}"
            
            # Upload to Supabase Storage bucket 'resumes'
            response = self.client.storage.from_("resumes").upload(
                path=unique_filename,
                file=file_content,
                file_options={"content-type": "application/pdf"}
            )
            
            # Get public URL
            public_url = self.client.storage.from_("resumes").get_public_url(unique_filename)
            return public_url
        except Exception as e:
            logger.error(f"Error uploading application to storage: {e}")
            # Fallback: return empty or raise
            raise AgentError(f"Failed to upload to Supabase Storage: {str(e)}", "BookingService")
