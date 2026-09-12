from app.api.routes import api_router
from app.api.importance import router as importance_router
from app.api.public_feed import router as public_feed_router
from app.api.source_management import router as source_management_router
from app.api.cloud_admin import legacy_router as legacy_cloud_admin_router
from app.api.cloud_admin import router as cloud_admin_router
from app.api.notifications import router as notifications_router

api_router.include_router(importance_router)
api_router.include_router(public_feed_router)
api_router.include_router(source_management_router)
api_router.include_router(cloud_admin_router)
api_router.include_router(legacy_cloud_admin_router)
api_router.include_router(notifications_router)

__all__ = ["api_router"]
