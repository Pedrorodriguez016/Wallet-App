"""
Credentials Endpoints
Handles credential issuance via walt.id Issuer API (OID4VCI).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.issuer_service import IssuerService
from app.core.security import get_current_user

router = APIRouter()


class CredentialOfferRequest(BaseModel):
    credential_type: str = "ComercioCredencial"
    user_claims: dict = {}


class CredentialOfferResponse(BaseModel):
    offer_url: str  # openid-credential-offer:// URI
    credential_type: str


@router.post("/offer", response_model=CredentialOfferResponse)
async def create_credential_offer(
    request: CredentialOfferRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a credential offer that can be claimed by a wallet.
    Returns an OID4VCI offer URL (displayable as QR or deep link).
    """
    issuer = IssuerService()
    offer_url = await issuer.create_offer(
        credential_type=request.credential_type,
        claims=request.user_claims,
    )
    return CredentialOfferResponse(
        offer_url=offer_url,
        credential_type=request.credential_type,
    )



@router.get("/types")
async def list_credential_types():
    """Lists available credential types that can be issued."""
    issuer = IssuerService()
    return await issuer.get_supported_types()
