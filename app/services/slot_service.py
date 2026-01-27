"""
Slot Service

Handles interview slot management with Supabase.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from supabase import create_client, Client
from app.config import Config
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class SlotService:
    """Service for managing interview slots using Supabase"""
    
    def __init__(self, config: Config):
        self.config = config
        self.supabase: Client = create_client(
            config.supabase.url,
            config.supabase.service_role_key
        )
    
    def create_slot(
        self,
        start_time: datetime,
        end_time: datetime,
        max_bookings: int = 1,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new interview slot in Supabase.
        """
        try:
            slot_data = {
                "slot_datetime": start_time.isoformat(), # Keep old column for backward compatibility/constraints
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "max_bookings": max_bookings,
                "current_bookings": 0,
                "is_booked": False,
                "notes": notes,
                "status": "active",
                "created_at": get_now_ist().isoformat()
            }
            
            result = self.supabase.table('interview_slots').insert(slot_data).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            raise AgentError("Failed to create slot in Supabase", "SlotService")
        except Exception as e:
            logger.error(f"Error creating slot: {e}")
            raise AgentError(f"Failed to create slot: {str(e)}", "SlotService")

    def get_slot(self, slot_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a slot by ID from Supabase.
        """
        try:
            result = self.supabase.table('interview_slots').select("*").eq("id", slot_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching slot: {e}")
            return None

    def get_all_slots(self, status: Optional[str] = None, include_past: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all available interview slots from Supabase with optional filtering.
        """
        try:
            query = self.supabase.table('interview_slots').select("*")
            if status == "available":
                query = query.eq("is_booked", False)
            elif status == "booked":
                query = query.eq("is_booked", True)
            
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error fetching all slots: {e}")
            return []

    def get_slots(self, status: Optional[str] = None, admin_view: bool = False) -> List[Dict[str, Any]]:
        """
        Alias for get_all_slots with slightly different params for backward compatibility.
        """
        # Mapping 'active' to available for simple compatibility
        effective_status = "available" if status == "active" else status
        return self.get_all_slots(status=effective_status)

    def get_available_slots(self) -> List[Dict[str, Any]]:
        """
        Fetch only available (not fully booked) slots.
        """
        return self.get_all_slots(status="available")

    def update_slot(self, slot_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a slot's details in Supabase.
        """
        try:
            result = self.supabase.table('interview_slots').update(updates).eq("id", slot_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            raise AgentError("Failed to update slot in Supabase", "SlotService")
        except Exception as e:
            logger.error(f"Error updating slot: {e}")
            raise AgentError(f"Failed to update slot: {str(e)}", "SlotService")

    def delete_slot(self, slot_id: str) -> bool:
        """
        Delete a slot from Supabase.
        """
        try:
            result = self.supabase.table('interview_slots').delete().eq("id", slot_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting slot: {e}")
            return False

    def update_slot_status(self, slot_id: str, is_booked: bool) -> bool:
        """
        Update slot booking status in Supabase.
        """
        try:
            result = self.supabase.table('interview_slots').update({"is_booked": is_booked}).eq("id", slot_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error updating slot status: {e}")
            return False

    def increment_booking_count(self, slot_id: str) -> bool:
        """
        Increment the booking count for a slot and mark as booked if limit reached.
        """
        try:
            slot = self.get_slot(slot_id)
            if not slot:
                return False
            
            new_count = slot.get('current_bookings', 0) + 1
            max_bookings = slot.get('max_bookings', 1)
            is_booked = new_count >= max_bookings
            
            result = self.supabase.table('interview_slots').update({
                "current_bookings": new_count,
                "is_booked": is_booked
            }).eq("id", slot_id).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error incrementing booking count: {e}")
            return False
