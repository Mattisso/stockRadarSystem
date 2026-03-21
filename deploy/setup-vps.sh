#!/usr/bin/env bash
# Stock Radar System — VPS Setup Script
# Covers BuildGuide sections 3–7: packages, IB Gateway, IBC, systemd, firewall.
# Designed to be idempotent — safe to re-run.
#
# Usage: sudo bash deploy/setup-vps.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IBC_VERSION="3.19.0"
IB_GATEWAY_VERSION="10.30.1t"  # Update to match your IBKR version
APP_DIR="/opt/stock-radar"
IBC_DIR="/opt/ibc"

# ── Helpers ──────────────────────────────────────────────────────────

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; exit 1; }

require_root() {
    [[ $EUID -eq 0 ]] || error "This script must be run as root (sudo)."
}

# ── 1. System Packages ──────────────────────────────────────────────

install_packages() {
    info "Installing system packages..."
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        xfce4 xfce4-goodies \
        tigervnc-standalone-server tigervnc-common \
        openjdk-11-jre-headless \
        python3 python3-venv python3-pip \
        postgresql-client \
        ufw unzip wget curl git
    info "System packages installed."
}

# ── 2. Service Users ────────────────────────────────────────────────

create_users() {
    info "Creating service users..."
    id -u ibc &>/dev/null        || useradd -r -m -d /home/ibc -s /bin/bash ibc
    id -u stockradar &>/dev/null || useradd -r -m -d /home/stockradar -s /bin/bash stockradar
    info "Service users ready."
}

# ── 3. IB Gateway ───────────────────────────────────────────────────

install_ib_gateway() {
    local installer="/tmp/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh"

    if [[ -d /opt/ibgateway ]]; then
        info "IB Gateway already installed, skipping."
        return
    fi

    if [[ ! -f "$installer" ]]; then
        warn "IB Gateway installer not found at $installer"
        warn "Download it from https://www.interactivebrokers.com/en/trading/ibgateway-stable.php"
        warn "Place it at $installer and re-run this script."
        return
    fi

    info "Installing IB Gateway..."
    chmod +x "$installer"
    "$installer" -q -dir /opt/ibgateway
    info "IB Gateway installed to /opt/ibgateway."
}

# ── 4. IBC (IB Controller) ──────────────────────────────────────────

install_ibc() {
    if [[ -d "$IBC_DIR/scripts" ]]; then
        info "IBC already installed, skipping."
        return
    fi

    info "Installing IBC ${IBC_VERSION}..."
    local archive="/tmp/IBCLinux-${IBC_VERSION}.zip"
    if [[ ! -f "$archive" ]]; then
        wget -q "https://github.com/IbcAlpha/IBC/releases/download/${IBC_VERSION}/IBCLinux-${IBC_VERSION}.zip" \
            -O "$archive"
    fi

    mkdir -p "$IBC_DIR"
    unzip -qo "$archive" -d "$IBC_DIR"
    chmod +x "$IBC_DIR"/scripts/*.sh

    # Deploy config template if no config exists yet
    if [[ ! -f "$IBC_DIR/ibc.ini" ]]; then
        cp "${SCRIPT_DIR}/ibc/ibc.ini.example" "$IBC_DIR/ibc.ini"
        warn "Copied ibc.ini.example → $IBC_DIR/ibc.ini — edit with real credentials!"
    fi

    chown -R ibc:ibc "$IBC_DIR"
    info "IBC installed to $IBC_DIR."
}

# ── 5. Application Directory ────────────────────────────────────────

setup_app_dir() {
    info "Setting up application directory..."
    mkdir -p "$APP_DIR"
    chown -R stockradar:stockradar "$APP_DIR"

    if [[ ! -d "$APP_DIR/venv" ]]; then
        sudo -u stockradar python3 -m venv "$APP_DIR/venv"
        info "Python venv created at $APP_DIR/venv."
    fi

    info "Application directory ready at $APP_DIR."
}

# ── 6. Systemd Services ─────────────────────────────────────────────

install_services() {
    info "Installing systemd services..."
    cp "${SCRIPT_DIR}/systemd/ibgateway.service" /etc/systemd/system/
    cp "${SCRIPT_DIR}/systemd/trading-engine.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable ibgateway.service trading-engine.service
    info "Systemd services installed and enabled."
    warn "Start with: systemctl start ibgateway && systemctl start trading-engine"
}

# ── 7. Firewall (UFW) ───────────────────────────────────────────────

configure_firewall() {
    info "Configuring firewall..."
    ufw --force enable
    ufw default deny incoming
    ufw default allow outgoing

    # SSH
    ufw allow 22/tcp

    # VNC (restrict to your IP in production)
    ufw allow 5901/tcp

    # Stock Radar API
    ufw allow 8000/tcp

    # IB Gateway API — localhost only (default, no rule needed)
    # Ports 4001/4002 should NOT be exposed externally.

    ufw reload
    info "Firewall configured."
}

# ── Main ─────────────────────────────────────────────────────────────

main() {
    require_root
    info "Stock Radar VPS Setup — starting..."
    install_packages
    create_users
    install_ib_gateway
    install_ibc
    setup_app_dir
    install_services
    configure_firewall
    info "Setup complete."
    echo ""
    echo "Next steps:"
    echo "  1. Edit $IBC_DIR/ibc.ini with your IBKR credentials"
    echo "  2. Deploy backend code to $APP_DIR/backend/"
    echo "  3. Install Python deps: $APP_DIR/venv/bin/pip install -r $APP_DIR/backend/requirements.txt"
    echo "  4. Create $APP_DIR/backend/.env (see backend/.env.example)"
    echo "  5. Start services: systemctl start ibgateway && systemctl start trading-engine"
    echo "  6. First-time only: VNC in to complete IB Gateway GUI login"
}

main "$@"
