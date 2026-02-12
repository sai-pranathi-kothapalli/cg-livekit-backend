"""
Authentication Service

Handles JWT-based authentication for both admin, manager, and student users.
"""

import os
from typing import Optional, Dict, Any
from datetime import timedelta
import jwt
import bcrypt
import secrets
import string
import uuid
from datetime import datetime

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class AuthService:
    """Service for managing authentication and JWT tokens"""

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()
        self.jwt_secret = os.getenv("JWT_SECRET_KEY")
        if not self.jwt_secret or not self.jwt_secret.strip():
            raise ValueError(
                "JWT_SECRET_KEY must be set in environment. "
                "Generate a secret (e.g. openssl rand -hex 32) and set it in .env"
            )

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

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
            # Query users table for admin or manager with username
            # Note: We support LoginRequest with username. 
            # For admin, it's username. For manager? 
            # The prompt says "enroll managers name and email id". 
            # Usually managers might login with email. 
            # But let's assume admin uses 'username' field.
            
            response = self.client.table("users").select("*").eq("username", username).execute()
            if not response.data:
                logger.warning(f"[AuthService] User not found: {username}")
                return None
                
            user = response.data[0]
            
            # Allow admin or manager to login via this flow if they have a username?
            # Or strict role check? 
            # Existing code checked 'admin_users' collection. 
            # We'll check role is 'admin' or 'manager'.
            if user.get('role') not in ['admin', 'manager']:
                return None

            password_hash = user.get("password_hash")
            if not password_hash:
                return None

            if self.verify_password(password, password_hash):
                logger.info(f"[AuthService] ✅ {user.get('role')} authenticated: {username}")
                return {
                    "id": user.get("id"),
                    "username": user.get("username"),
                    "role": user.get("role"),
                    "created_at": user.get("created_at"),
                    "email": user.get("email"),
                    "name": user.get("name")
                }
            return None
        except Exception as e:
            logger.error(f"[AuthService] Authentication error: {str(e)}", exc_info=True)
            return None

    def authenticate_student(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table("users").select("*").eq("email", email).eq("role", "student").execute()
            if not response.data:
                logger.warning(f"[AuthService] Student not found: {email}")
                return None
            
            student = response.data[0]
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
            # Check if email exists
            res = self.client.table("users").select("id").eq("email", email).execute()
            if res.data:
                raise AgentError("Email already registered", "auth")
                
            password_hash = self.hash_password(password)
            
            user_id = str(uuid.uuid4())
            student_data = {
                "id": user_id,
                "email": email,
                "password_hash": password_hash,
                "name": name,
                "phone": phone,
                "role": "student",
                "must_change_password": must_change_password,
                "created_at": get_now_ist().isoformat(),
            }
            
            self.client.table("users").insert(student_data).execute()
            
            logger.info(f"[AuthService] ✅ Created student user: {email}")
            return student_data
            
        except AgentError:
            raise
        except Exception as e:
            logger.error(f"[AuthService] Failed to create student: {str(e)}", exc_info=True)
            if "duplicate key" in str(e) or "unique constraint" in str(e):
                 raise AgentError("Email already registered", "auth")
            raise AgentError(f"Failed to create student user: {str(e)}", "auth")

    def register_manager(self, name: str, email: str) -> Dict[str, Any]:
        """Enroll a manager. Generates a temp password."""
        try:
            # Check if exists
            res = self.client.table("users").select("id").eq("email", email).execute()
            if res.data:
                raise AgentError(f"User with email {email} already exists", "auth")

            temp_password = self.generate_temporary_password()
            password_hash = self.hash_password(temp_password)
            
            user_id = str(uuid.uuid4())
            manager_data = {
                "id": user_id,
                "email": email,
                "username": email, # Use email as username for managers? Or prompt for username? Request said: "enroll mangers name and email id"
                "password_hash": password_hash,
                "name": name,
                "role": "manager",
                "must_change_password": True,
                "created_at": get_now_ist().isoformat(),
            }
            
            self.client.table("users").insert(manager_data).execute()
            logger.info(f"[AuthService] ✅ Created manager user: {email}")
            
            # Identify that we should send them an email with the password. 
            # Caller handles email sending? Or we return the password.
            # Returning the password so caller can send email.
            manager_data['temp_password'] = temp_password
            return manager_data
            
        except AgentError:
            raise
        except Exception as e:
            logger.error(f"[AuthService] Failed to register manager: {str(e)}", exc_info=True)
            raise AgentError(f"Failed to register manager: {str(e)}", "auth")

    def delete_user_by_email(self, email: str) -> bool:
        """Delete user by email."""
        try:
            r = self.client.table("users").delete().eq("email", email).execute()
            # Supabase delete returns data of deleted rows
            if r.data:
                logger.info(f"[AuthService] ✅ Deleted user account: {email}")
                return True
            return False
        except Exception as e:
            logger.error(f"[AuthService] Failed to delete user: {str(e)}", exc_info=True)
            return False
            
    def delete_student_by_email(self, email: str) -> bool:
        """Delete student user by email."""
        try:
            r = self.client.table("users").delete().eq("email", email).eq("role", "student").execute()
            if r.data:
                logger.info(f"[AuthService] ✅ Deleted student account: {email}")
                return True
            return False
        except Exception as e:
            logger.error(f"[AuthService] Failed to delete student: {str(e)}", exc_info=True)
            return False

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table("users").select("*").eq("email", email).execute()
            if not response.data:
                return None
            return response.data[0]
        except Exception as e:
            logger.error(f"[AuthService] Error fetching user by email: {str(e)}")
            return None
    def get_student_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_email(email)
        if user and user.get('role') == 'student':
            return user
        return None
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            # Validate UUID format to avoid Postgres errors for legacy IDs
            try:
                uuid.UUID(str(user_id))
            except ValueError:
                # Not a valid UUID, likely a legacy Mongo ID
                return None

            response = self.client.table("users").select("*").eq("id", user_id).execute()
            if not response.data:
                return None
            return response.data[0]
        except Exception as e:
            logger.error(f"[AuthService] Error fetching user: {str(e)}", exc_info=True)
            return None
    
    # Aliases for backward compatibility if needed, but better to use get_user_by_id and check role
    def get_student_by_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_id(student_id)
        if user and user.get('role') == 'student':
            return user
        return None

    def get_admin_by_id(self, admin_id: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_id(admin_id)
        if user and user.get('role') == 'admin':
            return user
        return None

    def reset_password(self, email: str, new_password: str) -> bool:
        """Reset password for any user (student or manager)."""
        try:
            new_password_hash = self.hash_password(new_password)
            response = self.client.table("users").update({
                "password_hash": new_password_hash,
                "must_change_password": False,
                "updated_at": get_now_ist().isoformat()
            }).eq("email", email).in_("role", ["student", "manager"]).execute()
            
            return bool(response.data)
        except Exception as e:
            logger.error(f"[AuthService] Reset password error: {str(e)}", exc_info=True)
            return False

    # Alias for backward compatibility
    def reset_student_password(self, email: str, new_password: str) -> bool:
        return self.reset_password(email, new_password)

    def change_student_password(self, email: str, old_password: str, new_password: str) -> bool:
        try:
            student = self.authenticate_student(email, old_password)
            if not student:
                return False
            new_password_hash = self.hash_password(new_password)
            
            response = self.client.table("users").update({
                "password_hash": new_password_hash,
                "must_change_password": False,
                "updated_at": get_now_ist().isoformat()
            }).eq("email", email).execute()
            
            if response.data:
                logger.info(f"[AuthService] ✅ Password changed for {email}")
                return True
            return False
        except Exception as e:
            logger.error(f"[AuthService] Password change error: {str(e)}", exc_info=True)
            return False
