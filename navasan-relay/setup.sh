#!/bin/sh
# Creates the relay login and starts the relay with Docker.
set -e
cd "$(dirname "$0")"

if [ ! -f htpasswd ]; then
    printf "Choose a username for the relay: "
    read -r user
    printf "Choose a password: "
    stty -echo; read -r pass; stty echo; echo
    printf '%s:%s\n' "$user" "$(openssl passwd -apr1 "$pass")" > htpasswd
    echo "Saved login to htpasswd"
fi

docker compose up -d
echo "Relay is running. Open http://<your-vps-ip>/ in your browser."
