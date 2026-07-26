"""
Security dependencies for FastAPI endpoints.
Validates Keycloak JWT tokens on protected routes.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.keycloak_service import KeycloakService

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency that validates the Bearer token against Keycloak
    and returns the decoded user claims.
    """
    keycloak = KeycloakService()
    try:
        payload = await keycloak.verify_token(credentials.credentials)
        return payload
    except ValueError as e:
        from jose import jwt
        try:
            unverified_header = jwt.get_unverified_header(credentials.credentials)
            unverified_claims = jwt.get_unverified_claims(credentials.credentials)
        except Exception as ex:
            unverified_header = f"failed to parse header: {ex}"
            unverified_claims = f"failed to parse claims: {ex}"
        print(f"DEBUG: Token: {credentials.credentials[:30]}...[truncated]")
        print(f"DEBUG: Unverified Header: {unverified_header}")
        print(f"DEBUG: Unverified Claims: {unverified_claims}")
        print(f"DEBUG: Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> dict | None:
    """Optional auth — returns None if no token provided."""
    if credentials is None:
        return None
    keycloak = KeycloakService()
    try:
        return await keycloak.verify_token(credentials.credentials)
    except ValueError:
        return None
