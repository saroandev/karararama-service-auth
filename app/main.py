"""
Main FastAPI application.
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import api_router
from app.api.well_known import router as well_known_router
from app.api.oauth_html import router as oauth_html_router

# Swagger/OpenAPI is an attack-surface map — only expose it when DEBUG is on
# (local dev). Preprod/prod configmaps set DEBUG=False, so docs stay hidden.
_DOCS_ENABLED = settings.DEBUG

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
)

# CORS middleware. `allow_origin_regex` covers the *.onedocs.ai whitelabel
# fleet (and onedocs.ai itself) so we don't have to enumerate every tenant
# subdomain; `allow_origins` keeps localhost/dev origins from .env working.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# RFC 8414 well-known endpoints — mounted at root, NO /api/v1 prefix.
app.include_router(well_known_router)

# OAuth browser-facing HTML pages (/oauth/authorize, /oauth/login,
# /oauth/consent). Also root-mounted because Claude.ai resolves them
# directly via the issuer URL from authorization-server metadata.
app.include_router(oauth_html_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/")
async def root():
    """Root endpoint."""
    payload = {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
    }
    if _DOCS_ENABLED:
        payload["docs"] = "/docs"
    return payload