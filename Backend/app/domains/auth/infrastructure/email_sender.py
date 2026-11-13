"""Local-console and SMTP verification email senders."""

import asyncio
import smtplib
from email.message import EmailMessage

from app.domains.auth.domain.email_verification import VerificationEmailSender
from app.domains.auth.domain.exceptions import VerificationDeliveryUnavailableError


class DisabledVerificationEmailSender(VerificationEmailSender):
    async def send_verification_code(
        self,
        *,
        email: str,
        code: str,
        expires_in_minutes: int,
    ) -> None:
        raise VerificationDeliveryUnavailableError(
            "Email verification delivery is not configured."
        )


class ConsoleVerificationEmailSender(VerificationEmailSender):
    """Print codes for local development only; never use in hosted environments."""

    async def send_verification_code(
        self,
        *,
        email: str,
        code: str,
        expires_in_minutes: int,
    ) -> None:
        print(
            f"[LOCAL EMAIL] Verification code for {email}: {code} "
            f"(expires in {expires_in_minutes} minutes)"
        )


class SMTPVerificationEmailSender(VerificationEmailSender):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        use_starttls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._use_starttls = use_starttls

    async def send_verification_code(
        self,
        *,
        email: str,
        code: str,
        expires_in_minutes: int,
    ) -> None:
        message = EmailMessage()
        message["Subject"] = "Verify your Smart Peer Companion account"
        message["From"] = self._from_address
        message["To"] = email
        message.set_content(
            "Your Smart Peer Companion verification code is "
            f"{code}. It expires in {expires_in_minutes} minutes. "
            "If you did not request this account, ignore this email."
        )

        def deliver() -> None:
            with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
                if self._use_starttls:
                    smtp.starttls()
                if self._username:
                    smtp.login(self._username, self._password)
                smtp.send_message(message)

        try:
            await asyncio.to_thread(deliver)
        except (OSError, smtplib.SMTPException) as exc:
            raise VerificationDeliveryUnavailableError(
                "The verification email could not be delivered."
            ) from exc
