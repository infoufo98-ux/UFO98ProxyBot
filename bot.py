import os
import json
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = Path("/data/data.json")
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("ufo98proxy")

DEFAULT_DATA = {"proxies": [], "channels": [], "users": [], "clicks": 0}

def load_data():
    if not DATA_FILE.exists():
        save_data(DEFAULT_DATA.copy())
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for key, value in DEFAULT_DATA.items():
            data.setdefault(key, value.copy() if isinstance(value, list) else value)
        return data
    except (json.JSONDecodeError, OSError):
        log.exception("Could not read data.json; starting with empty data.")
        return DEFAULT_DATA.copy()

def save_data(data):
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def is_admin(user_id):
    return user_id in ADMIN_IDS

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 دریافت پروکسی", callback_data="get_proxy")],
        [InlineKeyboardButton("📣 کانال‌های ما", callback_data="channels")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")]
    ])

def channels_keyboard(data):
    rows = []
    for ch in data["channels"]:
        title = ch.get("title") or ch["url"]
        rows.append([InlineKeyboardButton(f"📣 {title}", url=ch["url"])])
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="home")])
    return InlineKeyboardMarkup(rows)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    if user and user.id not in data["users"]:
        data["users"].append(user.id)
        save_data(data)
    text = (
        "🛸 به UFO98 Proxy خوش آمدی!\n\n"
        "این ربات برای معرفی کانال‌های ما و ارائه لینک پروکسی‌های "
        "ثبت‌شده توسط مدیر ساخته شده است.\n\n"
        "⚠️ فعلاً ممکن است هیچ پروکسی فعالی ثبت نشده باشد. "
        "فعال‌بودن و امنیت هر پروکسی باید جداگانه بررسی شود."
    )
    await update.effective_message.reply_text(text, reply_markup=main_keyboard())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "راهنما:\n/start — منوی اصلی\n"
        "/channels — کانال‌های معرفی‌شده\n"
        "/getproxy — دریافت پروکسی ثبت‌شده\n\n"
        "دستورهای مدیر در README پروژه توضیح داده شده‌اند."
    )

async def channels_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["channels"]:
        await update.effective_message.reply_text(
            "هنوز کانالی ثبت نشده است.", reply_markup=main_keyboard()
        )
        return
    await update.effective_message.reply_text(
        "کانال‌های معرفی‌شده در UFO98 Proxy:",
        reply_markup=channels_keyboard(data)
    )

async def getproxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_proxy(update.effective_message, context)

async def send_proxy(message, context):
    data = load_data()
    if not data["proxies"]:
        await message.reply_text(
            "فعلاً پروکسی‌ای در سامانه ثبت نشده است. لطفاً بعداً دوباره بررسی کن.",
            reply_markup=main_keyboard()
        )
        return
    # Round-robin rotation; this is not a live health check.
    proxy = data["proxies"][0]
    data["proxies"] = data["proxies"][1:] + data["proxies"][:1]
    save_data(data)
    await message.reply_text(
        "📡 لینک پروکسی ثبت‌شده:\n"
        f"{proxy['url']}\n\n"
        "⚠️ این ربات در این نسخه سلامت لحظه‌ای پروکسی را تضمین نمی‌کند. "
        "روی لینک فقط در صورتی بزن که به منبع آن اعتماد داری.",
        disable_web_page_preview=True,
        reply_markup=main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    if query.data == "home":
        await query.edit_message_text(
            "🛸 منوی اصلی UFO98 Proxy", reply_markup=main_keyboard()
        )
    elif query.data == "channels":
        if not data["channels"]:
            await query.edit_message_text(
                "هنوز کانالی ثبت نشده است.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ بازگشت", callback_data="home")]
                ])
            )
        else:
            await query.edit_message_text(
                "کانال‌های معرفی‌شده:",
                reply_markup=channels_keyboard(data)
            )
    elif query.data == "get_proxy":
        data["clicks"] += 1
        save_data(data)
        await send_proxy(query.message, context)
    elif query.data == "help":
        await query.edit_message_text(
            "برای دریافت پروکسی از دکمه «دریافت پروکسی» استفاده کن.\n"
            "وضعیت اتصال و امنیت لینک‌ها در این نسخه به‌صورت خودکار بررسی نمی‌شود.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ بازگشت", callback_data="home")]
            ])
        )

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("این دستور فقط برای مدیر مجاز است.")
        return
    await update.effective_message.reply_text(
        "دستورهای مدیر:\n"
        "/myid — نمایش شناسه تلگرام شما\n"
        "/addproxy mtproto://... — افزودن لینک پروکسی\n"
        "/delproxy — حذف همه پروکسی‌ها\n"
        "/addchannel عنوان | https://t.me/channel — افزودن کانال\n"
        "/delchannels — حذف همه کانال‌ها\n"
        "/stats — آمار پایه\n\n"
        "فقط لینک‌هایی را اضافه کنید که منبع و امنیتشان را بررسی کرده‌اید."
    )

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"شناسه عددی شما: {update.effective_user.id}")

async def addproxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("دسترسی غیرمجاز.")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "روش استفاده:\n/addproxy https://t.me/proxy?server=...&port=...&secret=..."
        )
        return
    url = " ".join(context.args).strip()
    if not url.startswith(("https://t.me/proxy?", "tg://proxy?", "https://t.me/socks?")):
        await update.effective_message.reply_text(
            "این لینک شبیه لینک استاندارد پروکسی تلگرام نیست. "
            "لینک معتبر MTProto یا SOCKS را بررسی و دوباره ارسال کن."
        )
        return
    data = load_data()
    if any(p["url"] == url for p in data["proxies"]):
        await update.effective_message.reply_text("این پروکسی قبلاً ثبت شده است.")
        return
    data["proxies"].append({"url": url})
    save_data(data)
    await update.effective_message.reply_text("پروکسی به فهرست اضافه شد. سلامت آن خودکار بررسی نشده است.")

async def delproxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("دسترسی غیرمجاز.")
        return
    data = load_data()
    count = len(data["proxies"])
    data["proxies"] = []
    save_data(data)
    await update.effective_message.reply_text(f"{count} پروکسی حذف شد.")

async def addchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("دسترسی غیرمجاز.")
        return
    raw = update.effective_message.text.partition(" ")[2].strip()
    if "|" not in raw:
        await update.effective_message.reply_text(
            "روش استفاده:\n/addchannel نام کانال | https://t.me/channel"
        )
        return
    title, url = [part.strip() for part in raw.split("|", 1)]
    if not url.startswith("https://t.me/"):
        await update.effective_message.reply_text("لینک کانال باید از نوع https://t.me/... باشد.")
        return
    data = load_data()
    if any(ch["url"] == url for ch in data["channels"]):
        await update.effective_message.reply_text("این کانال قبلاً ثبت شده است.")
        return
    data["channels"].append({"title": title[:60], "url": url})
    save_data(data)
    await update.effective_message.reply_text("کانال تبلیغاتی اضافه شد.")

async def delchannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("دسترسی غیرمجاز.")
        return
    data = load_data()
    count = len(data["channels"])
    data["channels"] = []
    save_data(data)
    await update.effective_message.reply_text(f"{count} کانال حذف شد.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("دسترسی غیرمجاز.")
        return
    data = load_data()
    await update.effective_message.reply_text(
        f"📊 آمار UFO98 Proxy\n"
        f"کاربران یکتا: {len(data['users'])}\n"
        f"درخواست‌های دریافت پروکسی: {data['clicks']}\n"
        f"پروکسی‌های ثبت‌شده: {len(data['proxies'])}\n"
        f"کانال‌های تبلیغاتی: {len(data['channels'])}"
    )

def main():
    if not TOKEN:
        raise SystemExit(
            "BOT_TOKEN تنظیم نشده است. فایل .env.example را طبق README تنظیم کنید."
        )
    if not ADMIN_IDS:
        log.warning("ADMIN_IDS تنظیم نشده؛ هیچ کاربری دسترسی مدیریتی ندارد.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("channels", channels_cmd))
    app.add_handler(CommandHandler("getproxy", getproxy_cmd))
    app.add_handler(CommandHandler("admin", admin_help))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("addproxy", addproxy))
    app.add_handler(CommandHandler("delproxy", delproxy))
    app.add_handler(CommandHandler("addchannel", addchannel))
    app.add_handler(CommandHandler("delchannels", delchannels))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_handler))
    log.info("UFO98 Proxy bot is starting.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
