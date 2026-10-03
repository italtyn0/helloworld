"""Web form for people who cannot reach Telegram.

They send their name and phone here, get a private status page (/s/<token>) that shows the
admin's decision, their links and remaining traffic, and can ask for more traffic from it.
If they later start the bot and share the same phone number, the account moves to Telegram
(see bot.link_web_user) and the status page keeps working.
"""
import base64
import html
import logging
import secrets
import time
from collections import defaultdict, deque

from aiohttp import web

from . import bot as B
from . import texts as T
from .panel import PanelError

log = logging.getLogger(__name__)

REQUESTS_PER_IP_PER_HOUR = 5
MAX_PENDING_WEB = 50  # stops a flood of fake requests from burying real ones

CSS = """
:root { --bg:#f4f6fb; --card:#fff; --text:#1d2433; --muted:#667085; --accent:#2563eb; --ok:#15803d;
        --warn:#b45309; --bad:#b91c1c; --border:#e4e7ec; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0f1420; --card:#182030; --text:#e7eaf0; --muted:#98a2b3; --accent:#60a5fa; --ok:#4ade80;
          --warn:#fbbf24; --bad:#f87171; --border:#2a3446; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); line-height:1.8;
       font-family:Vazirmatn, Tahoma, "Segoe UI", sans-serif; }
main { max-width:520px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:1.35rem; margin:0 0 4px; }
.sub { color:var(--muted); margin:0 0 20px; font-size:.95rem; }
.card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:18px; margin-bottom:16px; }
label { display:block; font-weight:600; margin:12px 0 6px; }
input[type=text], input[type=tel] { width:100%; padding:12px; font-size:1rem; border-radius:10px;
       border:1px solid var(--border); background:var(--bg); color:var(--text); font-family:inherit; }
button { width:100%; margin-top:18px; padding:12px; font-size:1rem; font-weight:700; border:0;
         border-radius:10px; background:var(--accent); color:#fff; cursor:pointer; font-family:inherit; }
.hp { position:absolute; width:1px; height:1px; padding:0; border:0; opacity:0; overflow:hidden; pointer-events:none; }
.err { color:var(--bad); font-weight:600; }
.ok { color:var(--ok); } .warn { color:var(--warn); } .bad { color:var(--bad); }
.status { font-size:1.15rem; font-weight:700; }
textarea { width:100%; direction:ltr; text-align:left; font:13px/1.5 ui-monospace, monospace; padding:10px;
           border-radius:10px; border:1px solid var(--border); background:var(--bg); color:var(--text);
           resize:none; word-break:break-all; }
.qr { display:block; margin:10px auto 0; width:220px; max-width:100%; background:#fff; padding:8px; border-radius:10px; }
.row { display:flex; justify-content:space-between; gap:8px; }
.note { color:var(--muted); font-size:.9rem; }
"""

PAGE = """<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">{refresh}
<title>VPN آلتن</title><style>{css}</style></head>
<body><main>{body}</main></body></html>"""


def esc(value) -> str:
    return html.escape(str(value or ""))


def page(body: str, status: int = 200, refresh: bool = False) -> web.Response:
    resp = web.Response(
        text=PAGE.format(css=CSS, body=body, refresh='\n<meta http-equiv="refresh" content="60">' if refresh else ""),
        content_type="text/html", status=status,
    )
    # Status pages carry a secret token in the URL: keep it out of caches and referrers.
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp


def form_page(error: str = "", name: str = "", phone: str = "") -> web.Response:
    err = f'<p class="err">{esc(error)}</p>' if error else ""
    return page(f"""
<h1>درخواست VPN آلتن</h1>
<p class="sub">اگر به تلگرام دسترسی ندارید، از همین‌جا درخواست بدهید.</p>
<div class="card">
  {err}
  <form method="post" action="/request" autocomplete="on">
    <label for="name">نام و نام خانوادگی</label>
    <input id="name" name="name" type="text" required maxlength="40" value="{esc(name)}">
    <label for="phone">شماره موبایل</label>
    <input id="phone" name="phone" type="tel" required inputmode="tel" dir="ltr"
           placeholder="09121234567" value="{esc(phone)}">
    <input class="hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
    <button type="submit">ارسال درخواست</button>
  </form>
</div>
<p class="note">پس از ارسال، صفحه‌ای مخصوص شما باز می‌شود. آن را ذخیره (Bookmark) کنید؛
نتیجه‌ی بررسی و لینک‌های اتصال همان‌جا نمایش داده می‌شود.</p>""", status=400 if error else 200)


def qr_img(data: str) -> str:
    b64 = base64.b64encode(B.qr_png(data).getvalue()).decode()
    return f'<img class="qr" alt="QR" src="data:image/png;base64,{b64}">'


def link_block(title: str, link: str) -> str:
    rows = min(6, len(link) // 40 + 2)
    return f"""<div class="card"><b>{title}</b>
<textarea readonly rows="{rows}" onclick="this.select()">{esc(link)}</textarea>
<p class="note">روی لینک بزنید تا انتخاب شود، سپس کپی کنید. یا QR را با برنامه اسکن کنید.</p>{qr_img(link)}</div>"""


class WebApp:
    def __init__(self, ctx):
        self.ctx = ctx
        self.hits: dict[str, deque] = defaultdict(deque)

    # ---- helpers
    def rate_limited(self, ip: str) -> bool:
        now = time.time()
        q = self.hits[ip]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= REQUESTS_PER_IP_PER_HOUR:
            return True
        q.append(now)
        return False

    def telegram_hint(self) -> str:
        username = getattr(self.ctx.bot, "username", None)
        bot = f'<a href="https://t.me/{esc(username)}">@{esc(username)}</a>' if username else "ربات"
        return (f'<p class="note">اگر بعداً به تلگرام دسترسی پیدا کردید، {bot} را استارت کنید و '
                f'<b>همین شماره</b> را بفرستید تا اکانتتان به تلگرام وصل شود. این صفحه هم کار می‌کند.</p>')

    # ---- routes
    async def index(self, request: web.Request) -> web.Response:
        return form_page()

    async def submit(self, request: web.Request) -> web.Response:
        data = await request.post()
        if data.get("website"):  # honeypot filled in: a bot, not a person
            return form_page("درخواست نامعتبر است.")
        raw_name, raw_phone = str(data.get("name", "")), str(data.get("phone", ""))
        name = B.clean_name(raw_name)
        if not name:
            return form_page("نام معتبر نیست. نام و نام خانوادگی را (بین ۲ تا ۴۰ حرف) بنویسید.", raw_name, raw_phone)
        phone = B.normalize_phone(raw_phone)
        if not phone:
            return form_page("شماره معتبر نیست. مثلاً 09121234567 بنویسید.", raw_name, raw_phone)
        if self.rate_limited(request.remote or "?"):
            return form_page("تعداد درخواست‌ها زیاد است. لطفاً یک ساعت دیگر دوباره تلاش کنید.", raw_name, raw_phone)
        db = B.db(self.ctx)
        if db.phone_in_use(phone):
            return form_page("این شماره قبلاً ثبت شده است. اگر لینک صفحه‌ی خود را ندارید با مدیر تماس بگیرید.",
                             raw_name, raw_phone)
        if sum(1 for r in db.by_status("pending") if r["tg_id"] < 0) >= MAX_PENDING_WEB:
            return form_page("در حال حاضر امکان ثبت درخواست نیست. لطفاً بعداً تلاش کنید.", raw_name, raw_phone)

        token = secrets.token_urlsafe(18)
        tg_id = db.add_web_request(name, phone, token)
        text, kb = B.request_card(db.get(tg_id))
        for admin_id in B.cfg(self.ctx).admin_ids:
            await B.notify(self.ctx, admin_id, text, reply_markup=kb)
        raise web.HTTPSeeOther(f"/s/{token}")

    async def status(self, request: web.Request) -> web.Response:
        row = B.db(self.ctx).by_token(request.match_info["token"])
        if not row:
            return page('<h1>صفحه پیدا نشد</h1><p class="sub">این لینک معتبر نیست یا اکانت حذف شده است.</p>'
                        '<p><a href="/">ثبت درخواست جدید</a></p>', status=404)
        head = f'<h1>سلام {esc(row["name"])} 👋</h1><p class="sub">این صفحه مخصوص شماست. آن را ذخیره کنید.</p>'
        st = row["status"]
        if st == "pending":
            return page(head + '<div class="card"><p class="status warn">⏳ درخواست شما در حال بررسی است</p>'
                        '<p>پس از تایید مدیر، لینک‌های اتصال همین‌جا نمایش داده می‌شود. '
                        'این صفحه هر دقیقه خودکار به‌روز می‌شود.</p></div>' + self.telegram_hint(), refresh=True)
        if st == "rejected":
            return page(head + '<div class="card"><p class="status bad">❌ درخواست شما تایید نشد</p>'
                        '<p><a href="/">ثبت درخواست دوباره</a></p></div>')
        if st == "disabled":
            return page(head + '<div class="card"><p class="status bad">⛔️ اکانت شما غیرفعال شده است</p>'
                        '<p>برای پیگیری با مدیر تماس بگیرید.</p></div>')
        return page(head + await self.account_html(row, request.query.get("more")) + self.telegram_hint())

    async def account_html(self, row, more_flag: str | None) -> str:
        ctx = self.ctx
        c = B.cfg(ctx)
        parts = []
        try:
            t = await B.panel(ctx).client_traffic(row["email"])
            used, total = B.used_total(t)
            remaining = max(total - used, 0)
            low = total > 0 and remaining <= c.low_traffic_gb * B.GB
            state = '<span class="ok">🟢 فعال</span>' if t.get("enable", True) else \
                '<span class="bad">🔴 غیرفعال (حجم تمام شده)</span>'
            parts.append(f"""<div class="card"><p class="status">📊 وضعیت اکانت</p>
<div class="row"><span>وضعیت</span><span>{state}</span></div>
<div class="row"><span>مصرف شده</span><span>{B.gb(used)} گیگابایت</span></div>
<div class="row"><span>حجم کل</span><span>{B.gb(total)} گیگابایت</span></div>
<div class="row"><span>باقی‌مانده</span><b class="{'warn' if low else 'ok'}">{B.gb(remaining)} گیگابایت</b></div>
{'<p class="warn">⚠️ حجم شما رو به اتمام است.</p>' if low else ''}
{self.more_html(row, more_flag)}</div>""")
        except PanelError as exc:
            log.warning("web traffic lookup failed for %s: %s", row["email"], exc)
            parts.append('<div class="card"><p class="warn">⚠️ دریافت میزان مصرف فعلاً ممکن نیست.</p></div>')

        sub, vless = await B.build_links(ctx, row)
        if sub:
            parts.append(link_block("📥 لینک اشتراک (Subscription)", sub))
        if vless:
            parts.append(link_block("🔑 لینک کانفیگ (VLESS)", vless))
        parts.append(f'<div class="card" style="white-space:pre-line">{WEB_GUIDE}</div>')
        return "".join(parts)

    def more_html(self, row, more_flag: str | None) -> str:
        if more_flag == "sent":
            return '<p class="ok">✅ درخواست حجم بیشتر برای مدیر ارسال شد.</p>'
        if row["extra_requested_at"]:
            return '<p class="note">⏳ درخواست حجم بیشتر شما در حال بررسی است.</p>'
        return (f'<form method="post" action="/s/{esc(row["web_token"])}/more">'
                f'<button type="submit">{T.BTN_MORE_TRAFFIC}</button></form>')

    async def more(self, request: web.Request) -> web.Response:
        token = request.match_info["token"]
        row = B.db(self.ctx).by_token(token)
        if not row:
            raise web.HTTPNotFound()
        if row["status"] == "approved":
            await B.submit_more(self.ctx, row)
        raise web.HTTPSeeOther(f"/s/{token}?more=sent")


WEB_GUIDE = (
    "📖 <b>راهنمای اتصال</b>\n"
    "<b>۱.</b> برنامه نصب کنید: اندروید v2rayNG یا Hiddify، آیفون V2Box یا Streisand، ویندوز v2rayN یا Hiddify.\n"
    "<b>۲.</b> لینک اشتراک بالا را کپی کنید و در برنامه گزینه‌ی Import from clipboard یا Add subscription را بزنید "
    "(یا QR را اسکن کنید).\n"
    "<b>۳.</b> اشتراک را Update کنید، کانفیگ را انتخاب و وصل شوید.\n"
    "💡 اگر لینک اشتراک کار نکرد، لینک کانفیگ VLESS را به همان روش اضافه کنید."
)


async def start_web(ctx, host: str, port: int) -> web.AppRunner:
    app_ = WebApp(ctx)
    app = web.Application(client_max_size=16 * 1024)
    app.add_routes([
        web.get("/", app_.index),
        web.post("/request", app_.submit),
        web.get(r"/s/{token:[A-Za-z0-9_-]{16,64}}", app_.status),
        web.post(r"/s/{token:[A-Za-z0-9_-]{16,64}}/more", app_.more),
    ])
    runner = web.AppRunner(app, access_log=None)  # no access log: status URLs contain the secret token
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    log.info("web form listening on http://%s:%s/", host, port)
    return runner
