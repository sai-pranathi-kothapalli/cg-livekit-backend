"""
Admin Service

Handles admin authentication and user management with MongoDB.
"""

import secrets
from typing import Optional, Dict, Any

import bcrypt

from app.config import Config
from app.db.mongo import get_database, doc_with_id
from app.utils.logger import get_logger
from app.utils.datetime_utils import get_now_ist
from app.utils.exceptions import AgentError

logger = get_logger(__name__)


class AdminService:
    """Service for managing admin users and authentication"""

    def __init__(self, config: Config):
        self.config = config
        self.db = get_database(config)
        self.col = self.db["admin_users"]

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"[AdminService] Password verification error: {str(e)}")
            return False

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self.col.find_one({"username": username})
            if not doc:
                logger.warning(f"[AdminService] Admin user not found: {username}")
                return None
            admin_user = doc_with_id(doc)
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
        try:
            password_hash = self.hash_password(password)
            admin_data = {
                "username": username,
                "password_hash": password_hash,
                "created_at": get_now_ist().isoformat(),
            }
            r = self.col.insert_one(admin_data)
            doc = self.col.find_one({"_id": r.inserted_id})
            admin = doc_with_id(doc)
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
