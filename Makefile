NAMESPACE := stock-radar
PUBLIC_NAMESPACE := stock-radar-public
REGISTRY := localhost:32000
PUBLIC_REGISTRY ?= $(REGISTRY)
HELM_DIR := helm/stock-radar
HELM_RELEASE := stock-radar
PUBLIC_HELM_RELEASE := stock-radar-public
PUBLIC_IMAGE_TAG ?= $(shell printf '%s-%s' "$$(date +%Y%m%d%H%M%S)" "$$(git rev-parse --short=12 HEAD 2>/dev/null || echo manual)")
PUBLIC_IMAGE_TAG_FILE := .public-image-tag
CURRENT_USER ?= $(shell id -un)
export KUBECONFIG ?= $(HOME)/.kube/merged-config
PF_API_LOG := /tmp/stock-radar-port-forward-api.$(CURRENT_USER).log
PF_FRONTEND_LOG := /tmp/stock-radar-port-forward-frontend.$(CURRENT_USER).log
PF_PROMETHEUS_LOG := /tmp/stock-radar-port-forward-prometheus.$(CURRENT_USER).log
PF_GRAFANA_LOG := /tmp/stock-radar-port-forward-grafana.$(CURRENT_USER).log
CF_BACKEND_LOG := /tmp/cf_be.$(CURRENT_USER).log
CF_FRONTEND_LOG := /tmp/cf_fe.$(CURRENT_USER).log
CF_GRAFANA_LOG := /tmp/cf_grafana.$(CURRENT_USER).log

# ── Tilt (local K8s dev) ────────────────────────────────────────────
.PHONY: up up-stockradarx-tunnel down logs stop restart refresh trigger-api trigger-frontend

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

up-stockradarx-tunnel:
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
	TILT_HELM_VALUES_EXTRA=$(HELM_DIR)/values.mode.stockradarx-tunnel.yaml tilt up --host=0.0.0.0

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

trigger-api:
	tilt trigger stock-radar-api

trigger-frontend:
	tilt trigger stock-radar-frontend

# ── Docker ──────────────────────────────────────────────────────────
.PHONY: build build-dev build-prod push docker-build-frontend

build-dev:
	docker build -t $(REGISTRY)/stock-radar-api:dev \
		-f backend/Dockerfile_dev .

build-prod:
	docker build -t $(REGISTRY)/stock-radar-api:latest \
		-f backend/Dockerfile_prod backend

docker-build-frontend:
	docker build -t $(REGISTRY)/stock-radar-frontend:latest \
		-f frontend/Dockerfile_prod frontend

build: build-prod docker-build-frontend

push:
	docker push $(REGISTRY)/stock-radar-api:latest
	docker push $(REGISTRY)/stock-radar-frontend:latest

# ── Helm ────────────────────────────────────────────────────────────
.PHONY: helm-template helm-install helm-upgrade helm-uninstall helm-test deploy-stockradarx deploy-stockradarx-tunnel public-bootstrap public-status build-public-images deploy-stockradarx-public public-uninstall show-public-image-tag public-images public-worker-image public-pod-images

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
	helm test $(HELM_RELEASE) --namespace $(NAMESPACE)

deploy-stockradarx:
	helm upgrade --install stock-radar $(HELM_DIR) \
		--namespace $(NAMESPACE) \
		--values $(HELM_DIR)/values.yaml \
		--values $(HELM_DIR)/values.local.yaml \
		--values $(HELM_DIR)/values.mode.stockradarx.com.yaml

deploy-stockradarx-tunnel:
	helm upgrade --install $(HELM_RELEASE) $(HELM_DIR) \
		--namespace $(NAMESPACE) \
		--values $(HELM_DIR)/values.yaml \
		--values $(HELM_DIR)/values.local.yaml \
		--values $(HELM_DIR)/values.mode.stockradarx-tunnel.yaml

public-bootstrap:
	kubectl create namespace $(PUBLIC_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	@for secret in postgres-secret api-secret polygon-secret; do \
		echo "Syncing $$secret from $(NAMESPACE) to $(PUBLIC_NAMESPACE)..."; \
		kubectl get secret $$secret -n $(NAMESPACE) -o json | jq '.metadata.namespace = "$(PUBLIC_NAMESPACE)" | del(.metadata.uid,.metadata.resourceVersion,.metadata.creationTimestamp,.metadata.managedFields,.metadata.annotations."kubectl.kubernetes.io/last-applied-configuration",.metadata.ownerReferences)' | kubectl apply -f -; \
	done

public-status:
	@echo "=== Public Namespace ==="
	kubectl get all -n $(PUBLIC_NAMESPACE)
	@echo ""
	@echo "=== Public Ingress ==="
	kubectl get ingress -n $(PUBLIC_NAMESPACE)

build-public-images:
	docker build -t $(PUBLIC_REGISTRY)/stock-radar-api:$(PUBLIC_IMAGE_TAG) \
		-f backend/Dockerfile_prod backend
	docker build -t $(PUBLIC_REGISTRY)/stock-radar-frontend:$(PUBLIC_IMAGE_TAG) \
		-f frontend/Dockerfile_prod frontend
	docker push $(PUBLIC_REGISTRY)/stock-radar-api:$(PUBLIC_IMAGE_TAG)
	docker push $(PUBLIC_REGISTRY)/stock-radar-frontend:$(PUBLIC_IMAGE_TAG)
	@printf '%s\n' '$(PUBLIC_IMAGE_TAG)' > $(PUBLIC_IMAGE_TAG_FILE)
	@echo "Recorded public image tag: $(PUBLIC_IMAGE_TAG)"
	@echo "Pushed public images to: $(PUBLIC_REGISTRY)"

deploy-stockradarx-public:
	@test -f $(PUBLIC_IMAGE_TAG_FILE) || (echo "Missing $(PUBLIC_IMAGE_TAG_FILE). Run 'make build-public-images' first."; exit 1)
	@TAG=$$(cat $(PUBLIC_IMAGE_TAG_FILE)); \
	helm upgrade --install $(PUBLIC_HELM_RELEASE) $(HELM_DIR) \
		--namespace $(PUBLIC_NAMESPACE) \
		--create-namespace \
		--values $(HELM_DIR)/values.yaml \
		--values $(HELM_DIR)/values.public.yaml \
		--set-string api.image.tag=$$TAG \
		--set-string frontend.image.tag=$$TAG \
		--values $(HELM_DIR)/values.mode.stockradarx-tunnel.yaml

public-uninstall:
	helm uninstall $(PUBLIC_HELM_RELEASE) --namespace $(PUBLIC_NAMESPACE)

show-public-image-tag:
	@test -f $(PUBLIC_IMAGE_TAG_FILE) || (echo "No recorded public image tag yet."; exit 1)
	@cat $(PUBLIC_IMAGE_TAG_FILE)

public-images:
	kubectl get deploy -n $(PUBLIC_NAMESPACE) -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{.spec.template.spec.containers[0].image}{"\n"}{end}'

public-worker-image:
	kubectl get deploy -n $(PUBLIC_NAMESPACE) stock-radar-worker -o jsonpath='{.spec.template.spec.containers[0].image}'; echo

public-pod-images:
	kubectl get pods -n $(PUBLIC_NAMESPACE) -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{.spec.containers[0].image}{"\n"}{end}'

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
.PHONY: ns secret status restart-api restart-frontend port-forward-api port-forward-frontend port-forward-prometheus port-forward-grafana port-forward-all port-forward-stop open-api open-frontend open-prometheus open-grafana open-docs open-redoc open-all print-client-tunnel

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

restart-api:
	kubectl rollout restart -n $(NAMESPACE) deployment/stock-radar-api
	kubectl rollout status -n $(NAMESPACE) deployment/stock-radar-api

restart-frontend:
	kubectl rollout restart -n $(NAMESPACE) deployment/stock-radar-frontend
	kubectl rollout status -n $(NAMESPACE) deployment/stock-radar-frontend

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
.PHONY: dev test frontend-specs frontend-specs-watch frontend-check migrate serve-frontend tunnel tunnel-frontend

dev:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

serve-frontend:
	cd frontend && npx ng serve --proxy-config proxy.conf.json --host 0.0.0.0 --allowed-hosts

test:
	cd backend && python -m pytest tests/ -v

frontend-specs:
	@test -n "$$(find frontend/src -name '*.spec.ts' -print -quit)" || (echo "No frontend *.spec.ts files found under frontend/src."; exit 1)
	cd frontend && npm run test

frontend-specs-watch:
	@test -n "$$(find frontend/src -name '*.spec.ts' -print -quit)" || (echo "No frontend *.spec.ts files found under frontend/src."; exit 1)
	cd frontend && npm run test:watch

frontend-check: frontend-specs

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
	-tmux kill-session -t cf-grafana 2>/dev/null || true
	@sleep 2
	# Start Port-Forwards
	kubectl port-forward svc/stock-radar-api 18100:8000 -n $(NAMESPACE) --address 0.0.0.0 > $(PF_API_LOG) 2>&1 &
	kubectl port-forward svc/stock-radar-frontend 14200:4200 -n $(NAMESPACE) --address 0.0.0.0 > $(PF_FRONTEND_LOG) 2>&1 &
	kubectl port-forward svc/stock-radar-grafana 13000:3000 -n $(NAMESPACE) --address 0.0.0.0 > $(PF_GRAFANA_LOG) 2>&1 &
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
	tmux new-session -d -s cf-frontend 'cloudflared tunnel --url http://localhost:14200 --no-autoupdate 2>&1 | tee $(CF_FRONTEND_LOG)'; \
	tmux new-session -d -s cf-grafana 'cloudflared tunnel --url http://localhost:13000 --no-autoupdate 2>&1 | tee $(CF_GRAFANA_LOG)'
	@echo "Waiting for frontend and Grafana URLs..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
		FRONTEND_URL=$$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_FRONTEND_LOG) | head -n 1); \
		GRAFANA_URL=$$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_GRAFANA_LOG) | head -n 1); \
		if [ -n "$$FRONTEND_URL" ] && [ -n "$$GRAFANA_URL" ]; then \
			break; \
		fi; \
		sleep 1; \
	done
	@echo "\n🚀 PUBLIC LINKS:"
	@echo "Frontend: $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_FRONTEND_LOG) | head -n 1)"
	@echo "Backend:  $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_BACKEND_LOG) | head -n 1)"
	@echo "Grafana:  $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_GRAFANA_LOG) | head -n 1)"
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
	@echo "Grafana:  $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_GRAFANA_LOG) 2>/dev/null | head -n 1 || true)"
	@echo "Docs:     $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' $(CF_BACKEND_LOG) 2>/dev/null | head -n 1 | sed 's#$$#/docs#' || true)"
	@echo ""
	@echo "=== Logs ==="
	@echo "$(CF_FRONTEND_LOG)"
	@echo "$(CF_BACKEND_LOG)"
	@echo "$(CF_GRAFANA_LOG)"
	@echo "$(PF_API_LOG)"
	@echo "$(PF_FRONTEND_LOG)"
	@echo "$(PF_GRAFANA_LOG)"

tunnel-stop:
	@echo "Stopping Cloudflare tunnels and related port-forwards..."
	-pkill -f "kubectl port-forward"
	-pkill -f "cloudflared"
	-tmux kill-session -t cf-backend 2>/dev/null || true
	-tmux kill-session -t cf-frontend 2>/dev/null || true
	-tmux kill-session -t cf-grafana 2>/dev/null || true
	@echo "Stopped."

# ── API Key Management ─────────────────────────────────────────────
.PHONY: rotate-api-key show-api-key show-api-key-public show-polygon-key show-polygon-key-public show-access-token show-access-token-public apply-polygon-secret apply-polygon-secret-public check-polygon-secret check-polygon-secret-public

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

show-api-key-public:
	@kubectl get secret api-secret -n $(PUBLIC_NAMESPACE) -o jsonpath='{.data.API_SECRET_KEY}' | base64 -d; echo

show-polygon-key:
	@kubectl get secret polygon-secret -n $(NAMESPACE) -o jsonpath='{.data.POLYGON_API_KEY}' | base64 -d; echo

show-polygon-key-public:
	@kubectl get secret polygon-secret -n $(PUBLIC_NAMESPACE) -o jsonpath='{.data.POLYGON_API_KEY}' | base64 -d; echo

apply-polygon-secret:
	@test -n "$(POLYGON_API_KEY)" || (echo "POLYGON_API_KEY is required"; exit 1)
	@test -n "$(AWS_ACCESS_KEY_ID)" || (echo "AWS_ACCESS_KEY_ID is required"; exit 1)
	@test -n "$(AWS_SECRET_ACCESS_KEY)" || (echo "AWS_SECRET_ACCESS_KEY is required"; exit 1)
	kubectl create secret generic polygon-secret \
		--from-literal=POLYGON_API_KEY="$(POLYGON_API_KEY)" \
		--from-literal=AWS_ACCESS_KEY_ID="$(AWS_ACCESS_KEY_ID)" \
		--from-literal=AWS_SECRET_ACCESS_KEY="$(AWS_SECRET_ACCESS_KEY)" \
		--namespace=$(NAMESPACE) \
		--dry-run=client -o yaml | kubectl apply -f -

apply-polygon-secret-public:
	@test -n "$(POLYGON_API_KEY)" || (echo "POLYGON_API_KEY is required"; exit 1)
	@test -n "$(AWS_ACCESS_KEY_ID)" || (echo "AWS_ACCESS_KEY_ID is required"; exit 1)
	@test -n "$(AWS_SECRET_ACCESS_KEY)" || (echo "AWS_SECRET_ACCESS_KEY is required"; exit 1)
	kubectl create secret generic polygon-secret \
		--from-literal=POLYGON_API_KEY="$(POLYGON_API_KEY)" \
		--from-literal=AWS_ACCESS_KEY_ID="$(AWS_ACCESS_KEY_ID)" \
		--from-literal=AWS_SECRET_ACCESS_KEY="$(AWS_SECRET_ACCESS_KEY)" \
		--namespace=$(PUBLIC_NAMESPACE) \
		--dry-run=client -o yaml | kubectl apply -f -

check-polygon-secret:
	@echo "Namespace: $(NAMESPACE)"
	@for KEY in POLYGON_API_KEY AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do \
		if kubectl get secret polygon-secret -n $(NAMESPACE) -o jsonpath="{.data.$$KEY}" | grep -q .; then \
			echo "$$KEY: present"; \
		else \
			echo "$$KEY: missing"; \
			exit 1; \
		fi; \
	done

check-polygon-secret-public:
	@echo "Namespace: $(PUBLIC_NAMESPACE)"
	@for KEY in POLYGON_API_KEY AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do \
		if kubectl get secret polygon-secret -n $(PUBLIC_NAMESPACE) -o jsonpath="{.data.$$KEY}" | grep -q .; then \
			echo "$$KEY: present"; \
		else \
			echo "$$KEY: missing"; \
			exit 1; \
		fi; \
	done

show-access-token:
	@kubectl exec -n $(NAMESPACE) deploy/stock-radar-api -- python3 -c "from app.core.auth import create_access_token; print(create_access_token())"

show-access-token-public:
	@kubectl exec -n $(PUBLIC_NAMESPACE) deploy/stock-radar-api -- python3 -c "from app.core.auth import create_access_token; print(create_access_token())"

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
