"""All user-facing text (Persian). Messages are sent with HTML parse mode."""

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(value) -> str:
    return str(value).translate(_FA_DIGITS)


# ---------- coworker side ----------
ASK_NAME = (
    "سلام 👋\n"
    "به ربات VPN آلتن خوش آمدید.\n\n"
    "لطفاً <b>نام و نام خانوادگی</b> خود را وارد کنید:"
)
INVALID_NAME = "❗️ نام وارد شده معتبر نیست. لطفاً نام و نام خانوادگی خود را (بین ۲ تا ۴۰ حرف) بنویسید:"
ASK_PHONE = (
    "ممنون {name} 🌱\n\n"
    "حالا لطفاً با زدن دکمه‌ی <b>«📱 ارسال شماره تماس»</b> در پایین صفحه، شماره‌ی خود را ارسال کنید."
)
BTN_SHARE_PHONE = "📱 ارسال شماره تماس"
USE_PHONE_BUTTON = "لطفاً فقط از دکمه‌ی <b>«📱 ارسال شماره تماس»</b> در پایین صفحه استفاده کنید."
NOT_OWN_CONTACT = "❗️ لطفاً شماره‌ی <b>خودتان</b> را با دکمه‌ی پایین صفحه ارسال کنید."
REQUEST_SUBMITTED = (
    "✅ درخواست شما ثبت شد و برای مدیر ارسال گردید.\n"
    "پس از تایید، لینک‌های اتصال همین‌جا برای شما ارسال می‌شود. 🙏"
)
REQUEST_PENDING = "⏳ درخواست شما در حال بررسی است. لطفاً منتظر تایید مدیر بمانید."
REQUEST_REJECTED = (
    "❌ متاسفانه درخواست شما تایید نشد.\n"
    "در صورت نیاز می‌توانید با زدن /start دوباره درخواست دهید."
)
ACCOUNT_DISABLED = "⛔️ اکانت شما غیرفعال شده است. برای پیگیری با مدیر تماس بگیرید."
ACCOUNT_ENABLED = "✅ اکانت شما دوباره فعال شد."
ACCOUNT_DELETED = "🗑 اکانت VPN شما حذف شد. در صورت نیاز می‌توانید با /start دوباره درخواست دهید."
PRESS_START = "برای شروع /start را بزنید."
TRY_LATER = "⚠️ در حال حاضر امکان دریافت اطلاعات وجود ندارد. لطفاً کمی بعد دوباره تلاش کنید."

APPROVED_HEADER = (
    "🎉 <b>درخواست شما تایید شد!</b>\n\n"
    "👤 نام: {name}\n"
    "📦 حجم ماهانه: {gb} گیگابایت\n\n"
)
LINKS_HEADER = "🔗 <b>لینک‌های اتصال شما</b>\n\n"
LINK_SUB = "📥 <b>لینک اشتراک (Subscription):</b>\n<code>{sub}</code>\n\n"
LINK_VLESS = "🔑 <b>لینک کانفیگ (VLESS):</b>\n<code>{vless}</code>\n\n"
LINKS_FOOTER = (
    "روی هر لینک بزنید تا کپی شود.\n"
    "برای آموزش اتصال، دکمه‌ی «📖 راهنمای اتصال» را بزنید."
)
QR_SUB = "📥 QR لینک اشتراک"
QR_VLESS = "🔑 QR لینک کانفیگ"

BTN_USAGE = "📊 حجم باقی‌مانده"
BTN_LINKS = "🔗 لینک‌های من"
BTN_GUIDE = "📖 راهنمای اتصال"
USER_MENU = "از منوی پایین یکی از گزینه‌ها را انتخاب کنید 👇"

USAGE = (
    "📊 <b>وضعیت اکانت شما</b>\n\n"
    "👤 نام: {name}\n"
    "📶 وضعیت: {status}\n"
    "📉 مصرف شده: {used} گیگابایت\n"
    "📦 حجم کل: {total} گیگابایت\n"
    "✅ باقی‌مانده: <b>{remaining}</b> گیگابایت"
)
STATUS_ON = "🟢 فعال"
STATUS_OFF = "🔴 غیرفعال (حجم تمام شده یا مسدود)"

V2BOX_IOS = "https://apps.apple.com/app/v2box-v2ray-client/id6446814690"
V2BOX_ANDROID = "https://play.google.com/store/apps/details?id=dev.hexasoftware.v2box"
GUIDE_STEPS = (
    "<b>۱. نصب V2Box (آخرین نسخه)</b>\n"
    f"• آیفون / آیپد / مک: <a href=\"{V2BOX_IOS}\">V2Box در App Store</a>\n"
    f"• اندروید: <a href=\"{V2BOX_ANDROID}\">V2Box در Google Play</a>\n"
    "⚠️ اگر V2Box را از قبل دارید، حتماً آن را از App Store یا Google Play به آخرین نسخه به‌روزرسانی کنید.\n"
    "فقط از برنامه‌ی V2Box استفاده کنید.\n\n"
    "<b>۲. افزودن اشتراک</b>\n"
    "لینک اشتراک را کپی کنید. در V2Box به بخش <i>Configs</i> بروید، دکمه‌ی <b>+</b> را بزنید و "
    "<i>Add subscription</i> را انتخاب کنید، لینک را جای‌گذاری و ذخیره کنید "
    "(یا با <i>Scan QR code</i>، QR لینک اشتراک را اسکن کنید).\n\n"
    "<b>۳. اتصال</b>\n"
    "اشتراک را به‌روزرسانی (Update) کنید، کانفیگ را انتخاب کنید و در صفحه‌ی <i>Home</i> دکمه‌ی اتصال را بزنید.\n\n"
    "💡 اگر لینک اشتراک کار نکرد، لینک کانفیگ VLESS را کپی کنید و در همان منوی <b>+</b> گزینه‌ی "
    "<i>Import v2ray uri from clipboard</i> را بزنید."
)
GUIDE = "📖 <b>راهنمای اتصال</b>\n\n" + GUIDE_STEPS
RENEWED = "🔄 حجم ماهانه‌ی شما تمدید شد!\n📦 {gb} گیگابایت جدید در اختیار شماست. 🌱"

# ---------- admin side ----------
BTN_PENDING = "📋 درخواست‌های در انتظار"
BTN_USERS = "👥 کاربران"
BTN_RENEW_ALL = "🔄 تمدید ماهانه همه"
BTN_STATUS = "ℹ️ وضعیت ربات"
ADMIN_MENU = "👑 پنل مدیریت ربات"

NEW_REQUEST = (
    "🆕 <b>درخواست جدید</b>\n\n"
    "👤 نام: {name}\n"
    "📱 شماره: <code>{phone}</code>\n"
    "🆔 آیدی عددی: <code>{tg_id}</code>\n"
    "🔗 یوزرنیم: {username}\n"
    "🕒 زمان: {time}"
)
BTN_APPROVE = "✅ تایید"
BTN_REJECT = "❌ رد"
REQ_APPROVED = "\n\n✅ <b>تایید شد</b> — کلاینت «{email}» ساخته شد."
REQ_REJECTED = "\n\n❌ <b>رد شد</b>"
REQ_ALREADY = "این درخواست قبلاً بررسی شده است."
APPROVE_FAILED = "⚠️ ساخت کلاینت برای {name} ناموفق بود:\n<code>{error}</code>\n\nمشکل را بررسی و دوباره «تایید» را بزنید."
NO_PENDING = "✅ درخواستی در انتظار نیست."
NO_USERS = "هنوز کاربری تایید نشده است."
USERS_TITLE = "👥 <b>کاربران</b> ({count} نفر) — برای مدیریت روی نام بزنید:"

USER_CARD = (
    "👤 <b>{name}</b>\n"
    "📱 <code>{phone}</code>\n"
    "🆔 <code>{tg_id}</code> | {username}\n"
    "📧 کلاینت: <code>{email}</code>\n"
    "📶 وضعیت ربات: {status}\n"
    "{usage}"
)
CARD_USAGE = "📉 مصرف: {used} از {total} گیگابایت ({panel_status})"
CARD_USAGE_ERR = "⚠️ خطا در دریافت مصرف: <code>{error}</code>"
BTN_RESEND = "🔗 ارسال مجدد لینک"
BTN_RESET = "🔄 ریست حجم"
BTN_DISABLE = "⛔️ غیرفعال"
BTN_ENABLE = "✅ فعال"
BTN_DELETE = "🗑 حذف"
BTN_CONFIRM_DELETE = "⚠️ بله، حذف شود"
BTN_CANCEL = "انصراف"
CONFIRM_DELETE = "آیا کلاینت «{email}» از پنل و ربات حذف شود؟"
DONE = "✅ انجام شد."
CANCELLED = "لغو شد."

CONFIRM_RENEW = (
    "🔄 مصرف <b>{count}</b> کاربر فعال صفر می‌شود و به آن‌ها پیام تمدید ارسال می‌گردد.\n"
    "(کاربران غیرفعال شده تمدید نمی‌شوند.)\n\nادامه می‌دهید؟"
)
BTN_CONFIRM_RENEW = "✅ بله، تمدید کن"
RENEW_DONE = "✅ تمدید انجام شد.\n🔄 ریست شده: {affected}\n📨 مطلع شده: {notified}"
RENEW_NONE = "کاربر فعالی برای تمدید وجود ندارد."
PANEL_FAIL = "⚠️ خطای پنل:\n<code>{error}</code>"

STATUS = (
    "ℹ️ <b>وضعیت ربات</b>\n\n"
    "🖥 پنل: {panel}\n"
    "📡 اینباند: {inbound}\n"
    "📥 لینک اشتراک: <code>{sub}</code>\n\n"
    "🟢 فعال: {approved}\n"
    "⛔️ غیرفعال: {disabled}\n"
    "⏳ در انتظار: {pending}"
)
STARTED = "🤖 ربات روشن شد.\n\n"

# ---------- low traffic / extra traffic ----------
LOW_TRAFFIC = (
    "⚠️ <b>حجم شما رو به اتمام است</b>\n\n"
    "📉 مصرف شده: {used} از {total} گیگابایت\n"
    "✅ باقی‌مانده: <b>{remaining}</b> گیگابایت\n\n"
    "برای درخواست حجم بیشتر، دکمه‌ی زیر را بزنید 👇"
)
BTN_MORE_TRAFFIC = "➕ درخواست حجم بیشتر"
MORE_SUBMITTED = "✅ درخواست حجم بیشتر برای مدیر ارسال شد. پس از تایید به شما اطلاع داده می‌شود. 🙏"
MORE_ALREADY = "⏳ درخواست قبلی شما هنوز در حال بررسی است."
MORE_APPROVED = "🎉 درخواست شما تایید شد!\n➕ {gb} گیگابایت به حجم شما اضافه شد. 🌱"
MORE_REJECTED = "❌ متاسفانه درخواست حجم بیشتر شما تایید نشد."

NEW_MORE_REQUEST = (
    "➕ <b>درخواست حجم بیشتر</b>\n\n"
    "👤 نام: {name}\n"
    "📱 شماره: <code>{phone}</code>\n"
    "🆔 آیدی عددی: <code>{tg_id}</code>\n"
    "📧 کلاینت: <code>{email}</code>\n"
    "{usage}\n"
    "🕒 زمان: {time}"
)
BTN_APPROVE_MORE = "✅ تایید (+{gb} گیگ)"
MORE_REQ_APPROVED = "\n\n✅ <b>تایید شد</b> — {gb} گیگابایت اضافه شد."
ADD_TRAFFIC_FAILED = "⚠️ افزودن حجم به «{email}» انجام نشد:\n<code>{error}</code>"

# ---------- web requests ----------
WEB_SOURCE = "🌐 ثبت شده از طریق وب‌سایت"
WEB_ONLY = "⏳ هنوز به تلگرام وصل نشده"
LINKED_HEADER = "🎉 <b>اکانت شما پیدا شد و به تلگرام وصل شد!</b>\n\n👤 نام: {name}\n\n"
LINKED_PENDING = "🔗 درخواست شما از وب‌سایت پیدا شد و به تلگرام وصل شد.\n" + REQUEST_PENDING
ADMIN_LINKED = "🔗 «{name}» (<code>{phone}</code>) ربات را استارت کرد و اکانتش به تلگرام وصل شد."

# ---------- admin adds a user by hand ----------
BTN_ADD_USER = "➕ افزودن کاربر"
ADD_ASK_NAME = "➕ <b>افزودن کاربر</b>\n\nنام و نام خانوادگی کاربر را بنویسید:"
ADD_ASK_PHONE = (
    "👤 نام: {name}\n\n"
    "شماره‌ی موبایل کاربر را بنویسید (مثلاً <code>09121234567</code>) یا کارت مخاطب او را بفرستید:"
)
ADD_INVALID_PHONE = "❗️ شماره معتبر نیست. دوباره بنویسید (مثلاً <code>09121234567</code>):"
ADD_PHONE_EXISTS = "❗️ این شماره قبلاً ثبت شده است (برای «{name}»)."
ADD_DONE = (
    "✅ <b>کاربر اضافه شد</b>\n\n"
    "👤 نام: {name}\n"
    "📱 شماره: <code>{phone}</code>\n"
    "📧 کلاینت: <code>{email}</code>\n"
    "📦 حجم: {gb} گیگابایت\n\n"
    "وقتی کاربر ربات را استارت کند و همین شماره را بفرستد، اکانتش خودکار به تلگرامش وصل می‌شود.\n"
    "{web}"
    "لینک‌های اتصال او در پیام بعدی است تا در صورت نیاز برایش بفرستید 👇"
)
ADD_WEB_PAGE = "🌐 صفحه‌ی شخصی او (بدون تلگرام):\n{url}\n\n"
ADD_FAILED = "⚠️ ساخت کلاینت ناموفق بود:\n<code>{error}</code>"
