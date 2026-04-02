"""
OTP Service

Handles OTP generation, hashing, verification, and storage
for the password reset flow. Uses SHA-256 hashing — plain
OTPs are never stored in the database.
"""
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import Config
from app.db.supabase import get_supabase
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OTPService:
    """Handles OTP generation, hashing, and verification for password resets."""

    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 10
    MAX_ATTEMPTS = 5  # Invalidate OTP after 5 wrong attempts

    def __init__(self, config: Config):
        self.config = config
        self.client = get_supabase()

    def generate_otp(self) -> str:
        """Generate a cryptographically secure random 6-digit OTP."""
        return "".join([str(secrets.randbelow(10)) for _ in range(self.OTP_LENGTH)])

    def hash_otp(self, otp: str) -> str:
        """SHA-256 hash the OTP. Never store plain OTPs in the database."""
        return hashlib.sha256(otp.encode()).hexdigest()

    def create_otp(self, email: str) -> str:
        """
        Generate an OTP for the given email.
        Invalidates any existing unused OTPs for this email first.
        Returns the plain OTP (caller must send this via email).
        The database only stores the hash.
        """
        email = email.strip().lower()

        # Invalidate any existing unused OTPs for this email
        try:
            self.client.table("password_reset_otps").update(
                {"used": True}
            ).eq("email", email).eq("used", False).execute()
        except Exception as e:
            logger.warning(f"[OTPService] Could not invalidate old OTPs for {email}: {e}")

        # Generate OTP and store hash
        otp = self.generate_otp()
        otp_hash = self.hash_otp(otp)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=self.OTP_EXPIRY_MINUTES)
        ).isoformat()

        self.client.table("password_reset_otps").insert({
            "email": email,
            "otp_hash": otp_hash,
            "expires_at": expires_at,
            "used": False,
            "attempts": 0,
        }).execute()

        logger.info(f"[OTPService] OTP created for {email}, expires in {self.OTP_EXPIRY_MINUTES}m")
        return otp  # Return plain OTP — caller sends via email

    def verify_otp(self, email: str, otp: str) -> bool:
        """
        Verify an OTP for the given email.

        Returns:
            True if the OTP is valid.

        Raises:
            ValueError: with a user-friendly reason if verification fails.
        """
        email = email.strip().lower()

        # Find the latest unused OTP for this email
        result = self.client.table("password_reset_otps").select("*").eq(
            "email", email
        ).eq("used", False).order("created_at", desc=True).limit(1).execute()

        if not result.data:
            raise ValueError(
                "No password reset was requested for this email. "
                "Please request a new reset code first."
            )

        record = result.data[0]
        record_id = record["id"]

        # Check expiry
        expires_at_str = record["expires_at"].replace("Z", "+00:00")
        expires_at = datetime.fromisoformat(expires_at_str)
        now = datetime.now(timezone.utc)

        if now > expires_at:
            self.client.table("password_reset_otps").update(
                {"used": True}
            ).eq("id", record_id).execute()
            raise ValueError("This reset code has expired. Please request a new one.")

        # Check attempt limit before incrementing
        current_attempts = record.get("attempts", 0)
        if current_attempts >= self.MAX_ATTEMPTS:
            self.client.table("password_reset_otps").update(
                {"used": True}
            ).eq("id", record_id).execute()
            raise ValueError(
                "Too many incorrect attempts. "
                "This code has been invalidated. Please request a new one."
            )

        # Increment attempt counter
        self.client.table("password_reset_otps").update(
            {"attempts": current_attempts + 1}
        ).eq("id", record_id).execute()

        # Verify hash
        if self.hash_otp(otp.strip()) != record["otp_hash"]:
            remaining = self.MAX_ATTEMPTS - (current_attempts + 1)
            if remaining <= 0:
                self.client.table("password_reset_otps").update(
                    {"used": True}
                ).eq("id", record_id).execute()
                raise ValueError(
                    "Too many incorrect attempts. "
                    "This code has been invalidated. Please request a new one."
                )
            raise ValueError(f"Incorrect reset code. {remaining} attempt(s) remaining.")

        # OTP is valid — mark as used so it cannot be reused
        self.client.table("password_reset_otps").update(
            {"used": True}
        ).eq("id", record_id).execute()

        logger.info(f"[OTPService] OTP verified successfully for {email}")
        return True
