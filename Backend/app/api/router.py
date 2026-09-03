# Mount domain routers under /api/v1; these paths form the frontend HTTP contract.
# The health response checks API liveness only, not the database, worker, or model.
from fastapi import APIRouter

from app.api.routers.auth import router as auth_router
from app.api.routers.users import router as users_router
from app.api.routers.notes import router as notes_router
from app.api.routers.study_groups import router as study_groups_router
from app.api.routers.knowledge_graph import router as knowledge_graph_router
from app.api.routers.notifications import router as notifications_router
from app.api.routers.analytics import router as analytics_router
from app.api.routers.administration import router as administration_router
# from app.api.routers.ai import router as ai_router

api_router = APIRouter(
    prefix="/api/v1",
)


@api_router.get(
    "/health",
    tags=["System"],
)
async def health():
    return {
        "status": "healthy",
        "service": "SPC Backend",
    }


api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(notes_router)
api_router.include_router(study_groups_router)
api_router.include_router(knowledge_graph_router)
api_router.include_router(notifications_router)
api_router.include_router(analytics_router)
api_router.include_router(administration_router)

# Enable these when they're ready

# api_router.include_router(ai_router)
