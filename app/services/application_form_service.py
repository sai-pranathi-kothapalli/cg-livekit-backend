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
        """
        try:
            result = self.supabase.table('student_application_forms').select("*").eq("student_id", user_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching form: {e}")
            return None

    def create_or_update_form(self, student_id: str, data: Dict[str, Any], status: str = 'draft') -> Dict[str, Any]:
        """
        Upsert an application form.
        """
        try:
            existing = self.get_form_by_user_id(student_id)
            form_data = {
                "student_id": student_id,
                "data": data,
                "status": status,
                "updated_at": get_now_ist().isoformat()
            }
            
            if existing:
                result = self.supabase.table('student_application_forms').update(form_data).eq("student_id", student_id).execute()
            else:
                form_data["created_at"] = get_now_ist().isoformat()
                result = self.supabase.table('student_application_forms').insert(form_data).execute()
                
            if result.data and len(result.data) > 0:
                return result.data[0]
            raise AgentError("Failed to upsert form in Supabase", "ApplicationFormService")
        except Exception as e:
            logger.error(f"Error upserting form: {e}")
            raise AgentError(f"Failed to upsert form: {str(e)}", "ApplicationFormService")
