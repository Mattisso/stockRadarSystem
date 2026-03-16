# Stock Radar System — Tilt local K8s dev environment
# Usage: make up  (or: tilt up --host=0.0.0.0)

allow_k8s_contexts(["microk8s", "svcdeployer-context"])
default_registry("localhost:32000")

NAMESPACE = "stock-radar"
REGISTRY = "localhost:32000"

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

# ── Helm deploy ─────────────────────────────────────────────────────
helm_cmd = " ".join([
    "helm template stock-radar ./helm/stock-radar",
    "--namespace " + NAMESPACE,
    "--skip-tests",
    "--values helm/stock-radar/values.yaml",
    "--values helm/stock-radar/values.local.yaml",
    "--set api.image.repository=" + REGISTRY + "/stock-radar-api",
    "--set api.image.tag=tilt",
])

k8s_yaml(local(helm_cmd, quiet=True))

# ── K8s resources & port forwarding ─────────────────────────────────
k8s_resource(
    "stock-radar-api",
    port_forwards=["8000:8000"],
    labels=["app"],
)
