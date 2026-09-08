# Shared wrapper around Python logging; avoid logging passwords, tokens or raw documents.
import logging


logger = logging.getLogger("spc")


class LoggingService:
    """Application logging service."""

    def info(
        self,
        message: str,
    ):
        logger.info(message)

    def warning(
        self,
        message: str,
    ):
        logger.warning(message)

    def error(
        self,
        message: str,
    ):
        logger.error(message)
