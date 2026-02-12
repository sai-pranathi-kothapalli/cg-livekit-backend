"""
Assignment Service

Handles user-slot assignment operations with Supabase.
"""

from typing import Optional, Dict, Any, List
import uuid

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class AssignmentService:
    """Service for managing user-slot assignments using Supabase"""

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

    def assign_slots_to_user(self, user_id: str, slot_ids: List[str]) -> List[Dict[str, Any]]:
        try:
            created = []
            for slot_id in slot_ids:
                assignment_data = {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "slot_id": slot_id,
                    "status": "assigned",
                    "assigned_at": get_now_ist().isoformat(),
                }
                response = self.client.table("assignments").insert(assignment_data).execute()
                if response.data:
                    created.append(response.data[0])
            return created
        except Exception as e:
            logger.error(f"Error assigning slots: {e}")
            raise AgentError(f"Failed to assign slots: {str(e)}", "AssignmentService")

    def get_user_assignments(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            query = self.client.table("assignments").select("*").eq("user_id", user_id)
            if status:
                query = query.eq("status", status)
            response = query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching user assignments: {e}")
            return []

    def select_slot_for_user(self, user_id: str, assignment_id: str) -> bool:
        try:
            response = self.client.table("assignments").update({
                "status": "selected",
                "selected_at": get_now_ist().isoformat()
            }).eq("user_id", user_id).eq("id", assignment_id).execute()
            
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error selecting slot: {e}")
            return False

    def cancel_other_assignments(self, user_id: str, selected_assignment_id: str) -> bool:
        try:
            response = self.client.table("assignments").update({
                "status": "cancelled"
            }).eq("user_id", user_id).eq("status", "assigned").neq("id", selected_assignment_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error cancelling other assignments: {e}")
            return False

    def delete_assignments_by_user_id(self, user_id: str) -> int:
        """Delete all slot assignments for a user_id. Returns count deleted."""
        try:
            response = self.client.table("assignments").delete().eq("user_id", user_id).execute()
            count = len(response.data) if response.data else 0
            if count > 0:
                logger.info(f"[AssignmentService] Deleted {count} assignment(s) for user_id={user_id}")
            return count
        except Exception as e:
            logger.error(f"Error deleting assignments by user_id: {e}")
            return 0
