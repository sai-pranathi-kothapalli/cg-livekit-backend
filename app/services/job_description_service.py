"""
Job Description Service

Handles job description CRUD operations with MongoDB.
"""

from typing import Dict, Any

from app.config import Config
from app.db.mongo import get_database
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class JobDescriptionService:
    """Service for managing job descriptions"""

    JD_KEY = "default"  # Single JD document key in MongoDB

    def __init__(self, config: Config):
        self.config = config
        self.db = get_database(config)
        self.col = self.db["job_descriptions"]

    def get_job_description(self) -> Dict[str, Any]:
        """Get interview/agent context from DB. Single 'context' field for admin-editable prompt."""
        try:
            doc = self.col.find_one({"jd_id": self.JD_KEY})
            if doc and doc.get("context") is not None:
                logger.info("[JobDescriptionService] Found job description (context) in database")
                return {"context": doc.get("context", "")}
            # Backward compatibility: if old doc has title/description but no context, return empty (agent will use fallback)
            if doc:
                return {"context": doc.get("context", "")}
            return {"context": ""}
        except Exception as e:
            logger.error(f"[JobDescriptionService] Error: {str(e)}", exc_info=True)
            return {"context": ""}

    def update_job_description(self, context: str) -> Dict[str, Any]:
        """Update interview/agent context in DB. Admin edits this in Job Description section."""
        try:
            jd_data = {
                "jd_id": self.JD_KEY,
                "context": context,
                "updated_at": get_now_ist().isoformat(),
            }
            r = self.col.update_one(
                {"jd_id": self.JD_KEY},
                {"$set": jd_data},
                upsert=True,
            )
            if r.upserted_id:
                jd_data["created_at"] = get_now_ist().isoformat()
            logger.info("[JobDescriptionService] ✅ Updated job description (context)")
            return {"context": context}
        except Exception as e:
            logger.error(f"[JobDescriptionService] Failed: {str(e)}", exc_info=True)
            raise AgentError(f"Failed to update job description: {str(e)}", "job_description")
