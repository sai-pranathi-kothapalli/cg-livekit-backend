"""
Email Service

Handles sending interview confirmation emails via SMTP.
"""

from datetime import datetime
from typing import Optional, Tuple
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """Service for sending emails"""
    
    def __init__(self, config: Config):
        self.config = config
        self.enabled = bool(
            config.smtp.host and
            config.smtp.user and
            config.smtp.password
        )
    
    async def send_interview_email(
        self,
        to_email: str,
        name: str,
        interview_url: str,
        scheduled_at: datetime,
    ) -> Tuple[bool, Optional[str]]:
        """
        Send interview confirmation email.
        
        Args:
            to_email: Recipient email address
            name: Recipient name
            interview_url: Interview join URL
            scheduled_at: Scheduled interview datetime
            
        Returns:
            Tuple of (success, error_message)
        """
        if not self.enabled:
            logger.warning("[EmailService] SMTP not configured - skipping email send")
            return False, "Email service not configured"
        
        try:
            # Format date/time
            formatted_date = scheduled_at.strftime("%A, %B %d, %Y")
            formatted_time = scheduled_at.strftime("%I:%M %p")
            
            # Create email message
            message = MIMEMultipart("alternative")
            message["Subject"] = "Your Regional Rural Bank PO Interview - Join Link"
            message["From"] = f'"{self.config.smtp.from_name}" <{self.config.smtp.from_email}>'
            message["To"] = to_email
            
            # Create HTML email
            html_content = self._create_email_html(
                name, interview_url, formatted_date, formatted_time
            )
            
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            # For port 587: use STARTTLS (connect plain, then upgrade to TLS)
            # For port 465: use direct TLS/SSL connection
            # SMTP_SECURE=true means use direct TLS (port 465), false means use STARTTLS (port 587)
            use_tls = self.config.smtp.secure  # Direct TLS for port 465
            start_tls = not self.config.smtp.secure  # STARTTLS for port 587
            
            await aiosmtplib.send(
                message,
                hostname=self.config.smtp.host,
                port=self.config.smtp.port,
                use_tls=use_tls,
                start_tls=start_tls,
                username=self.config.smtp.user,
                password=self.config.smtp.password,
                timeout=30.0,  # Increased timeout to 30 seconds
            )
            
            logger.info(f"[EmailService] ✅ Email sent successfully to {to_email}")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(f"[EmailService] {error_msg}", exc_info=True)
            return False, error_msg
    
    async def send_enrollment_email(
        self,
        to_email: str,
        name: str,
        email: str,
        temporary_password: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Send enrollment email with credentials.
        
        Args:
            to_email: Recipient email address
            name: Recipient name
            email: Login email
            temporary_password: Temporary password
            
        Returns:
            Tuple of (success, error_message)
        """
        if not self.enabled:
            logger.warning("[EmailService] SMTP not configured - skipping email send")
            return False, "Email service not configured"
        
        try:
            logger.info(f"[EmailService] 📧 Preparing enrollment email for {to_email}")
            logger.debug(f"[EmailService] SMTP Config: host={self.config.smtp.host}, port={self.config.smtp.port}, user={self.config.smtp.user}")
            
            # Create email message
            message = MIMEMultipart("alternative")
            message["Subject"] = "Welcome to Sreedhar's CCE - Your Account Credentials"
            message["From"] = f'"{self.config.smtp.from_name}" <{self.config.smtp.from_email}>'
            message["To"] = to_email
            
            # Create HTML email
            html_content = self._create_enrollment_email_html(name, email, temporary_password)
            
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            use_tls = self.config.smtp.secure
            start_tls = not self.config.smtp.secure
            
            logger.info(f"[EmailService] 📧 Connecting to SMTP server...")
            
            await aiosmtplib.send(
                message,
                hostname=self.config.smtp.host,
                port=self.config.smtp.port,
                use_tls=use_tls,
                start_tls=start_tls,
                username=self.config.smtp.user,
                password=self.config.smtp.password,
                timeout=30.0,  # Increased timeout to 30 seconds
            )
            
            logger.info(f"[EmailService] ✅ Enrollment email sent successfully to {to_email}")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to send enrollment email: {str(e)}"
            logger.error(f"[EmailService] {error_msg}", exc_info=True)
            return False, error_msg
    
    def _create_enrollment_email_html(self, name: str, email: str, temporary_password: str) -> str:
        """Create HTML email content for enrollment. Login link uses PUBLIC_FRONTEND_URL or FRONTEND_URL."""
        base = (
            getattr(self.config.server, "public_frontend_url", None)
            or self.config.server.frontend_url
            or "https://interview.skillifire.com"
        )
        base = (base or "").strip().rstrip("/")
        login_url = f"{base}/login" if base else "/login"
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #002cf2 0%, #1fd5f9 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .credentials {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border: 2px solid #002cf2; }}
        .credential-row {{ margin: 15px 0; padding: 10px; background: #f0f7ff; border-radius: 4px; }}
        .credential-label {{ font-weight: bold; color: #002cf2; }}
        .credential-value {{ font-family: monospace; font-size: 16px; color: #333; margin-top: 5px; }}
        .button {{ display: inline-block; background: #002cf2; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
        .button:hover {{ background: #001bb8; }}
        .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to Sreedhar's CCE!</h1>
            <p style="margin: 0; font-size: 18px;">Your Account Has Been Created</p>
        </div>
        <div class="content">
            <p>Hi <strong>{name}</strong>,</p>
            
            <p>Your account has been successfully created. Please use the following credentials to log in:</p>
            
            <div class="credentials">
                <h2 style="margin-top: 0; color: #002cf2;">🔐 Your Login Credentials</h2>
                <div class="credential-row">
                    <div class="credential-label">Email:</div>
                    <div class="credential-value">{email}</div>
                </div>
                <div class="credential-row">
                    <div class="credential-label">Temporary Password:</div>
                    <div class="credential-value">{temporary_password}</div>
                </div>
            </div>
            
            <div class="warning">
                <strong>⚠️ Important:</strong> You will be required to change this temporary password when you first log in.
            </div>
            
            <p><strong>Next Steps:</strong></p>
            <ol>
                <li>Click the button below to go to the login page</li>
                <li>Enter your email and temporary password</li>
                <li>You will be prompted to set a new password</li>
                <li>After setting your password, you'll be taken to your dashboard</li>
                <li>Go to <strong>"My Interviews"</strong> section in your dashboard</li>
                <li>Select a flexible time slot from the available slots assigned to you</li>
            </ol>
            
            <div style="text-align: center;">
                <a href="{login_url}" class="button" style="color: #ffffff !important; background-color: #002cf2; text-decoration: none;">Login Now</a>
            </div>
            
            <div class="warning" style="margin-top: 20px;">
                <strong>📅 Important:</strong> Please choose a convenient time slot from the available slots within the next 2 days. The slots will be visible in your dashboard after login.
            </div>
            
            <div class="footer">
                <p>Best regards,<br><strong>Sreedhar's CCE Team</strong><br>RESULTS SUPER STAR</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    def _create_email_html(self, name: str, interview_url: str, formatted_date: str, formatted_time: str) -> str:
        """Create HTML email content"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #002cf2 0%, #1fd5f9 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
        .details {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .button {{ display: inline-block; background: #002cf2; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0; }}
        .button:hover {{ background: #001bb8; }}
        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
        .detail-row {{ margin: 10px 0; }}
        .detail-label {{ font-weight: bold; color: #555; }}
        .logo-text {{ font-size: 16px; font-weight: bold; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Your Interview is Scheduled!</h1>
            <p style="margin: 0; font-size: 18px;">Regional Rural Bank Probationary Officer (PO)</p>
            <div class="logo-text">Sreedhar's CCE - RESULTS SUPER STAR</div>
        </div>
        <div class="content">
            <p>Hi <strong>{name}</strong>,</p>
            
            <p>Thank you for applying for the <strong>Regional Rural Bank Probationary Officer (PO)</strong> position!</p>
            
            <div class="details">
                <h2 style="margin-top: 0; color: #002cf2;">📅 Interview Details</h2>
                <div class="detail-row">
                    <span class="detail-label">Date:</span> {formatted_date}
                </div>
                <div class="detail-row">
                    <span class="detail-label">Time:</span> {formatted_time} (IST)
                </div>
                <div class="detail-row">
                    <span class="detail-label">Position:</span> Regional Rural Bank Probationary Officer (PO)
                </div>
            </div>

            <p><strong>Your unique interview link is ready!</strong> Click the button below to join your interview at the scheduled time:</p>
            
            <div style="text-align: center;">
                <a href="{interview_url}" class="button" style="color: #ffffff !important; background-color: #002cf2; text-decoration: none;">Join Interview</a>
            </div>
            
            <p style="font-size: 14px; color: #666; margin-top: 30px;">
                <strong>Important Notes:</strong>
            </p>
            <ul style="font-size: 14px; color: #666;">
                <li>This link will be active <strong>5 minutes before</strong> your scheduled time</li>
                <li>The interview window is open for <strong>60 minutes</strong> after the scheduled time</li>
                <li>Please ensure you have a stable internet connection and a quiet environment</li>
                <li>You can test your microphone and camera before joining</li>
                <li>The interview will cover: Personal Introduction, RRB Background, Current Affairs for Banking, and Domain Knowledge</li>
            </ul>
            
            <p style="font-size: 12px; color: #999; margin-top: 20px;">
                If you have any questions or need to reschedule, please contact us at your earliest convenience.
            </p>
            
            <div class="footer">
                <p>Best regards,<br><strong>Sreedhar's CCE Team</strong><br>RESULTS SUPER STAR</p>
                <p style="margin-top: 20px;">
                    <a href="{interview_url}" style="color: #002cf2; word-break: break-all;">{interview_url}</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""

