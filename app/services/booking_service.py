"""
Booking Service

Handles interview booking operations with Supabase.
"""

import time
import random
import string
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger
from app.utils.exceptions import AgentError
from app.utils.datetime_utils import get_now_ist, parse_datetime_safe

logger = get_logger(__name__)


class BookingService:
    """Service for managing interview bookings using Supabase"""

    def __init__(self, config: Config, slot_service=None):
        self.config = config
        self.client = get_supabase()
        self.slot_service = slot_service

    def create_booking(
        self,
        name: str,
        email: str,
        scheduled_at: datetime,
        phone: Optional[str] = None,
        application_text: Optional[str] = None,
        application_url: Optional[str] = None,
        slot_id: Optional[str] = None,
        user_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        application_form_id: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> str:
        """Create a new interview booking with transactional guarantees."""
        token = "".join(random.choices(string.ascii_letters + string.digits, k=32))
        
        # === PRE-CHECKS ===
        if slot_id:
            try:
                slot = self.client.table('slots').select('*').eq('id', slot_id).single().execute()
                if not slot.data:
                    raise ValueError("Slot not found")
                slot_data = slot.data
                if slot_data.get('status') == 'full' or slot_data.get('booked_count', 0) >= slot_data.get('capacity', 999):
                    raise ValueError("This slot is fully booked. Please select another slot.")
            except ValueError:
                raise
            except Exception as e:
                raise Exception(f"Failed to fetch slot: {str(e)}")

            if user_id:
                try:
                    # Check existing booking for this exact slot
                    existing = self.client.table('interview_bookings').select('id').eq('user_id', user_id).eq('slot_id', slot_id).eq('status', 'scheduled').execute()
                    if existing.data and len(existing.data) > 0:
                        raise ValueError("You already have a booking for this slot.")
                        
                    # Check conflicting bookings at the same time
                    slot_datetime = slot_data.get('slot_datetime')
                    if slot_datetime:
                        conflicting = self.client.table('interview_bookings').select('id').eq('user_id', user_id).eq('status', 'scheduled').eq('scheduled_at', slot_datetime).execute()
                        if conflicting.data and len(conflicting.data) > 0:
                            raise ValueError("You already have an interview scheduled at this time. Please select a different time slot.")
                except ValueError:
                    raise
                except Exception as e:
                    logger.warning(f"Could not check existing bookings: {str(e)}")

        # === STEP 3: ATOMIC RESERVE SLOT ===
        if slot_id and self.slot_service:
            try:
                updated_slot = self.slot_service.increment_booking_count(slot_id)
                logger.info(f"Slot {slot_id} reserved for user {user_id}. Count: {updated_slot.get('booked_count')}")
            except ValueError as e:
                # Slot is full (atomic check failed)
                raise ValueError(str(e))
            except Exception as e:
                raise Exception(f"Failed to reserve slot: {str(e)}")
                
        # === STEP 4: CREATE BOOKING ===
        try:
            booking_data = {
                "id": str(uuid.uuid4()),
                "token": token,
                "name": name,
                "email": email,
                "phone": phone,
                "scheduled_at": scheduled_at.isoformat(),
                "application_text": application_text,
                "application_url": application_url,
                "prompt": prompt,
                "slot_id": slot_id,
                "user_id": user_id,
                "assignment_id": assignment_id,
                "application_form_id": application_form_id,
                "status": "scheduled",
                "created_at": get_now_ist().isoformat(),
            }
            result = self.client.table("interview_bookings").insert(booking_data).execute()
            
            if not result.data or len(result.data) == 0:
                raise Exception("Booking insert returned empty result")
                
            logger.info(f"Booking created: token={token}, user={user_id}, slot={slot_id}")
            return token
            
        except Exception as e:
            # === COMPENSATION: UNDO SLOT RESERVE ===
            if slot_id and self.slot_service:
                logger.error(
                    f"Booking creation failed for user {user_id}, slot {slot_id}: {str(e)}. "
                    f"COMPENSATING: releasing slot reservation."
                )
                try:
                    self.slot_service.decrement_booking_count(slot_id)
                    logger.info(f"Compensation successful: slot {slot_id} released.")
                except Exception as comp_error:
                    logger.critical(
                        f"COMPENSATION FAILED! Slot {slot_id} has a phantom reservation. "
                        f"Manual fix required. Original error: {str(e)}. "
                        f"Compensation error: {str(comp_error)}"
                    )
            
            raise AgentError(f"Failed to create booking: {str(e)}", "BookingService")

    def get_booking(self, token: str) -> Optional[Dict[str, Any]]:
        """Fetch a booking by token from Supabase."""
        try:
            response = self.client.table("interview_bookings").select("*").eq("token", token).execute()
            if not response.data:
                return None
            booking = response.data[0]
            if booking and booking.get("scheduled_at"):
                try:
                    scheduled_at_ist = parse_datetime_safe(booking["scheduled_at"])
                    booking["scheduled_at"] = scheduled_at_ist.isoformat()
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not convert scheduled_at for booking {token}: {e}")
            return booking
        except Exception as e:
            logger.error(f"Error fetching booking: {e}")
            return None

    def _normalize_booking(self, booking: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize booking datetime fields."""
        for field in ["scheduled_at", "created_at"]:
            if booking and booking.get(field):
                try:
                    dt_ist = parse_datetime_safe(booking[field])
                    booking[field] = dt_ist.isoformat()
                except (ValueError, TypeError):
                    pass
        return booking

    def get_all_bookings(self) -> List[Dict[str, Any]]:
        """Fetch all bookings from Supabase."""
        try:
            response = self.client.table("interview_bookings").select("*").order("created_at", desc=True).execute()
            return [self._normalize_booking(b) for b in (response.data or [])]
        except Exception as e:
            logger.error(f"Error fetching all bookings: {e}")
            return []

    def get_user_bookings(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch all bookings for a specific user from Supabase."""
        try:
            response = self.client.table("interview_bookings").select("*").eq("user_id", user_id).order("scheduled_at", desc=True).execute()
            return [self._normalize_booking(b) for b in (response.data or [])]
        except Exception as e:
            logger.error(f"Error fetching user bookings for {user_id}: {e}")
            return []

    def update_booking_status(self, token: str, status: str) -> bool:
        """Update booking status in Supabase."""
        try:
            response = self.client.table("interview_bookings").update({"status": status}).eq("token", token).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating booking status: {e}")
            return False

    def update_booking(self, token: str, **kwargs) -> bool:
        """Update booking fields by token."""
        try:
            response = self.client.table("interview_bookings").update(kwargs).eq("token", token).execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Error updating booking: {e}")
            return False

    def get_bookings_by_email(self, email: str) -> List[Dict[str, Any]]:
        """Get bookings matching email (case-insensitive)."""
        try:
            response = self.client.table("interview_bookings").select("*").ilike("email", email).execute()
            return [self._normalize_booking(b) for b in (response.data or [])]
        except Exception as e:
            logger.error(f"Error fetching bookings by email: {e}")
            return []

    def get_bookings_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        """Get bookings for a user_id."""
        try:
            response = self.client.table("interview_bookings").select("*").eq("user_id", user_id).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching bookings by user_id: {e}")
            return []

    def delete_bookings_by_user_id(self, user_id: str) -> List[str]:
        """Delete all bookings for a user_id. Returns list of booking tokens that were deleted."""
        try:
            # First get the tokens
            response = self.client.table("interview_bookings").select("token").eq("user_id", user_id).execute()
            tokens = [b["token"] for b in (response.data or []) if b.get("token")]
            
            if tokens:
                self.client.table("interview_bookings").delete().eq("user_id", user_id).execute()
                logger.info(f"[BookingService] Deleted {len(tokens)} booking(s) for user_id={user_id}")
            return tokens
        except Exception as e:
            logger.error(f"Error deleting bookings by user_id: {e}")
            return []

    def upload_application_to_storage(self, file_content: bytes, filename: str) -> str:
        """Upload an application file to Supabase Storage and return the file URL."""
        try:
            unique_filename = f"{int(time.time())}_{filename}"
            
            # Upload to Supabase Storage bucket 'resumes'
            response = self.client.storage.from_("resumes").upload(
                path=unique_filename,
                file=file_content,
                file_options={"content-type": "application/pdf"}
            )
            
            # Get public URL
            public_url = self.client.storage.from_("resumes").get_public_url(unique_filename)
            return public_url
        except Exception as e:
            logger.error(f"Error uploading application to storage: {e}")
            # Fallback: return empty or raise
            raise AgentError(f"Failed to upload to Supabase Storage: {str(e)}", "BookingService")

    def cancel_booking(self, booking_id: str, user_id: Optional[str] = None) -> dict:
        """Cancel a booking with transactional guarantees."""
        try:
            query = self.client.table('interview_bookings').select('*').eq('id', booking_id)
            if user_id:
                query = query.eq('user_id', user_id)
            result = query.single().execute()
            
            if not result.data:
                raise ValueError("Booking not found or you don't have permission to cancel it.")
                
            booking = result.data
            if booking.get('status') != 'scheduled':
                raise ValueError(
                    f"Cannot cancel booking with status '{booking.get('status')}'. "
                    f"Only 'scheduled' bookings can be cancelled."
                )
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Failed to fetch booking: {str(e)}")

        slot_id = booking.get('slot_id')

        # Step 2: Cancel the booking
        try:
            self.client.table('interview_bookings').update({
                'status': 'cancelled',
            }).eq('id', booking_id).execute()
            logger.info(f"Booking {booking_id} cancelled for slot {slot_id}")
        except Exception as e:
            raise Exception(f"Failed to cancel booking: {str(e)}")

        # Step 3: Release the slot capacity
        if slot_id and self.slot_service:
            try:
                self.slot_service.decrement_booking_count(slot_id)
                logger.info(f"Slot {slot_id} capacity released after cancellation")
            except Exception as e:
                logger.critical(
                    f"SLOT RELEASE FAILED after booking {booking_id} cancellation! "
                    f"Slot {slot_id} may have phantom reservation. "
                    f"Manual fix required. Error: {str(e)}"
                )

        return {"message": "Booking cancelled successfully", "booking_id": booking_id}

    def cancel_booking_by_token(self, token: str) -> dict:
        try:
            result = self.client.table('interview_bookings').select('*').eq('token', token).execute()
            if not result.data:
                raise ValueError("Booking not found.")
            booking = result.data[0]
            return self.cancel_booking(booking['id'])
        except Exception as e:
            raise e

    def bulk_create_bookings(
        self,
        assignments: List[Dict[str, Any]],
    ) -> dict:
        """Create multiple bookings with per-booking compensation."""
        results = {
            'successful': [],
            'failed': [],
            'total': len(assignments),
        }

        for assignment in assignments:
            try:
                token = self.create_booking(
                    name=assignment.get('name', 'Student'),
                    email=assignment['email'],
                    scheduled_at=assignment['scheduled_at'],
                    phone=assignment.get('phone', ''),
                    slot_id=assignment.get('slot_id'),
                    user_id=assignment.get('user_id'),
                    prompt=assignment.get('prompt')
                )
                results['successful'].append({
                    'user_id': assignment.get('user_id'),
                    'email': assignment['email'],
                    'booking_token': token,
                })
            except ValueError as e:
                results['failed'].append({
                    'user_id': assignment.get('user_id'),
                    'email': assignment['email'],
                    'reason': str(e),
                })
            except Exception as e:
                results['failed'].append({
                    'user_id': assignment.get('user_id'),
                    'email': assignment['email'],
                    'reason': f"System error: {str(e)}",
                })

        logger.info(
            f"Bulk booking: {len(results['successful'])} succeeded, "
            f"{len(results['failed'])} failed out of {results['total']}"
        )

        return results

    def check_slot_consistency(self, slot_id: str) -> dict:
        """Compare a slot's booked_count against actual active bookings."""
        slot = self.client.table('slots').select(
            'booked_count, capacity'
        ).eq('id', slot_id).single().execute()
        
        if not slot.data:
            return {"error": "Slot not found"}

        recorded_count = slot.data.get('booked_count', 0)

        bookings = self.client.table('interview_bookings').select(
            'id', count='exact'
        ).eq(
            'slot_id', slot_id
        ).eq(
            'status', 'scheduled'
        ).execute()

        actual_count = bookings.count if bookings.count is not None else len(bookings.data or [])

        if recorded_count != actual_count:
            logger.warning(
                f"INCONSISTENCY: Slot {slot_id} has booked_count={recorded_count} "
                f"but {actual_count} active bookings."
            )
            return {
                "slot_id": slot_id,
                "consistent": False,
                "recorded_count": recorded_count,
                "actual_count": actual_count,
                "difference": recorded_count - actual_count,
            }

        return {
            "slot_id": slot_id,
            "consistent": True,
            "count": recorded_count,
        }
