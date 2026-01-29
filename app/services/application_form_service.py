"""
Application Form Service

Handles student application form operations with Supabase.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from supabase import create_client, Client
from app.config import Config
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class ApplicationFormService:
    """Service for managing student application forms using Supabase"""
    
    def __init__(self, config: Config):
        self.config = config
        self.supabase: Client = create_client(
            config.supabase.url,
            config.supabase.service_role_key
        )
    
    def submit_form(
        self,
        student_id: str,
        form_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submit an application form to Supabase.
        """
        try:
            data = {
                "student_id": student_id,
                "data": form_data,
                "status": "submitted",
                "submitted_at": get_now_ist().isoformat()
            }
            result = self.supabase.table('student_application_forms').insert(data).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            raise AgentError("Failed to submit form in Supabase", "ApplicationFormService")
        except Exception as e:
            logger.error(f"Error submitting form: {e}")
            raise AgentError(f"Failed to submit form: {str(e)}", "ApplicationFormService")

    def get_form_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch application form for a user.
        
        Args:
            user_id: enrolled_users.id
        """
        try:
            result = self.supabase.table('student_application_forms')\
                .select("*")\
                .eq("user_id", user_id)\
                .execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching form: {e}", exc_info=True)
            return None

    def create_or_update_form(self, user_id: str, data: Dict[str, Any], status: str = 'submitted') -> Dict[str, Any]:
        """
        Upsert an application form.
        Stores data directly in database columns (not nested in 'data' field).
        
        Args:
            user_id: enrolled_users.id (not student_id)
            data: Dictionary with field names matching database columns
            status: Form status ('draft', 'submitted', 'verified', 'rejected')
        """
        try:
            # Check if form exists by user_id
            existing = self.get_form_by_user_id(user_id)
            
            # Prepare form data - store fields directly as columns
            form_data = {
                "user_id": user_id,
                "status": status,
                "updated_at": get_now_ist().isoformat(),
                **data  # Spread all fields directly into form_data
            }
            
            if existing:
                # Update existing form
                result = self.supabase.table('student_application_forms')\
                    .update(form_data)\
                    .eq("user_id", user_id)\
                    .execute()
            else:
                # Create new form
                form_data["created_at"] = get_now_ist().isoformat()
                if status == 'submitted':
                    form_data["submitted_at"] = get_now_ist().isoformat()
                result = self.supabase.table('student_application_forms')\
                    .insert(form_data)\
                    .execute()
                
            if result.data and len(result.data) > 0:
                logger.info(f"✅ Application form {'updated' if existing else 'created'} for user {user_id}")
                return result.data[0]
            raise AgentError("Failed to upsert form in Supabase", "ApplicationFormService")
        except Exception as e:
            logger.error(f"Error upserting form: {e}", exc_info=True)
            raise AgentError(f"Failed to upsert form: {str(e)}", "ApplicationFormService")
