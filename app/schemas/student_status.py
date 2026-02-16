"""
Student interview status and assignment related Pydantic schemas.
Moved from app.api.main without changing fields or validation.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.slots import SlotResponse


class AssignmentResponse(BaseModel):
    id: str
    user_id: str
    slot_id: str
    status: str
    assigned_at: str
    selected_at: Optional[str] = None
    slot: SlotResponse


class SelectSlotRequest(BaseModel):
    slot_id: str = Field(..., example="bc7d68f3-982b-4dbe-95bb-8d5621ac88cc")
    prompt: Optional[str] = Field(None, example="Focus more on Python concurrency during this round.")


class MyInterviewResponse(BaseModel):
    upcoming: List[Dict[str, Any]] = []  # All upcoming interviews (scheduled by admin)
    missed: List[Dict[str, Any]] = []  # Past interviews that were not attended/completed
    completed: List[Dict[str, Any]] = []  # Past interviews that were completed


__all__ = [
    "AssignmentResponse",
    "SelectSlotRequest",
    "MyInterviewResponse",
]

