from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging

from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.prices import router as prices_router
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.admin import router as admin_router
from app.api.routes.trading_bots import router as trading_bots_router

def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title=settings.APP_NAME)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(prices_router)
    app.include_router(portfolio_router)
    app.include_router(alerts_router)
    app.include_router(admin_router)
    app.include_router(trading_bots_router)

    return app

app = create_app()
