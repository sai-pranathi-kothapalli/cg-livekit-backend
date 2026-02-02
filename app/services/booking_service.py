"""
Booking Service

Handles interview booking operations with MongoDB.
"""

import time
import random
import string
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.config import Config
from app.db.mongo import get_database, doc_with_id
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist, parse_datetime_safe

logger = get_logger(__name__)


class BookingService:
    """Service for managing interview bookings using MongoDB"""

    def __init__(self, config: Config):
        self.config = config
        self.db = get_database(config)
        self.col = self.db["interview_bookings"]

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
    ) -> str:
        """Create a new interview booking in MongoDB."""
        try:
            token = "".join(random.choices(string.ascii_letters + string.digits, k=32))
            booking_data = {
                "token": token,
                "name": name,
                "email": email,
                "phone": phone,
                "scheduled_at": scheduled_at.isoformat(),
                "application_text": application_text,
                "application_url": application_url,
                "slot_id": slot_id,
                "user_id": user_id,
                "assignment_id": assignment_id,
                "application_form_id": application_form_id,
                "status": "scheduled",
                "created_at": get_now_ist().isoformat(),
            }
            self.col.insert_one(booking_data)
            return token
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            raise AgentError(f"Failed to create booking: {str(e)}", "BookingService")

    def get_booking(self, token: str) -> Optional[Dict[str, Any]]:
        """Fetch a booking by token from MongoDB."""
        try:
            doc = self.col.find_one({"token": token})
            if not doc:
                return None
            booking = doc_with_id(doc)
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

    def _doc_to_booking(self, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert MongoDB document to booking dict with proper timezone handling."""
        if not doc:
            return None
        booking = doc_with_id(doc)
        if booking and booking.get("scheduled_at"):
            try:
                scheduled_at_ist = parse_datetime_safe(booking["scheduled_at"])
                booking["scheduled_at"] = scheduled_at_ist.isoformat()
            except (ValueError, TypeError):
                pass
        return booking

    def get_all_bookings(self) -> List[Dict[str, Any]]:
        """Fetch all bookings from MongoDB."""
        try:
            cursor = self.col.find({})
            out = []
            for doc in cursor:
                booking = self._doc_to_booking(doc)
                if booking:
                    out.append(booking)
            return out
        except Exception as e:
            logger.error(f"Error fetching all bookings: {e}")
            return []

    def update_booking_status(self, token: str, status: str) -> bool:
        """Update booking status in MongoDB."""
        try:
            r = self.col.update_one({"token": token}, {"$set": {"status": status}})
            return r.modified_count > 0 or r.matched_count > 0
        except Exception as e:
            logger.error(f"Error updating booking status: {e}")
            return False

    def update_booking(self, token: str, **kwargs) -> bool:
        """Update booking fields by token."""
        try:
            r = self.col.update_one({"token": token}, {"$set": kwargs})
            return r.matched_count > 0
        except Exception as e:
            logger.error(f"Error updating booking: {e}")
            return False

    def get_bookings_by_email(self, email: str) -> List[Dict[str, Any]]:
        """Get bookings matching email (case-insensitive)."""
        try:
            all_bookings = self.get_all_bookings()
            return [b for b in all_bookings if (b.get("email") or "").lower() == email.lower()]
        except Exception as e:
            logger.error(f"Error fetching bookings by email: {e}")
            return []

    def get_bookings_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        """Get bookings for a user_id."""
        try:
            return [doc_with_id(d) for d in self.col.find({"user_id": user_id})]
        except Exception as e:
            logger.error(f"Error fetching bookings by user_id: {e}")
            return []

    def delete_bookings_by_user_id(self, user_id: str) -> List[str]:
        """Delete all bookings for a user_id. Returns list of booking tokens that were deleted."""
        try:
            cursor = self.col.find({"user_id": user_id}, {"token": 1})
            tokens = [d["token"] for d in cursor if d.get("token")]
            if tokens:
                self.col.delete_many({"user_id": user_id})
                logger.info(f"[BookingService] Deleted {len(tokens)} booking(s) for user_id={user_id}")
            return tokens
        except Exception as e:
            logger.error(f"Error deleting bookings by user_id: {e}")
            return []

    def upload_application_to_storage(self, file_content: bytes, filename: str) -> str:
        """Upload an application file to MongoDB GridFS and return the file URL."""
        try:
            from gridfs import GridFS
            unique_filename = f"{int(time.time())}_{filename}"
            fs = GridFS(self.db)
            file_id = fs.put(file_content, filename=unique_filename)
            base = getattr(self.config.server, "base_url", None) or f"http://{self.config.server.host}:{self.config.server.port}"
            return f"{base}/api/files/{file_id}"
        except Exception as e:
            logger.error(f"Error uploading application to storage: {e}")
            return ""
