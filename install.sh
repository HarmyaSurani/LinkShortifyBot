#!/usr/bin/env bash
# LinkShortify Bot — one-command installer
# Usage: bash install.sh

set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="linkshortify-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV_DIR="${INSTALL_DIR}/.venv"
PYTHON="python3"

echo "==> LinkShortify Bot Installer"
echo "    Install dir : ${INSTALL_DIR}"

# ── 1. Check Python ───────────────────────────────────────────────────────────
if ! command -v ${PYTHON} &>/dev/null; then
    echo "[ERROR] python3 not found. Install Python 3.13+ first."
    exit 1
fi

PY_VERSION=$(${PYTHON} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "    Python       : ${PY_VERSION}"

# ── 2. Virtual environment ────────────────────────────────────────────────────
echo "==> Creating virtual environment..."
${PYTHON} -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

# ── 3. Install dependencies ───────────────────────────────────────────────────
echo "==> Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r "${INSTALL_DIR}/requirements.txt" --quiet
echo "    Dependencies installed."

# ── 4. Check .env ─────────────────────────────────────────────────────────────
if [ ! -f "${INSTALL_DIR}/.env" ]; then
    echo "==> No .env found — copying from .env.example"
    cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"
    echo ""
    echo "  !! IMPORTANT: Edit ${INSTALL_DIR}/.env and fill in your credentials."
    echo "  !! Then re-run: sudo systemctl start ${SERVICE_NAME}"
    echo ""
fi

# ── 5. Systemd service (requires root) ───────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo "==> Skipping systemd setup (not root). Run with sudo to install service."
else
    CURRENT_USER="${SUDO_USER:-$(whoami)}"
    echo "==> Installing systemd service as user: ${CURRENT_USER}"

    cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=LinkShortify Telegram Bot
After=network.target mongod.service
Wants=mongod.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/bot.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
    systemctl start "${SERVICE_NAME}"

    echo "==> Service installed and started."
    echo "    Status  : sudo systemctl status ${SERVICE_NAME}"
    echo "    Logs    : sudo journalctl -u ${SERVICE_NAME} -f"
    echo "    Restart : sudo systemctl restart ${SERVICE_NAME}"
fi

echo ""
echo "==> Installation complete!"
