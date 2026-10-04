# navasan relay

Lets you view https://www.navasan.net through your VPS, with no VPN.
Your browser only talks to the VPS; the VPS fetches the site for you and
passes it back, including the live price updates and charts.

## Requirements

- A VPS that **can** open navasan.net itself. Test from the VPS with
  `curl -sI https://www.navasan.net/`; you want `HTTP/2 200`.
- Docker with the compose plugin on the VPS.
- A free port, 8080 by default (`RELAY_PORT=8181 ./setup.sh` to change it),
  open in the VPS firewall.

## Setup

```sh
git clone <this repo> && cd helloworld/navasan-relay
./setup.sh
```

It asks for a username and password (so strangers can't use your relay),
then starts nginx. Open `http://<your-vps-ip>:8080/` and log in.

The relay runs in its own Docker container on its own port, so it sits next
to other services such as an x-ui panel without touching them. It stays off
port 80 because x-ui's certificate renewal (acme.sh) needs that port.

Stop it with `docker compose down`, and change the login by deleting
`htpasswd` and running `./setup.sh` again.

## Without Docker

Install nginx (`apt install nginx`), then:

```sh
sed 's/listen 80;/listen 8080;/' navasan.conf | sudo tee /etc/nginx/sites-enabled/navasan.conf
printf 'me:%s\n' "$(openssl passwd -apr1 'your-password')" | sudo tee /etc/nginx/htpasswd
sudo nginx -t && sudo systemctl reload nginx
```

## How it works

`navasan.conf` is an nginx reverse proxy that:

- forwards every page, script, and chart-data request to www.navasan.net;
- relays the live price WebSocket (`wss://ws2.navasan.net`) at `/ws2/`;
- relays jQuery from code.jquery.com at `/_jquery/`, so the page doesn't
  need any other site;
- rewrites the page's JavaScript so links and the WebSocket point back at
  the relay, and so the site's request token still uses the real hostname
  (otherwise the site rejects the live feed with `error 789`).

The site ties its session to the IP address that loaded the page, which
here is always the VPS. A VPS with one fixed outbound IP (the normal case)
works. Outbound IPs that rotate between connections break the live feed.

## HTTPS (recommended)

Plain HTTP sends your relay password unencrypted. If you have a domain
pointing at the VPS, put HTTPS in front with certbot
(`apt install certbot python3-certbot-nginx && certbot --nginx`) using the
non-Docker setup (first change `server_name _;` in `navasan.conf` to your
domain). The WebSocket switches to `wss://` automatically.
