"""
SiteSync AI — FastAPI application factory.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SiteSync AI API",
        description="Field to Schedule Intelligence — Backend API",
        version=settings.app_version,
        # Disable docs in production
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
    )

    # CORS — allow only configured origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Error handlers matching ARCHITECTURE.md format
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc: HTTPException):
        from fastapi.responses import JSONResponse
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            content = exc.detail
        else:
            content = {
                "error": {
                    "code": "HTTP_" + str(exc.status_code),
                    "message": str(exc.detail),
                    "details": {},
                }
            }
        return JSONResponse(status_code=exc.status_code, content=content)

    # Register API routers
    app.include_router(v1_router)

    return app


app = create_app()
