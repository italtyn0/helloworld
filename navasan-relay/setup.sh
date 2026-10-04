#!/bin/sh
# Creates the relay login and starts the relay with Docker.
set -e
cd "$(dirname "$0")"

port="${RELAY_PORT:-8080}"
if command -v ss >/dev/null && ss -ltn | awk '{print $4}' | grep -qE "[:.]$port\$"; then
    if ! docker compose ps --status running 2>/dev/null | grep -q relay; then
        echo "Port $port is already used by something else (maybe x-ui)."
        echo "Pick another one, e.g.:  RELAY_PORT=8181 ./setup.sh"
        exit 1
    fi
fi

if [ ! -f htpasswd ]; then
    printf "Choose a username for the relay: "
    read -r user
    printf "Choose a password: "
    stty -echo; read -r pass; stty echo; echo
    printf '%s:%s\n' "$user" "$(openssl passwd -apr1 "$pass")" > htpasswd
    echo "Saved login to htpasswd"
fi

RELAY_PORT="$port" docker compose up -d
echo "Relay is running. Open http://<your-vps-ip>:$port/ in your browser."
echo "If it doesn't load, open port $port in your VPS firewall (e.g. ufw allow $port/tcp)."
