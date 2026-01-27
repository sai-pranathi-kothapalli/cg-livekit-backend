"""
Admin Service

Handles admin authentication and user management with Supabase.
"""

from typing import Optional, Dict, Any
import bcrypt
import secrets
from supabase import create_client, Client
from app.config import Config
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError

logger = get_logger(__name__)


class AdminService:
    """Service for managing admin users and authentication"""
    
    def __init__(self, config: Config):
        self.config = config
        self.supabase: Client = create_client(
            config.supabase.url,
            config.supabase.service_role_key
        )
    
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
            logger.error(f"[AdminService] Password verification error: {str(e)}")
            return False
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Bcrypt hash string
        """
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
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
            
            if not result.data:
                logger.warning(f"[AdminService] Admin user not found: {username}")
                return None
            
            admin_user = result.data
            password_hash = admin_user.get('password_hash')
            
            if not password_hash:
                logger.warning(f"[AdminService] No password hash for user: {username}")
                return None
            
            if self.verify_password(password, password_hash):
                logger.info(f"[AdminService] ✅ Admin authenticated: {username}")
                # Don't return password hash
                return {
                    'id': admin_user.get('id'),
                    'username': admin_user.get('username'),
                    'created_at': admin_user.get('created_at'),
                }
            else:
                logger.warning(f"[AdminService] ❌ Invalid password for: {username}")
                return None
                
        except Exception as e:
            logger.error(f"[AdminService] Authentication error: {str(e)}", exc_info=True)
            return None
    
    def create_admin_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        Create a new admin user.
        
        Args:
            username: Admin username
            password: Plain text password (will be hashed)
            
        Returns:
            Created admin user dict
            
        Raises:
            AgentError: If creation fails
        """
        try:
            password_hash = self.hash_password(password)
            
            admin_data = {
                'username': username,
                'password_hash': password_hash,
            }
            
            result = self.supabase.table('admin_users')\
                .insert(admin_data)\
                .execute()
            
            if result.data:
                logger.info(f"[AdminService] ✅ Created admin user: {username}")
                return {
                    'id': result.data[0].get('id'),
                    'username': result.data[0].get('username'),
                    'created_at': result.data[0].get('created_at'),
                }
            else:
                raise AgentError("Failed to create admin user: No data returned", "admin")
                
        except Exception as e:
            error_msg = f"Failed to create admin user: {str(e)}"
            logger.error(f"[AdminService] {error_msg}", exc_info=True)
            raise AgentError(error_msg, "admin")
    
    def generate_token(self) -> str:
        """
        Generate a simple authentication token.
        
        Returns:
            URL-safe token string
        """
        return secrets.token_urlsafe(32)

