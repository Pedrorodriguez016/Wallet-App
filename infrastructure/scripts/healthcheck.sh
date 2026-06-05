#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# VC-Wallet Platform — Health Check Script
# Ejecuta esto después de "docker compose up -d" para verificar
# que todos los servicios están corriendo.
# ═══════════════════════════════════════════════════════════════
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  VC-Wallet Platform — Health Check${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

PASS=0
FAIL=0

check_service() {
    local name="$1"
    local url="$2"

    printf "  %-25s " "$name"

    for i in 1 2 3; do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 500 ]; then
            echo -e "${GREEN}✅ OK${NC} (HTTP $HTTP_CODE)"
            PASS=$((PASS + 1))
            return 0
        fi
        sleep 2
    done

    echo -e "${RED}❌ FAIL${NC} (HTTP $HTTP_CODE)"
    FAIL=$((FAIL + 1))
    return 1
}

check_container() {
    local name="$1"
    printf "  %-25s " "$name"

    STATUS=$(docker inspect --format='{{.State.Status}}' "$name" 2>/dev/null || echo "not found")

    if [ "$STATUS" = "running" ]; then
        echo -e "${GREEN}✅ running${NC}"
        PASS=$((PASS + 1))
        return 0
    else
        echo -e "${RED}❌ $STATUS${NC}"
        FAIL=$((FAIL + 1))
        return 1
    fi
}

# ── Step 1: Check Docker containers ────────────────────────────
echo -e "${YELLOW}1. Comprobando contenedores Docker...${NC}"
echo ""

check_container "vc-postgres"
check_container "vc-keycloak"
check_container "vc-issuer"
check_container "vc-verifier"
check_container "vc-wallet"

echo ""

# ── Step 2: Check service endpoints ───────────────────────────
echo -e "${YELLOW}2. Comprobando endpoints de servicios...${NC}"
echo ""

echo -e "  ${BLUE}[PostgreSQL]${NC}"
printf "  %-25s " "PostgreSQL :5432"
if docker exec vc-postgres pg_isready -U keycloak > /dev/null 2>&1; then
    echo -e "${GREEN}✅ OK${NC}"
    PASS=$((PASS + 1))
else
    echo -e "${RED}❌ FAIL${NC}"
    FAIL=$((FAIL + 1))
fi

echo ""
echo -e "  ${BLUE}[Keycloak]${NC}"
check_service "Keycloak :8080" "http://localhost:8080/health/ready"
check_service "Keycloak Realm" "http://localhost:8080/realms/vc-wallet/.well-known/openid-configuration"

echo ""
echo -e "  ${BLUE}[walt.id Issuer API]${NC}"
check_service "Issuer API :7002" "http://localhost:7002"

echo ""
echo -e "  ${BLUE}[walt.id Verifier API]${NC}"
check_service "Verifier API :7003" "http://localhost:7003"

echo ""
echo -e "  ${BLUE}[walt.id Wallet API]${NC}"
check_service "Wallet API :7001" "http://localhost:7001"

echo ""

# ── Step 3: Quick functional test ─────────────────────────────
echo -e "${YELLOW}3. Test funcional rápido...${NC}"
echo ""

printf "  %-25s " "Wallet register"
REGISTER_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
    -X POST "http://localhost:7001/wallet-api/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
        "type": "email",
        "name": "HealthCheck Test",
        "email": "healthcheck@test.local",
        "password": "test1234"
    }' 2>/dev/null || echo "000")

if [ "$REGISTER_RESPONSE" -ge 200 ] && [ "$REGISTER_RESPONSE" -lt 400 ]; then
    echo -e "${GREEN}✅ OK${NC} (HTTP $REGISTER_RESPONSE)"
    PASS=$((PASS + 1))
elif [ "$REGISTER_RESPONSE" = "409" ]; then
    echo -e "${GREEN}✅ OK${NC} (ya existe, HTTP 409)"
    PASS=$((PASS + 1))
else
    echo -e "${RED}❌ FAIL${NC} (HTTP $REGISTER_RESPONSE)"
    FAIL=$((FAIL + 1))
fi

printf "  %-25s " "Wallet login"
LOGIN_RESPONSE=$(curl -s --max-time 10 \
    -X POST "http://localhost:7001/wallet-api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
        "type": "email",
        "email": "healthcheck@test.local",
        "password": "test1234"
    }' 2>/dev/null || echo "")

if echo "$LOGIN_RESPONSE" | grep -q "token"; then
    echo -e "${GREEN}✅ OK${NC} (token recibido)"
    PASS=$((PASS + 1))
else
    echo -e "${RED}❌ FAIL${NC}"
    FAIL=$((FAIL + 1))
fi

echo ""

# ── Summary ───────────────────────────────────────────────────
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "  Resultado: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

if [ $FAIL -gt 0 ]; then
    echo -e "${YELLOW}💡 Tips para errores:${NC}"
    echo ""
    echo "  • Si Keycloak falla: espera 30-60s más, es lento arrancando"
    echo "    docker logs vc-keycloak --tail 20"
    echo ""
    echo "  • Si walt.id falla: revisa logs del servicio"
    echo "    docker logs vc-wallet --tail 30"
    echo "    docker logs vc-issuer --tail 30"
    echo "    docker logs vc-verifier --tail 30"
    echo ""
    echo "  • Para descargar configs oficiales:"
    echo "    bash infrastructure/scripts/setup.sh"
    echo ""
    echo "  • Para empezar de cero:"
    echo "    make clean && make up-build"
    echo ""
    exit 1
else
    echo -e "${GREEN}🎉 ¡Todo funciona correctamente!${NC}"
    echo ""
    echo "  URLs disponibles:"
    echo "    🔐 Keycloak:       http://localhost:8080  (admin/admin)"
    echo "    📤 Issuer API:     http://localhost:7002"
    echo "    ✅ Verifier API:   http://localhost:7003"
    echo "    👛 Wallet API:     http://localhost:7001"
    echo ""
    exit 0
fi