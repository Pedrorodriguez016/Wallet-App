-- ═══════════════════════════════════════════════════════════
-- Init script: creates additional databases alongside keycloak
-- ═══════════════════════════════════════════════════════════

-- Database for the FastAPI backend application
CREATE DATABASE vc_wallet;
GRANT ALL PRIVILEGES ON DATABASE vc_wallet TO keycloak;
