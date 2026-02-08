from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.logging import setup_logging

from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.prices import router as prices_router
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.admin import router as admin_router
from app.api.routes.trading_bots import router as trading_bots_router
from app.api.routes.symbols import router as symbols_router

def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title=settings.APP_NAME)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(prices_router)
    app.include_router(portfolio_router)
    app.include_router(admin_router)
    app.include_router(trading_bots_router)
    app.include_router(symbols_router)

    return app

app = create_app()
