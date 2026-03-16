#!/bin/bash
set -euo pipefail

NAMESPACE="stock-radar"
SECRET_NAME="postgres-secret"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Extracting PostgreSQL credentials from K8s secret..."
PGUSER=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.PGUSER}' | base64 -d)
PGPASSWORD=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.PGPASSWORD}' | base64 -d)
PGHOST=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.PGHOST}' 2>/dev/null | base64 -d || echo "localhost")
PGPORT=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.PGPORT}' 2>/dev/null | base64 -d || echo "5434")

echo "==> Writing secrets.auto.tfvars..."
cat > "$SCRIPT_DIR/secrets.auto.tfvars" <<EOF
pg_superuser          = "$PGUSER"
pg_superuser_password = "$PGPASSWORD"
pg_host               = "$PGHOST"
pg_port               = $PGPORT
app_role_password     = "$PGPASSWORD"
EOF

echo "==> Running Terraform..."
cd "$SCRIPT_DIR"
terraform init
terraform apply --auto-approve

echo "==> Capturing Terraform outputs..."
DB_URL=$(terraform output -raw database_url)
SCHEMA_NAME=$(terraform output -raw schema_name)
APP_ROLE=$(terraform output -raw app_role_name)

echo "==> Generating backend/.env..."
cat > "$SCRIPT_DIR/../../backend/.env" <<EOF
PGUSER=$PGUSER
PGHOST=$PGHOST
PGPORT=$PGPORT
PGPASSWORD=$PGPASSWORD
PGDATABASE=stock_radar
DATABASE_URL=$DB_URL
API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=change-me-in-production
TRADING_MODE=paper
MAX_POSITION_SIZE=5000.0
MAX_CONCURRENT_POSITIONS=5
STOP_LOSS_PCT=0.05
DAILY_LOSS_LIMIT=500.0
TARGET_PROFIT_PER_SHARE_MIN=0.10
TARGET_PROFIT_PER_SHARE_MAX=0.25
UNIVERSE_MIN_PRICE=1.0
UNIVERSE_MAX_PRICE=10.0
UNIVERSE_MIN_VOLUME=100000
EOF

echo "==> Done. Database provisioned, .env generated."
echo "    Schema: $SCHEMA_NAME"
echo "    Role:   $APP_ROLE"
