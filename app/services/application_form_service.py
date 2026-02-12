"""
Application Form Service

Handles student application form operations with Supabase.
"""

from typing import Optional, Dict, Any
import uuid

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class ApplicationFormService:
    """Service for managing student application forms using Supabase"""

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

    def _map_to_frontend(self, form: Dict[str, Any]) -> Dict[str, Any]:
        """Map database fields to frontend response format by flattening form_data."""
        if not form:
            return form
        
        # Start with the top-level fields
        mapped_form = {
            "id": form.get("id"),
            "user_id": form.get("user_id"),
            "status": form.get("status"),
            "submitted_at": form.get("submitted_at"),
            "created_at": form.get("created_at"),
            "updated_at": form.get("updated_at"),
        }

        # Unpack form_data JSONB into top-level fields
        form_data = form.get("form_data", {})
        if isinstance(form_data, dict):
            for key, value in form_data.items():
                mapped_form[key] = value

        return mapped_form

    def submit_form(self, student_id: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            db_data = {
                "id": str(uuid.uuid4()),
                "user_id": student_id,
                "form_data": form_data,
                "status": "submitted",
                "submitted_at": get_now_ist().isoformat(),
                "created_at": get_now_ist().isoformat(),
                "updated_at": get_now_ist().isoformat(),
            }
            response = self.client.table("application_forms").insert(db_data).execute()
            result = response.data[0] if response.data else db_data
            return self._map_to_frontend(result)
        except Exception as e:
            logger.error(f"Error submitting form: {e}")
            raise AgentError(f"Failed to submit form: {str(e)}", "ApplicationFormService")

    def get_form_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table("application_forms").select("*").eq("user_id", user_id).execute()
            if response.data:
                return self._map_to_frontend(response.data[0])
            return None
        except Exception as e:
            logger.error(f"Error fetching form: {e}", exc_info=True)
            return None

    def create_or_update_form(
        self,
        user_id: str,
        data: Dict[str, Any],
        status: str = "submitted",
    ) -> Dict[str, Any]:
        try:
            existing = self.get_form_by_user_id(user_id)
            
            db_data = {
                "user_id": user_id,
                "status": status,
                "updated_at": get_now_ist().isoformat(),
                "form_data": data,
            }
            
            if existing:
                response = self.client.table("application_forms").update(db_data).eq("user_id", user_id).execute()
                result = response.data[0] if response.data else existing
            else:
                db_data["id"] = str(uuid.uuid4())
                db_data["created_at"] = get_now_ist().isoformat()
                if status == "submitted":
                    db_data["submitted_at"] = get_now_ist().isoformat()
                response = self.client.table("application_forms").insert(db_data).execute()
                result = response.data[0] if response.data else db_data
            
            logger.info(f"✅ Application form {'updated' if existing else 'created'} for user {user_id}")
            return self._map_to_frontend(result)
        except Exception as e:
            logger.error(f"Error upserting form: {e}", exc_info=True)
            raise AgentError(f"Failed to upsert form: {str(e)}", "ApplicationFormService")

    def delete_form_by_user_id(self, user_id: str) -> bool:
        """Delete application form for a user_id. Returns True if a document was deleted."""
        try:
            response = self.client.table("application_forms").delete().eq("user_id", user_id).execute()
            deleted = len(response.data) if response.data else 0
            if deleted > 0:
                logger.info(f"[ApplicationFormService] Deleted form(s) for user_id={user_id}")
            return deleted > 0
        except Exception as e:
            logger.error(f"Error deleting form by user_id: {e}")
            return False
