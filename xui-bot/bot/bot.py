import asyncio
import html
import io
import logging
import re
import secrets
import string
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import qrcode
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LinkPreviewOptions,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)

from . import texts as T
from .config import Config
from .db import DB
from .panel import GB, Panel, PanelAPIError, PanelError

log = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("Asia/Tehran")
except Exception:  # tzdata missing
    TZ = timezone.utc

USER_KB = ReplyKeyboardMarkup([[T.BTN_USAGE, T.BTN_LINKS], [T.BTN_GUIDE]], resize_keyboard=True)
ADMIN_KB = ReplyKeyboardMarkup([[T.BTN_PENDING, T.BTN_USERS], [T.BTN_RENEW_ALL, T.BTN_STATUS]], resize_keyboard=True)
MORE_KB = InlineKeyboardMarkup([[InlineKeyboardButton(T.BTN_MORE_TRAFFIC, callback_data="more")]])
PHONE_KB = ReplyKeyboardMarkup(
    [[KeyboardButton(T.BTN_SHARE_PHONE, request_contact=True)]], resize_keyboard=True, one_time_keyboard=True
)

_INVISIBLE = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_UNSAFE_EMAIL = re.compile(r"[\s\\/#?%&\"'<>`|,;:@{}\[\]]+")


# ---------------------------------------------------------------- helpers
def cfg(ctx) -> Config:
    return ctx.bot_data["config"]


def db(ctx) -> DB:
    return ctx.bot_data["db"]


def panel(ctx) -> Panel:
    return ctx.bot_data["panel"]


def is_admin(ctx, user_id: int) -> bool:
    return user_id in cfg(ctx).admin_ids


def esc(value) -> str:
    return html.escape(str(value or ""))


def gb(n_bytes: int) -> str:
    return T.fa(f"{n_bytes / GB:.2f}")


def used_total(t: dict) -> tuple[int, int]:
    return int(t.get("up", 0)) + int(t.get("down", 0)), int(t.get("total", 0))


def tehran_time(ts: int) -> str:
    return T.fa(datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M"))


def username_of(row) -> str:
    return f"@{esc(row['username'])}" if row["username"] else "—"


def clean_name(text: str) -> str | None:
    name = " ".join(_INVISIBLE.sub("", text).split())
    letters = sum(ch.isalpha() for ch in name)
    if not (2 <= len(name) <= 40) or letters < 2 or name.startswith("/"):
        return None
    return name


def normalize_phone(text: str) -> str | None:
    """'+98 912…', '0912…', '912…', '0098912…' (Persian digits too) -> '+98912…'. None if it is not a number."""
    raw = text.translate(_DIGITS).strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    elif raw.startswith("0") and len(digits) == 11:  # Iranian local format
        digits = "98" + digits[1:]
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "98" + digits
    if not 10 <= len(digits) <= 15 or re.sub(r"[\d\s+()\-]", "", raw):
        return None
    return "+" + digits


def email_base(name: str) -> str:
    return _UNSAFE_EMAIL.sub("_", name).strip("_")[:32] or "user"


def random_sub_id() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def qr_png(data: str) -> io.BytesIO:
    buf = io.BytesIO()
    qrcode.make(data, box_size=8, border=2).save(buf, format="PNG")
    buf.seek(0)
    return buf


async def inbound_id(ctx) -> int:
    c = cfg(ctx)
    if c.inbound_id:
        return c.inbound_id
    if "inbound_id" not in ctx.bot_data:
        ctx.bot_data["inbound_id"] = await panel(ctx).find_inbound_id(c.inbound_remark)
    return ctx.bot_data["inbound_id"]


async def sub_base(ctx) -> str | None:
    c = cfg(ctx)
    if c.sub_url:
        return c.sub_url if c.sub_url.endswith("/") else c.sub_url + "/"
    if ctx.bot_data.get("sub_base") is None:
        try:
            ctx.bot_data["sub_base"] = await panel(ctx).subscription_base()
        except PanelError as exc:
            log.warning("could not read subscription settings: %s", exc)
            return None
    return ctx.bot_data["sub_base"]


async def build_links(ctx, row) -> tuple[str | None, str | None]:
    c = cfg(ctx)
    base = await sub_base(ctx)
    sub = base + row["sub_id"] if base and row["sub_id"] else None

    vless = None
    try:
        for link in await panel(ctx).client_links(row["email"]):
            if link.startswith("vless://") and c.cdn_domain and c.cdn_domain in link:
                vless = link
                break
    except PanelError as exc:
        log.warning("client_links failed for %s: %s", row["email"], exc)
    if vless is None and c.vless_template and row["uuid"]:
        remark = quote(f"{c.inbound_remark}-{row['email']}", safe="-_")
        vless = c.vless_template.replace("{uuid}", row["uuid"]).replace("{remark}", remark)
    return sub, vless


async def send_links(ctx, row, header: str, chat_id: int | None = None) -> None:
    sub, vless = await build_links(ctx, row)
    text = header
    if sub:
        text += T.LINK_SUB.format(sub=esc(sub))
    if vless:
        text += T.LINK_VLESS.format(vless=esc(vless))
    text += T.LINKS_FOOTER
    to_user = chat_id is None
    chat_id = row["tg_id"] if to_user else chat_id
    await ctx.bot.send_message(chat_id, text, reply_markup=USER_KB if to_user else None)
    if sub:
        await ctx.bot.send_photo(chat_id, qr_png(sub), caption=T.QR_SUB)
    if vless:
        await ctx.bot.send_photo(chat_id, qr_png(vless), caption=T.QR_VLESS)


def request_card(row) -> tuple[str, InlineKeyboardMarkup]:
    text = T.NEW_REQUEST.format(
        name=esc(row["name"]), phone=esc(row["phone"]), tg_id=row["tg_id"] if row["tg_id"] > 0 else "—",
        username=username_of(row) if row["tg_id"] > 0 else T.WEB_SOURCE, time=tehran_time(row["created_at"]),
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(T.BTN_APPROVE, callback_data=f"ap:{row['tg_id']}"),
        InlineKeyboardButton(T.BTN_REJECT, callback_data=f"rj:{row['tg_id']}"),
    ]])
    return text, kb


async def extra_card(ctx, row) -> tuple[str, InlineKeyboardMarkup]:
    try:
        used, total = used_total(await panel(ctx).client_traffic(row["email"]))
        usage = T.CARD_USAGE.format(used=gb(used), total=gb(total), panel_status=f"{gb(max(total - used, 0))} باقی‌مانده")
    except PanelError as exc:
        usage = T.CARD_USAGE_ERR.format(error=esc(exc))
    text = T.NEW_MORE_REQUEST.format(
        name=esc(row["name"]), phone=esc(row["phone"]), tg_id=row["tg_id"], email=esc(row["email"]),
        usage=usage, time=tehran_time(row["extra_requested_at"]),
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(T.BTN_APPROVE_MORE.format(gb=T.fa(cfg(ctx).extra_traffic_gb)), callback_data=f"xa:{row['tg_id']}"),
        InlineKeyboardButton(T.BTN_REJECT, callback_data=f"xr:{row['tg_id']}"),
    ]])
    return text, kb


async def notify(ctx, chat_id: int, text: str, **kwargs) -> bool:
    if chat_id <= 0:  # web user without Telegram; they read their status on the web page
        return False
    try:
        await ctx.bot.send_message(chat_id, text, **kwargs)
        return True
    except Exception as exc:  # user blocked the bot, etc.
        log.warning("could not message %s: %s", chat_id, exc)
        return False


# ---------------------------------------------------------------- coworker flow
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if is_admin(ctx, user.id):
        await update.message.reply_text(T.ADMIN_MENU, reply_markup=ADMIN_KB)
        return
    row = db(ctx).get(user.id)
    status = row["status"] if row else None
    if status in (None, "rejected", "awaiting_name"):
        db(ctx).start_registration(user.id, user.username)
        await update.message.reply_text(T.ASK_NAME, reply_markup=ReplyKeyboardRemove())
    elif status == "awaiting_phone":
        await update.message.reply_text(T.ASK_PHONE.format(name=esc(row["name"])), reply_markup=PHONE_KB)
    elif status == "pending":
        await update.message.reply_text(T.REQUEST_PENDING)
    elif status == "disabled":
        await update.message.reply_text(T.ACCOUNT_DISABLED, reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(T.USER_MENU, reply_markup=USER_KB)


async def on_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if is_admin(ctx, user.id):
        return
    row = db(ctx).get(user.id)
    if not row or row["status"] != "awaiting_phone":
        await update.message.reply_text(T.PRESS_START)
        return
    contact = update.message.contact
    if contact.user_id != user.id:
        await update.message.reply_text(T.NOT_OWN_CONTACT, reply_markup=PHONE_KB)
        return
    phone = normalize_phone(contact.phone_number) or "+" + contact.phone_number.lstrip("+")
    web_row = db(ctx).web_by_phone(phone)
    if web_row:
        await link_web_user(update, ctx, web_row)
        return
    db(ctx).update(user.id, phone=phone, username=user.username, status="pending", created_at=int(time.time()))
    await update.message.reply_text(T.REQUEST_SUBMITTED, reply_markup=ReplyKeyboardRemove())

    text, kb = request_card(db(ctx).get(user.id))
    for admin_id in cfg(ctx).admin_ids:
        await notify(ctx, admin_id, text, reply_markup=kb)


async def link_web_user(update: Update, ctx, web_row) -> None:
    user = update.effective_user
    db(ctx).link(web_row["tg_id"], user.id, user.username)
    row = db(ctx).get(user.id)
    if row["status"] == "pending":
        await update.message.reply_text(T.LINKED_PENDING, reply_markup=ReplyKeyboardRemove())
    elif row["status"] == "disabled":
        await update.message.reply_text(T.ACCOUNT_DISABLED, reply_markup=ReplyKeyboardRemove())
    else:
        try:
            await send_links(ctx, row, T.LINKED_HEADER.format(name=esc(row["name"])))
        except PanelError:
            await update.message.reply_text(T.USER_MENU, reply_markup=USER_KB)
    for admin_id in cfg(ctx).admin_ids:
        await notify(ctx, admin_id, T.ADMIN_LINKED.format(name=esc(row["name"]), phone=esc(row["phone"])))


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text.strip()
    if is_admin(ctx, user.id):
        await admin_text(update, ctx, text)
        return

    row = db(ctx).get(user.id)
    status = row["status"] if row else None
    if status is None:
        await update.message.reply_text(T.PRESS_START)
    elif status == "awaiting_name":
        name = clean_name(text)
        if not name:
            await update.message.reply_text(T.INVALID_NAME)
            return
        db(ctx).update(user.id, name=name, username=user.username, status="awaiting_phone")
        await update.message.reply_text(T.ASK_PHONE.format(name=esc(name)), reply_markup=PHONE_KB)
    elif status == "awaiting_phone":
        await update.message.reply_text(T.USE_PHONE_BUTTON, reply_markup=PHONE_KB)
    elif status == "pending":
        await update.message.reply_text(T.REQUEST_PENDING)
    elif status == "rejected":
        await update.message.reply_text(T.REQUEST_REJECTED)
    elif status == "disabled":
        await update.message.reply_text(T.ACCOUNT_DISABLED)
    elif text == T.BTN_USAGE:
        await show_usage(update, ctx, row)
    elif text == T.BTN_LINKS:
        try:
            await send_links(ctx, row, T.LINKS_HEADER)
        except PanelError:
            await update.message.reply_text(T.TRY_LATER)
    elif text == T.BTN_GUIDE:
        await update.message.reply_text(T.GUIDE, reply_markup=USER_KB)
    else:
        await update.message.reply_text(T.USER_MENU, reply_markup=USER_KB)


async def show_usage(update: Update, ctx, row) -> None:
    try:
        t = await panel(ctx).client_traffic(row["email"])
    except PanelError as exc:
        log.warning("traffic lookup failed for %s: %s", row["email"], exc)
        await update.message.reply_text(T.TRY_LATER)
        return
    used, total = used_total(t)
    await update.message.reply_text(
        T.USAGE.format(
            name=esc(row["name"]),
            status=T.STATUS_ON if t.get("enable", True) else T.STATUS_OFF,
            used=gb(used), total=gb(total), remaining=gb(max(total - used, 0)),
        ),
        reply_markup=MORE_KB,
    )


async def request_more(update: Update, ctx) -> None:
    q = update.callback_query
    tg_id = q.from_user.id
    row = db(ctx).get(tg_id)
    if not row or row["status"] != "approved":
        await q.answer()
        return
    if not await submit_more(ctx, row):
        await q.answer(T.MORE_ALREADY, show_alert=True)
        return
    await q.answer()
    await ctx.bot.send_message(tg_id, T.MORE_SUBMITTED, reply_markup=USER_KB)


async def submit_more(ctx, row) -> bool:
    """Record a "more traffic" request and tell the admins. False if one is already waiting."""
    if row["extra_requested_at"]:
        return False
    db(ctx).update(row["tg_id"], extra_requested_at=int(time.time()))
    text, kb = await extra_card(ctx, db(ctx).get(row["tg_id"]))
    for admin_id in cfg(ctx).admin_ids:
        await notify(ctx, admin_id, text, reply_markup=kb)
    return True


# ---------------------------------------------------------------- admin
async def admin_text(update: Update, ctx, text: str) -> None:
    if text == T.BTN_PENDING:
        rows = db(ctx).by_status("pending")
        extra = db(ctx).extra_requests()
        if not rows and not extra:
            await update.message.reply_text(T.NO_PENDING, reply_markup=ADMIN_KB)
        for row in rows:
            card, kb = request_card(row)
            await update.message.reply_text(card, reply_markup=kb)
        for row in extra:
            card, kb = await extra_card(ctx, row)
            await update.message.reply_text(card, reply_markup=kb)
    elif text == T.BTN_USERS:
        await list_users(update, ctx)
    elif text == T.BTN_RENEW_ALL:
        count = len(db(ctx).by_status("approved"))
        if not count:
            await update.message.reply_text(T.RENEW_NONE)
            return
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(T.BTN_CONFIRM_RENEW, callback_data="renew"),
            InlineKeyboardButton(T.BTN_CANCEL, callback_data="x"),
        ]])
        await update.message.reply_text(T.CONFIRM_RENEW.format(count=T.fa(count)), reply_markup=kb)
    elif text == T.BTN_STATUS:
        await update.message.reply_text(await status_text(ctx), reply_markup=ADMIN_KB)
    else:
        await update.message.reply_text(T.ADMIN_MENU, reply_markup=ADMIN_KB)


async def status_text(ctx) -> str:
    try:
        inbound = f"{esc(cfg(ctx).inbound_remark)} (ID {await inbound_id(ctx)})"
        panel_state = "🟢 متصل"
    except PanelError as exc:
        inbound = "—"
        panel_state = f"🔴 {esc(exc)}"
    sub = await sub_base(ctx)
    counts = db(ctx).counts()
    return T.STATUS.format(
        panel=panel_state, inbound=inbound, sub=esc(sub or "—"),
        approved=T.fa(counts.get("approved", 0)), disabled=T.fa(counts.get("disabled", 0)),
        pending=T.fa(counts.get("pending", 0)),
    )


async def list_users(update: Update, ctx) -> None:
    rows = db(ctx).by_status("approved", "disabled")
    if not rows:
        await update.message.reply_text(T.NO_USERS, reply_markup=ADMIN_KB)
        return
    buttons = [
        InlineKeyboardButton(("🟢 " if r["status"] == "approved" else "⛔️ ") + r["name"], callback_data=f"u:{r['tg_id']}")
        for r in rows
    ]
    for start in range(0, len(buttons), 60):
        chunk = buttons[start:start + 60]
        kb = InlineKeyboardMarkup([chunk[i:i + 2] for i in range(0, len(chunk), 2)])
        await update.message.reply_text(T.USERS_TITLE.format(count=T.fa(len(rows))), reply_markup=kb)


async def user_card(ctx, row) -> tuple[str, InlineKeyboardMarkup]:
    try:
        t = await panel(ctx).client_traffic(row["email"])
        usage = T.CARD_USAGE.format(
            used=gb(int(t.get("up", 0)) + int(t.get("down", 0))), total=gb(int(t.get("total", 0))),
            panel_status=T.STATUS_ON if t.get("enable", True) else T.STATUS_OFF,
        )
    except PanelError as exc:
        usage = T.CARD_USAGE_ERR.format(error=esc(exc))
    active = row["status"] == "approved"
    text = T.USER_CARD.format(
        name=esc(row["name"]), phone=esc(row["phone"]),
        tg_id=row["tg_id"] if row["tg_id"] > 0 else "—", username=username_of(row) if row["tg_id"] > 0 else T.WEB_ONLY,
        email=esc(row["email"]), status=T.STATUS_ON if active else "⛔️ غیرفعال", usage=usage,
    )
    uid = row["tg_id"]
    if active:
        rows = [
            [InlineKeyboardButton(T.BTN_RESEND, callback_data=f"rs:{uid}"),
             InlineKeyboardButton(T.BTN_RESET, callback_data=f"rt:{uid}")],
            [InlineKeyboardButton(T.BTN_DISABLE, callback_data=f"ds:{uid}"),
             InlineKeyboardButton(T.BTN_DELETE, callback_data=f"dl:{uid}")],
        ]
    else:
        rows = [[InlineKeyboardButton(T.BTN_ENABLE, callback_data=f"en:{uid}"),
                 InlineKeyboardButton(T.BTN_DELETE, callback_data=f"dl:{uid}")]]
    return text, InlineKeyboardMarkup(rows)


async def unique_email(ctx, name: str, tg_id: int) -> str:
    base = email_base(name)
    candidate, n = base, 2
    while db(ctx).email_taken(candidate, tg_id) or await panel(ctx).get_client(candidate) is not None:
        candidate, n = f"{base}_{n}", n + 1
    return candidate


async def approve(update: Update, ctx, tg_id: int) -> None:
    q = update.callback_query
    row = db(ctx).get(tg_id)
    if not row or row["status"] != "pending":
        await q.answer(T.REQ_ALREADY, show_alert=True)
        return
    await q.answer("⏳")
    c = cfg(ctx)
    try:
        ib = await inbound_id(ctx)
        if not row["email"]:
            # Saved before the panel call so a retry reuses the same identity.
            db(ctx).update(tg_id, email=await unique_email(ctx, row["name"], tg_id),
                           uuid=str(uuid.uuid4()), sub_id=random_sub_id())
            row = db(ctx).get(tg_id)
        if await panel(ctx).get_client(row["email"]) is None:
            await panel(ctx).add_client(
                email=row["email"], uuid=row["uuid"], sub_id=row["sub_id"],
                total_bytes=c.traffic_gb * GB, tg_id=max(tg_id, 0),
                comment=f"{row['name']} | {row['phone']}", inbound_id=ib,
            )
    except PanelError as exc:
        log.exception("approve failed for %s", tg_id)
        await ctx.bot.send_message(q.message.chat_id, T.APPROVE_FAILED.format(name=esc(row["name"]), error=esc(exc)))
        return

    db(ctx).update(tg_id, status="approved", approved_at=int(time.time()))
    await q.edit_message_text(q.message.text_html + T.REQ_APPROVED.format(email=esc(row["email"])))
    if tg_id < 0:  # web user: the links show up on their status page
        return
    header = T.APPROVED_HEADER.format(name=esc(row["name"]), gb=T.fa(c.traffic_gb))
    try:
        await send_links(ctx, row, header)
    except Exception as exc:
        log.warning("could not send links to %s: %s", tg_id, exc)


async def reject(update: Update, ctx, tg_id: int) -> None:
    q = update.callback_query
    row = db(ctx).get(tg_id)
    if not row or row["status"] != "pending":
        await q.answer(T.REQ_ALREADY, show_alert=True)
        return
    db(ctx).update(tg_id, status="rejected")
    await q.answer()
    await q.edit_message_text(q.message.text_html + T.REQ_REJECTED)
    await notify(ctx, tg_id, T.REQUEST_REJECTED, reply_markup=ReplyKeyboardRemove())


async def approve_more(update: Update, ctx, tg_id: int) -> None:
    q = update.callback_query
    row = db(ctx).get(tg_id)
    if not row or not row["extra_requested_at"]:
        await q.answer(T.REQ_ALREADY, show_alert=True)
        return
    if row["status"] != "approved":  # disabled since the request was made
        db(ctx).update(tg_id, extra_requested_at=None)
        await q.answer(T.REQ_ALREADY, show_alert=True)
        return
    await q.answer("⏳")
    extra = cfg(ctx).extra_traffic_gb
    try:
        await panel(ctx).add_traffic(row["email"], extra * GB)
    except PanelError as exc:
        log.warning("add traffic failed for %s: %s", row["email"], exc)
        await ctx.bot.send_message(q.message.chat_id, T.ADD_TRAFFIC_FAILED.format(email=esc(row["email"]), error=esc(exc)))
        return
    db(ctx).update(tg_id, extra_requested_at=None, low_alerted=0)
    await q.edit_message_text(q.message.text_html + T.MORE_REQ_APPROVED.format(gb=T.fa(extra)))
    await notify(ctx, tg_id, T.MORE_APPROVED.format(gb=T.fa(extra)), reply_markup=USER_KB)


async def reject_more(update: Update, ctx, tg_id: int) -> None:
    q = update.callback_query
    row = db(ctx).get(tg_id)
    if not row or not row["extra_requested_at"]:
        await q.answer(T.REQ_ALREADY, show_alert=True)
        return
    db(ctx).update(tg_id, extra_requested_at=None)
    await q.answer()
    await q.edit_message_text(q.message.text_html + T.REQ_REJECTED)
    await notify(ctx, tg_id, T.MORE_REJECTED, reply_markup=USER_KB)


async def renew_all(update: Update, ctx) -> None:
    q = update.callback_query
    await q.answer("⏳")
    rows = db(ctx).by_status("approved")
    if not rows:
        await q.edit_message_text(T.RENEW_NONE)
        return
    try:
        result = await panel(ctx).bulk_reset_traffic([r["email"] for r in rows])
    except PanelError as exc:
        await q.edit_message_text(T.PANEL_FAIL.format(error=esc(exc)))
        return
    text = T.RENEWED.format(gb=T.fa(cfg(ctx).traffic_gb))
    notified = 0
    for r in rows:
        notified += await notify(ctx, r["tg_id"], text, reply_markup=USER_KB)
    affected = result.get("affected", len(rows)) if isinstance(result, dict) else len(rows)
    await q.edit_message_text(T.RENEW_DONE.format(affected=T.fa(affected), notified=T.fa(notified)))


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if q.data == "more":
        await request_more(update, ctx)
        return
    if not is_admin(ctx, q.from_user.id):
        await q.answer()
        return
    action, _, arg = q.data.partition(":")
    if action == "x":
        await q.answer()
        await q.edit_message_text(T.CANCELLED)
        return
    if action == "renew":
        await renew_all(update, ctx)
        return

    tg_id = int(arg)
    if action == "ap":
        await approve(update, ctx, tg_id)
        return
    if action == "rj":
        await reject(update, ctx, tg_id)
        return
    if action == "xa":
        await approve_more(update, ctx, tg_id)
        return
    if action == "xr":
        await reject_more(update, ctx, tg_id)
        return

    row = db(ctx).get(tg_id)
    if not row or row["status"] not in ("approved", "disabled"):
        await q.answer(T.REQ_ALREADY, show_alert=True)
        return
    p = panel(ctx)
    try:
        if action == "u":
            await q.answer()
        elif action == "rs":
            # A web-only user has no chat with the bot, so the admin gets the links to pass on.
            await send_links(ctx, row, T.LINKS_HEADER, chat_id=q.message.chat_id if tg_id < 0 else None)
            await q.answer(T.DONE)
        elif action == "rt":
            await p.reset_traffic(row["email"])
            await notify(ctx, tg_id, T.RENEWED.format(gb=T.fa(cfg(ctx).traffic_gb)))
            await q.answer(T.DONE)
        elif action == "ds":
            await p.set_enabled(row["email"], False)
            db(ctx).update(tg_id, status="disabled")
            await notify(ctx, tg_id, T.ACCOUNT_DISABLED, reply_markup=ReplyKeyboardRemove())
            await q.answer(T.DONE)
        elif action == "en":
            await p.set_enabled(row["email"], True)
            db(ctx).update(tg_id, status="approved")
            await notify(ctx, tg_id, T.ACCOUNT_ENABLED, reply_markup=USER_KB)
            await q.answer(T.DONE)
        elif action == "dl":
            await q.answer()
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(T.BTN_CONFIRM_DELETE, callback_data=f"dly:{tg_id}"),
                InlineKeyboardButton(T.BTN_CANCEL, callback_data=f"u:{tg_id}"),
            ]])
            await q.edit_message_text(T.CONFIRM_DELETE.format(email=esc(row["email"])), reply_markup=kb)
            return
        elif action == "dly":
            try:
                await p.delete_client(row["email"])
            except PanelAPIError as exc:  # already gone from the panel
                log.warning("delete %s: %s", row["email"], exc)
            db(ctx).delete(tg_id)
            await notify(ctx, tg_id, T.ACCOUNT_DELETED, reply_markup=ReplyKeyboardRemove())
            await q.answer(T.DONE)
            await q.edit_message_text(T.DONE)
            return
        else:
            await q.answer()
            return
    except PanelError as exc:
        await q.answer()
        await ctx.bot.send_message(q.message.chat_id, T.PANEL_FAIL.format(error=esc(exc)))
        return

    text, kb = await user_card(ctx, db(ctx).get(tg_id))
    try:
        await q.edit_message_text(text, reply_markup=kb)
    except Exception:  # message too old to edit, or unchanged
        await ctx.bot.send_message(q.message.chat_id, text, reply_markup=kb)


# ---------------------------------------------------------------- low-traffic alerts
async def check_traffic(ctx) -> None:
    threshold = cfg(ctx).low_traffic_gb * GB
    for row in db(ctx).by_status("approved"):
        if row["tg_id"] < 0:  # web-only: the status page shows the warning instead
            continue
        try:
            used, total = used_total(await panel(ctx).client_traffic(row["email"]))
        except PanelError as exc:
            log.warning("traffic check failed for %s: %s", row["email"], exc)
            continue
        if total <= 0:  # unlimited
            continue
        remaining = max(total - used, 0)
        if remaining > threshold:
            if row["low_alerted"]:
                db(ctx).update(row["tg_id"], low_alerted=0)
        elif not row["low_alerted"]:
            text = T.LOW_TRAFFIC.format(used=gb(used), total=gb(total), remaining=gb(remaining))
            # Marked even if delivery fails (e.g. bot blocked) so it is not retried every round.
            db(ctx).update(row["tg_id"], low_alerted=1)
            await notify(ctx, row["tg_id"], text, reply_markup=MORE_KB)


async def traffic_loop(ctx) -> None:
    while True:
        try:
            await check_traffic(ctx)
        except Exception:
            log.exception("traffic check round failed")
        await asyncio.sleep(cfg(ctx).traffic_check_minutes * 60)


# ---------------------------------------------------------------- lifecycle
async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("unhandled error", exc_info=ctx.error)


async def post_init(app: Application) -> None:
    c: Config = app.bot_data["config"]
    app.bot_data["panel"] = Panel(c.panel_url, c.panel_token, c.panel_verify_ssl)

    class _Ctx:  # lets the ctx-based helpers run before any update arrives
        bot_data = app.bot_data
        bot = app.bot

    status = await status_text(_Ctx)
    log.info("startup status:\n%s", status)
    for admin_id in c.admin_ids:
        await notify(_Ctx, admin_id, T.STARTED + status, reply_markup=ADMIN_KB)
    app.bot_data["traffic_task"] = asyncio.create_task(traffic_loop(_Ctx))
    if c.web_port:
        from .web import start_web

        try:
            app.bot_data["web_runner"] = await start_web(_Ctx, c.web_host, c.web_port, c.web_cert_file, c.web_key_file)
        except Exception:  # bad certificate path, port in use… keep the Telegram bot running
            log.exception("web form failed to start")


async def post_shutdown(app: Application) -> None:
    task = app.bot_data.get("traffic_task")
    if task:
        task.cancel()
    if "web_runner" in app.bot_data:
        await app.bot_data["web_runner"].cleanup()
    if "panel" in app.bot_data:
        await app.bot_data["panel"].close()


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    c = Config.load()

    app = (
        Application.builder()
        .token(c.bot_token)
        .defaults(Defaults(parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True)))
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.bot_data["config"] = c
    app.bot_data["db"] = DB(c.db_path)

    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", cmd_start, filters=private))
    app.add_handler(MessageHandler(private & filters.CONTACT, on_contact))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_error_handler(on_error)

    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
