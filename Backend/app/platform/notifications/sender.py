class NotificationSender:
    """Notification delivery service."""

    async def send_email(
        self,
        recipient: str,
        subject: str,
        message: str,
    ):
        return True

    async def send_push(
        self,
        recipient: str,
        message: str,
    ):
        return True