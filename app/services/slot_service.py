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
from app.utils.datetime_utils import get_now_ist, to_ist, parse_datetime_safe

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
                        dt = parse_datetime_safe(dt_str)
                        slot[field] = dt.isoformat()
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
        batch: Optional[str] = None,
        location: Optional[str] = None,
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
                "batch": batch,
                "location": location,
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
            # Canonicalize input for comparison
            dt = parse_datetime_safe(slot_datetime_iso)
            response = self.client.table("slots").select("*").eq("slot_datetime", dt.isoformat()).execute()
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
            
            # Map batch/location if present (they are already DB keys but for clarity)
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

    def create_day_slots(
        self,
        date: Any,
        start_hour: int,
        start_minute: int,
        end_hour: int,
        end_minute: int,
        interval_minutes: int,
        max_capacity: int = 1,
        notes: Optional[str] = None,
        batch: Optional[str] = None,
        location: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """Generate multiple slots for a specific day."""
        from datetime import time, timedelta
        
        created_slots = []
        errors = []
        
        current_time = datetime.combine(date, time(hour=start_hour, minute=start_minute))
        end_time_boundary = datetime.combine(date, time(hour=end_hour, minute=end_minute))
        
        while current_time < end_time_boundary:
            next_slot_time = current_time + timedelta(minutes=interval_minutes)
            if next_slot_time > end_time_boundary:
                break
                
            try:
                slot = self.create_slot(
                    start_time=current_time,
                    end_time=next_slot_time,
                    max_bookings=max_capacity,
                    notes=notes,
                    duration_minutes=interval_minutes,
                    batch=batch,
                    location=location
                )
                created_slots.append(slot)
            except Exception as e:
                errors.append(f"Failed to create slot at {current_time.isoformat()}: {str(e)}")
            
            current_time = next_slot_time
            
        return created_slots, errors


    def increment_booking_count(self, slot_id: str) -> dict:
        """
        Atomically increment the booking count for a slot.

        Uses a single PostgreSQL UPDATE with a WHERE guard (via RPC) to
        guarantee there is no read-check-write race condition under concurrent
        load. PostgreSQL serialises the update at the row level, so only one
        request can win when the last seat is taken.

        Returns:
            dict: The updated slot row (id, booked_count, capacity, status).

        Raises:
            ValueError: Slot is full, doesn't exist, or status is 'full'.
            Exception: Unexpected database error.
        """
        try:
            result = self.client.rpc(
                "atomic_book_slot",
                {"p_slot_id": slot_id}
            ).execute()

            if not result.data or len(result.data) == 0:
                raise ValueError(
                    f"Slot {slot_id} is fully booked or does not exist"
                )

            logger.info(
                f"[SlotService] Atomic book slot {slot_id}: "
                f"booked_count={result.data[0].get('booked_count')}, "
                f"status={result.data[0].get('status')}"
            )
            return result.data[0]

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error atomically incrementing booking count for {slot_id}: {e}")
            raise Exception(f"Failed to book slot {slot_id}: {str(e)}")

    def decrement_booking_count(self, slot_id: str) -> dict:
        """
        Atomically release one booking from a slot (used on cancellation).

        Uses a single PostgreSQL UPDATE with a WHERE guard (via RPC).
        Sets status back to 'available' if the count drops below capacity.

        Returns:
            dict: The updated slot row.

        Raises:
            ValueError: Slot has no bookings to release or doesn't exist.
            Exception: Unexpected database error.
        """
        try:
            result = self.client.rpc(
                "atomic_release_slot",
                {"p_slot_id": slot_id}
            ).execute()

            if not result.data or len(result.data) == 0:
                raise ValueError(
                    f"Slot {slot_id} has no bookings to release or does not exist"
                )

            logger.info(
                f"[SlotService] Atomic release slot {slot_id}: "
                f"booked_count={result.data[0].get('booked_count')}, "
                f"status={result.data[0].get('status')}"
            )
            return result.data[0]

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error atomically decrementing booking count for {slot_id}: {e}")
            raise Exception(f"Failed to release slot {slot_id}: {str(e)}")

    async def create_window_slots(
        self,
        batch: str,
        location: str,
        date: str,
        window_start: str,
        window_end: str,
        interview_duration: int,
        curriculum_topics: str = None,
        capacity: int = 30,
        student_id: str = None,
        created_by: str = None
    ) -> list:
        """
        Create interview slots across a time window for a batch.
        
        Args:
            batch: "PFS-106"
            location: "vijayawada"
            date: "2026-04-07"
            window_start: "08:00"
            window_end: "20:00"
            interview_duration: 30 (minutes)
            curriculum_topics: "Python: loops, functions; MySQL: joins"
            capacity: max students per slot
        
        Returns: list of created slot records
        """
        from datetime import datetime, timedelta
        
        # Parse start and end times - Localize to IST immediately
        from app.utils.datetime_utils import to_ist
        start_dt = to_ist(datetime.strptime(f"{date} {window_start}", "%Y-%m-%d %H:%M"))
        end_dt = to_ist(datetime.strptime(f"{date} {window_end}", "%Y-%m-%d %H:%M"))

        if end_dt <= start_dt:
            raise ValueError("window_end must be after window_start")

        if interview_duration <= 0 or interview_duration > 120:
            raise ValueError("interview_duration must be between 1 and 120 minutes")

        # Calculate how many slots fit in the window
        total_minutes = int((end_dt - start_dt).total_seconds() / 60)
        slot_count = total_minutes // interview_duration

        if slot_count == 0:
            raise ValueError("Time window too short for the given interview duration")

        # Generate slot data
        slots_to_create = []
        current_time = start_dt

        import uuid
        from app.utils.datetime_utils import get_now_ist
        now_iso = get_now_ist().isoformat()

        # Fetch existing slots for this batch and date to minimize DB calls
        existing_res = self.client.table('slots').select('*').eq('batch', batch).gte('slot_datetime', start_dt.isoformat()).lte('slot_datetime', end_dt.isoformat()).execute()
        
        # Canonicalize keys (parse and refreeze ISO) to ensure match (e.g. +05:30 vs +0530)
        existing_slots_map = {}
        for s in (existing_res.data or []):
            try:
                dt = parse_datetime_safe(s['slot_datetime'])
                existing_slots_map[dt.isoformat()] = s
            except:
                existing_slots_map[s['slot_datetime']] = s

        for i in range(slot_count):
            slot_iso = current_time.isoformat()
            slot_end = current_time + timedelta(minutes=interview_duration)

            if slot_iso in existing_slots_map:
                # Slot already exists, skip creation and use existing
                logger.info(f"[SlotService] Slot already exists for batch {batch} at {slot_iso}, skipping.")
                # Update map with existing slots we found
                current_time = slot_end
                continue

            # Note: We simulate start_time and end_time for the frontend formatting, but we don't save them.
            slots_to_create.append({
                'id': str(uuid.uuid4()),
                'slot_datetime': slot_iso,
                'duration_minutes': interview_duration,
                'capacity': capacity,
                'booked_count': 0,
                'status': 'active',
                'batch': batch,
                'location': location,
                'curriculum_topics': curriculum_topics,
                'student_id': student_id,
                'created_by': created_by, # Now as UUID or None
                'created_at': now_iso,
                'updated_at': now_iso,
            })

            current_time = slot_end

        # Bulk insert only the NEW slots
        if slots_to_create:
            result = self.client.table('slots').insert(slots_to_create).execute()
            if not result.data:
                raise Exception("Failed to create slots — insert returned no data")
            new_created = [self._map_to_frontend(s) for s in result.data]
        else:
            new_created = []

        # Return all slots in window (both existing and newly created)
        final_res = self.client.table('slots').select('*').eq('batch', batch).gte('slot_datetime', start_dt.isoformat()).lte('slot_datetime', end_dt.isoformat()).order('slot_datetime').execute()
        return [self._map_to_frontend(s) for s in (final_res.data or [])]

    def get_slots_by_batch(self, batch: str) -> list:
        """
        Get all slots for a specific batch with current availability.
        Returns slots sorted by time.
        """
        result = self.client.table('slots').select(
            'id, slot_datetime, duration_minutes, capacity, booked_count, status, curriculum_topics'
        ).eq(
            'batch', batch
        ).order(
            'slot_datetime', desc=False
        ).execute()

        # Add computed 'available' count for each slot
        slots = []
        for slot in (result.data or []):
            slot['available'] = max(0, slot.get('capacity', 0) - slot.get('booked_count', 0))
            # compute start_time and end_time for the API
            slots.append(self._map_to_frontend(slot))

        return slots
