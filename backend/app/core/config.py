"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # General
    APP_ENV: str = "development"
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # Keycloak
    KEYCLOAK_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "vc-wallet"
    KEYCLOAK_CLIENT_ID: str = "vc-wallet-backend"
    KEYCLOAK_CLIENT_SECRET: str = "change-me-in-production"
    KEYCLOAK_ADMIN: str = "admin"
    KEYCLOAK_ADMIN_PASSWORD: str = "admin"

    # walt.id Services
    WALTID_ISSUER_URL: str = "http://localhost:7002"
    WALTID_VERIFIER_URL: str = "http://localhost:7003"
    WALTID_WALLET_URL: str = "http://localhost:7001"
    WALTID_ISSUER_DID: str = "did:key:z6MkjoRhq1jSNJdLiruSXrFFxagqrztZaXHqHGUTKJbcNywp"
    WALTID_ISSUER_KEY_JWK: str = '{"kty": "OKP", "d": "mDhpwaH6JYSrD2Bq7Cs-pzmsjlLj4EOhxyI-9DM1mFI", "crv": "Ed25519", "kid": "Wst-oAE-zBMV07eodtgVmmPDqYjwsxFOjaCI3VPnMVY", "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"}'

    # CORS
    CORS_ORIGINS: str = "http://localhost,http://localhost:8000,*"

    # QR Login
    QR_SESSION_TTL_SECONDS: int = 300  # 5 minutes


    @property
    def keycloak_openid_config_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/.well-known/openid-configuration"

    @property
    def keycloak_token_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/token"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
