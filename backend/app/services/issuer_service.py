"""
Issuer Service
Communicates with walt.id Issuer API to create credential offers (OID4VCI).
"""

import httpx

from app.core.config import settings


class IssuerService:
    def __init__(self):
        self.base_url = settings.WALTID_ISSUER_URL

    async def create_offer(
        self,
        credential_type: str = "ComercioCredencial",
        claims: dict | None = None,
        auth_method: str = "PRE_AUTHORIZED",
    ) -> str:
        """
        Creates a credential offer via walt.id Issuer API.
        Returns the credential offer URL (openid-credential-offer://).

        Endpoint: POST /openid4vc/jwt/issue
        """
        if claims is None:
            claims = {}

        import json
        jwk = json.loads(settings.WALTID_ISSUER_KEY_JWK)

        # Build the issuance request
        # The credentialData follows the W3C VC data model
        payload = {
            "issuerKey": {
                "type": "jwk",
                "jwk": jwk,
            },
            "issuerDid": settings.WALTID_ISSUER_DID,
            "credentialConfigurationId": f"{credential_type}_jwt_vc_json",
            "credentialData": {
                "@context": [
                    "https://www.w3.org/2018/credentials/v1"
                ],
                "type": [
                    "VerifiableCredential",
                    "Credencial Comerç" if credential_type == "ComercioCredencial" else credential_type,
                ],
                "credentialSubject": claims,
            },
            "authenticationMethod": auth_method,
        }

        params = {
            "baseUrl": f"{settings.WALTID_ISSUER_URL}",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/openid4vc/jwt/issue",
                json=payload,
                params=params,
            )
            response.raise_for_status()

            # Returns the credential offer URL as plain text
            offer_url = response.text.strip().strip('"')
            return offer_url

    async def get_supported_types(self) -> list[dict]:
        """Returns the list of supported credential types."""
        return [
            {
                "id": "ComercioCredencial",
                "name": "Credencial Comerç",
                "description": "Local commerce digital credential with name, email, and town",
                "format": "jwt_vc_json",
            },
            {
                "id": "VerifiableId",
                "name": "Verifiable ID",
                "description": "Basic identity credential with name and date of birth",
                "format": "jwt_vc_json",
            }
        ]

    async def create_offer_with_keycloak_claims(
        self,
        credential_type: str,
        keycloak_user_info: dict,
    ) -> str:
        """
        Creates a credential offer populated with claims from Keycloak.
        Maps Keycloak user attributes to VC credential subject.
        """
        # Retrieve name fields
        full_name = keycloak_user_info.get("name", "")
        if not full_name:
            given = keycloak_user_info.get("given_name", "")
            family = keycloak_user_info.get("family_name", "")
            full_name = f"{given} {family}".strip() or "Usuario Keycloak"

        # Check for poblacion custom attribute in Keycloak attributes
        attrs = keycloak_user_info.get("attributes", {})
        poblacion = attrs.get("poblacion", ["Barcelona"])[0] if "poblacion" in attrs else "Barcelona"

        claims = {
            "id": f"did:key:{keycloak_user_info.get('sub', '')}",
            "name": full_name,
            "email": keycloak_user_info.get("email", ""),
            "poblacion": poblacion,
        }

        return await self.create_offer(
            credential_type=credential_type,
            claims=claims,
        )
