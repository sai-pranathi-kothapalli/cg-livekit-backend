"""
User Service

Handles enrolled user management operations with Supabase.
"""

from typing import Optional, Dict, Any, List
import uuid

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class UserService:
    """Service for managing enrolled users using Supabase"""

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

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
                "id": str(uuid.uuid4()),
                "name": name,
                "email": email,
                "phone": phone,
                "notes": notes,
                "status": "enrolled",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            response = self.client.table("enrolled_users").insert(user_data).execute()
            return response.data[0] if response.data else user_data
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise AgentError(f"Failed to create user: {str(e)}", "UserService")

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table("enrolled_users").select("*").eq("email", email).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table("enrolled_users").select("*").eq("id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

    def get_all_users(
        self,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get enrolled users with optional pagination. Max limit 500."""
        try:
            query = self.client.table("enrolled_users").select("*").order("created_at", desc=True)
            
            if skip is not None and skip > 0:
                query = query.range(skip, skip + (limit or 500) - 1)
            elif limit is not None:
                query = query.limit(min(limit, 500))
            
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
            return []

    def count_users(self) -> int:
        """Total count of enrolled users (for pagination)."""
        try:
            response = self.client.table("enrolled_users").select("id", count="exact").execute()
            return response.count if response.count is not None else 0
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            return 0

    def update_user(self, user_id: str, **kwargs) -> Dict[str, Any]:
        try:
            kwargs['updated_at'] = get_now_ist().isoformat()
            response = self.client.table("enrolled_users").update(kwargs).eq("id", user_id).execute()
            
            if not response.data:
                raise AgentError("Failed to update user", "UserService")
            return response.data[0]
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise AgentError(f"Failed to update user: {str(e)}", "UserService")

    def delete_user(self, user_id: str) -> bool:
        try:
            self.client.table("enrolled_users").delete().eq("id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False
