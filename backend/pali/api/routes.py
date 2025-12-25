"""
Main API router that combines all v1 routes.
"""
from fastapi import APIRouter

from .v1 import literature, translate, chat, dpd, health, admin

# Create main router
router = APIRouter()

# Include all v1 routes
router.include_router(health.router, tags=["Health"])
router.include_router(literature.router, prefix="/literature", tags=["Literature"])
router.include_router(translate.router, prefix="/translate", tags=["Translate"])
router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(dpd.router, prefix="/dpd", tags=["DPD Dictionary"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])
