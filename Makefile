NAMESPACE := stock-radar
REGISTRY := localhost:32000
HELM_DIR := helm/stock-radar
CURRENT_USER ?= $(shell id -un)
PF_API_LOG := /tmp/stock-radar-port-forward-api.$(CURRENT_USER).log
PF_FRONTEND_LOG := /tmp/stock-radar-port-forward-frontend.$(CURRENT_USER).log
PF_PROMETHEUS_LOG := /tmp/stock-radar-port-forward-prometheus.$(CURRENT_USER).log
PF_GRAFANA_LOG := /tmp/stock-radar-port-forward-grafana.$(CURRENT_USER).log
CF_BACKEND_LOG := /tmp/cf_be.$(CURRENT_USER).log
CF_FRONTEND_LOG := /tmp/cf_fe.$(CURRENT_USER).log

# ── Tilt (local K8s dev) ────────────────────────────────────────────
.PHONY: up down logs stop restart refresh

up:
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl create secret generic postgres-secret \
		--from-literal=PGUSER=postgres \
		--from-literal=PGPASSWORD=postgres \
		--namespace=$(NAMESPACE) \
		--dry-run=client -o yaml | kubectl apply -f -
	@if ! kubectl get secret api-secret -n $(NAMESPACE) > /dev/null 2>&1; then \
		API_KEY=$$(python3 -c "import secrets; print(secrets.token_urlsafe(32))"); \
		kubectl create secret generic api-secret \
			--from-literal=API_SECRET_KEY="$$API_KEY" \
			--namespace=$(NAMESPACE); \
		echo ""; \
		echo "╔══════════════════════════════════════════════════════════════╗"; \
		echo "║  API key generated. Retrieve it with:                      ║"; \
		echo "║  kubectl get secret api-secret -n $(NAMESPACE)             ║"; \
		echo "║    -o jsonpath='{.data.API_SECRET_KEY}' | base64 -d        ║"; \
		echo "╚══════════════════════════════════════════════════════════════╝"; \
		echo ""; \
	fi
	tilt up --host=0.0.0.0

down:
	tilt down

logs:
	tilt logs -f

stop:
	tilt down

restart: down up

refresh: down
	docker system prune -f
	$(MAKE) up

# ── Docker ──────────────────────────────────────────────────────────
.PHONY: build build-dev build-prod push build-frontend

build-dev:
	docker build -t $(REGISTRY)/stock-radar-api:dev \
		-f backend/Dockerfile_dev .

build-prod:
	docker build -t $(REGISTRY)/stock-radar-api:latest \
		-f backend/Dockerfile_prod .

build-frontend:
	docker build -t $(REGISTRY)/stock-radar-frontend:latest \
		-f frontend/Dockerfile_prod .

build: build-prod build-frontend

push:
	docker push $(REGISTRY)/stock-radar-api:latest
	docker push $(REGISTRY)/stock-radar-frontend:latest

# ── Helm ────────────────────────────────────────────────────────────
.PHONY: helm-template helm-install helm-upgrade helm-uninstall helm-test

helm-template:
	helm template stock-radar $(HELM_DIR) \
		--namespace $(NAMESPACE) \
		--values $(HELM_DIR)/values.yaml

helm-install:
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm install stock-radar $(HELM_DIR) \
		--namespace $(NAMESPACE) \
		--values $(HELM_DIR)/values.yaml

helm-upgrade:
	helm upgrade stock-radar $(HELM_DIR) \
		--namespace $(NAMESPACE) \
		--values $(HELM_DIR)/values.yaml

helm-uninstall:
	helm uninstall stock-radar --namespace $(NAMESPACE)

helm-test:
	helm test stock-radar --namespace $(NAMESPACE)

# ── Terraform (database provisioning) ──────────────────────────────
.PHONY: tf-init tf-plan tf-apply tf-destroy

tf-init:
	cd terraform/database && terraform init

tf-plan:
	cd terraform/database && terraform plan

tf-apply:
	cd terraform/database && bash apply.sh

tf-destroy:
	cd terraform/database && terraform destroy

# ── Kubernetes ──────────────────────────────────────────────────────
.PHONY: ns secret status port-forward-api port-forward-frontend port-forward-prometheus port-forward-grafana port-forward-all port-forward-stop open-api open-frontend open-prometheus open-grafana open-docs open-redoc open-all print-client-tunnel

ns:
	kubectl apply -f kubernetes/namespace.yaml

secret:
	@echo "Creating postgres-secret in $(NAMESPACE)..."
	@read -p "PGUSER [postgres]: " pguser; pguser=$${pguser:-postgres}; \
	read -sp "PGPASSWORD: " pgpass; echo; \
	kubectl create secret generic postgres-secret \
		--from-literal=PGUSER=$$pguser \
		--from-literal=PGPASSWORD=$$pgpass \
		--namespace=$(NAMESPACE) \
		--dry-run=client -o yaml | kubectl apply -f -

status:
	@echo "=== Namespace ==="
	kubectl get all -n $(NAMESPACE)
	@echo ""
	@echo "=== Pods ==="
	kubectl get pods -n $(NAMESPACE) -o wide
	@echo ""
	@echo "=== Services ==="
	kubectl get svc -n $(NAMESPACE)

port-forward-api:
	@echo "Port-forwarding API on http://127.0.0.1:18100 -> svc/stock-radar-api:8000"
	kubectl port-forward -n $(NAMESPACE) svc/stock-radar-api 18100:8000

port-forward-frontend:
	@echo "Port-forwarding frontend on http://127.0.0.1:14200 -> svc/stock-radar-frontend:4200"
	kubectl port-forward -n $(NAMESPACE) svc/stock-radar-frontend 14200:4200

port-forward-prometheus:
	@echo "Port-forwarding Prometheus on http://127.0.0.1:19090 -> svc/stock-radar-prometheus:9090"
	kubectl port-forward -n $(NAMESPACE) svc/stock-radar-prometheus 19090:9090

port-forward-grafana:
	@echo "Port-forwarding Grafana on http://127.0.0.1:13000 -> svc/stock-radar-grafana:3000"
	kubectl port-forward -n $(NAMESPACE) svc/stock-radar-grafana 13000:3000

port-forward-all:
	@echo "Starting background port-forwards for API, frontend, Prometheus, and Grafana..."
	-kubectl port-forward -n $(NAMESPACE) svc/stock-radar-api 18100:8000 > $(PF_API_LOG) 2>&1 &
	-kubectl port-forward -n $(NAMESPACE) svc/stock-radar-frontend 14200:4200 > $(PF_FRONTEND_LOG) 2>&1 &
	-kubectl port-forward -n $(NAMESPACE) svc/stock-radar-prometheus 19090:9090 > $(PF_PROMETHEUS_LOG) 2>&1 &
	-kubectl port-forward -n $(NAMESPACE) svc/stock-radar-grafana 13000:3000 > $(PF_GRAFANA_LOG) 2>&1 &
	@echo "API:        http://127.0.0.1:18100"
	@echo "Frontend:   http://127.0.0.1:14200"
	@echo "Prometheus: http://127.0.0.1:19090"
	@echo "Grafana:    http://127.0.0.1:13000"
	@echo "Logs:"
	@echo "  $(PF_API_LOG)"
	@echo "  $(PF_FRONTEND_LOG)"
	@echo "  $(PF_PROMETHEUS_LOG)"
	@echo "  $(PF_GRAFANA_LOG)"

port-forward-stop:
	@echo "Stopping stock-radar port-forwards..."
	-pkill -f "kubectl port-forward -n $(NAMESPACE) svc/stock-radar-api 18100:8000"
	-pkill -f "kubectl port-forward -n $(NAMESPACE) svc/stock-radar-frontend 14200:4200"
	-pkill -f "kubectl port-forward -n $(NAMESPACE) svc/stock-radar-prometheus 19090:9090"
	-pkill -f "kubectl port-forward -n $(NAMESPACE) svc/stock-radar-grafana 13000:3000"

open-api:
	@kubectl port-forward -n $(NAMESPACE) svc/stock-radar-api 18100:8000 > $(PF_API_LOG) 2>&1 &
	@sleep 2
	@if [ -n "$$DISPLAY" ] && command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://127.0.0.1:18100; \
	elif [ -n "$$DISPLAY" ] && command -v open >/dev/null 2>&1; then \
		open http://127.0.0.1:18100; \
	else \
		echo "Open http://127.0.0.1:18100 manually"; \
	fi

open-frontend:
	@kubectl port-forward -n $(NAMESPACE) svc/stock-radar-frontend 14200:4200 > $(PF_FRONTEND_LOG) 2>&1 &
	@sleep 2
	@if [ -n "$$DISPLAY" ] && command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://127.0.0.1:14200; \
	elif [ -n "$$DISPLAY" ] && command -v open >/dev/null 2>&1; then \
		open http://127.0.0.1:14200; \
	else \
		echo "Open http://127.0.0.1:14200 manually"; \
	fi

open-prometheus:
	@kubectl port-forward -n $(NAMESPACE) svc/stock-radar-prometheus 19090:9090 > $(PF_PROMETHEUS_LOG) 2>&1 &
	@sleep 2
	@if [ -n "$$DISPLAY" ] && command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://127.0.0.1:19090; \
	elif [ -n "$$DISPLAY" ] && command -v open >/dev/null 2>&1; then \
		open http://127.0.0.1:19090; \
	else \
		echo "Open http://127.0.0.1:19090 manually"; \
	fi

open-grafana:
	@kubectl port-forward -n $(NAMESPACE) svc/stock-radar-grafana 13000:3000 > $(PF_GRAFANA_LOG) 2>&1 &
	@sleep 2
	@if [ -n "$$DISPLAY" ] && command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://127.0.0.1:13000; \
	elif [ -n "$$DISPLAY" ] && command -v open >/dev/null 2>&1; then \
		open http://127.0.0.1:13000; \
	else \
		echo "Open http://127.0.0.1:13000 manually"; \
	fi

open-docs:
	@kubectl port-forward -n $(NAMESPACE) svc/stock-radar-api 18100:8000 > $(PF_API_LOG) 2>&1 &
	@sleep 2
	@if [ -n "$$DISPLAY" ] && command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://127.0.0.1:18100/docs; \
	elif [ -n "$$DISPLAY" ] && command -v open >/dev/null 2>&1; then \
		open http://127.0.0.1:18100/docs; \
	else \
		echo "Open http://127.0.0.1:18100/docs manually"; \
	fi

open-redoc:
	@kubectl port-forward -n $(NAMESPACE) svc/stock-radar-api 18100:8000 > $(PF_API_LOG) 2>&1 &
	@sleep 2
	@if [ -n "$$DISPLAY" ] && command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://127.0.0.1:18100/redoc; \
	elif [ -n "$$DISPLAY" ] && command -v open >/dev/null 2>&1; then \
		open http://127.0.0.1:18100/redoc; \
	else \
		echo "Open http://127.0.0.1:18100/redoc manually"; \
	fi

open-all: open-api open-frontend open-prometheus open-grafana open-docs

print-client-tunnel:
	@echo "Run this on your client machine and keep it open:"
	@echo "ssh -L 18100:127.0.0.1:18100 -L 14200:127.0.0.1:14200 $(CURRENT_USER)@<ubuntu-host>"
	@echo ""
	@echo "Then run these on Ubuntu:"
	@echo "make port-forward-api"
	@echo "make port-forward-frontend"
	@echo ""
	@echo "Then open on the client machine:"
	@echo "http://127.0.0.1:18100"
	@echo "http://127.0.0.1:14200"

# ── Local dev (no K8s) ──────────────────────────────────────────────
.PHONY: dev test migrate serve-frontend tunnel tunnel-frontend

dev:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

serve-frontend:
	cd frontend && npx ng serve --proxy-config proxy.conf.json --host 0.0.0.0 --allowed-hosts

test:
	cd backend && python -m pytest tests/ -v

migrate:
	cd backend && alembic upgrade head

tunnel:
	@echo "Starting Cloudflare quick tunnel for backend (port 8000)..."
	cloudflared tunnel --url http://localhost:8000

tunnel-frontend:
	@echo "Starting Cloudflare quick tunnel for frontend (port 4200)..."
	cloudflared tunnel --url http://localhost:4200

# ── K8s Tunneling (Public Access) ───────────────────────────────────
.PHONY: tunnel-k8s tunnel-status tunnel-stop

tunnel-k8s:
	@echo "Restarting K8s Port-Forwards and Tunnels..."
	-pkill -f "kubectl port-forward"
	-pkill -f "cloudflared"
	-tmux kill-session -t cf-backend 2>/dev/null || true
	-tmux kill-session -t cf-frontend 2>/dev/null || true
	@sleep 2
	# Start Port-Forwards
	kubectl port-forward svc/stock-radar-api 18100:8000 -n $(NAMESPACE) --address 0.0.0.0 > $(PF_API_LOG) 2>&1 &
	kubectl port-forward svc/stock-radar-frontend 14200:4200 -n $(NAMESPACE) --address 0.0.0.0 > $(PF_FRONTEND_LOG) 2>&1 &
	@sleep 3
	# Start backend tunnel first
	tmux new-session -d -s cf-backend 'cloudflared tunnel --url http://localhost:18100 --no-autoupdate 2>&1 | tee $(CF_BACKEND_LOG)'
	@echo "Waiting for backend URL..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
		BACKEND_URL=$$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_BACKEND_LOG) | head -n 1); \
		if [ -n "$$BACKEND_URL" ]; then \
			break; \
		fi; \
		sleep 1; \
	done; \
	BACKEND_URL=$$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_BACKEND_LOG) | head -n 1); \
	if [ -z "$$BACKEND_URL" ]; then \
		echo "Backend tunnel URL not found."; \
		exit 1; \
	fi; \
	echo "Patching frontend runtime config to $$BACKEND_URL/api"; \
	kubectl exec -n $(NAMESPACE) deploy/stock-radar-frontend -- sh -lc 'printf "%s\n" "window.__stockRadarConfig = {" "  apiBaseUrl: \"'$$BACKEND_URL'/api\"," "  wsBaseUrl: \"'$$BACKEND_URL'/api\"," "};" > /usr/share/nginx/html/runtime-config.js'; \
	tmux new-session -d -s cf-frontend 'cloudflared tunnel --url http://localhost:14200 --no-autoupdate 2>&1 | tee $(CF_FRONTEND_LOG)'
	@echo "Waiting for frontend URL..."
	@sleep 8
	@echo "\n🚀 PUBLIC LINKS:"
	@echo "Frontend: $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_FRONTEND_LOG) | head -n 1)"
	@echo "Backend:  $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_BACKEND_LOG) | head -n 1)"
	@echo "Docs:     $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_BACKEND_LOG) | head -n 1)/docs\n"

tunnel-status:
	@echo "=== Cloudflare Tunnels ==="
	@tmux ls 2>/dev/null | grep cf- || echo "No active tunnels."
	@echo ""
	@echo "=== Port-Forwards ==="
	@ps aux | grep "kubectl port-forward" | grep -v grep || echo "No active port-forwards."
	@echo ""
	@echo "=== Public URLs ==="
	@echo "Frontend: $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_FRONTEND_LOG) 2>/dev/null | head -n 1 || true)"
	@echo "Backend:  $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_BACKEND_LOG) 2>/dev/null | head -n 1 || true)"
	@echo "Docs:     $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_BACKEND_LOG) 2>/dev/null | head -n 1 | sed 's#$$#/docs#' || true)"
	@echo ""
	@echo "=== Logs ==="
	@echo "$(CF_FRONTEND_LOG)"
	@echo "$(CF_BACKEND_LOG)"
	@echo "$(PF_API_LOG)"
	@echo "$(PF_FRONTEND_LOG)"

tunnel-stop:
	@echo "Stopping Cloudflare tunnels and related port-forwards..."
	-pkill -f "cloudflared"
	-pkill -f "kubectl port-forward"
	-tmux kill-session -t cf-backend 2>/dev/null || true
	-tmux kill-session -t cf-frontend 2>/dev/null || true
	@echo "Stopped."

# ── API Key Management ─────────────────────────────────────────────
.PHONY: rotate-api-key show-api-key show-access-token

rotate-api-key:
	@API_KEY=$$(python3 -c "import secrets; print(secrets.token_urlsafe(32))"); \
	kubectl create secret generic api-secret \
		--from-literal=API_SECRET_KEY="$$API_KEY" \
		--namespace=$(NAMESPACE) \
		--dry-run=client -o yaml | kubectl apply -f -; \
	kubectl rollout restart deployment/stock-radar-api -n $(NAMESPACE); \
	echo "API key rotated. New key: $$API_KEY"

show-api-key:
	@kubectl get secret api-secret -n $(NAMESPACE) -o jsonpath='{.data.API_SECRET_KEY}' | base64 -d; echo

show-access-token:
	@kubectl exec -n $(NAMESPACE) deploy/stock-radar-api -- python3 -c "from app.core.auth import create_access_token; print(create_access_token())"

# ── VPS Deployment ─────────────────────────────────────────────────
.PHONY: deploy-vps deploy-engine

VPS_HOST ?= your-vps-host
VPS_USER ?= root

deploy-vps:
	@echo "Deploying VPS setup files to $(VPS_USER)@$(VPS_HOST)..."
	rsync -avz --mkpath deploy/ $(VPS_USER)@$(VPS_HOST):/opt/stock-radar/deploy/
	ssh $(VPS_USER)@$(VPS_HOST) "bash /opt/stock-radar/deploy/setup-vps.sh"

deploy-engine:
	@echo "Deploying backend to $(VPS_USER)@$(VPS_HOST)..."
	rsync -avz --exclude='__pycache__' --exclude='.env' --exclude='*.pyc' \
		backend/ $(VPS_USER)@$(VPS_HOST):/opt/stock-radar/backend/
	ssh $(VPS_USER)@$(VPS_HOST) "\
		/opt/stock-radar/venv/bin/pip install -q -r /opt/stock-radar/backend/requirements.txt && \
		systemctl restart trading-engine"

# ── Cleanup ─────────────────────────────────────────────────────────
.PHONY: clean prune

clean:
	-helm uninstall stock-radar --namespace $(NAMESPACE) 2>/dev/null
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found

prune: clean
	docker system prune -af --volumes
