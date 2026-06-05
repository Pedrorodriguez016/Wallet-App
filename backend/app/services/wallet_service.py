"""
Wallet Service
Communicates with walt.id Wallet API for custodial wallet management.
"""

import httpx

from app.core.config import settings


class WalletService:
    def __init__(self):
        self.base_url = settings.WALTID_WALLET_URL

    async def _authenticate(self, email: str, password: str) -> str:
        """Authenticates with the wallet API and returns a session token."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/wallet-api/auth/login",
                json={
                    "type": "email",
                    "email": email,
                    "password": password,
                },
            )
            response.raise_for_status()
            return response.json().get("token", "")

    async def authenticate_keycloak(self, email: str, password: str) -> str:
        """Authenticates with the wallet API using Keycloak OIDC and returns a session token."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/wallet-api/auth/keycloak/login",
                json={
                    "type": "keycloak",
                    "username": email,
                    "password": password,
                },
            )
            response.raise_for_status()
            return response.json().get("token", "")

    async def register(self, email: str, name: str, password: str) -> dict:
        """
        Registers a new wallet account.
        Each account gets a default did:key and Ed25519 key pair.
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/wallet-api/auth/register",
                json={
                    "type": "email",
                    "name": name,
                    "email": email,
                    "password": password,
                },
            )
            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return {}

    async def register_keycloak(self, email: str, password: str, admin_token: str) -> dict:
        """Registers a user in Keycloak and walt.id via the keycloak/create proxy."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/wallet-api/auth/keycloak/create",
                json={
                    "type": "keycloak",
                    "username": email,
                    "email": email,
                    "password": password,
                    "token": admin_token,
                },
            )

            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return {}


    async def get_wallets(self, token: str) -> dict:
        """Lists wallets for the authenticated user."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/wallet-api/wallet/accounts/wallets",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def list_credentials(self, wallet_id: str, token: str = "") -> list[dict]:
        """Lists all credentials in a wallet."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/wallet-api/wallet/{wallet_id}/credentials",
                headers={"Authorization": f"Bearer {token}"} if token else {},
            )
            response.raise_for_status()
            return response.json()

    async def list_dids(self, wallet_id: str, token: str = "") -> list[dict]:
        """Lists all DIDs in a wallet."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/wallet-api/wallet/{wallet_id}/dids",
                headers={"Authorization": f"Bearer {token}"} if token else {},
            )
            response.raise_for_status()
            return response.json()

    async def create_did(self, wallet_id: str, token: str) -> str:
        """Creates a default did:key in the wallet and returns the generated DID."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/wallet-api/wallet/{wallet_id}/dids/create/key",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.text.strip().strip('"')

    async def claim_credential(
        self, wallet_id: str, offer_url: str, token: str
    ) -> dict:
        """
        Claims a credential offer into the wallet.
        The offer_url is the OID4VCI credential offer URI.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/wallet-api/wallet/{wallet_id}/exchange/useOfferRequest",
                content=offer_url.encode(),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "text/plain",
                },
            )
            response.raise_for_status()
            return response.json()

    async def present_credential(
        self,
        wallet_id: str,
        presentation_url: str,
        credential_ids: list[str],
        token: str,
    ) -> dict:
        """
        Presents credentials from the wallet to a verifier.
        The presentation_url is the OID4VP authorization request URI.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/wallet-api/wallet/{wallet_id}/exchange/usePresentationRequest",
                json={
                    "presentationRequest": presentation_url,
                    "selectedCredentials": credential_ids,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def get_settings(self, wallet_id: str, token: str) -> dict:
        """Gets wallet settings."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/wallet-api/wallet/{wallet_id}/settings",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def update_settings(self, wallet_id: str, settings_payload: dict, token: str) -> dict:
        """Updates wallet settings."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/wallet-api/wallet/{wallet_id}/settings",
                json=settings_payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()
