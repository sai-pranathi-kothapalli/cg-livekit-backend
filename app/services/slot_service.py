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
from app.utils.datetime_utils import get_now_ist, to_ist, IST

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
        notes: Optional[str] = None,
        duration_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new interview slot in Supabase.
        Ensures all times are in IST timezone.
        """
        try:
            # Ensure times are in IST
            start_time_ist = to_ist(start_time)
            end_time_ist = to_ist(end_time)
            
            # Calculate duration if not provided
            if duration_minutes is None:
                duration_minutes = int((end_time_ist - start_time_ist).total_seconds() / 60)
            
            slot_data = {
                "slot_datetime": start_time_ist.isoformat(), # Keep old column for backward compatibility/constraints
                "start_time": start_time_ist.isoformat(),
                "end_time": end_time_ist.isoformat(),
                "duration_minutes": duration_minutes,  # Store duration explicitly
                "max_bookings": max_bookings,
                "current_bookings": 0,
                "is_booked": False,
                "notes": notes,
                "status": "active",
                "created_at": get_now_ist().isoformat()
            }
            
            result = self.supabase.table('interview_slots').insert(slot_data).execute()
            if result.data and len(result.data) > 0:
                created_slot = result.data[0]
                logger.info(f"[SlotService] Slot created: id={created_slot.get('id')}, duration_minutes={created_slot.get('duration_minutes')}, stored_keys={list(created_slot.keys())}")
                return created_slot
            raise AgentError("Failed to create slot in Supabase", "SlotService")
        except Exception as e:
            logger.error(f"Error creating slot: {e}")
            raise AgentError(f"Failed to create slot: {str(e)}", "SlotService")

    def get_slot(self, slot_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a slot by ID from Supabase.
        Converts datetime fields to IST timezone.
        """
        try:
            result = self.supabase.table('interview_slots').select("*").eq("id", slot_id).execute()
            if result.data and len(result.data) > 0:
                slot = result.data[0]
                logger.info(f"[SlotService] Slot retrieved from DB: id={slot_id}, duration_minutes={slot.get('duration_minutes')}, has_duration={slot.get('duration_minutes') is not None}, all_keys={list(slot.keys())}")
                # Convert datetime fields to IST
                slot = self._convert_slot_to_ist(slot)
                logger.info(f"[SlotService] Slot after conversion: duration_minutes={slot.get('duration_minutes')}")
                return slot
            return None
        except Exception as e:
            logger.error(f"Error fetching slot: {e}")
            return None
    
    def _convert_slot_to_ist(self, slot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert datetime fields in slot to IST timezone.
        Also calculates duration_minutes if missing.
        """
        datetime_fields = ['slot_datetime', 'start_time', 'end_time', 'created_at', 'updated_at']
        for field in datetime_fields:
            if slot.get(field):
                try:
                    # Parse the datetime string
                    dt_str = slot[field]
                    if isinstance(dt_str, str):
                        # Handle different datetime formats
                        if 'Z' in dt_str or '+00:00' in dt_str:
                            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                        else:
                            dt = datetime.fromisoformat(dt_str)
                        # Convert to IST
                        dt_ist = to_ist(dt)
                        # Store as ISO string with IST timezone
                        slot[field] = dt_ist.isoformat()
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not convert {field} to IST: {e}")
        
        # Calculate duration_minutes if missing
        if not slot.get('duration_minutes'):
            logger.info(f"[SlotService] duration_minutes missing for slot {slot.get('id', 'unknown')}, calculating from start_time and end_time")
            try:
                start_time_str = slot.get('start_time') or slot.get('slot_datetime')
                end_time_str = slot.get('end_time')
                if start_time_str and end_time_str:
                    # Parse times (they should already be in IST format from above)
                    if isinstance(start_time_str, str):
                        if 'Z' in start_time_str or '+00:00' in start_time_str:
                            start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                        else:
                            start_dt = datetime.fromisoformat(start_time_str)
                        start_dt = to_ist(start_dt)
                    else:
                        start_dt = start_time_str
                    
                    if isinstance(end_time_str, str):
                        if 'Z' in end_time_str or '+00:00' in end_time_str:
                            end_dt = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                        else:
                            end_dt = datetime.fromisoformat(end_time_str)
                        end_dt = to_ist(end_dt)
                    else:
                        end_dt = end_time_str
                    
                    duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
                    slot['duration_minutes'] = duration_minutes
                    logger.info(f"[SlotService] Calculated duration_minutes: {duration_minutes} for slot {slot.get('id', 'unknown')} (start={start_time_str}, end={end_time_str})")
                else:
                    logger.warning(f"[SlotService] Cannot calculate duration_minutes: start_time={start_time_str}, end_time={end_time_str}")
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Could not calculate duration_minutes for slot: {e}")
        else:
            logger.info(f"[SlotService] Slot {slot.get('id', 'unknown')} already has duration_minutes: {slot.get('duration_minutes')}")
        
        return slot

    def get_all_slots(self, status: Optional[str] = None, include_past: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all available interview slots from Supabase with optional filtering.
        Converts datetime fields to IST timezone.
        """
        try:
            # Supabase has a default limit of 1000 rows, so we need to fetch in batches
            # or use a high limit to get all slots
            query = self.supabase.table('interview_slots').select("*")
            
            # Filter by status field if provided
            # Status can be: 'active', 'inactive', 'full', 'cancelled'
            # Note: We don't filter by is_booked as that logic is handled by status + current_bookings
            if status:
                if status == "available":
                    # For "available", we'll fetch active slots and filter by capacity client-side
                    query = query.eq("status", "active")
                elif status == "booked":
                    # For "booked", fetch slots that are full or have bookings >= capacity
                    query = query.in_("status", ["full", "active"])
                else:
                    # For specific status values, filter directly
                    query = query.eq("status", status)
            
            # Remove past slots if not requested
            if not include_past:
                now = get_now_ist()
                # Filter out past slots by comparing slot_datetime
                # Note: This is done client-side after fetching to avoid timezone issues
                pass  # We'll filter after fetching
            
            # Set a high limit to get all slots (Supabase default is 1000)
            # For very large datasets, we might need pagination, but 10000 should be enough
            query = query.limit(10000)
            
            result = query.execute()
            slots = result.data if result.data else []
            
            logger.info(f"[SlotService] Fetched {len(slots)} slots from database")
            
            # Filter out past slots if not requested (client-side to avoid timezone issues)
            if not include_past:
                now = get_now_ist()
                filtered_slots = []
                for slot in slots:
                    try:
                        slot_datetime_str = slot.get('slot_datetime') or slot.get('start_time')
                        if slot_datetime_str:
                            # Parse and compare
                            if 'Z' in slot_datetime_str or '+00:00' in slot_datetime_str:
                                slot_dt = datetime.fromisoformat(slot_datetime_str.replace('Z', '+00:00'))
                            else:
                                slot_dt = datetime.fromisoformat(slot_datetime_str)
                            slot_dt = to_ist(slot_dt)
                            if slot_dt >= now:
                                filtered_slots.append(slot)
                    except (ValueError, KeyError, TypeError):
                        # If we can't parse, include it (better to show than hide)
                        filtered_slots.append(slot)
                slots = filtered_slots
                logger.info(f"[SlotService] After filtering past slots: {len(slots)} slots remain")
            
            # Additional client-side filtering for "available" and "booked" status
            if status == "available":
                # Available = active status AND not full (current_bookings < max_capacity)
                slots = [
                    slot for slot in slots 
                    if slot.get('status') == 'active' 
                    and slot.get('current_bookings', 0) < slot.get('max_capacity', 1)
                ]
                logger.info(f"[SlotService] After filtering for available: {len(slots)} slots remain")
            elif status == "booked":
                # Booked = full status OR current_bookings >= max_capacity
                slots = [
                    slot for slot in slots 
                    if slot.get('status') == 'full' 
                    or slot.get('current_bookings', 0) >= slot.get('max_capacity', 1)
                ]
                logger.info(f"[SlotService] After filtering for booked: {len(slots)} slots remain")
            
            # Convert all slots to IST
            return [self._convert_slot_to_ist(slot) for slot in slots]
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
