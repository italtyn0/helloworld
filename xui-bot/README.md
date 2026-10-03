# Altyn VPN Telegram bot (3X-UI)

A Persian Telegram bot that lets coworkers request a VPN account, and lets the admin approve
it with one tap. On approval the bot creates a client on the 3X-UI inbound (15 GB, no expiry,
no device limit) and sends the coworker a subscription link and a VLESS link, with QR codes.

## How it works

**Coworker**
1. `/start`, then types their full name.
2. Shares their phone number with the "📱 ارسال شماره تماس" button (only their own contact is accepted).
3. Waits for approval, then receives their links.
4. Menu: 📊 remaining traffic · 🔗 my links · 📖 connection guide.
5. When their remaining traffic drops to `LOW_TRAFFIC_GB` (default 2 GB) the bot warns them once,
   with a "➕ درخواست حجم بیشتر" button. The same button is under the 📊 remaining traffic message.

**Admin**
- Each new request arrives with ✅ تایید / ❌ رد buttons.
- Each "more traffic" request arrives with ✅ تایید (+5 گیگ) / ❌ رد buttons. Approving adds
  `EXTRA_TRAFFIC_GB` (default 5 GB) to the user's quota in the panel and re-enables them if they had run out.
- 📋 pending requests (new users and "more traffic" requests) · 👥 users (per user: resend links, reset traffic, disable/enable, delete)
- 🔄 **تمدید ماهانه همه**: resets traffic for every active user and tells each of them. Press it when you renew the server.
- ℹ️ status: panel connection, inbound ID, subscription URL and user counts.

The client name in the panel is the name the coworker typed. Spaces become `_`, and `_2`, `_3` and so on is added if the name is already taken.
The comment field holds `name | phone`, and `tgId` is set to the coworker's Telegram ID.

## Install (Ubuntu 22.04, as root, on the same server as the panel)

```bash
git clone -b claude/cloud-setup-billing-mqc25r https://github.com/italtyn0/helloworld.git
cd helloworld/xui-bot
sudo bash install.sh
```

The installer asks for:
- the bot token from @BotFather
- the admin Telegram ID
- the panel URL, including its base path
- the panel API token (Settings → Security → API Token)
- one working `vless://` link from the inbound, used as the template for new users' links

The answers are written to `/opt/altyn-bot/.env` (mode 600), never to git.
When the bot starts it sends you a status message. Check that the inbound ID and subscription link in that message are correct.

To update later: `git pull && sudo bash install.sh`. Your `.env` and database are kept.

## Operations

```bash
journalctl -u altyn-bot -f          # logs
systemctl restart altyn-bot         # after editing /opt/altyn-bot/.env
```

Useful `.env` settings:
- `SUB_URL`: set it if the subscription link in the status message is wrong (e.g. `https://sub.example.com:2096/sub/`).
- `TRAFFIC_GB`: the quota for new users.
- `LOW_TRAFFIC_GB`, `TRAFFIC_CHECK_MINUTES`, `EXTRA_TRAFFIC_GB`: the low-traffic alert and how much an approved request adds.
- `INBOUND_ID`: skips looking up the inbound by its `INBOUND_REMARK`.
