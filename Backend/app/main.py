# Application entry point: assemble FastAPI and mount the versioned router.
# Keep request business rules inside domain application services, not this file.
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.observability import logger
from app.api.router import api_router
from app.api.error_handlers import (
    ApiError,
    api_error_handler,
    validation_error_handler,
)

def create_application() -> FastAPI:
    """
    Create and configure the Smart Peer Companion FastAPI application.
    """
    logger.info("Starting Smart Peer Companion Backend...")

    application = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Backend API for the Smart Peer Companion platform, "
            "including users, notes, study groups, AI companions, "
            "quizzes, summaries, and knowledge retrieval."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Convert ApiError exceptions into the agreed JSON error contract.
    application.add_exception_handler(
        ApiError,
        api_error_handler,
    )
    application.add_exception_handler(
        RequestValidationError,
        validation_error_handler,
    )

    application.include_router(api_router)

    return application


app = create_application()


@app.get(
    "/",
    tags=["System"],
    summary="Backend root endpoint",
)
async def root() -> dict[str, str]:
    """
    Return basic information about the backend service.
    """

    return {
        "message": "Smart Peer Companion Backend API",
        "status": "running",
        "documentation": "/docs",
    }
