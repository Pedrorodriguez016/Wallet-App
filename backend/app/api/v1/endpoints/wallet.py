from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
import httpx

from app.services.wallet_service import WalletService

router = APIRouter()


class WalletCreateRequest(BaseModel):
    email: str
    name: str
    password: str


@router.post("/register")
async def register_wallet(request: WalletCreateRequest):
    """Registers a new wallet account in walt.id."""
    wallet = WalletService()
    return await wallet.register(
        email=request.email,
        name=request.name,
        password=request.password,
    )


@router.get("/accounts/wallets")
async def list_wallets(authorization: str | None = Header(None)):
    """Lists all wallets for the authenticated user."""
    wallet = WalletService()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    try:
        return await wallet.get_wallets(token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{wallet_id}/credentials")
async def list_wallet_credentials(wallet_id: str, authorization: str | None = Header(None)):
    """Lists all credentials stored in a wallet."""
    wallet = WalletService()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    try:
        return await wallet.list_credentials(wallet_id, token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{wallet_id}/dids")
async def list_wallet_dids(wallet_id: str, authorization: str | None = Header(None)):
    """Lists all DIDs associated with a wallet."""
    wallet = WalletService()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    try:
        return await wallet.list_dids(wallet_id, token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{wallet_id}/dids/create/key")
async def create_did_key(wallet_id: str, authorization: str | None = Header(None)):
    """Creates a default did:key DID inside the wallet."""
    wallet = WalletService()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    try:
        return await wallet.create_did(wallet_id, token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{wallet_id}/exchange/useOfferRequest")
async def use_offer_request(wallet_id: str, request: Request, authorization: str | None = Header(None)):
    """Claims a credential offer using OID4VCI (plain text URL body)."""
    body_bytes = await request.body()
    offer_url = body_bytes.decode("utf-8")
    
    wallet = WalletService()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    try:
        return await wallet.claim_credential(wallet_id, offer_url, token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{wallet_id}/exchange/usePresentationRequest")
async def use_presentation_request(wallet_id: str, payload: dict, authorization: str | None = Header(None)):
    """Presents a credential using OID4VP."""
    wallet = WalletService()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    try:
        return await wallet.present_credential(
            wallet_id=wallet_id,
            presentation_url=payload.get("presentationRequest", ""),
            credential_ids=payload.get("selectedCredentials", []),
            token=token
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{wallet_id}/settings")
async def get_wallet_settings(wallet_id: str, authorization: str | None = Header(None)):
    """Retrieves settings for a wallet."""
    wallet = WalletService()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    try:
        return await wallet.get_settings(wallet_id, token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{wallet_id}/settings")
async def update_wallet_settings(wallet_id: str, payload: dict, authorization: str | None = Header(None)):
    """Updates settings for a wallet."""
    wallet = WalletService()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    try:
        return await wallet.update_settings(wallet_id, payload, token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
