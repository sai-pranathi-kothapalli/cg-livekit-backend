"""
Slot Service

Handles interview slot management with MongoDB.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import Config
from app.db.mongo import get_database, doc_with_id, to_object_id
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist, to_ist

logger = get_logger(__name__)


class SlotService:
    """Service for managing interview slots using MongoDB"""

    def __init__(self, config: Config):
        self.config = config
        self.db = get_database(config)
        self.col = self.db["interview_slots"]

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
            slot_data = {
                "slot_datetime": start_time_ist.isoformat(),
                "start_time": start_time_ist.isoformat(),
                "end_time": end_time_ist.isoformat(),
                "duration_minutes": duration_minutes,
                "max_bookings": max_bookings,
                "max_capacity": max_bookings,
                "current_bookings": 0,
                "is_booked": False,
                "notes": notes,
                "status": "active",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            r = self.col.insert_one(slot_data)
            doc = self.col.find_one({"_id": r.inserted_id})
            slot = doc_with_id(doc)
            slot = self._convert_slot_to_ist(slot)
            logger.info(f"[SlotService] Slot created: id={slot.get('id')}")
            return slot
        except Exception as e:
            logger.error(f"Error creating slot: {e}")
            raise AgentError(f"Failed to create slot: {str(e)}", "SlotService")

    def get_slot_by_datetime(self, slot_datetime_iso: str) -> Optional[Dict[str, Any]]:
        """Return an existing slot with the same slot_datetime (avoid duplicates)."""
        try:
            doc = self.col.find_one({"slot_datetime": slot_datetime_iso})
            if not doc:
                return None
            slot = doc_with_id(doc)
            slot = self._convert_slot_to_ist(slot)
            slot["max_capacity"] = slot.get("max_capacity") or slot.get("max_bookings")
            return slot
        except Exception as e:
            logger.error(f"Error finding slot by datetime: {e}")
            return None

    def get_slot(self, slot_id: str) -> Optional[Dict[str, Any]]:
        try:
            oid = to_object_id(slot_id)
            doc = self.col.find_one({"_id": oid} if oid else {"id": slot_id})
            if not doc:
                return None
            slot = doc_with_id(doc)
            slot = self._convert_slot_to_ist(slot)
            if not slot.get("duration_minutes") and (slot.get("start_time") and slot.get("end_time")):
                try:
                    st = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
                    et = datetime.fromisoformat(slot["end_time"].replace("Z", "+00:00"))
                    slot["duration_minutes"] = int((et - st).total_seconds() / 60)
                except Exception:
                    pass
            slot["max_capacity"] = slot.get("max_capacity") or slot.get("max_bookings")
            return slot
        except Exception as e:
            logger.error(f"Error fetching slot: {e}")
            return None

    def _convert_slot_to_ist(self, slot: Dict[str, Any]) -> Dict[str, Any]:
        for field in ["slot_datetime", "start_time", "end_time", "created_at", "updated_at"]:
            val = slot.get(field)
            if val is None:
                continue
            if isinstance(val, datetime):
                slot[field] = to_ist(val).isoformat()
            elif isinstance(val, str):
                try:
                    dt_str = val
                    if "Z" in dt_str or "+00:00" in dt_str:
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    else:
                        dt = datetime.fromisoformat(dt_str)
                    slot[field] = to_ist(dt).isoformat()
                except (ValueError, TypeError):
                    pass
        return slot

    def get_all_slots(
        self,
        status: Optional[str] = None,
        include_past: bool = False,
    ) -> List[Dict[str, Any]]:
        try:
            query = {}
            if status:
                query["status"] = status
            if not include_past:
                from datetime import timezone
                now = datetime.now(timezone.utc).isoformat()
                query["slot_datetime"] = {"$gte": now}
            cursor = self.col.find(query).sort("slot_datetime", 1)
            out = []
            for doc in cursor:
                slot = doc_with_id(doc)
                slot = self._convert_slot_to_ist(slot)
                slot["max_capacity"] = slot.get("max_capacity") or slot.get("max_bookings")
                slot["duration_minutes"] = slot.get("duration_minutes") or 45
                out.append(slot)
            return out
        except Exception as e:
            logger.error(f"Error fetching slots: {e}")
            return []

    def get_available_slots(self) -> List[Dict[str, Any]]:
        return self.get_all_slots(status="active")

    def update_slot(self, slot_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        try:
            oid = to_object_id(slot_id)
            q = {"_id": oid} if oid else {"id": slot_id}
            self.col.update_one(q, {"$set": updates})
            slot = self.get_slot(slot_id)
            if not slot:
                raise AgentError("Failed to update slot", "SlotService")
            return slot
        except Exception as e:
            logger.error(f"Error updating slot: {e}")
            raise AgentError(f"Failed to update slot: {str(e)}", "SlotService")

    def delete_slot(self, slot_id: str) -> bool:
        try:
            oid = to_object_id(slot_id)
            q = {"_id": oid} if oid else {"id": slot_id}
            self.col.delete_one(q)
            return True
        except Exception as e:
            logger.error(f"Error deleting slot: {e}")
            return False

    def update_slot_status(self, slot_id: str, is_booked: bool) -> bool:
        try:
            oid = to_object_id(slot_id)
            q = {"_id": oid} if oid else {"id": slot_id}
            r = self.col.update_one(q, {"$set": {"is_booked": is_booked}})
            return r.matched_count > 0
        except Exception as e:
            logger.error(f"Error updating slot status: {e}")
            return False

    def increment_booking_count(self, slot_id: str) -> bool:
        try:
            slot = self.get_slot(slot_id)
            if not slot:
                return False
            new_count = slot.get("current_bookings", 0) + 1
            max_bookings = slot.get("max_bookings") or slot.get("max_capacity") or 1
            is_booked = new_count >= max_bookings
            oid = to_object_id(slot_id)
            q = {"_id": oid} if oid else {"id": slot_id}
            r = self.col.update_one(
                q,
                {"$set": {"current_bookings": new_count, "is_booked": is_booked}},
            )
            return r.matched_count > 0
        except Exception as e:
            logger.error(f"Error incrementing booking count: {e}")
            return False
