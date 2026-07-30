from fastapi import FastAPI

from app.core.config import settings
from app.core.observability import logger
from app.api.router import api_router


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
        version=settings.APP_NAME,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.include_router(
        api_router,
        prefix="/api/v1",
    )

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