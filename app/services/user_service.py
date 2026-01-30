"""
User Service

Handles enrolled user management operations with MongoDB.
"""

from typing import Optional, Dict, Any, List

from app.config import Config
from app.db.mongo import get_database, doc_with_id, to_object_id
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class UserService:
    """Service for managing enrolled users using MongoDB"""

    def __init__(self, config: Config):
        self.config = config
        self.db = get_database(config)
        self.col = self.db["enrolled_users"]

    def create_user(
        self,
        name: str,
        email: str,
        phone: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            now_iso = get_now_ist().isoformat()
            user_data = {
                "name": name,
                "email": email,
                "phone": phone,
                "notes": notes,
                "status": "enrolled",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            r = self.col.insert_one(user_data)
            doc = self.col.find_one({"_id": r.inserted_id})
            return doc_with_id(doc)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise AgentError(f"Failed to create user: {str(e)}", "UserService")

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self.col.find_one({"email": email})
            return doc_with_id(doc) if doc else None
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            oid = to_object_id(user_id)
            doc = self.col.find_one({"_id": oid} if oid else {"id": user_id})
            if not doc:
                doc = self.col.find_one({"id": user_id})
            return doc_with_id(doc) if doc else None
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

    def get_all_users(self) -> List[Dict[str, Any]]:
        try:
            return [doc_with_id(d) for d in self.col.find({})]
        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
            return []

    def update_user(self, user_id: str, **kwargs) -> Dict[str, Any]:
        try:
            oid = to_object_id(user_id)
            q = {"_id": oid} if oid else {"id": user_id}
            self.col.update_one(q, {"$set": kwargs})
            doc = self.col.find_one(q)
            if not doc:
                raise AgentError("Failed to update user", "UserService")
            return doc_with_id(doc)
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise AgentError(f"Failed to update user: {str(e)}", "UserService")

    def delete_user(self, user_id: str) -> bool:
        try:
            oid = to_object_id(user_id)
            q = {"_id": oid} if oid else {"id": user_id}
            self.col.delete_one(q)
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False
