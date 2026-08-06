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
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_in: int
    user: dict | None = None


class RegisterRequest(BaseModel):
    name: str
    lastName: str = ""
    email: str
    password: str
    address: str = ""
    city: str = "Barcelona"
    postalCode: str = ""


class UserLoginRequest(BaseModel):
    """Login request for traditional commerce app users (email + password)."""
    email: str
    password: str


class UserRegisterRequest(BaseModel):
    """Registration request for traditional commerce app users."""
    name: str
    surnames: str = ""
    email: str
    password: str
    address: str = ""
    city: str = ""
    postalCode: str = ""


@router.post("/qr-session", response_model=QRSessionResponse)
async def create_qr_session():
    """
    Initiates a login flow:
    - Calls walt.id Verifier API to create an OID4VP authorization request
    - Returns the openid4vp:// URL (to display as QR code)
    - Stores session state for later verification
    """
    now = datetime.now(timezone.utc)
    expired_keys = [
        k for k, v in qr_sessions.items() 
        if datetime.fromisoformat(v["expires_at"]) < now
    ]
    for k in expired_keys:
        del qr_sessions[k]

    session_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.QR_SESSION_TTL_SECONDS
    )


    verifier = VerifierService()

    callback_url = f"http://localhost:8000/auth/callback"

    oid4vp_url = await verifier.create_verification_request(
        session_id=session_id,
        credential_types=["ComercioCredencial"],
        callback_url=callback_url,
    )


    qs = urllib.parse.parse_qs(urllib.parse.urlparse(oid4vp_url).query)
    verifier_state = qs.get("state", [session_id])[0]

    qr_sessions[session_id] = {
        "status": "pending", 
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
                    pass  
            
            await websocket.send_json({"status": session["status"]})

            if session["status"] in ("verified", "expired"):
                break

            # Await client ping (usually sent every 2s)
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass



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



@router.post("/token", response_model=TokenResponse)
async def exchange_for_token(session_id: str):
    """
    After QR verification succeeds, the frontend exchanges the session
    for actual Keycloak access/refresh tokens.
    """
    session = qr_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.get("user_claims") and session.get("verifier_state"):
        try:
            verifier = VerifierService()
            result = await verifier.verify_presentation(session_id=session["verifier_state"])
            if result.get("claims"):
                session["user_claims"] = result.get("claims", {})
        except Exception:
            pass

    claims = session.get("user_claims", {})
    print(f"EXCHANGE_TOKEN: Verified user claims from VP: {claims}")
    keycloak = KeycloakService()
    tokens = await keycloak.create_session_for_verified_user(
        claims=claims
    )

    del qr_sessions[session_id]

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token", ""),
        expires_in=tokens.get("expires_in", 300),
        user={
            "id": claims.get("id", ""),
            "_id": claims.get("id", ""),
            "email": claims.get("email", ""),
            "name": claims.get("firstName", claims.get("givenName", claims.get("given_name", claims.get("name", "").split(" ")[0]))),
            "surnames": claims.get("lastName", claims.get("familyName", claims.get("family_name", ""))),
            "address": claims.get("address", ""),
            "city": claims.get("city", ""),
            "postalCode": claims.get("postalCode", claims.get("postal_code", "")),
            "firstLogin": False,
        }
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
        await keycloak.finalize_user_setup(
            email=request.email,
            name=request.name,
            last_name=request.lastName,
            password=request.password,
            address=request.address,
            city=request.city,
            postal_code=request.postalCode,
        )
    except httpx.HTTPStatusError as exc:
        print(f"REGISTER ERROR HTTPStatusError: {exc.response.status_code} - {exc.response.text}")
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
        import traceback
        print(f"REGISTER UNEXPECTED ERROR: {exc}\n{traceback.format_exc()}")
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
                "lastName": request.lastName,
                "email": request.email,
                "address": request.address,
                "city": request.city,
                "postalCode": request.postalCode,
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


# ── Commerce App — Simple email+password auth (realm: comercio-proximidad) ────

@router.post("/login/user/")
async def login_commerce_user(payload: UserLoginRequest):
    """
    Authenticates a traditional commerce app user against the 'comercio-proximidad' Keycloak realm.
    Uses Direct Access Grant (Resource Owner Password Credentials).
    Returns access_token, refresh_token, and user profile data.
    """
    email = payload.email.strip()
    realm_url = f"{settings.KEYCLOAK_URL}/realms/{settings.COMERCIO_KEYCLOAK_REALM}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Authenticate via Direct Access Grant
        try:
            token_response = await client.post(
                f"{realm_url}/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": settings.COMERCIO_KEYCLOAK_CLIENT_ID,
                    "client_secret": settings.COMERCIO_KEYCLOAK_CLIENT_SECRET,
                    "username": email,
                    "password": payload.password,
                    "scope": "openid",
                },
            )
            token_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid email or password")
            raise HTTPException(status_code=exc.response.status_code, detail="Authentication failed")

        tokens = token_response.json()
        access_token = tokens["access_token"]

        # 2. Fetch user profile from Keycloak userinfo endpoint
        try:
            userinfo_response = await client.get(
                f"{realm_url}/protocol/openid-connect/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()
        except Exception:
            userinfo = {}

    return {
        "token": access_token,
        "refresh_token": tokens.get("refresh_token", ""),
        "user": {
            "id": userinfo.get("sub", ""),
            "_id": userinfo.get("sub", ""),
            "email": userinfo.get("email", email),
            "name": userinfo.get("given_name", userinfo.get("name", email.split("@")[0])),
            "surnames": userinfo.get("family_name", ""),
            "city": userinfo.get("city", ""),
            "firstLogin": False,
        },
    }


@router.post("/register/user/")
async def register_commerce_user(payload: UserRegisterRequest):
    """
    Registers a new traditional user in the 'comercio-proximidad' Keycloak realm.
    Creates user with password — no wallet credentials.
    Address, city, and postalCode are stored as Keycloak user attributes.
    """
    email = payload.email.strip()
    admin_url = f"{settings.KEYCLOAK_URL}/admin/realms/{settings.COMERCIO_KEYCLOAK_REALM}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Get admin token from master realm
        try:
            admin_response = await client.post(
                f"{settings.KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": settings.KEYCLOAK_ADMIN,
                    "password": settings.KEYCLOAK_ADMIN_PASSWORD,
                },
            )
            admin_response.raise_for_status()
            admin_token = admin_response.json()["access_token"]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not obtain admin token: {exc}")

        # 2. Create user in Keycloak
        first_name = payload.name if payload.name else payload.email.split("@")[0]
        last_name = payload.surnames if payload.surnames else "-"

        user_data = {
            "enabled": True,
            "email": email,
            "emailVerified": True,
            "firstName": first_name,
            "lastName": last_name,
            "username": email,
            "credentials": [
                {
                    "type": "password",
                    "value": payload.password,
                    "temporary": False,
                }
            ],
            "attributes": {
                "auth_method": ["password"],
                "address": [payload.address],
                "city": [payload.city],
                "postalCode": [payload.postalCode],
            },
        }

        try:
            create_response = await client.post(
                f"{admin_url}/users",
                json=user_data,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not create user: {exc}")

        if create_response.status_code == 409:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")

        if create_response.status_code not in (201, 204):
            raise HTTPException(
                status_code=create_response.status_code,
                detail=f"User creation failed: {create_response.text}",
            )

    return {"success": True, "message": "User registered successfully."}

