#!/usr/bin/env bash
# Installs / updates the Altyn VPN Telegram bot on Ubuntu 22.04.
# Re-running it updates the code and keeps .env and the database.
set -euo pipefail

APP_DIR=/opt/altyn-bot
SERVICE=altyn-bot
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root: sudo bash install.sh" >&2
  exit 1
fi

echo "==> Installing system packages"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip tzdata

echo "==> Creating service user and folders"
id -u altynbot >/dev/null 2>&1 || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin altynbot
mkdir -p "$APP_DIR/data"
rm -rf "$APP_DIR/bot"
cp -r "$SRC_DIR/bot" "$SRC_DIR/requirements.txt" "$APP_DIR/"

echo "==> Installing Python packages"
[ -d "$APP_DIR/venv" ] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  echo "==> Creating $APP_DIR/.env"
  cp "$SRC_DIR/.env.example" "$APP_DIR/.env"
  read -rp  "Telegram bot token (from @BotFather): " BOT_TOKEN
  read -rp  "Admin Telegram user ID(s), comma-separated: " ADMIN_IDS
  read -rp  "Panel URL incl. base path (e.g. https://panel.example.com:2053/AbC123): " PANEL_URL
  read -rsp "3X-UI API token (Settings -> Security -> API Token): " PANEL_TOKEN; echo
  read -rp  "Paste one working vless:// link from the inbound: " SAMPLE_LINK
  export BOT_TOKEN ADMIN_IDS PANEL_URL PANEL_TOKEN SAMPLE_LINK
  python3 - "$APP_DIR/.env" <<'PY'
import os, re, sys
from urllib.parse import urlsplit

env = {k: os.environ[k].strip() for k in ("BOT_TOKEN", "ADMIN_IDS", "PANEL_URL", "PANEL_TOKEN")}
link = os.environ["SAMPLE_LINK"].strip()
m = re.match(r"^vless://[^@]+@([^#]+)", link)
if not m:
    sys.exit("That does not look like a vless:// link")
env["VLESS_TEMPLATE"] = "vless://{uuid}@" + m.group(1) + "#{remark}"
env["CDN_DOMAIN"] = urlsplit("vless://x@" + m.group(1)).hostname or ""

path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines()
for i, line in enumerate(lines):
    key = line.split("=", 1)[0]
    if key in env and not line.startswith("#"):
        lines[i] = f"{key}={env[key]}"
open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
else
  echo "==> Keeping existing $APP_DIR/.env"
fi

chown -R altynbot:altynbot "$APP_DIR"
chmod 600 "$APP_DIR/.env"

echo "==> Installing systemd service"
cp "$SRC_DIR/altyn-bot.service" "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null
systemctl restart "$SERVICE"
sleep 3
systemctl --no-pager --lines=15 status "$SERVICE" || true

echo
echo "Done. The bot sends you a status message on Telegram when it starts."
echo "Logs:     journalctl -u $SERVICE -f"
echo "Settings: nano $APP_DIR/.env   (then: systemctl restart $SERVICE)"
