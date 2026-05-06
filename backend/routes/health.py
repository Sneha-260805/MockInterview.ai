from fastapi import APIRouter
from database.connection import is_using_memory
from config import get_settings

router = APIRouter(prefix="/api", tags=["health"])
settings = get_settings()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "storage": "in-memory" if is_using_memory() else "mongodb",
    }
