"""
Verifier Service
Communicates with walt.id Verifier API to create OID4VP verification requests
and validate Verifiable Presentations.
"""

import uuid
import httpx

from app.core.config import settings


class VerifierService:
    def __init__(self):
        self.base_url = settings.WALTID_VERIFIER_URL

    async def create_verification_request(
        self,
        credential_types: list[str] | None = None,
        session_id: str | None = None,
        callback_url: str | None = None,
        policies: list[str] | None = None,
    ) -> str:
        """
        Creates an OID4VP verification request via walt.id Verifier API.
        Returns the openid4vp:// authorization URL to encode as QR.

        Endpoint: POST /openid4vc/verify
        """
        if credential_types is None:
            credential_types = ["ComercioCredencial"]

        if session_id is None:
            session_id = str(uuid.uuid4())

        if policies is None:
            policies = ["signature"]

        # Build the verification request payload
        requested_credentials = []
        for cred_type in credential_types:
            requested_credentials.append({
                "type": cred_type,
                "format": "jwt_vc_json",
                "policies": [{"policy": p} for p in policies],
            })

        payload = {
            "request_credentials": requested_credentials,
        }

        # Query params for the verification request
        params = {
            "state": session_id,
            "authorizeBaseUrl": "openid4vp://authorize",
            "responseMode": "direct_post",
            "responseUrl": f"{settings.WALTID_VERIFIER_URL}/openid4vc/pd/{session_id}",
        }

        if callback_url:
            params["successRedirectUri"] = callback_url
            params["errorRedirectUri"] = callback_url

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/openid4vc/verify",
                json=payload,
                params=params,
            )
            response.raise_for_status()

            # The API returns the openid4vp:// URL as plain text
            oid4vp_url = response.text.strip().strip('"')
            return oid4vp_url

    async def verify_presentation(
        self,
        session_id: str,
        vp_token: str | None = None,
    ) -> dict:
        """
        Checks the verification result for a given session.

        Endpoint: GET /openid4vc/session/{session_id}
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/openid4vc/session/{session_id}",
            )
            response.raise_for_status()
            result = response.json()

            # verificationResult is a top-level boolean
            is_valid = result.get("verificationResult", False)

            claims = {}
            for entry in result.get("policyResults", {}).get("results", []):
                for policy_result in entry.get("policyResults", []):
                    subject = policy_result.get("result", {}).get("vc", {}).get("credentialSubject", {})
                    claims.update(subject)

            return {
                "valid": is_valid,
                "claims": claims,
                "raw": result,
            }

    async def get_session_status(self, session_id: str) -> dict:
        """Gets the current status of a verification session."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/openid4vc/session/{session_id}",
            )
            if response.status_code == 404:
                return {"status": "not_found", "session_id": session_id}

            response.raise_for_status()
            return response.json()
