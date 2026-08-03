import logging
import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.core.config import settings
from app.services.issuer_service import IssuerService
from app.services.wallet_service import WalletService
from app.services.keycloak_service import KeycloakService

logger = logging.getLogger(__name__)
router = APIRouter()


class OdooCredentialRequest(BaseModel):
    email: str
    event_id: str
    event_name: str
    partner_name: str
    company_name: str | None = None

@router.post("/odoo-credential")
async def handle_odoo_event_completion(
    payload: OdooCredentialRequest,
):
    """
    Called by Odoo (BCNMercatus_eventos) when an organizer confirms event attendance.
    Emits an EventCredencial via walt.id Issuer API and claims it into the user's wallet.
    """
    email = payload.email.strip()
    wallet_service = WalletService()
    keycloak_service = KeycloakService()

    # 2. Localiza la cuenta del usuario en walt.id de forma limpia sin tocar su contraseña
    account_id = wallet_service.get_account_id_by_email(email)
    if not account_id:
        try:
            admin_token = await keycloak_service._get_admin_token()
            account_id = await keycloak_service._find_user_by_email(admin_token, email)
        except Exception:
            pass

    if not account_id:
        raise HTTPException(status_code=404, detail=f"No account found for user with email '{email}'")

    # 3. Genera el token de sesión de walt.id firmado para la cuenta sin alterar contraseñas
    waltid_session_token = wallet_service.generate_session_token(account_id)

    # 4. Obtiene la lista de wallets del usuario
    try:
        wallets_data = await wallet_service.get_wallets(waltid_session_token)
        wallets_list = []
        if isinstance(wallets_data, list):
            wallets_list = wallets_data
        elif isinstance(wallets_data, dict) and "wallets" in wallets_data:
            wallets_list = wallets_data["wallets"]

        if not wallets_list:
            raise HTTPException(status_code=404, detail="No wallet found for this user account")
        
        wallet_id = wallets_list[0]["id"]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user wallet: {exc}")

    # 5. Obtiene o crea un DID para el usuario en la wallet
    try:
        dids = await wallet_service.list_dids(wallet_id, waltid_session_token)
        if dids:
            user_did = dids[0]["did"]
        else:
            user_did = await wallet_service.create_did(wallet_id, waltid_session_token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve/create DID: {exc}")

    # 6. Genera la oferta OID4VCI para la credencial de evento
    issuer_service = IssuerService()
    try:
        offer_url = await issuer_service.create_offer(
            credential_type="EventCredencial",
            claims={
                "id": user_did,
                "email": email,
                "name": payload.partner_name,
                "companyName": payload.company_name,
                "eventName": payload.event_name,
                "eventId": payload.event_id,
                "status": "Attended"
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create credential offer: {exc}")

    # 7. Deposita (claim) la credencial en el wallet custodial del usuario
    try:
        claim_result = await wallet_service.claim_credential(wallet_id, offer_url, waltid_session_token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to claim credential into wallet: {exc}")

    logger.info(f"Successfully issued EventCredencial to {email} for event {payload.event_name}")
    return {
        "success": True,
        "message": f"EventCredencial issued and claimed into wallet for event '{payload.event_name}'",
        "did": user_did,
        "claim_result": claim_result
    }