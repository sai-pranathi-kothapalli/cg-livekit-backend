"""
User Service

Handles enrolled user management operations with Supabase.
"""

from typing import Optional, Dict, Any, List
import uuid

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist

logger = get_logger(__name__)


class UserService:
    """Service for managing enrolled users using Supabase"""

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

    def create_user(
        self,
        name: str,
        email: str,
        phone: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            now_iso = get_now_ist().isoformat()
            user_data = {
                "id": str(uuid.uuid4()),
                "name": name,
                "email": email,
                "phone": phone,
                "notes": notes,
                "status": "enrolled",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            response = self.client.table("enrolled_users").insert(user_data).execute()
            return response.data[0] if response.data else user_data
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise AgentError(f"Failed to create user: {str(e)}", "UserService")

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table("enrolled_users").select("*").eq("email", email).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.table("enrolled_users").select("*").eq("id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

    def get_all_users(
        self,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get enrolled users with optional pagination. Max limit 500."""
        try:
            query = self.client.table("enrolled_users").select("*").order("created_at", desc=True)
            
            if skip is not None and skip > 0:
                query = query.range(skip, skip + (limit or 500) - 1)
            elif limit is not None:
                query = query.limit(min(limit, 500))
            
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching all users: {e}")
            return []

    def count_users(self) -> int:
        """Total count of enrolled users (for pagination)."""
        try:
            response = self.client.table("enrolled_users").select("id", count="exact").execute()
            return response.count if response.count is not None else 0
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            return 0

    def update_user(self, user_id: str, **kwargs) -> Dict[str, Any]:
        try:
            # Filter out None values to avoid overwriting with null in Supabase
            update_data = {k: v for k, v in kwargs.items() if v is not None}
            update_data['updated_at'] = get_now_ist().isoformat()
            
            response = self.client.table("enrolled_users").update(update_data).eq("id", user_id).execute()
            
            if not response.data:
                raise AgentError("Failed to update user", "UserService")
            return response.data[0]
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise AgentError(f"Failed to update user: {str(e)}", "UserService")

    def delete_user(self, user_id: str) -> bool:
        try:
            self.client.table("enrolled_users").delete().eq("id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False

    async def enroll_integration_students(self, batch: str, location: str, students: list) -> dict:
        """
        Bulk enroll students from LMS integration.
        
        Each student has: { student_id (external UUID), email, name, batch, location }
        
        Returns: { created: [ids], already_existed: [ids], failed: [{ student_id, error }] }
        
        Uses external_student_id for deduplication — if a student with this external ID
        already exists, skip them (don't create duplicate).
        """
        results = {
            "created": [],
            "already_existed": [],
            "failed": []
        }

        for student in students:
            external_id = student.get("student_id")
            email = student.get("email", "").strip().lower()
            name = student.get("name", "")

            try:
                # Check if student already exists by external_student_id
                existing = self.client.table('enrolled_users').select('id, external_student_id').eq(
                    'external_student_id', external_id
                ).execute()

                if existing.data and len(existing.data) > 0:
                    results["already_existed"].append(external_id)
                    continue

                # Also check by email (student may exist from standalone platform usage)
                existing_by_email = self.client.table('enrolled_users').select('id, external_student_id').eq(
                    'email', email
                ).execute()

                if existing_by_email.data and len(existing_by_email.data) > 0:
                    # Student exists by email but doesn't have external_student_id
                    # Link them by updating the external_student_id
                    self.client.table('enrolled_users').update({
                        'external_student_id': external_id,
                        'batch': batch,
                        'location': location,
                    }).eq('email', email).execute()

                    results["already_existed"].append(external_id)
                    continue

                # Create new student
                insert_data = {
                    'external_student_id': external_id,
                    'email': email,
                    'name': name,
                    'batch': batch,
                    'location': location,
                    'status': 'enrolled',
                }

                result = self.client.table('enrolled_users').insert(insert_data).execute()

                if result.data and len(result.data) > 0:
                    results["created"].append(external_id)
                else:
                    results["failed"].append({
                        "student_id": external_id,
                        "error": "Insert returned no data"
                    })

            except Exception as e:
                results["failed"].append({
                    "student_id": external_id,
                    "error": str(e)
                })

        return results

    def resolve_external_student_id(self, external_student_id: str) -> Optional[Dict[str, Any]]:
        """
        Given an LMS external_student_id, find our internal user record.
        Returns the full enrolled_user record or None.
        """
        try:
            result = self.client.table('enrolled_users').select('*').eq(
                'external_student_id', external_student_id
            ).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    def get_students_by_batch(self, batch: str) -> list:
        """
        Get all enrolled students for a specific batch.
        Returns list of students with external_student_id, email, name, batch, location.
        """
        try:
            result = self.client.table('enrolled_users').select(
                'external_student_id, email, name, batch, location, status, created_at'
            ).eq(
                'batch', batch
            ).order(
                'name', desc=False
            ).execute()

            return result.data or []

        except Exception as e:
            raise Exception(f"Failed to fetch students for batch {batch}: {str(e)}")
