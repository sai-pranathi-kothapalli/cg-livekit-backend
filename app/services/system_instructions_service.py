"""
System Instructions Service

Handles system instructions CRUD operations with Supabase.
Replaces the old job_description_service.
"""

from typing import Dict, Any
import uuid

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class SystemInstructionsService:
    """Service for managing system instructions"""

    INSTRUCTIONS_KEY = "default"  # Single system instructions document

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

    def get_system_instructions(self) -> Dict[str, Any]:
        """Get system instructions from DB."""
        try:
            response = self.client.table("system_instructions").select("*").eq("key", self.INSTRUCTIONS_KEY).execute()
            
            if response.data:
                instructions = response.data[0].get("instructions", "")
                logger.info(f"[SystemInstructionsService] Found system instructions, length={len(instructions)}")
                return {"instructions": instructions}
            
            logger.warning(f"[SystemInstructionsService] No system instructions found; returning empty")
            return {"instructions": ""}
        except Exception as e:
            logger.error(f"[SystemInstructionsService] Error: {str(e)}", exc_info=True)
            return {"instructions": ""}

    def update_system_instructions(self, instructions: str) -> Dict[str, Any]:
        """Update system instructions in DB."""
        try:
            # Check if exists
            response = self.client.table("system_instructions").select("id").eq("key", self.INSTRUCTIONS_KEY).execute()
            
            if response.data:
                # Update existing
                self.client.table("system_instructions").update({
                    "instructions": instructions,
                    "updated_at": get_now_ist().isoformat()
                }).eq("key", self.INSTRUCTIONS_KEY).execute()
            else:
                # Insert new
                self.client.table("system_instructions").insert({
                    "id": str(uuid.uuid4()),
                    "key": self.INSTRUCTIONS_KEY,
                    "instructions": instructions,
                    "created_at": get_now_ist().isoformat(),
                    "updated_at": get_now_ist().isoformat()
                }).execute()
            
            logger.info(f"[SystemInstructionsService] ✅ Updated system instructions (length={len(instructions)})")
            return {"instructions": instructions}
        except Exception as e:
            logger.error(f"[SystemInstructionsService] Failed: {str(e)}", exc_info=True)
            raise AgentError(f"Failed to update system instructions: {str(e)}", "system_instructions")
