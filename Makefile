.PHONY: help up down logs backend keycloak waltid clean status urls

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ═══════════════════════════════════════════════════════════════
# Docker Compose
# ═══════════════════════════════════════════════════════════════

up: ## Start all services (Database, Keycloak, walt.id, backend)
	docker compose up -d

up-build: ## Build and start all services
	docker compose up -d --build

down: ## Stop all services
	docker compose down

logs: ## Tail all logs
	docker compose logs -f

# ═══════════════════════════════════════════════════════════════
# Individual services
# ═══════════════════════════════════════════════════════════════

backend: ## Start/rebuild only the backend
	docker compose up -d --build backend

keycloak: ## Start Keycloak + Postgres
	docker compose up -d postgres keycloak

waltid: ## Start walt.id services
	docker compose up -d waltid-issuer waltid-verifier waltid-wallet waltid-web-wallet

# ═══════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════

clean: ## Remove volumes and containers
	docker compose down -v --remove-orphans

status: ## Show service status
	docker compose ps

urls: ## Show all service URLs
	@echo ""
	@echo "  🔧 Backend API:     http://localhost:8000/api/docs"
	@echo "  🔐 Keycloak:        http://localhost:8080  (admin/admin)"
	@echo "  📤 Issuer API:      http://localhost:7002"
	@echo "  ✅ Verifier API:    http://localhost:7003"
	@echo "  👛 Wallet API:      http://localhost:7001"
	@echo "  🌐 Wallet WEB:      http://localhost:7101"
	@echo ""
