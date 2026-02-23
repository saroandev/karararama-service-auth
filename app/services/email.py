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


# Password Reset Email Template
PASSWORD_RESET_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Şifre Sıfırlama - OneDocs</title>
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
            <h2 style="margin: 0 0 20px 0; color: #1e3a5f; font-size: 24px; font-weight: 600;">Şifre Sıfırlama Talebi</h2>

            <p style="margin: 0 0 24px 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                OneDocs hesabınız için şifre sıfırlama talebinde bulundunuz. Yeni bir şifre belirlemek için aşağıdaki butona tıklayın:
            </p>

            <!-- CTA Button -->
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ reset_url }}" style="display: inline-block; background-color: #1e3a5f; color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-size: 16px; font-weight: 600; transition: background-color 0.3s;">
                    Şifremi Sıfırla
                </a>
            </div>

            <p style="margin: 24px 0 0 0; color: #718096; font-size: 14px; line-height: 1.6; text-align: center;">
                <strong>Önemli:</strong> Bu bağlantı <strong>30 dakika</strong> boyunca geçerlidir.
                Bu süre içinde şifre sıfırlama işlemini tamamlamanız gerekmektedir.
            </p>

            <!-- Alternative Link -->
            <div style="margin-top: 30px; padding: 20px; background-color: #f7fafc; border-radius: 8px;">
                <p style="margin: 0 0 10px 0; color: #4a5568; font-size: 13px; font-weight: 600;">
                    Buton çalışmıyorsa aşağıdaki bağlantıyı kopyalayıp tarayıcınıza yapıştırın:
                </p>
                <p style="margin: 0; color: #718096; font-size: 12px; word-break: break-all;">
                    {{ reset_url }}
                </p>
            </div>

            <div style="margin-top: 30px; padding-top: 30px; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0; color: #a0aec0; font-size: 13px; line-height: 1.6;">
                    <strong>Güvenlik Uyarısı:</strong> Bu şifre sıfırlama talebini siz yapmadıysanız,
                    lütfen bu e-postayı göz ardı edin. Hesabınızda herhangi bir değişiklik yapılmayacaktır.
                    Hesabınızın güvenliğinden endişe ediyorsanız, lütfen destek ekibimizle iletişime geçin.
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


async def send_password_reset_email(email: str, reset_token: str) -> bool:
    """
    Send password reset email with reset link to user.

    Args:
        email: Recipient email address
        reset_token: Password reset token (URL-safe, 43 characters)

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get frontend URL from environment
        frontend_url = os.getenv("FRONTEND_RESET_PASSWORD_URL", "http://localhost:3000/reset-password")
        reset_url = f"{frontend_url}?token={reset_token}"

        # Console logging for development
        if ENABLE_CONSOLE_LOG:
            logger.info("=" * 60)
            logger.info("🔑 PASSWORD RESET EMAIL (Development Mode)")
            logger.info(f"   To: {email}")
            logger.info(f"   Token: {reset_token}")
            logger.info(f"   Reset URL: {reset_url}")
            logger.info(f"   Valid for: 30 minutes")
            logger.info("=" * 60)
            print(f"\n{'=' * 60}")
            print(f"🔑 PASSWORD RESET EMAIL (Development Mode)")
            print(f"   To: {email}")
            print(f"   Token: {reset_token}")
            print(f"   Reset URL: {reset_url}")
            print(f"   Valid for: 30 minutes")
            print(f"{'=' * 60}\n")

        # Render email template
        template = Template(PASSWORD_RESET_TEMPLATE)
        html_body = template.render(reset_url=reset_url)

        # Create email message
        message = MIMEMultipart("alternative")
        message["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
        message["To"] = email
        message["Subject"] = "OneDocs - Şifre Sıfırlama Talebi"

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

        logger.info(f"✅ Password reset email sent successfully to {email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send password reset email to {email}: {str(e)}")
        # In development mode, even if email fails, we logged to console
        if ENABLE_CONSOLE_LOG:
            logger.warning("⚠️  Email sending failed but reset link was logged to console (dev mode)")
            return True  # Consider success in dev mode since link is visible in console
        return False


# Role display name mapping (English role name → Turkish display name)
ROLE_DISPLAY_NAMES = {
    "owner": "Organizasyon Sahibi",
    "org-admin": "Organizasyon Yöneticisi",
    "managing-lawyer": "Yönetici Avukat",
    "lawyer": "Avukat",
    "trainee": "Stajyer Avukat",
    "admin": "Admin",
    "user": "Kullanıcı",
    "guest": "Misafir",
}

# Organization type display names
ORG_TYPE_DISPLAY_NAMES = {
    "law_firm": "Hukuk Bürosu",
    "in_house": "Şirket İçi Hukuk",
    "public": "Kamu Kurumu",
    "individual": "Bireysel",
    "other": "Diğer",
}


# Invitation Email Template
INVITATION_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Organizasyon Daveti - OneDocs</title>
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
            <h2 style="margin: 0 0 20px 0; color: #1e3a5f; font-size: 24px; font-weight: 600;">Organizasyon Davetiniz</h2>

            <p style="margin: 0 0 24px 0; color: #4a5568; font-size: 16px; line-height: 1.6;">
                <strong>{{ inviter_name }}</strong> sizi <strong>{{ organization_name }}</strong> organizasyonuna davet etti.
            </p>

            <!-- Invitation Details -->
            <div style="background-color: #f7fafc; border-left: 4px solid #1e3a5f; padding: 20px; margin: 30px 0; border-radius: 4px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #718096; font-size: 14px;">Organizasyon:</td>
                        <td style="padding: 8px 0; color: #1e3a5f; font-size: 14px; font-weight: 600;">{{ organization_name }}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #718096; font-size: 14px;">Organizasyon Türü:</td>
                        <td style="padding: 8px 0; color: #1e3a5f; font-size: 14px;">{{ organization_type }}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #718096; font-size: 14px;">Rolünüz:</td>
                        <td style="padding: 8px 0; color: #1e3a5f; font-size: 14px; font-weight: 600;">{{ role_display_name }}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #718096; font-size: 14px;">Davet Eden:</td>
                        <td style="padding: 8px 0; color: #1e3a5f; font-size: 14px;">{{ inviter_name }}</td>
                    </tr>
                </table>
            </div>

            <!-- CTA Button -->
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{ accept_url }}" style="display: inline-block; background-color: #1e3a5f; color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-size: 16px; font-weight: 600; transition: background-color 0.3s;">
                    Daveti Kabul Et
                </a>
            </div>

            <p style="margin: 24px 0 0 0; color: #718096; font-size: 14px; line-height: 1.6; text-align: center;">
                <strong>Önemli:</strong> Bu davet <strong>{{ expires_in_days }} gün</strong> boyunca geçerlidir.<br>
                Son kullanma tarihi: <strong>{{ expires_at }}</strong>
            </p>

            <div style="margin-top: 30px; padding-top: 30px; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0; color: #a0aec0; font-size: 13px; line-height: 1.6;">
                    Bu daveti siz talep etmediyseniz, güvenle göz ardı edebilirsiniz.
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


async def send_invitation_email(
    email: str,
    inviter_name: str,
    organization_name: str,
    organization_type: str,
    role: str,
    invitation_token: str,
    expires_at: str,
    expires_in_days: int = 7
) -> bool:
    """
    Send organization invitation email.

    Args:
        email: Recipient email address
        inviter_name: Name of the person sending the invitation
        organization_name: Name of the organization
        organization_type: Type of organization (law_firm, in_house, etc.)
        role: Role being assigned (org-admin, lawyer, etc.)
        invitation_token: UUID token for invitation acceptance
        expires_at: Expiration datetime as string
        expires_in_days: Number of days until expiration (default: 7)

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get frontend URL from environment or use default
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        accept_url = f"{frontend_url}/davet/{invitation_token}"

        # Get display names
        role_display_name = ROLE_DISPLAY_NAMES.get(role, role.title())
        org_type_display = ORG_TYPE_DISPLAY_NAMES.get(organization_type, organization_type.replace("_", " ").title())

        # Console logging for development
        if ENABLE_CONSOLE_LOG:
            logger.info("=" * 60)
            logger.info("📧 INVITATION EMAIL (Development Mode)")
            logger.info(f"   To: {email}")
            logger.info(f"   From: {inviter_name}")
            logger.info(f"   Organization: {organization_name}")
            logger.info(f"   Role: {role_display_name}")
            logger.info(f"   Token: {invitation_token}")
            logger.info(f"   Accept URL: {accept_url}")
            logger.info(f"   Expires: {expires_at}")
            logger.info("=" * 60)
            print(f"\n{'=' * 60}")
            print(f"📧 INVITATION EMAIL (Development Mode)")
            print(f"   To: {email}")
            print(f"   From: {inviter_name}")
            print(f"   Organization: {organization_name}")
            print(f"   Role: {role_display_name}")
            print(f"   Token: {invitation_token}")
            print(f"   Accept URL: {accept_url}")
            print(f"   Expires: {expires_at}")
            print(f"{'=' * 60}\n")

        # Render email template
        template = Template(INVITATION_EMAIL_TEMPLATE)
        html_body = template.render(
            inviter_name=inviter_name,
            organization_name=organization_name,
            organization_type=org_type_display,
            role_display_name=role_display_name,
            accept_url=accept_url,
            expires_at=expires_at,
            expires_in_days=expires_in_days
        )

        # Create email message
        message = MIMEMultipart("alternative")
        message["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
        message["To"] = email
        message["Subject"] = f"OneDocs Organizasyon Daveti - {organization_name}"

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

        logger.info(f"✅ Invitation email sent successfully to {email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send invitation email to {email}: {str(e)}")
        # In development mode, even if email fails, we logged to console
        if ENABLE_CONSOLE_LOG:
            logger.warning("⚠️  Email sending failed but invitation details logged to console (dev mode)")
            return True  # Consider success in dev mode since details are visible in console
        return False
