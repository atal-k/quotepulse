from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine
from app.core.errors import register_exception_handlers
from app.core.logging import RequestIdMiddleware, configure_logging
from app.modules.accounts.router import router as accounts_router
from app.modules.activities.router import router as activities_router
from app.modules.contacts.router import router as contacts_router
from app.modules.identity.router import router as identity_router
from app.modules.leads.router import router as leads_router
from app.modules.notifications.router import router as notifications_router
from app.modules.opportunities.router import router as opportunities_router
from app.modules.products.router import router as products_router


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="QuotePulse API",
        description="AI-native CRM for industrial sales workflows.",
    )

    register_exception_handlers(app)

    # Middleware order: last added wraps outermost. RequestIdMiddleware first so CORS ends up
    # outermost and applies its headers even to error responses.
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(identity_router, prefix="/api/v1")
    app.include_router(accounts_router, prefix="/api/v1")
    app.include_router(contacts_router, prefix="/api/v1")
    app.include_router(leads_router, prefix="/api/v1")
    app.include_router(opportunities_router, prefix="/api/v1")
    app.include_router(products_router, prefix="/api/v1")
    app.include_router(activities_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, str]:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app


app = create_app()
