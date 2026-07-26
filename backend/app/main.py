"""
VC-Wallet Platform — FastAPI Application
Integrates Keycloak (IAM) + walt.id (SSI) for credential issuance and validation.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print(f"🚀 Wallet Backend starting in {settings.APP_ENV} mode")
    yield
    print("👋 Wallet Backend shutting down")


app = FastAPI(
    title="Wallet Backend API",
    description="Backend wrapper for Verifiable Credentials Wallet with Keycloak + walt.id",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    )

# CORS configurations
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip() and origin.strip() != "*"]
print("Configured CORS origins:", origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routes
app.include_router(api_router, prefix="")
