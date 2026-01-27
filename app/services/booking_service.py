"""
Booking Service

Handles interview booking operations with Supabase.
"""

import secrets
import time
import random
import string
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from app.config import Config
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import IST, get_now_ist, to_ist

logger = get_logger(__name__)


class BookingService:
    """Service for managing interview bookings using Supabase"""
    
    def __init__(self, config: Config):
        self.config = config
        self.supabase: Client = create_client(
            config.supabase.url,
            config.supabase.service_role_key
        )
    
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
        """
        Create a new interview booking in Supabase.
        """
        try:
            # Generate a unique token for the interview
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            
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
                "created_at": get_now_ist().isoformat()
            }
            
            result = self.supabase.table('interview_bookings').insert(booking_data).execute()
            
            if not result.data:
                raise AgentError("Failed to create booking in Supabase", "BookingService")
                
            return token
        except Exception as e:
            logger.error(f"Error creating booking: {e}")
            raise AgentError(f"Failed to create booking: {str(e)}", "BookingService")

    def get_booking(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a booking by token from Supabase.
        """
        try:
            result = self.supabase.table('interview_bookings').select("*").eq("token", token).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching booking: {e}")
            return None

    def get_all_bookings(self) -> List[Dict[str, Any]]:
        """
        Fetch all bookings from Supabase.
        """
        try:
            result = self.supabase.table('interview_bookings').select("*").execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error fetching all bookings: {e}")
            return []

    def update_booking_status(self, token: str, status: str) -> bool:
        """
        Update booking status in Supabase.
        """
        try:
            result = self.supabase.table('interview_bookings').update({"status": status}).eq("token", token).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error updating booking status: {e}")
            return False

    def upload_application_to_storage(self, file_content: bytes, filename: str) -> str:
        """
        Upload an application file to Supabase Storage and return the public URL.
        """
        try:
            # Generate a unique filename to avoid collisions
            unique_filename = f"{int(time.time())}_{filename}"
            bucket_name = "applications"
            
            # Ensure bucket exists (this might fail if already exists or no permissions)
            try:
                self.supabase.storage.create_bucket(bucket_name)
            except:
                pass
                
            # Upload file
            res = self.supabase.storage.from_(bucket_name).upload(
                path=unique_filename,
                file=file_content,
                file_options={"content-type": "application/octet-stream"}
            )
            
            # Get public URL
            public_url = self.supabase.storage.from_(bucket_name).get_public_url(unique_filename)
            return public_url
        except Exception as e:
            logger.error(f"Error uploading application to storage: {e}")
            # Fallback: if storage fails, we might just not have a URL
            return ""
