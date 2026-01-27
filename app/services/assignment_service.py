"""
Assignment Service

Handles user-slot assignment operations with Supabase.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from supabase import create_client, Client
from app.config import Config
from app.utils.logger import get_logger
pub_schema = "public"
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class AssignmentService:
    """Service for managing user-slot assignments using Supabase"""
    
    def __init__(self, config: Config):
        self.config = config
        self.supabase: Client = create_client(
            config.supabase.url,
            config.supabase.service_role_key
        )
    
    def assign_slots_to_user(
        self,
        user_id: str,
        slot_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Assign multiple slots to a user in Supabase.
        """
        try:
            created_assignments = []
            for slot_id in slot_ids:
                assignment_data = {
                    "user_id": user_id,
                    "slot_id": slot_id,
                    "status": "assigned",
                    "assigned_at": get_now_ist().isoformat()
                }
                result = self.supabase.table('user_slot_assignments').insert(assignment_data).execute()
                if result.data:
                    created_assignments.append(result.data[0])
            return created_assignments
        except Exception as e:
            logger.error(f"Error assigning slots: {e}")
            raise AgentError(f"Failed to assign slots: {str(e)}", "AssignmentService")

    def get_user_assignments(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch assignments for a user with optional status filter.
        """
        try:
            query = self.supabase.table('user_slot_assignments').select("*").eq("user_id", user_id)
            if status:
                query = query.eq("status", status)
            
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error fetching user assignments: {e}")
            return []

    def select_slot_for_user(self, user_id: str, assignment_id: str) -> bool:
        """
        Mark a specific assignment as 'selected'.
        """
        try:
            result = self.supabase.table('user_slot_assignments').update({
                "status": "selected",
                "selected_at": get_now_ist().isoformat()
            }).eq("id", assignment_id).eq("user_id", user_id).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error selecting slot for user: {e}")
            return False

    def cancel_other_assignments(self, user_id: str, selected_assignment_id: str) -> bool:
        """
        Cancel all other 'assigned' slots for a user once they select one.
        """
        try:
            # Update status to 'cancelled' for all other assignments
            result = self.supabase.table('user_slot_assignments').update({
                "status": "cancelled"
            }).eq("user_id", user_id).neq("id", selected_assignment_id).eq("status", "assigned").execute()
            
            return True
        except Exception as e:
            logger.error(f"Error cancelling other assignments: {e}")
            return False
