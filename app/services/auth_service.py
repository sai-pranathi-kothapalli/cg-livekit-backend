"""
Authentication Service

Handles JWT-based authentication for both admin and student users.
"""

import os
from typing import Optional, Dict, Any
from datetime import timedelta
import jwt
import bcrypt
import secrets
import string

from app.config import Config
from app.db.mongo import get_database, doc_with_id, to_object_id
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)

JWT_SECRET_KEY = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class AuthService:
    """Service for managing authentication and JWT tokens"""

    def __init__(self, config: Config):
        self.config = config
        self.db = get_database(config)
        self.students = self.db["students"]
        self.admin_users = self.db["admin_users"]
        self.jwt_secret = os.getenv("JWT_SECRET_KEY", JWT_SECRET_KEY)

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"[AuthService] Password verification error: {str(e)}")
            return False

    def generate_token(self, user_id: str, role: str, email: Optional[str] = None, username: Optional[str] = None) -> str:
        payload = {
            "user_id": user_id,
            "role": role,
            "exp": get_now_ist() + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": get_now_ist(),
        }
        if email:
            payload["email"] = email
        if username:
            payload["username"] = username
        return jwt.encode(payload, self.jwt_secret, algorithm=JWT_ALGORITHM)

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, self.jwt_secret, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            logger.warning("[AuthService] Token has expired")
            return None
        except jwt.InvalidTokenError:
            return None

    def authenticate_admin(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self.admin_users.find_one({"username": username})
            if not doc:
                logger.warning(f"[AuthService] Admin user not found: {username}")
                return None
            admin_user = doc_with_id(doc)
            password_hash = admin_user.get("password_hash")
            if not password_hash:
                return None
            if self.verify_password(password, password_hash):
                logger.info(f"[AuthService] ✅ Admin authenticated: {username}")
                return {
                    "id": admin_user.get("id"),
                    "username": admin_user.get("username"),
                    "role": "admin",
                    "created_at": admin_user.get("created_at"),
                }
            return None
        except Exception as e:
            logger.error(f"[AuthService] Authentication error: {str(e)}", exc_info=True)
            return None

    def authenticate_student(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self.students.find_one({"email": email})
            if not doc:
                logger.warning(f"[AuthService] Student not found: {email}")
                return None
            student = doc_with_id(doc)
            password_hash = student.get("password_hash")
            if not password_hash:
                return None
            if self.verify_password(password, password_hash):
                logger.info(f"[AuthService] ✅ Student authenticated: {email}")
                return {
                    "id": student.get("id"),
                    "email": student.get("email"),
                    "name": student.get("name"),
                    "phone": student.get("phone"),
                    "role": "student",
                    "created_at": student.get("created_at"),
                    "must_change_password": student.get("must_change_password", False),
                }
            return None
        except Exception as e:
            logger.error(f"[AuthService] Authentication error: {str(e)}", exc_info=True)
            return None

    def generate_temporary_password(self, length: int = 12) -> str:
        alphabet = string.ascii_letters + string.digits
        password = secrets.choice(string.ascii_lowercase) + secrets.choice(string.ascii_uppercase) + secrets.choice(string.digits)
        password += "".join(secrets.choice(alphabet) for _ in range(length - 3))
        password_list = list(password)
        secrets.SystemRandom().shuffle(password_list)
        return "".join(password_list)

    def register_student(
        self,
        email: str,
        password: str,
        name: str,
        phone: Optional[str] = None,
        must_change_password: bool = False,
    ) -> Dict[str, Any]:
        try:
            if self.students.find_one({"email": email}):
                raise AgentError("Email already registered", "auth")
            password_hash = self.hash_password(password)
            student_data = {
                "email": email,
                "password_hash": password_hash,
                "name": name,
                "phone": phone,
                "must_change_password": must_change_password,
                "created_at": get_now_ist().isoformat(),
            }
            r = self.students.insert_one(student_data)
            student = doc_with_id(self.students.find_one({"_id": r.inserted_id}))
            logger.info(f"[AuthService] ✅ Created student user: {email}")
            return {
                "id": student.get("id"),
                "email": student.get("email"),
                "name": student.get("name"),
                "phone": student.get("phone"),
                "role": "student",
                "created_at": student.get("created_at"),
                "must_change_password": must_change_password,
            }
        except AgentError:
            raise
        except Exception as e:
            logger.error(f"[AuthService] Failed to create student: {str(e)}", exc_info=True)
            raise AgentError(f"Failed to create student user: {str(e)}", "auth")

    def get_student_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get student by email. Returns dict with id, email, name, etc. (no password_hash)."""
        try:
            doc = self.students.find_one({"email": email})
            if not doc:
                return None
            student = doc_with_id(doc)
            return {
                "id": student.get("id"),
                "email": student.get("email"),
                "name": student.get("name"),
                "phone": student.get("phone"),
                "role": "student",
                "created_at": student.get("created_at"),
            }
        except Exception as e:
            logger.error(f"[AuthService] Error fetching student by email: {str(e)}")
            return None

    def get_student_by_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        try:
            oid = to_object_id(student_id)
            doc = self.students.find_one({"_id": oid} if oid else {"id": student_id})
            if not doc:
                doc = self.students.find_one({"id": student_id})
            if not doc:
                return None
            student = doc_with_id(doc)
            return {
                "id": student.get("id"),
                "email": student.get("email"),
                "name": student.get("name"),
                "phone": student.get("phone"),
                "role": "student",
                "created_at": student.get("created_at"),
            }
        except Exception as e:
            logger.error(f"[AuthService] Error fetching student: {str(e)}", exc_info=True)
            return None

    def get_admin_by_id(self, admin_id: str) -> Optional[Dict[str, Any]]:
        try:
            oid = to_object_id(admin_id)
            doc = self.admin_users.find_one({"_id": oid} if oid else {"id": admin_id})
            if not doc:
                doc = self.admin_users.find_one({"id": admin_id})
            if not doc:
                return None
            admin = doc_with_id(doc)
            return {
                "id": admin.get("id"),
                "username": admin.get("username"),
                "role": "admin",
                "created_at": admin.get("created_at"),
            }
        except Exception as e:
            logger.error(f"[AuthService] Error fetching admin: {str(e)}", exc_info=True)
            return None

    def reset_student_password(self, email: str, new_password: str) -> bool:
        """Reset student password by email (no old password check). Returns True if updated."""
        try:
            doc = self.students.find_one({"email": email})
            if not doc:
                return False
            new_password_hash = self.hash_password(new_password)
            r = self.students.update_one(
                {"email": email},
                {"$set": {"password_hash": new_password_hash, "must_change_password": False, "updated_at": get_now_ist().isoformat()}},
            )
            return r.matched_count > 0
        except Exception as e:
            logger.error(f"[AuthService] Reset password error: {str(e)}", exc_info=True)
            return False

    def change_student_password(self, email: str, old_password: str, new_password: str) -> bool:
        try:
            student = self.authenticate_student(email, old_password)
            if not student:
                return False
            new_password_hash = self.hash_password(new_password)
            r = self.students.update_one(
                {"email": email},
                {
                    "$set": {
                        "password_hash": new_password_hash,
                        "must_change_password": False,
                        "updated_at": get_now_ist().isoformat(),
                    }
                },
            )
            if r.modified_count > 0 or r.matched_count > 0:
                logger.info(f"[AuthService] ✅ Password changed for {email}")
                return True
            return False
        except Exception as e:
            logger.error(f"[AuthService] Password change error: {str(e)}", exc_info=True)
            return False
