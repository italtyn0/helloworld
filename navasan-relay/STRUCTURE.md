# How the navasan relay works

## The big picture

```
 Your PC (browser)                Your VPS (95.182.91.213)                 The internet
┌──────────────────┐   :8181    ┌──────────────────────────────┐   HTTPS   ┌──────────────────────┐
│ http://VPS:8181/ │ ─────────► │ Docker container             │ ────────► │ www.navasan.net      │
│                  │            │  └─ nginx (the "relay")      │           │  pages, tables, data │
│  sees navasan    │ ◄───────── │      asks for your password, │ ────────► │ ws2.navasan.net      │
│  as if direct    │            │      fetches, rewrites,      │           │  live price ticks    │
└──────────────────┘            │      passes back             │ ────────► │ code.jquery.com      │
                                │                              │           │  a script the page   │
                                │ x-ui, Telegram bot: untouched│           │  needs               │
                                └──────────────────────────────┘           └──────────────────────┘
```

Your browser only ever talks to your VPS. The VPS does the actual visiting of
navasan.net and hands the result back. To navasan.net it looks like your VPS
is the visitor.

## The files

| File | What it is | Do you edit it? |
|---|---|---|
| `setup.sh` | Start script. Asks for a login the first time, saves the port, starts the relay. | No. Just run it. |
| `docker-compose.yml` | Tells Docker how to run the relay: which image (nginx), which port, memory cap, log limits. | Rarely. |
| `navasan.conf` | The relay's brain: the nginx configuration (explained below). | Only if the site changes. |
| `htpasswd` | Your relay username and scrambled password. Created by `setup.sh`, never uploaded to GitHub. | Delete it and rerun `setup.sh` to change the login. |
| `.env` | Remembers your port (`RELAY_PORT=8181`). Created by `setup.sh`. | Only to change the port. |
| `README.md` | Install instructions. | No. |

## What happens when you open the page

1. **Login.** nginx asks for the username and password from `htpasswd`. Without
   it nobody can use your VPS as a proxy.
2. **Page request.** Your browser asks the VPS for `/`. nginx asks
   `https://www.navasan.net/` for the same thing and gets the page back.
3. **Rewriting.** Before handing the page to you, nginx edits a few pieces of
   text in it (`sub_filter` lines in `navasan.conf`):
   - links to `https://www.navasan.net/...` become `/...`, so clicks stay on
     your relay;
   - the live connection address `wss://ws2.navasan.net/` becomes
     `ws://VPS:8181/ws2/`, so live prices also come through the relay;
   - the site builds a security token from the page's address. nginx makes it
     use `www.navasan.net` instead of your VPS's address; otherwise the site
     refuses the live feed with `error 789`;
   - `code.jquery.com` becomes `/_jquery/`, so your browser doesn't need any
     other site.
4. **Everything else the page loads** (styles, scripts, chart data, the table
   refreshes every 2 minutes) goes through the same path as step 2.
5. **Live prices.** The page opens a live connection (a WebSocket) to
   `/ws2/`. nginx keeps a matching connection open to `ws2.navasan.net` and
   passes every price tick straight through. If the connection drops, the page
   reconnects by itself after 15 seconds.

The `location` blocks in `navasan.conf` are the routing table:

| Address on your relay | Goes to |
|---|---|
| `/ws2/` | `wss://ws2.navasan.net/` (live ticks) |
| `/_jquery/` | `https://code.jquery.com/` |
| everything else | `https://www.navasan.net/` |

## Why it's set up this way

- **Docker:** keeps the relay separate from x-ui and your bot. Removing it
  (`docker compose down`) leaves nothing behind running.
- **Host network (`network_mode: host`):** your VPS has no route to Docker's
  internal network (common on VPN servers), so the relay uses the server's
  own network directly instead.
- **Port 8181, not 80:** x-ui's certificate renewal needs port 80, and 8080
  was already taken on your server.
- **One fixed IP:** navasan.net ties its session to the IP that loaded the
  page. Your VPS has one IP, so that works.

## Resource use on your VPS (1 core, 2 GB)

| Part | RAM | CPU |
|---|---|---|
| nginx relay | about 10 MB (measured: 2 MB master + 7 MB worker) | about 0% idle; a short blip when you load the page |
| Docker itself (dockerd + containerd) | about 80–120 MB | about 0% idle |
| **Total added** | **about 100–130 MB** | **close to nothing** |

Your server shows 512 MB used of 1.92 GB, with CPU averaging 25% and peaking
at 39%. That leaves about 1.4 GB of RAM free and plenty of CPU, so the relay
fits easily. Most of that CPU is your bot and x-ui, not the relay.

Bandwidth is small too: roughly 1–2 MB for each full page load, then a few
tens of KB per minute for the table refreshes and live ticks while the page is open.

### Could it become a problem later?

Unlikely, because of the limits it already has:

- **Memory cap:** the container is limited to 64 MB (`mem_limit`), so even if
  something went wrong it can't eat your bot's memory.
- **Log cap:** Docker keeps at most 2 MB of relay logs (`max-size`,
  `max-file`), so the disk doesn't slowly fill up.
- **Single user:** it's password-protected, so only you use it; load doesn't
  grow on its own.

Things that *could* change:

- **If navasan.net changes its page code**, live prices may stop through the
  relay (tables would most likely keep working). The fix is updating the
  `sub_filter` lines in `navasan.conf`.
- **If RAM ever gets tight**, you can run nginx without Docker and save the
  ~100 MB Docker uses (see "Without Docker" in `README.md`).

## Everyday commands

Run these in `~/navasan/navasan-relay` on the VPS:

| Want to | Command |
|---|---|
| Check it's running | `docker compose ps` |
| See its resource use | `docker stats --no-stream` |
| See recent logs | `docker compose logs --tail 20` |
| Restart it | `docker compose restart` |
| Stop it | `docker compose down` |
| Start it again | `./setup.sh` |
| Get updates from GitHub | `git pull && ./setup.sh` |
| Change the password | `rm htpasswd && ./setup.sh` |
| Change the port | `RELAY_PORT=8282 ./setup.sh` |

It starts by itself after a VPS reboot.
