# Stock Radar System — Tilt local K8s dev environment
# Usage: make up  (or: tilt up --host=0.0.0.0)

allow_k8s_contexts(["microk8s", "svcdeployer-context"])
default_registry("localhost:32000")

NAMESPACE = "stock-radar"
REGISTRY = "localhost:32000"
LOCAL_API_FORWARD_PORT = "18100"

# ── Global ignores ──────────────────────────────────────────────────
WATCH_IGNORES = [
    "**/__pycache__",
    "**/*.pyc",
    "**/.pytest_cache",
    "**/.ruff_cache",
    "**/.git",
    "**/coverage",
    "**/tmp",
    "**/.cache",
    "**/*.log",
    "terraform/.terraform*",
    "helm/**/*.tgz",
    "**/.env",
    "**/venv",
    "**/.venv",
    "tests/",
    ".claude/",
]

DOCKER_IGNORE = [
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".git",
    "coverage",
    "tmp",
    ".cache",
    "*.log",
    ".env",
    "venv",
    ".venv",
    "helm",
    "terraform/.terraform*",
    "tests",
    ".claude",
]

# ── Docker builds ───────────────────────────────────────────────────
docker_build(
    REGISTRY + "/stock-radar-api",
    context=".",
    dockerfile="backend/Dockerfile_dev",
    only=[
        "backend/app",
        "backend/alembic",
        "backend/alembic.ini",
        "backend/requirements.txt",
        "backend/pyproject.toml",
        "backend/docker-entrypoint_dev.sh",
    ],
    ignore=DOCKER_IGNORE,
    live_update=[
        sync("backend/app", "/app/app"),
        sync("backend/alembic", "/app/alembic"),
    ],
)

docker_build(
    REGISTRY + "/stock-radar-frontend",
    context=".",
    dockerfile="frontend/Dockerfile_prod",
    only=[
        "frontend/docker-entrypoint.sh",
        "frontend/src",
        "frontend/public",
        "frontend/angular.json",
        "frontend/runtime-config.template.js",
        "frontend/tsconfig.json",
        "frontend/tsconfig.app.json",
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/nginx.conf",
    ],
    ignore=DOCKER_IGNORE,
)

# ── Helm deploy ─────────────────────────────────────────────────────
helm_cmd = " ".join([
    "helm template stock-radar ./helm/stock-radar",
    "--namespace " + NAMESPACE,
    "--skip-tests",
    "--values helm/stock-radar/values.yaml",
    "--values helm/stock-radar/values.local.yaml",
    "--set api.image.repository=" + REGISTRY + "/stock-radar-api",
    "--set api.image.tag=tilt",
    "--set frontend.image.repository=" + REGISTRY + "/stock-radar-frontend",
    "--set frontend.image.tag=tilt",
])

k8s_yaml(local(helm_cmd, quiet=True))

# ── K8s resources & port forwarding ─────────────────────────────────

# RBAC must be applied before any workload that references the ServiceAccount
k8s_resource(
    new_name="rbac",
    objects=[
        "svcdeployer:serviceaccount",
        "svcdeployer-role:role",
        "svcdeployer-clusterrole:clusterrole",
        "svcdeployer-rolebinding:rolebinding",
        "svcdeployer-binding:clusterrolebinding",
    ],
    labels=["infra"],
)

k8s_resource(
    "check-secrets",
    resource_deps=["rbac"],
    labels=["infra"],
)

k8s_resource(
    "stock-radar-api",
    port_forwards=[LOCAL_API_FORWARD_PORT + ":8000"],
    resource_deps=["rbac"],
    labels=["app"],
)

k8s_resource(
    "stock-radar-frontend",
    port_forwards=["4201:4200"],
    resource_deps=["rbac", "stock-radar-api"],
    labels=["app"],
)

k8s_resource(
    "stock-radar-prometheus",
    port_forwards=["9090:9090"],
    labels=["monitoring"],
    objects=[
        "stock-radar-prometheus-config:configmap",
    ],
)

k8s_resource(
    "stock-radar-grafana",
    port_forwards=["3000:3000"],
    resource_deps=["stock-radar-prometheus"],
    labels=["monitoring"],
    objects=[
        "stock-radar-grafana-datasources:configmap",
        "stock-radar-grafana-dashboards-provider:configmap",
        "stock-radar-grafana-dashboard:configmap",
    ],
)
