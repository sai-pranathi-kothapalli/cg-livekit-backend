"""
Assignment Service

Handles user-slot assignment operations with MongoDB.
"""

from typing import Optional, Dict, Any, List

from app.config import Config
from app.db.mongo import get_database, doc_with_id, to_object_id
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class AssignmentService:
    """Service for managing user-slot assignments using MongoDB"""

    def __init__(self, config: Config):
        self.config = config
        self.db = get_database(config)
        self.col = self.db["user_slot_assignments"]

    def assign_slots_to_user(self, user_id: str, slot_ids: List[str]) -> List[Dict[str, Any]]:
        try:
            created = []
            for slot_id in slot_ids:
                assignment_data = {
                    "user_id": user_id,
                    "slot_id": slot_id,
                    "status": "assigned",
                    "assigned_at": get_now_ist().isoformat(),
                }
                r = self.col.insert_one(assignment_data)
                doc = self.col.find_one({"_id": r.inserted_id})
                created.append(doc_with_id(doc))
            return created
        except Exception as e:
            logger.error(f"Error assigning slots: {e}")
            raise AgentError(f"Failed to assign slots: {str(e)}", "AssignmentService")

    def get_user_assignments(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            q = {"user_id": user_id}
            if status:
                q["status"] = status
            return [doc_with_id(d) for d in self.col.find(q)]
        except Exception as e:
            logger.error(f"Error fetching user assignments: {e}")
            return []

    def select_slot_for_user(self, user_id: str, assignment_id: str) -> bool:
        try:
            oid = to_object_id(assignment_id)
            q = {"user_id": user_id}
            if oid:
                q["_id"] = oid
            else:
                q["id"] = assignment_id
            r = self.col.update_one(
                q,
                {"$set": {"status": "selected", "selected_at": get_now_ist().isoformat()}},
            )
            return r.matched_count > 0
        except Exception as e:
            logger.error(f"Error selecting slot: {e}")
            return False

    def cancel_other_assignments(self, user_id: str, selected_assignment_id: str) -> bool:
        try:
            oid = to_object_id(selected_assignment_id)
            q = {"user_id": user_id, "status": "assigned"}
            if oid:
                q["_id"] = {"$ne": oid}
            else:
                q["id"] = {"$ne": selected_assignment_id}
            self.col.update_many(q, {"$set": {"status": "cancelled"}})
            return True
        except Exception as e:
            logger.error(f"Error cancelling other assignments: {e}")
            return False

    def delete_assignments_by_user_id(self, user_id: str) -> int:
        """Delete all slot assignments for a user_id. Returns count deleted."""
        try:
            r = self.col.delete_many({"user_id": user_id})
            if r.deleted_count > 0:
                logger.info(f"[AssignmentService] Deleted {r.deleted_count} assignment(s) for user_id={user_id}")
            return r.deleted_count
        except Exception as e:
            logger.error(f"Error deleting assignments by user_id: {e}")
            return 0
