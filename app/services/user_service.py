"""
User Service

Handles enrolled user management operations with Supabase.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from supabase import create_client, Client
from app.config import Config
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class UserService:
    """Service for managing enrolled users using Supabase"""
    
    def __init__(self, config: Config):
        self.config = config
        self.supabase: Client = create_client(
            config.supabase.url,
            config.supabase.service_role_key
        )
    
    def create_user(
        self,
        name: str,
        email: str,
        phone: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new enrolled user in Supabase.
        """
        try:
            user_data = {
                "name": name,
                "email": email,
                "phone": phone,
                "notes": notes,
                "created_at": get_now_ist().isoformat()
            }
            
            result = self.supabase.table('enrolled_users').insert(user_data).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            raise AgentError("Failed to create user in Supabase", "UserService")
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise AgentError(f"Failed to create user: {str(e)}", "UserService")

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a user by email from Supabase.
        """
        try:
            result = self.supabase.table('enrolled_users').select("*").eq("email", email).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a user by ID from Supabase.
        """
        try:
            result = self.supabase.table('enrolled_users').select("*").eq("id", user_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Fetch all enrolled users from Supabase.
        """
        try:
            result = self.supabase.table('enrolled_users').select("*").execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
            return []

    def update_user(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        Update a user's details in Supabase.
        """
        try:
            result = self.supabase.table('enrolled_users').update(kwargs).eq("id", user_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            raise AgentError("Failed to update user in Supabase", "UserService")
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise AgentError(f"Failed to update user: {str(e)}", "UserService")

    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user from Supabase.
        """
        try:
            result = self.supabase.table('enrolled_users').delete().eq("id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False
