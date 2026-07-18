from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from kavach_saathi.config import Settings
from kavach_saathi.providers import otp_core


class EmailIntegrationClient:
    """Email-OTP delivery via plain SMTP (e.g. Gmail with an App Password) --
    the free-tier alternative to Twilio WhatsApp OTP, which on a trial account
    only delivers to one verified phone number. Config-gated on
    smtp_host/smtp_username/smtp_password; callers must catch RuntimeError and
    degrade honestly rather than fake a "sent" response, matching
    TwilioIntegrationClient's convention.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.smtp_host and self.settings.smtp_username and self.settings.smtp_password)

    def _send(self, to_email: str, subject: str, body: str) -> None:
        message = MIMEText(body)
        message["Subject"] = subject
        from_name = self.settings.smtp_from_name
        from_email = self.settings.smtp_from_email or self.settings.smtp_username
        message["From"] = f"{from_name} <{from_email}>"
        message["To"] = to_email

        timeout = self.settings.provider_timeout_seconds
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=timeout) as server:
            server.starttls()
            server.login(self.settings.smtp_username, self.settings.smtp_password)
            server.send_message(message)

    def send_otp_email(self, email: str, *, purpose: str, reference_id: str) -> None:
        if not self.is_configured:
            raise RuntimeError("Email OTP delivery is not configured")

        from kavach_saathi.redis_client import get_redis

        contact = email.strip().lower()
        code = otp_core.store_otp(
            get_redis(), self.settings, purpose=purpose, reference_id=reference_id, contact=contact
        )
        subject_by_purpose = {
            "signup": "Verify your email for Kavach Saathi",
            "order_confirm": "Confirm your Kavach Saathi order",
            "delivery": "Confirm delivery of your Kavach Saathi order",
            "return": "Confirm your Kavach Saathi return",
        }
        subject = subject_by_purpose.get(purpose, "Your Kavach Saathi verification code")
        body = (
            f"Your Kavach Saathi verification code is: {code}\n\n"
            f"It expires in {self.settings.otp_expiry_seconds // 60} minutes. "
            "If you did not request this, you can ignore this email."
        )
        try:
            self._send(email, subject, body)
        except Exception as exc:
            try:
                get_redis().delete(otp_core.otp_key(purpose, reference_id))
            except Exception:
                pass
            raise RuntimeError("Email OTP delivery is temporarily unavailable") from exc
