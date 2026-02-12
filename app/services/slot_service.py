"""
Slot Service

Handles interview slot management with Supabase.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist, to_ist

logger = get_logger(__name__)


class SlotService:
    """Service for managing interview slots using Supabase"""

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

    def _map_to_frontend(self, slot: Dict[str, Any]) -> Dict[str, Any]:
        """Map DB columns to frontend expected fields."""
        if not slot:
            return slot
        # Map capacity -> max_capacity
        if "capacity" in slot:
            slot["max_capacity"] = slot["capacity"]
        elif "max_capacity" not in slot:
            slot["max_capacity"] = slot.get("max_bookings", 30)
            
        # Map booked_count -> current_bookings
        if "booked_count" in slot:
            slot["current_bookings"] = slot["booked_count"]
        elif "current_bookings" not in slot:
            slot["current_bookings"] = 0
            
        # Calculate duration if missing or from start/end
        if "duration_minutes" in slot and slot["duration_minutes"] is not None:
             pass # already have it
        elif (slot.get("start_time") and slot.get("end_time")):
            try:
                st = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
                et = datetime.fromisoformat(slot["end_time"].replace("Z", "+00:00"))
                slot["duration_minutes"] = int((et - st).total_seconds() / 60)
            except Exception:
                pass
        
        # ENSURE ALL DATETIMES ARE IST STRINGS FOR FRONTEND
        # Supabase may return UTC strings even if we stored IST.
        # We convert them here to ensure frontend always sees IST.
        datetime_fields = ["slot_datetime", "start_time", "end_time", "created_at", "updated_at"]
        for field in datetime_fields:
            if field in slot and slot[field]:
                try:
                    # Parse (properly handling Z or offset) and convert to IST
                    dt_str = slot[field]
                    if isinstance(dt_str, str):
                        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                        slot[field] = to_ist(dt).isoformat()
                except (ValueError, TypeError):
                    logger.warning(f"Failed to convert field {field} to IST: {slot[field]}")

        # PROVIDE start_time AND end_time for frontend if missing
        if "slot_datetime" in slot:
            try:
                dt = datetime.fromisoformat(slot["slot_datetime"].replace("Z", "+00:00"))
                # slot["slot_datetime"] is already IST from loop above
                slot["start_time"] = dt.isoformat()
                if slot.get("duration_minutes"):
                    from datetime import timedelta
                    et = dt + timedelta(minutes=slot["duration_minutes"])
                    slot["end_time"] = et.isoformat()
            except Exception:
                pass

        return slot

    def create_slot(
        self,
        start_time: datetime,
        end_time: datetime,
        max_bookings: int = 1,
        notes: Optional[str] = None,
        duration_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            start_time_ist = to_ist(start_time)
            end_time_ist = to_ist(end_time)
            if duration_minutes is None:
                duration_minutes = int((end_time_ist - start_time_ist).total_seconds() / 60)
            
            now_iso = get_now_ist().isoformat()
            
            # Use DB column names for insert
            # REMOVED: start_time, end_time (not in Supabase schema)
            slot_data_db = {
                "id": str(uuid.uuid4()),
                "slot_datetime": start_time_ist.isoformat(),
                "duration_minutes": duration_minutes,
                "capacity": max_bookings,     # DB column: capacity
                "booked_count": 0,            # DB column: booked_count
                "status": "active",
                "notes": notes,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            
            response = self.client.table("slots").insert(slot_data_db).execute()
            created_slot = response.data[0] if response.data else slot_data_db
            
            logger.info(f"[SlotService] Slot created: id={created_slot.get('id')}")
            return self._map_to_frontend(created_slot)
            
        except Exception as e:
            logger.error(f"Error creating slot: {e}")
            raise AgentError(f"Failed to create slot: {str(e)}", "SlotService")

    def get_slot_by_datetime(self, slot_datetime_iso: str) -> Optional[Dict[str, Any]]:
        """Return an existing slot with the same slot_datetime (avoid duplicates)."""
        try:
            response = self.client.table("slots").select("*").eq("slot_datetime", slot_datetime_iso).execute()
            if not response.data:
                return None
            return self._map_to_frontend(response.data[0])
        except Exception as e:
            logger.error(f"Error finding slot by datetime: {e}")
            return None

    def get_slot(self, slot_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table("slots").select("*").eq("id", slot_id).execute()
            if not response.data:
                return None
            return self._map_to_frontend(response.data[0])
        except Exception as e:
            logger.error(f"Error fetching slot: {e}")
            return None

    def get_all_slots(
        self,
        status: Optional[str] = None,
        include_past: bool = False,
    ) -> List[Dict[str, Any]]:
        try:
            query = self.client.table("slots").select("*")
            
            if status:
                query = query.eq("status", status)
            
            if not include_past:
                from datetime import timezone
                now = datetime.now(timezone.utc).isoformat()
                query = query.gte("slot_datetime", now)
            
            query = query.order("slot_datetime", desc=False)
            response = query.execute()
            
            slots = []
            for slot in (response.data or []):
                slots.append(self._map_to_frontend(slot))
            return slots
        except Exception as e:
            logger.error(f"Error fetching slots: {e}")
            return []

    def get_available_slots(self) -> List[Dict[str, Any]]:
        return self.get_all_slots(status="active")

    def update_slot(self, slot_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Map frontend keys to DB keys if present in updates
            if "max_capacity" in updates:
                updates["capacity"] = updates.pop("max_capacity")
            if "current_bookings" in updates:
                updates["booked_count"] = updates.pop("current_bookings")
            
            # Remove keys not in schema
            for key in ["start_time", "end_time", "max_bookings", "current_bookings", "max_capacity"]:
                if key in updates:
                    del updates[key]

            updates["updated_at"] = get_now_ist().isoformat()
            response = self.client.table("slots").update(updates).eq("id", slot_id).execute()
            
            if not response.data:
                raise AgentError("Failed to update slot", "SlotService")
            return self._map_to_frontend(response.data[0])
        except Exception as e:
            logger.error(f"Error updating slot: {e}")
            raise AgentError(f"Failed to update slot: {str(e)}", "SlotService")

    def delete_slot(self, slot_id: str) -> bool:
        try:
            self.client.table("slots").delete().eq("id", slot_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting slot: {e}")
            return False

    def update_slot_status(self, slot_id: str, is_booked: bool) -> bool:
        try:
            # Note: 'is_booked' is not in schema explicitly as a boolean column? 
            # Looking at schema: status TEXT DEFAULT 'available'. 
            # Wait, create_slot used "status": "active". 
            # Previous code had "is_booked": False in dict but not in schema table create script.
            # Schema has: status TEXT.
            # Let's assume we map boolean to status if needed, 
            # OR if "status" is the only field, we update that.
            # For now, let's update status='full' if booked?
            
            status = "full" if is_booked else "active"
            response = self.client.table("slots").update({"status": status}).eq("id", slot_id).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating slot status: {e}")
            return False

    def increment_booking_count(self, slot_id: str) -> bool:
        try:
            # Get current state
            # We can't use self.get_slot because returns mapped dict
            # Need raw DB data to be safe, or just use mapped and map back
            response = self.client.table("slots").select("*").eq("id", slot_id).execute()
            if not response.data:
                return False
            
            slot_db = response.data[0]
            current_count = slot_db.get("booked_count", 0)
            capacity = slot_db.get("capacity", 1)
            
            new_count = current_count + 1
            
            updates = {
                "booked_count": new_count,
                "updated_at": get_now_ist().isoformat()
            }
            
            if new_count >= capacity:
                updates["status"] = "full"
            
            response = self.client.table("slots").update(updates).eq("id", slot_id).execute()
            
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error incrementing booking count: {e}")
            return False
