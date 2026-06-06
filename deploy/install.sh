#!/usr/bin/env bash
# LinkShortify Bot — one-command installer (works on a fresh Ubuntu/Debian server)
# Usage: sudo bash deploy/install.sh   (run from the project root)

set -euo pipefail

# This script lives in deploy/ — the project root is its parent directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="linkshortify-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV_DIR="${INSTALL_DIR}/.venv"
MIN_PY_MINOR=10   # Python 3.10+

echo "================================================"
echo "  LinkShortify Bot Installer"
echo "  Install dir: ${INSTALL_DIR}"
echo "================================================"

# ── 1. Install Python if missing ──────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "==> Python3 not found. Installing..."
    apt-get update -qq
    apt-get install -y python3 python3-venv python3-pip
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
echo "==> Python ${PY_VERSION} found."

if [ "${PY_MINOR}" -lt "${MIN_PY_MINOR}" ]; then
    echo "==> Python 3.${MIN_PY_MINOR}+ required. Installing from deadsnakes PPA..."
    apt-get install -y software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -qq
    apt-get install -y python3.12 python3.12-venv python3.12-distutils
    PYTHON=python3.12
else
    PYTHON=python3
fi

# ── 2. Install system dependencies ────────────────────────────────────────────
echo "==> Installing system packages..."
apt-get install -y --no-install-recommends \
    python3-venv \
    curl \
    ca-certificates \
    2>/dev/null || true

# ── 3. Virtual environment ────────────────────────────────────────────────────
echo "==> Creating virtual environment..."
${PYTHON} -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

# ── 4. Install Python dependencies ───────────────────────────────────────────
echo "==> Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r "${INSTALL_DIR}/requirements.txt"
echo "==> Dependencies installed."

# ── 5. Check .env ─────────────────────────────────────────────────────────────
if [ ! -f "${INSTALL_DIR}/.env" ]; then
    if [ -f "${INSTALL_DIR}/.env.example" ]; then
        cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"
        echo ""
        echo "  !! .env created from .env.example"
        echo "  !! Edit ${INSTALL_DIR}/.env with your credentials before starting."
        echo ""
    else
        echo "[ERROR] No .env or .env.example found. Create .env manually."
        exit 1
    fi
else
    echo "==> .env found."
fi

# ── 6. Systemd service ────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo ""
    echo "==> Not running as root — skipping systemd setup."
    echo "    Re-run with: sudo bash install.sh"
    echo ""
    echo "==> To start manually:"
    echo "    cd ${INSTALL_DIR} && ${VENV_DIR}/bin/python run.py"
else
    CURRENT_USER="${SUDO_USER:-$(logname 2>/dev/null || whoami)}"
    echo "==> Installing systemd service (user: ${CURRENT_USER})..."

    cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=LinkShortify Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/run.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
    systemctl start "${SERVICE_NAME}"

    echo ""
    echo "================================================"
    echo "  Bot installed and started!"
    echo "  Status  : sudo systemctl status ${SERVICE_NAME}"
    echo "  Logs    : sudo journalctl -u ${SERVICE_NAME} -f"
    echo "  Restart : sudo systemctl restart ${SERVICE_NAME}"
    echo "  Stop    : sudo systemctl stop ${SERVICE_NAME}"
    echo "================================================"
fi
