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
        try:
            doc = self.col.find_one({"jd_id": self.JD_KEY})
            if doc:
                logger.info("[JobDescriptionService] Found job description in database")
                return {
                    "title": doc.get("title", ""),
                    "description": doc.get("description", ""),
                    "requirements": doc.get("requirements", ""),
                    "preparation_areas": doc.get("preparation_areas", []),
                }
            return self._get_default_jd()
        except Exception as e:
            logger.error(f"[JobDescriptionService] Error: {str(e)}", exc_info=True)
            return self._get_default_jd()

    def update_job_description(
        self,
        title: str,
        description: str,
        requirements: str,
        preparation_areas: list,
    ) -> Dict[str, Any]:
        try:
            jd_data = {
                "jd_id": self.JD_KEY,
                "title": title,
                "description": description,
                "requirements": requirements,
                "preparation_areas": preparation_areas,
                "updated_at": get_now_ist().isoformat(),
            }
            r = self.col.update_one(
                {"jd_id": self.JD_KEY},
                {"$set": jd_data},
                upsert=True,
            )
            if r.upserted_id:
                jd_data["created_at"] = get_now_ist().isoformat()
            logger.info("[JobDescriptionService] ✅ Updated job description")
            return {
                "title": title,
                "description": description,
                "requirements": requirements,
                "preparation_areas": preparation_areas,
            }
        except Exception as e:
            logger.error(f"[JobDescriptionService] Failed: {str(e)}", exc_info=True)
            raise AgentError(f"Failed to update job description: {str(e)}", "job_description")

    def _get_default_jd(self) -> Dict[str, Any]:
        return {
            "title": "Regional Rural Bank Probationary Officer (PO)",
            "description": "We are conducting interviews for the Regional Rural Bank Probationary Officer (PO) position. This is an excellent opportunity to build a career in the banking sector and serve rural communities through financial inclusion and banking services.",
            "requirements": "Graduation degree from a recognized university. Knowledge of local language. Computer literacy.",
            "preparation_areas": [
                "Candidate Personal Introduction: Your background, education, and motivation",
                "Background/History of Regional Rural Bank: Understanding of RRBs, their structure and role",
                "Current Affairs for Banking: Recent developments in banking sector, RBI policies, government schemes",
                "Domain Knowledge: Banking fundamentals, operations, and financial awareness",
            ],
        }
