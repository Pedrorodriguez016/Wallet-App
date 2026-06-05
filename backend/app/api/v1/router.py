"""API v1 Router — aggregates all endpoint modules."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, credentials, verification, wallet

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(credentials.router, prefix="/credentials", tags=["Credentials"])
api_router.include_router(verification.router, prefix="/verification", tags=["Verification"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["Wallet"])
