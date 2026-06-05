"""
Authentication Endpoints
Handles QR-based login flow using OID4VP + Keycloak session creation,
as well as direct walt.id user registration and credential issuance.
"""

import uuid
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Header
from pydantic import BaseModel

from app.core.config import settings
from app.services.verifier_service import VerifierService
from app.services.keycloak_service import KeycloakService
from app.services.wallet_service import WalletService
from app.services.issuer_service import IssuerService

router = APIRouter()

# In-memory session store
qr_sessions: dict[str, dict] = {}


class QRSessionResponse(BaseModel):
    session_id: str
    qr_data: str  # openid4vp:// URI to encode as QR
    expires_at: str


class VerificationCallbackRequest(BaseModel):
    state: str  # session_id
    vp_token: str
    presentation_submission: dict | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    poblacion: str = "Barcelona"


# ── 1. Create QR Login Session ──────────────────────────────────────────────
@router.post("/qr-session", response_model=QRSessionResponse)
async def create_qr_session():
    """
    Initiates a login flow:
    - Calls walt.id Verifier API to create an OID4VP authorization request
    - Returns the openid4vp:// URL (to display as QR code)
    - Stores session state for later verification
    """
    session_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.QR_SESSION_TTL_SECONDS
    )

    verifier = VerifierService()
    # Build callback URL pointing back to the backend
    callback_url = f"http://localhost:8000/api/v1/auth/callback"

    oid4vp_url = await verifier.create_verification_request(
        session_id=session_id,
        credential_types=["ComercioCredencial"],
        callback_url=callback_url,
    )

    # Extract state from URL if the verifier generated its own
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(oid4vp_url).query)
    verifier_state = qs.get("state", [session_id])[0]

    qr_sessions[session_id] = {
        "status": "pending",  # pending | scanned | verified | expired
        "verifier_state": verifier_state,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
        "vp_token": None,
        "user_claims": None,
    }

    print("Created QR session:", session_id)
    return QRSessionResponse(
        session_id=session_id,
        qr_data=oid4vp_url,
        expires_at=expires_at.isoformat(),
    )


# ── 2. WebSocket for real-time QR scan status ───────────────────────────────
@router.websocket("/qr-session/{session_id}/ws")
async def qr_session_ws(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for the client to receive real-time updates
    when the user scans the QR with their wallet.
    """
    await websocket.accept()
    try:
        while True:
            session = qr_sessions.get(session_id)
            if not session:
                await websocket.send_json({"status": "not_found"})
                break

            # Poll the verifier if still pending
            if session["status"] == "pending" and session.get("verifier_state"):
                try:
                    verifier = VerifierService()
                    result = await verifier.verify_presentation(
                        session_id=session["verifier_state"]
                    )
                    if result.get("valid"):
                        session["status"] = "verified"
                        session["user_claims"] = result.get("claims", {})
                except Exception:
                    pass  # Keep polling until ready
            
            await websocket.send_json({"status": session["status"]})

            if session["status"] in ("verified", "expired"):
                break

            # Await client ping (usually sent every 2s)
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass


# ── 3. Verification Callback (from walt.id Verifier) ────────────────────────
@router.post("/callback")
async def verification_callback(request: VerificationCallbackRequest):
    """
    Called by walt.id Verifier API after the wallet presents credentials.
    Validates the VP token and extracts user claims.
    """
    session = qr_sessions.get(request.state)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] != "pending":
        raise HTTPException(status_code=409, detail="Session already processed")

    verifier = VerifierService()
    verification_result = await verifier.verify_presentation(
        session_id=request.state,
        vp_token=request.vp_token,
    )

    if verification_result.get("valid"):
        session["status"] = "verified"
        session["vp_token"] = request.vp_token
        session["user_claims"] = verification_result.get("claims", {})
    else:
        session["status"] = "expired"

    return {"status": session["status"]}


# ── 4. Exchange verified session for Keycloak tokens ────────────────────────
@router.post("/token", response_model=TokenResponse)
async def exchange_for_token(session_id: str):
    """
    After QR verification succeeds, the frontend exchanges the session
    for actual Keycloak access/refresh tokens.
    """
    session = qr_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] == "pending":
        verifier = VerifierService()
        result = await verifier.verify_presentation(session_id=session["verifier_state"])
        if result.get("valid"):
            session["status"] = "verified"
            session["user_claims"] = result.get("claims", {})

    if session["status"] != "verified":
        raise HTTPException(status_code=403, detail="Session not verified")

    keycloak = KeycloakService()
    tokens = await keycloak.create_session_for_verified_user(
        claims=session["user_claims"]
    )

    # Cleanup session
    del qr_sessions[session_id]

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens.get("expires_in", 300),
    )


# ── 5. Register — creates wallet account + issues ComercioCredencial ─────────
@router.post("/register", status_code=201)
async def register(request: RegisterRequest):
    """
    Registers a new user and issues their ComercioCredencial immediately:
    1. Creates a wallet account in walt.id
    2. Logins to walt.id to obtain account session token
    3. Fetches the wallets list and gets the default wallet ID
    4. Lists DIDs in the wallet. If none exists, creates a did:key DID
    5. Requests a ComercioCredencial from walt.id Issuer API with name, email, DID and poblacion
    6. Claims the issued credential into the user's wallet
    """
    wallet = WalletService()

    # Step 1: Register wallet account and link to Keycloak
    try:
        keycloak = KeycloakService()
        admin_token = await keycloak._get_admin_token()
        await wallet.register_keycloak(email=request.email, password=request.password, admin_token=admin_token)
        
        # Step 1.5: Finalize user setup in Keycloak (verify email, make password permanent)
        await keycloak.finalize_user_setup(email=request.email, name=request.name, password=request.password)
    except httpx.HTTPStatusError as exc:

        if exc.response.status_code == 409:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Try logging in.",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Could not create wallet account: {exc.response.text}",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")

    # Step 2: Authenticate to walt.id wallet via Keycloak OIDC login
    try:
        token = await wallet.authenticate_keycloak(request.email, request.password)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Wallet authentication failed: {exc}")


    # Step 3: Get default wallet ID
    wallets_data = await wallet.get_wallets(token)
    
    wallets_list = []
    if isinstance(wallets_data, list):
        wallets_list = wallets_data
    elif isinstance(wallets_data, dict) and "wallets" in wallets_data:
        wallets_list = wallets_data["wallets"]
        
    if not wallets_list:
        raise HTTPException(status_code=500, detail="No wallet found for this account")
    wallet_id = wallets_list[0]["id"]

    # Step 4: Check if DID exists, otherwise create it
    try:
        dids = await wallet.list_dids(wallet_id, token)
        if dids:
            user_did = dids[0]["did"]
        else:
            user_did = await wallet.create_did(wallet_id, token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve or create DID: {exc}")

    # Step 5: Issue ComercioCredencial
    issuer = IssuerService()
    try:
        offer_url = await issuer.create_offer(
            credential_type="ComercioCredencial",
            claims={
                "id": user_did,
                "name": request.name,
                "email": request.email,
                "poblacion": request.poblacion,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Credential issuance failed: {exc}")

    # Step 6: Claim credential into user's wallet
    try:
        await wallet.claim_credential(wallet_id, offer_url, token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Credential claim failed: {exc}")

    return {
        "success": True,
        "message": "User wallet registered and ComercioCredencial successfully issued and stored.",
        "did": user_did
    }


# ── Proxy endpoints to walt.id Wallet API for Flutter compatibility ───────────

@router.get("/keycloak/token")
async def proxy_keycloak_token():
    """Proxies GET /auth/keycloak/token to walt.id Wallet API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{settings.WALTID_WALLET_URL}/wallet-api/auth/keycloak/token"
            )
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))


@router.post("/keycloak/login")
async def proxy_keycloak_login(payload: dict):
    """Proxies POST /auth/keycloak/login to walt.id Wallet API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{settings.WALTID_WALLET_URL}/wallet-api/auth/keycloak/login",
                json=payload
            )
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))


@router.post("/keycloak/create")
async def proxy_keycloak_create(payload: dict):
    """Proxies POST /auth/keycloak/create to walt.id Wallet API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{settings.WALTID_WALLET_URL}/wallet-api/auth/keycloak/create",
                json=payload
            )
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))


@router.get("/user-info")
async def proxy_user_info(authorization: str | None = Header(None)):
    """Proxies GET /auth/user-info to walt.id Wallet API."""
    headers = {}
    if authorization:
        headers["Authorization"] = authorization
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{settings.WALTID_WALLET_URL}/wallet-api/auth/user-info",
                headers=headers
            )
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
