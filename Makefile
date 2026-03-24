NAMESPACE := stock-radar
REGISTRY := localhost:32000
HELM_DIR := helm/stock-radar

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
.PHONY: ns secret status

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
.PHONY: tunnel-k8s tunnel-status

tunnel-k8s:
	@echo "Restarting K8s Port-Forwards and Tunnels..."
	-pkill -f "kubectl port-forward"
	-pkill -f "cloudflared"
	-tmux kill-session -t cf-backend 2>/dev/null || true
	-tmux kill-session -t cf-frontend 2>/dev/null || true
	@sleep 2
	# Start Port-Forwards
	kubectl port-forward svc/stock-radar-api 8000:8000 -n $(NAMESPACE) --address 0.0.0.0 > /dev/null 2>&1 &
	kubectl port-forward svc/stock-radar-frontend 4201:4200 -n $(NAMESPACE) --address 0.0.0.0 > /dev/null 2>&1 &
	@sleep 3
	# Start Tunnels in Tmux
	tmux new-session -d -s cf-backend 'cloudflared tunnel --url http://localhost:8000 --no-autoupdate 2>&1 | tee /tmp/cf_be.log'
	tmux new-session -d -s cf-frontend 'cloudflared tunnel --url http://localhost:4201 --no-autoupdate 2>&1 | tee /tmp/cf_fe.log'
	@echo "Waiting for URLs..."
	@sleep 12
	@echo "\n🚀 PUBLIC LINKS:"
	@echo "Frontend: $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' /tmp/cf_fe.log | head -n 1)"
	@echo "Backend:  $$(grep -o 'https://[a-z-]*\.trycloudflare\.com' /tmp/cf_be.log | head -n 1)/docs\n"

tunnel-status:
	@tmux ls 2>/dev/null | grep cf- || echo "No active tunnels."
	@ps aux | grep port-forward | grep -v grep || echo "No active port-forwards."

# ── API Key Management ─────────────────────────────────────────────
.PHONY: rotate-api-key show-api-key

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
