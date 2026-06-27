"""
Keycloak Service
Handles authentication flows, token exchange, and user management
with Keycloak as the IAM backend.
"""

import httpx
from jose import jwt, JWTError

from app.core.config import settings


class KeycloakService:
    def __init__(self):
        self.base_url = settings.KEYCLOAK_URL
        self.realm = settings.KEYCLOAK_REALM
        self.client_id = settings.KEYCLOAK_CLIENT_ID
        self.client_secret = settings.KEYCLOAK_CLIENT_SECRET

    @property
    def _realm_url(self) -> str:
        return f"{self.base_url}/realms/{self.realm}"

    @property
    def _admin_url(self) -> str:
        return f"{self.base_url}/admin/realms/{self.realm}"

    async def _get_admin_token(self) -> str:
        """Gets an admin access token via the master realm."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.base_url}/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": settings.KEYCLOAK_ADMIN,
                    "password": settings.KEYCLOAK_ADMIN_PASSWORD,
                },
            )
            response.raise_for_status()
            return response.json()["access_token"]

    async def create_session_for_verified_user(self, claims: dict) -> dict:
        """
        After a Verifiable Presentation is validated, this method:
        1. Finds or creates the user in Keycloak based on VC claims
        2. Issues tokens via direct grant or token exchange

        This bridges SSI verification → traditional Keycloak session.
        """
        email = claims.get("email", "")
        did = claims.get("id", "")

        # Derive first/last name — the VC may only have a combined "name" field
        full_name = claims.get("name", "")
        parts = full_name.split(" ", 1) if full_name else []
        given_name = claims.get("givenName", claims.get("given_name", parts[0] if parts else email.split("@")[0]))
        family_name = claims.get("familyName", claims.get("family_name", parts[1] if len(parts) > 1 else "-"))

        # Step 1: Find or create user in Keycloak
        admin_token = await self._get_admin_token()
        user_id = await self._find_user_by_email(admin_token, email)

        if not user_id and did:
            user_id = await self._find_user_by_attribute(admin_token, "did", did)

        if not user_id:
            user_id = await self._create_user(
                admin_token=admin_token,
                email=email,
                first_name=given_name,
                last_name=family_name,
                did=did,
            )
        else:
            # Ensure required profile fields are set on existing users
            await self._ensure_profile(admin_token, user_id, given_name, family_name)

        # Step 2: Generate tokens for the user
        tokens = await self._impersonate_user(admin_token, user_id)
        return tokens

    async def _ensure_profile(
        self, admin_token: str, user_id: str, first_name: str, last_name: str
    ) -> None:
        """Patches firstName/lastName on an existing user if they are missing."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{self._admin_url}/users/{user_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            r.raise_for_status()
            user = r.json()
            if not user.get("firstName") or not user.get("lastName"):
                await client.put(
                    f"{self._admin_url}/users/{user_id}",
                    json={
                        **user,
                        "firstName": user.get("firstName") or first_name,
                        "lastName": user.get("lastName") or last_name,
                    },
                    headers={"Authorization": f"Bearer {admin_token}"},
                )

    async def _find_user_by_email(self, admin_token: str, email: str) -> str | None:
        """Finds a user by email, returns user ID or None."""
        if not email:
            return None

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._admin_url}/users",
                params={"email": email, "exact": "true"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            response.raise_for_status()
            users = response.json()
            return users[0]["id"] if users else None

    async def _find_user_by_attribute(
        self, admin_token: str, attr_key: str, attr_value: str
    ) -> str | None:
        """Finds a user by custom attribute (e.g., DID)."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._admin_url}/users",
                params={"q": f"{attr_key}:{attr_value}"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            response.raise_for_status()
            users = response.json()
            return users[0]["id"] if users else None

    async def _create_user(
        self,
        admin_token: str,
        email: str,
        first_name: str,
        last_name: str,
        did: str,
    ) -> str:
        """Creates a new user in Keycloak with VC-derived attributes."""
        user_data = {
            "enabled": True,
            "email": email,
            "emailVerified": True,  # Verified via VC
            "firstName": first_name,
            "lastName": last_name,
            "username": email or did,
            "attributes": {
                "did": [did],
                "auth_method": ["verifiable_credential"],
            },
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self._admin_url}/users",
                json=user_data,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            response.raise_for_status()

            # Get user ID from Location header
            location = response.headers.get("Location", "")
            user_id = location.split("/")[-1]
            return user_id

    async def _impersonate_user(self, admin_token: str, user_id: str) -> dict:
        """
        Issues tokens on behalf of a user using Keycloak's token exchange grant type.
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Get the username
            r = await client.get(
                f"{self._admin_url}/users/{user_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            r.raise_for_status()
            username = r.json().get("username") or r.json().get("email")

            # 2. Perform token-exchange
            r = await client.post(
                f"{self._realm_url}/protocol/openid-connect/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "requested_subject": username,
                    "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
                },
            )
            r.raise_for_status()
            tokens = r.json()

        return tokens

    async def verify_token(self, token: str) -> dict:
        """Verifies and decodes a Keycloak JWT access token."""
        # Fetch JWKS for verification
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(settings.keycloak_jwks_url)
            response.raise_for_status()
            jwks = response.json()

        try:
            payload = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self._realm_url,
            )
            return payload
        except JWTError as e:
            raise ValueError(f"Token verification failed: {e}")

    async def get_user_info(self, access_token: str) -> dict:
        """Gets user info from Keycloak using an access token."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self._realm_url}/protocol/openid-connect/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()

    async def register_user(self, email: str, first_name: str, last_name: str, password: str) -> str:
        """Registers a user in Keycloak with a password."""
        admin_token = await self._get_admin_token()
        
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
                    "value": password,
                    "temporary": False
                }
            ],
            "attributes": {
                "auth_method": ["password"],
            }
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self._admin_url}/users",
                json=user_data,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            if response.status_code == 409:
                return await self._find_user_by_email(admin_token, email) or ""
            response.raise_for_status()
            
            location = response.headers.get("Location", "")
            user_id = location.split("/")[-1]
            return user_id

    async def finalize_user_setup(self, email: str, name: str, password: str) -> None:
        """Ensures the user account is fully active, email verified, and password is non-temporary."""
        admin_token = await self._get_admin_token()
        user_id = await self._find_user_by_email(admin_token, email)
        if not user_id:
            raise ValueError(f"User with email {email} not found in Keycloak")
            
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Fetch user data to preserve other fields
            r = await client.get(
                f"{self._admin_url}/users/{user_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            r.raise_for_status()
            user_data = r.json()
            
            # 2. Update user: verify email, clear required actions, and set first/last name
            parts = name.split(" ", 1) if name else []
            first_name = parts[0] if parts else email.split("@")[0]
            last_name = parts[1] if len(parts) > 1 else "-"

            user_data["emailVerified"] = True
            user_data["requiredActions"] = []
            user_data["firstName"] = user_data.get("firstName") or first_name
            user_data["lastName"] = user_data.get("lastName") or last_name
            
            r = await client.put(
                f"{self._admin_url}/users/{user_id}",
                json=user_data,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            r.raise_for_status()
            
            # 3. Reset password to make it non-temporary
            r = await client.put(
                f"{self._admin_url}/users/{user_id}/reset-password",
                json={"type": "password", "value": password, "temporary": False},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            r.raise_for_status()


