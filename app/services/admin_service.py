"""
Admin Service

Handles admin authentication and user management with Supabase.
Note: Most admin auth logic is now in AuthService.
This service can be deprecated or used for admin-specific operations.
"""

import secrets
from typing import Optional, Dict, Any
import uuid

import bcrypt

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.datetime_utils import get_now_ist
from app.utils.exceptions import AgentError

logger = get_logger(__name__)


class AdminService:
    """Service for managing admin users and authentication"""

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"[AdminService] Password verification error: {str(e)}")
            return False

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate admin user. Prefer using AuthService.authenticate_admin instead."""
        try:
            response = self.client.table("users").select("*").eq("username", username).eq("role", "admin").execute()
            
            if not response.data:
                logger.warning(f"[AdminService] Admin user not found: {username}")
                return None
            
            admin_user = response.data[0]
            password_hash = admin_user.get("password_hash")
            if not password_hash:
                return None
            
            if self.verify_password(password, password_hash):
                logger.info(f"[AdminService] ✅ Admin authenticated: {username}")
                return {
                    "id": admin_user.get("id"),
                    "username": admin_user.get("username"),
                    "created_at": admin_user.get("created_at"),
                }
            return None
        except Exception as e:
            logger.error(f"[AdminService] Authentication error: {str(e)}", exc_info=True)
            return None

    def create_admin_user(self, username: str, password: str) -> Dict[str, Any]:
        """Create admin user. Use this for initial setup."""
        try:
            password_hash = self.hash_password(password)
            admin_data = {
                "id": str(uuid.uuid4()),
                "username": username,
                "password_hash": password_hash,
                "role": "admin",
                "created_at": get_now_ist().isoformat(),
            }
            response = self.client.table("users").insert(admin_data).execute()
            
            admin = response.data[0] if response.data else admin_data
            logger.info(f"[AdminService] ✅ Created admin user: {username}")
            return {
                "id": admin.get("id"),
                "username": admin.get("username"),
                "created_at": admin.get("created_at"),
            }
        except Exception as e:
            logger.error(f"[AdminService] Failed to create admin: {str(e)}", exc_info=True)
            raise AgentError(f"Failed to create admin user: {str(e)}", "admin")

    def generate_token(self) -> str:
        return secrets.token_urlsafe(32)
