"""
Application Form Service

Handles student application form operations with MongoDB.
"""

from typing import Optional, Dict, Any

from app.config import Config
from app.db.mongo import get_database, doc_with_id
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class ApplicationFormService:
    """Service for managing student application forms using MongoDB"""

    def __init__(self, config: Config):
        self.config = config
        self.db = get_database(config)
        self.col = self.db["student_application_forms"]

    def submit_form(self, student_id: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = {
                "student_id": student_id,
                "data": form_data,
                "status": "submitted",
                "submitted_at": get_now_ist().isoformat(),
                "created_at": get_now_ist().isoformat(),
            }
            r = self.col.insert_one(data)
            doc = self.col.find_one({"_id": r.inserted_id})
            return doc_with_id(doc)
        except Exception as e:
            logger.error(f"Error submitting form: {e}")
            raise AgentError(f"Failed to submit form: {str(e)}", "ApplicationFormService")

    def get_form_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self.col.find_one({"user_id": user_id})
            return doc_with_id(doc) if doc else None
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
            form_data = {
                "user_id": user_id,
                "status": status,
                "updated_at": get_now_ist().isoformat(),
                **data,
            }
            if existing:
                self.col.update_one({"user_id": user_id}, {"$set": form_data})
                doc = self.col.find_one({"user_id": user_id})
            else:
                form_data["created_at"] = get_now_ist().isoformat()
                if status == "submitted":
                    form_data["submitted_at"] = get_now_ist().isoformat()
                r = self.col.insert_one(form_data)
                doc = self.col.find_one({"_id": r.inserted_id})
            if not doc:
                raise AgentError("Failed to upsert form", "ApplicationFormService")
            logger.info(f"✅ Application form {'updated' if existing else 'created'} for user {user_id}")
            return doc_with_id(doc)
        except Exception as e:
            logger.error(f"Error upserting form: {e}", exc_info=True)
            raise AgentError(f"Failed to upsert form: {str(e)}", "ApplicationFormService")

    def delete_form_by_user_id(self, user_id: str) -> bool:
        """Delete application form for a user_id. Returns True if a document was deleted."""
        try:
            r = self.col.delete_many({"user_id": user_id})
            if r.deleted_count > 0:
                logger.info(f"[ApplicationFormService] Deleted form(s) for user_id={user_id}")
            return r.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting form by user_id: {e}")
            return False
