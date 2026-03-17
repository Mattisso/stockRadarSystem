NAMESPACE := stock-radar
REGISTRY := localhost:32000
HELM_DIR := helm/stock-radar

# ── Tilt (local K8s dev) ────────────────────────────────────────────
.PHONY: up down logs stop restart refresh

up:
	tilt up --host=0.0.0.0

down:
	tilt down
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found

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

# ── Cleanup ─────────────────────────────────────────────────────────
.PHONY: clean prune

clean:
	-helm uninstall stock-radar --namespace $(NAMESPACE) 2>/dev/null
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found

prune: clean
	docker system prune -af --volumes
