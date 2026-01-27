"""
Authentication Service

Handles JWT-based authentication for both admin and student users.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
import secrets
import string
from supabase import create_client, Client
from app.config import Config
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)

# JWT configuration
JWT_SECRET_KEY = "your-secret-key-change-in-production"  # Should be in env var
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class AuthService:
    """Service for managing authentication and JWT tokens"""
    
    def __init__(self, config: Config):
        self.config = config
        self.supabase: Client = create_client(
            config.supabase.url,
            config.supabase.service_role_key
        )
        # Use secret key from environment if available, otherwise use default
        import os
        self.jwt_secret = os.getenv("JWT_SECRET_KEY", JWT_SECRET_KEY)
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Bcrypt hash string
        """
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against a hash.
        
        Args:
            password: Plain text password
            password_hash: Bcrypt hash
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"[AuthService] Password verification error: {str(e)}")
            return False
    
    def generate_token(self, user_id: str, role: str, email: Optional[str] = None, username: Optional[str] = None) -> str:
        """
        Generate a JWT token for a user.
        
        Args:
            user_id: User ID
            role: User role ('admin' or 'student')
            email: User email (for students)
            username: Username (for admins)
            
        Returns:
            JWT token string
        """
        payload = {
            'user_id': user_id,
            'role': role,
            'exp': get_now_ist() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': get_now_ist(),
        }
        if email:
            payload['email'] = email
        if username:
            payload['username'] = username
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=JWT_ALGORITHM)
        return token
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("[AuthService] Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"[AuthService] Invalid token: {str(e)}")
            return None
    
    def authenticate_admin(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate an admin user.
        
        Args:
            username: Admin username
            password: Admin password
            
        Returns:
            Admin user dict if authenticated, None otherwise
        """
        try:
            result = self.supabase.table('admin_users')\
                .select('*')\
                .eq('username', username)\
                .maybe_single()\
                .execute()
            
            if not result or not result.data:
                logger.warning(f"[AuthService] Admin user not found: {username}")
                return None
            
            admin_user = result.data
            password_hash = admin_user.get('password_hash')
            
            if not password_hash:
                logger.warning(f"[AuthService] No password hash for user: {username}")
                return None
            
            if self.verify_password(password, password_hash):
                logger.info(f"[AuthService] ✅ Admin authenticated: {username}")
                return {
                    'id': admin_user.get('id'),
                    'username': admin_user.get('username'),
                    'role': 'admin',
                    'created_at': admin_user.get('created_at'),
                }
            else:
                logger.warning(f"[AuthService] ❌ Invalid password for: {username}")
                return None
                
        except Exception as e:
            logger.error(f"[AuthService] Authentication error: {str(e)}", exc_info=True)
            return None
    
    def authenticate_student(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a student user.
        
        Args:
            email: Student email
            password: Student password
            
        Returns:
            Student user dict if authenticated, None otherwise
        """
        try:
            result = self.supabase.table('students')\
                .select('*')\
                .eq('email', email)\
                .maybe_single()\
                .execute()
            
            if not result or not result.data:
                logger.warning(f"[AuthService] Student not found: {email}")
                return None
            
            student = result.data
            password_hash = student.get('password_hash')
            
            if not password_hash:
                logger.warning(f"[AuthService] No password hash for student: {email}")
                return None
            
            if self.verify_password(password, password_hash):
                logger.info(f"[AuthService] ✅ Student authenticated: {email}")
                return {
                    'id': student.get('id'),
                    'email': student.get('email'),
                    'name': student.get('name'),
                    'phone': student.get('phone'),
                    'role': 'student',
                    'created_at': student.get('created_at'),
                    'must_change_password': student.get('must_change_password', False),
                }
            else:
                logger.warning(f"[AuthService] ❌ Invalid password for: {email}")
                return None
                
        except Exception as e:
            logger.error(f"[AuthService] Authentication error: {str(e)}", exc_info=True)
            return None
    
    def generate_temporary_password(self, length: int = 12) -> str:
        """
        Generate a secure temporary password.
        
        Args:
            length: Password length (default 12)
            
        Returns:
            Temporary password string
        """
        # Use uppercase, lowercase, digits
        alphabet = string.ascii_letters + string.digits
        # Ensure at least one of each type
        password = secrets.choice(string.ascii_lowercase)
        password += secrets.choice(string.ascii_uppercase)
        password += secrets.choice(string.digits)
        # Fill the rest randomly
        password += ''.join(secrets.choice(alphabet) for _ in range(length - 3))
        # Shuffle to randomize position
        password_list = list(password)
        secrets.SystemRandom().shuffle(password_list)
        return ''.join(password_list)
    
    def register_student(self, email: str, password: str, name: str, phone: Optional[str] = None, must_change_password: bool = False) -> Dict[str, Any]:
        """
        Register a new student user.
        
        Args:
            email: Student email
            password: Plain text password (will be hashed)
            name: Student name
            phone: Student phone (optional)
            must_change_password: Whether user must change password on first login (default False)
            
        Returns:
            Created student user dict
            
        Raises:
            AgentError: If registration fails
        """
        try:
            # Check if email already exists
            existing = self.supabase.table('students')\
                .select('id')\
                .eq('email', email)\
                .maybe_single()\
                .execute()
            
            if existing and existing.data:
                raise AgentError("Email already registered", "auth")
            
            password_hash = self.hash_password(password)
            
            student_data = {
                'email': email,
                'password_hash': password_hash,
                'name': name,
                'phone': phone,
                'must_change_password': must_change_password,
            }
            
            result = self.supabase.table('students')\
                .insert(student_data)\
                .execute()
            
            if result and hasattr(result, 'data') and result.data:
                logger.info(f"[AuthService] ✅ Created student user: {email} (must_change_password={must_change_password})")
                student = result.data[0]
                return {
                    'id': student.get('id'),
                    'email': student.get('email'),
                    'name': student.get('name'),
                    'phone': student.get('phone'),
                    'role': 'student',
                    'created_at': student.get('created_at'),
                    'must_change_password': must_change_password,
                }
            else:
                raise AgentError("Failed to create student user: No data returned", "auth")
                
        except Exception as e:
            error_msg = f"Failed to create student user: {str(e)}"
            logger.error(f"[AuthService] {error_msg}", exc_info=True)
            if isinstance(e, AgentError):
                raise
            raise AgentError(error_msg, "auth")
    
    def get_student_by_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Get student by ID.
        
        Args:
            student_id: Student ID
            
        Returns:
            Student user dict or None if not found
        """
        try:
            result = self.supabase.table('students')\
                .select('*')\
                .eq('id', student_id)\
                .maybe_single()\
                .execute()
            
            if result.data:
                student = result.data
                return {
                    'id': student.get('id'),
                    'email': student.get('email'),
                    'name': student.get('name'),
                    'phone': student.get('phone'),
                    'role': 'student',
                    'created_at': student.get('created_at'),
                }
            return None
        except Exception as e:
            logger.error(f"[AuthService] Error fetching student: {str(e)}", exc_info=True)
            return None
    
    def get_admin_by_id(self, admin_id: str) -> Optional[Dict[str, Any]]:
        """
        Get admin by ID.
        
        Args:
            admin_id: Admin ID
            
        Returns:
            Admin user dict or None if not found
        """
        try:
            result = self.supabase.table('admin_users')\
                .select('*')\
                .eq('id', admin_id)\
                .maybe_single()\
                .execute()
            
            if result.data:
                admin = result.data
                return {
                    'id': admin.get('id'),
                    'username': admin.get('username'),
                    'role': 'admin',
                    'created_at': admin.get('created_at'),
                }
            return None
        except Exception as e:
            logger.error(f"[AuthService] Error fetching admin: {str(e)}", exc_info=True)
            return None
    
    def change_student_password(self, email: str, old_password: str, new_password: str) -> bool:
        """
        Change a student's password.
        
        Args:
            email: Student email
            old_password: Current password
            new_password: New password
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Authenticate with old password
            student = self.authenticate_student(email, old_password)
            if not student:
                logger.warning(f"[AuthService] Cannot change password: authentication failed for {email}")
                return False
            
            # Hash new password
            new_password_hash = self.hash_password(new_password)
            
            # Update password and clear must_change_password flag
            result = self.supabase.table('students')\
                .update({
                    'password_hash': new_password_hash,
                    'must_change_password': False,
                    'updated_at': get_now_ist().isoformat()
                })\
                .eq('email', email)\
                .execute()
            
            if result.data:
                logger.info(f"[AuthService] ✅ Password changed successfully for {email}")
                return True
            else:
                logger.error(f"[AuthService] Failed to update password for {email}")
                return False
                
        except Exception as e:
            logger.error(f"[AuthService] Password change error: {str(e)}", exc_info=True)
            return False

