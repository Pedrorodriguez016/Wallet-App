"""
Verification Endpoints
Handles credential verification sessions via walt.id Verifier API (OID4VP).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.verifier_service import VerifierService

router = APIRouter()


class VerificationRequest(BaseModel):
    credential_types: list[str] = ["ComercioCredencial"]
    policies: list[str] = ["signature"]


class VerificationResponse(BaseModel):
    verification_url: str  # openid4vp:// URI
    session_id: str


@router.post("/request", response_model=VerificationResponse)
async def create_verification_request(request: VerificationRequest):
    """
    Creates a verification request (independent of login flow).
    Useful for verifying credentials in other contexts.
    """
    verifier = VerifierService()
    result_url = await verifier.create_verification_request(
        credential_types=request.credential_types,
        policies=request.policies,
    )
    
    # Generate unique state for local reference if needed, or query from URL query string
    import urllib.parse
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(result_url).query)
    session_id = qs.get("state", [""])[0]

    return VerificationResponse(
        verification_url=result_url,
        session_id=session_id,
    )


@router.get("/status/{session_id}")
async def check_verification_status(session_id: str):
    """Checks the status of a verification session."""
    verifier = VerifierService()
    return await verifier.get_session_status(session_id)
