"""
Email service for sending verification emails via SMTP.
"""
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib
from jinja2 import Template


logger = logging.getLogger(__name__)


# Email configuration from environment variables
SMTP_HOST = os.getenv("BACKEND_MAIL_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("BACKEND_MAIL_PORT", "587"))
SMTP_USER = os.getenv("BACKEND_MAIL_AUTH_USER", "")
SMTP_PASSWORD = os.getenv("BACKEND_MAIL_AUTH_PASS", "")
MAIL_FROM = os.getenv("BACKEND_MAIL_SENDER", "noreply@onedocs.ai")
MAIL_FROM_NAME = os.getenv("BACKEND_MAIL_SENDER_NAME", "OneDocs")
ENABLE_CONSOLE_LOG = os.getenv("ENABLE_EMAIL_CODE_CONSOLE", "false").lower() == "true"


# HTML Email Template
EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Doğrulama - OneDocs</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1e3a5f 0%, #1e3a5f 50%, rgba(30, 58, 95, 0.8) 100%); padding: 40px 20px; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">OneDocs</h1>
            <p style="margin: 10px 0 0 0; color: rgba(255, 255, 255, 0.7); font-size: 14px;">Hukuki Araştırma Platformu</p>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; color: #1e3a5f; font-size: 24px; font-weight: 600;">Email Adresinizi Doğrulayın</h2>

            <p style="margin: 0 0 24px 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                OneDocs'a hoş geldiniz! Hesabınızı aktifleştirmek için aşağıdaki 6 haneli doğrulama kodunu kullanın:
            </p>

            <!-- Verification Code -->
            <div style="background-color: #f7fafc; border: 2px dashed #cbd5e0; border-radius: 8px; padding: 30px; text-align: center; margin: 30px 0;">
                <div style="font-size: 42px; font-weight: 700; letter-spacing: 8px; color: #1e3a5f; font-family: 'Courier New', monospace;">
                    {{ verification_code }}
                </div>
            </div>

            <p style="margin: 24px 0 0 0; color: #718096; font-size: 14px; line-height: 1.6;">
                <strong>Önemli:</strong> Bu kod <strong>30 dakika</strong> boyunca geçerlidir.
                Bu süre içinde doğrulama işlemini tamamlamanız gerekmektedir.
            </p>

            <div style="margin-top: 30px; padding-top: 30px; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0; color: #a0aec0; font-size: 13px; line-height: 1.6;">
                    Bu e-postayı siz istemediyseniz, güvenle göz ardı edebilirsiniz.
                    Hesabınızda herhangi bir değişiklik yapılmayacaktır.
                </p>
            </div>
        </div>

        <!-- Footer -->
        <div style="background-color: #f7fafc; padding: 30px; text-align: center; border-top: 1px solid #e2e8f0;">
            <p style="margin: 0 0 10px 0; color: #718096; font-size: 13px;">
                © 2026 OneDocs. Tüm hakları saklıdır.
            </p>
            <p style="margin: 0; color: #a0aec0; font-size: 12px;">
                Bu e-posta otomatik olarak gönderilmiştir. Lütfen yanıtlamayın.
            </p>
        </div>
    </div>
</body>
</html>
"""


async def send_verification_email(email: str, verification_code: str) -> bool:
    """
    Send verification email with 6-digit code to user.

    Args:
        email: Recipient email address
        verification_code: 6-digit verification code

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Console logging for development
        if ENABLE_CONSOLE_LOG:
            logger.info("=" * 60)
            logger.info("📧 EMAIL VERIFICATION CODE (Development Mode)")
            logger.info(f"   To: {email}")
            logger.info(f"   Code: {verification_code}")
            logger.info(f"   Valid for: 30 minutes")
            logger.info("=" * 60)
            print(f"\n{'=' * 60}")
            print(f"📧 EMAIL VERIFICATION CODE (Development Mode)")
            print(f"   To: {email}")
            print(f"   Code: {verification_code}")
            print(f"   Valid for: 30 minutes")
            print(f"{'=' * 60}\n")

        # Render email template
        template = Template(EMAIL_TEMPLATE)
        html_body = template.render(verification_code=verification_code)

        # Create email message
        message = MIMEMultipart("alternative")
        message["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
        message["To"] = email
        message["Subject"] = f"OneDocs Email Doğrulama - Kodunuz: {verification_code}"

        # Add HTML part
        html_part = MIMEText(html_body, "html", "utf-8")
        message.attach(html_part)

        # Send email via SMTP
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True,
        )

        logger.info(f"✅ Verification email sent successfully to {email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send verification email to {email}: {str(e)}")
        # In development mode, even if email fails, we logged to console
        if ENABLE_CONSOLE_LOG:
            logger.warning("⚠️  Email sending failed but code was logged to console (dev mode)")
            return True  # Consider success in dev mode since code is visible in console
        return False


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """
    Generic email sending function.

    Args:
        to: Recipient email address
        subject: Email subject
        html_body: HTML email body

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Create email message
        message = MIMEMultipart("alternative")
        message["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
        message["To"] = to
        message["Subject"] = subject

        # Add HTML part
        html_part = MIMEText(html_body, "html", "utf-8")
        message.attach(html_part)

        # Send email via SMTP
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True,
        )

        logger.info(f"✅ Email sent successfully to {to}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send email to {to}: {str(e)}")
        return False
