from fastapi import APIRouter


# AI endpoints will be registered here once their application services are
# implemented. Keeping a real router avoids the previous self-import cycle.
router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)
