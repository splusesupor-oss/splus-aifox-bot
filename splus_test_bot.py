#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIFox — ربات سروش‌پلاس (Bot API رسمی) — @Aifox_bot
====================================================
قابلیت‌ها (فقط در PV):
  1. /start -> عکس خوش‌آمد + متن عضویت + دکمه‌های «کانال روباه» و
     «گروه روباه» (دکمه‌های URL: با کلیک مستقیم داخل کانال/گروه می‌رود)
     + دکمه «✅ تایید عضویت»
  2. تایید عضویت: Bot API کلیک روی دکمه‌های لینک را به سرور گزارش
     نمی‌کند؛ کاربر بعد از وارد شدن به کانال/گروه، وقتی برگشت روی
     «✅ تایید عضویت» می‌زند، تأیید می‌شود و همان لحظه پنل کیبورد
     اصلی در همان پیام نمایش داده می‌شود.
  3. منوی اصلی (Reply Keyboard در پایین چت، ۲ دکمه در هر ردیف):
     ردیف ۱: خرید ربات | ارسال گزارش به پشتیبانی
     ردیف ۲: تمدید اشتراک | مهلت باقی‌ماندهٔ گروه
     ردیف ۳: سایت بازی روباه | کانال راهنما
  4. خرید ربات -> متن کامل (عنوان bold با HTML) + نقل‌قول سروشِ
     پشتیبانی (MarkdownV2: > )
  5. مهلت باقی‌ماندهٔ گروه -> پیام راهنما + دکمهٔ شیشه‌ای (inline URL)
     سایت استعلام؛ کاربر در سایت، نام گروه یا لینک گروه خودش را در
     قسمت استعلام وارد می‌کند (آدرس از config.json: deadline_site_url).
  6. سایت بازی روباه -> عکس + دکمهٔ inline URL
  7. کانال راهنما -> دکمهٔ inline URL
  8. ارسال گزارش کاربر به پشتیبان (@osine2) همراه با نام/username/
     شناسهٔ کاربر + نگاشت پایدار تیکت برای برگشت دقیق Reply
     پشتیبان به همان کاربر.
  9. تمدید اشتراک -> هدایت به صفحهٔ خرید/تمدید سایت.
  10. دستورات مدیریتی مالک (فقط تایپی؛ owner_user_id از config.json):
      «دیدن اعضا» = لیست همه‌کسی که /start زده‌اند (نام، id، وضعیت تایید)؛
      «اطلاع رسانی» = متن بعدی به پیوی همهٔ اعضا بازنشر می‌شود (مثل
      اطلاع‌رسانی ربات اصلی) + گزارش تعداد موفق/خطا.
  11. مسدودسازی (مدیر): «مسدود <اید عددی | @یوزرنیم>» /
      «رفع مسدودی ...» (یا «آزاد ...») / «لیست مسدودشده‌ها».
      کاربر مسدود هیچ پیامی پردازش نمی‌شود و فقط «🚫 مسدود شده‌اید»
      می‌گیرد؛ لیست در data/ پایدار است. مالک هرگز مسدود نمی‌شود.

زیرساخت:
  * getUpdates با Long Polling — بدون Webhook
  * فقط کتابخانهٔ استاندارد Python (urllib) — بدون pip install
  * Token از متغیر محیطی SPLUS_BOT_TOKEN — هرگز در کد/لاگ/git
  * وضعیت کاربران و تیکت‌ها در data/ (خارج از git)
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

API_URL_TEMPLATE = "https://api.splus.ir/bot{token}/{method}"

WELCOME_TEXT = (
    "سلام 👋\n"
    "\n"
    "به AIFox خوش آمدید.\n"
    "\n"
    "این ربات فعلاً در حال آزمایش است."
)

LONG_POLL_TIMEOUT_SECONDS = 30
# حاشیهٔ زمانی برای تاخیر شبکه؛ تا اتصال long-poll را زودتر نپاره
HTTP_TIMEOUT_SECONDS = LONG_POLL_TIMEOUT_SECONDS + 35
RETRY_BACKOFFS = (1, 2, 5, 10, 30)  # ثانیه؛ سقف ۳۰

# ---------------------------------------------------------------------------
# مسیرها و متن‌ها
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "pv_state.json"
WELCOME_PHOTO = BASE_DIR / "assets" / "start_photo.jpg"
GAME_PHOTO = BASE_DIR / "assets" / "game_site.jpg"

START_CAPTION = "برای فعال سازی ربات باید عضو گروه و کانال روباه باشید"

VERIFY_CALLBACK = "verify_membership"
MENU_BUY = "🦊 خرید ربات روباه"
MENU_REPORT = "🎧 ارسال گزارش به پشتیبانی"
MENU_EXTEND = "🔄 تمدید اشتراک ربات"
MENU_DEADLINE = "⏳ مهلت باقی‌مانده گروه"
MENU_GAME = "🎮 سایت بازی روباه"
MENU_GUIDE = "📚 کانال راهنما"
MENU_MINIAPP = "🚀 روباه پلاس (برنامک)"
MAIN_MENU_TEXT = "🦊 منوی اصلی AIFox\n\nیکی از گزینه‌های زیر را انتخاب کنید:"

PURCHASE_MAIN_HTML = (
    "<b>🎉 پلن خرید اشتراک روباه</b>\n\n"
    "مراحل :\n\n"
    "🔸 وارد سایت میشوید قوانین میخوانید تایید میکنید و شماره تلفن یا یوزنیم "
    "حساب اصلیتون رو وارد میکنید\n\n"
    "🔸 اشتراک مورد نظر خودتون رو انتخاب میکنید\n\n"
    "🔸 به شماره کارت داخل کادر پرداخت میکنید رسید پرداخت رو وارد و لینک "
    "گروه تون رو می‌نویسید بعد دکمه ارسال درخواست\n\n"
    "🔸 برای دیدن سفارشات ثبت شده و برسی می‌توانید گزینه برسی سفارشات رو "
    "بزنید و ببینید آیا رد شده یا آیا در حال انتضار یا تایید شده\n\n"
    "🔸 بعد از تایید به شماره تلفن ثبت شده یا ایدیتون پیام خواهیم داد\n\n"
    "👇\n\n"
    "https://fox-bot.aifox-chat.workers.dev\n"
    "سایت خرید پلن ربات"
)
# نقل‌قول پشتیبانی: MarkdownV2 سروش کاراکتر '>' را رد می‌کند
# (400: can't parse entities) — متن ساده فرستاده می‌شود
PURCHASE_QUOTE_TEXT = (
    "در صورت وجود هر مشکل یا پشتیبانی پیام بدهید\n"
    "@osine2"
)

EXTEND_TEXT = (
    "🔄 تمدید اشتراک ربات\n\n"
    "برای تمدید اشتراک، وارد سایت خرید روباه شوید و همان مراحل خرید را "
    "برای تمدید اشتراک خود طی کنید."
)

REPORT_PROMPT_TEXT = (
    "🎧 گزارش یا پیام خود را همین‌جا ارسال کنید تا برای پشتیبانی "
    "(@osine2) ارسال شود."
)
REPORT_OK_TEXT = (
    "✅ گزارش شما برای پشتیبانی ارسال شد.\n"
    "هرگاه پشتیبان روی همان گزارش Reply کند، پاسخ را همین‌جا دریافت می‌کنید."
)
REPORT_FAIL_TEXT = (
    "⚠️ ارسال به پشتیبانی فعلاً ناموفق بود؛ لطفاً کمی دیگر گزارش را "
    "ارسال کنید."
)
REPORT_NEED_TEXT = (
    "لطفاً گزارش را به صورت **متن** ارسال کنید (نسخهٔ فعلی فقط گزارش "
    "متنی را به پشتیبانی می‌فرستد)."
)

DEADLINE_SITE_TEXT = (
    "برای دیدن مهلت باقی‌ماندهٔ گروه‌تون، وارد سایت زیر شوید و از قسمت "
    "استعلام، نام گروه خودتون یا لینک گروه خودتون رو وارد کنید 👇\n"
    "\n"
    "⛔ مستقیم روی سایت کلیک نکنید سایت رو کپی کنید و داخل مرورگر باز کنید"
)
DEADLINE_BUTTON_TEXT = "🌐 ورود به سایت استعلام مهلت گروه"

MEMBERS_EMPTY_TEXT = "👥 هنوز کاربری استارت را نزده است."
NOTIFY_ASK_TEXT = (
    "📢 متن اطلاع‌رسانی را بفرستید تا به پیوی همهٔ اعضا ارسال شود.\n"
    "(برای لغو: «انصراف»)"
)
NOTIFY_NO_USERS_TEXT = "📢 هنوز عضوی برای اطلاع‌رسانی وجود ندارد."
CANCEL_TEXTS = ("انصراف", "لغو", "/cancel")
ADMIN_MEMBERS_CMD = "دیدن اعضا"
ADMIN_NOTIFY_CMD = "اطلاع رسانی"
ADMIN_BLOCK_PREFIX = "مسدود"
ADMIN_UNBLOCK_PREFIXES = ("رفع مسدودی", "آزاد")
ADMIN_BLOCKLIST_CMD = "لیست مسدودشده‌ها"
BLOCK_TEXT = "🚫 شما از این ربات مسدود شده‌اید."
BLOCK_USAGE_TEXT = (
    "🚫 نحوهٔ استفاده:\n"
    "مسدود <اید عددی>      مثال: مسدود 12345678\n"
    "مسدود @یوزرنیم         مثال: مسدود @someuser\n"
    "رفع مسدودی <اید یا @یوزرنیم>   (یا: آزاد ...)"
)
GAME_BUTTON_TEXT = "🎮 ورود به سایت بازی روباه"
GUIDE_BUTTON_TEXT = "📚 ورود به کانال راهنما"
MINIAPP_BUTTON_TEXT = "🚀 ورود به روباه پلاس"

# مقادیر پیش‌فرض (config.json می‌تواند روی آن‌ها برسد)
DEFAULT_CONFIG = {
    "channel_url": "https://splus.ir/ai_fox",
    "channel_username": "ai_fox",
    "channel_title": "کانال روباه",
    "group_url": "https://splus.ir/joingroup/AI_hfuzaN9GGKPWF0MsDJg",
    "group_title": "گروه روباه",
    "support_username": "osine2",
    "site_url": "https://fox-bot.aifox-chat.workers.dev",
    "game_site_url": "https://fox-game.aifox-chat.workers.dev",
    "deadline_site_url": "https://fox-robah.aifox-bot.workers.dev/",
    "guide_channel_url": "https://splus.ir/Plunfox",
    "miniapp_url": "https://ai-fox.aifox-bot.workers.dev/",
    "owner_user_id": 37858988,
}

CFG = dict(DEFAULT_CONFIG)
STATE = {"learned": {}, "users": {}, "tickets": {}, "blocked": {}}


class NetworkError(Exception):
    """خطای موقت شبکه — قابل تلاش دوباره."""


class BotError(Exception):
    """API پاسخ OK=false (یا غیر-JSON) داد."""

    def __init__(self, code, description, retry_after=None):
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description
        self.retry_after = retry_after


def log(level, message):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {level.upper():5s} {message}", flush=True)


# ---------------------------------------------------------------------------
# لایهٔ API
# ---------------------------------------------------------------------------

def api_call(method, params=None):
    """یک متد API را صدا می‌زند.

    موفقیت -> مقدار `result`. شکست -> NetworkError یا BotError.
    """
    token = os.environ.get("SPLUS_BOT_TOKEN", "").strip()
    url = API_URL_TEMPLATE.format(token=token, method=method)
    body = json.dumps(params or {}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    status, raw = None, b""
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as exc:  # سرور استاتس خطا برگرداند
        status = exc.code
        try:
            raw = exc.read()
        except Exception:
            raw = b""
    except Exception as exc:  # قطع اتصال، DNS، timeout و ...
        raise NetworkError(f"{type(exc).__name__}: {exc}")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise BotError(status or -1, f"پاسخ غیر-JSON (HTTP {status})")

    # Soroush Plus returns {"ok": true, ...} — accept any key case
    ok_value = None
    for key, value in payload.items():
        if str(key).lower() == "ok":
            ok_value = value
            break
    if ok_value is True:
        return payload.get("result")

    error_params = payload.get("parameters") or {}
    retry_after = (
        error_params.get("retry_after") if isinstance(error_params, dict) else None
    )
    raise BotError(
        payload.get("error_code", status),
        payload.get("description") or "خطای ناشناخته",
        retry_after,
    )


def api_call_multipart(method, fields, files):
    """مثل api_call ولی با بار multipart (برای آپلود فایل مثل عکس).

    fields: list of (name, value)
    files:  list of (name, filename, content_bytes, content_type)
    """
    token = os.environ.get("SPLUS_BOT_TOKEN", "").strip()
    url = API_URL_TEMPLATE.format(token=token, method=method)
    boundary = uuid.uuid4().hex
    chunks = []
    for name, value in fields:
        chunks.append(
            (f'--{boundary}\r\nContent-Disposition: form-data; '
             f'name="{name}"\r\n\r\n{value}\r\n').encode("utf-8")
        )
    for name, filename, content, content_type in files:
        chunks.append(
            (f'--{boundary}\r\nContent-Disposition: form-data; '
             f'name="{name}"; filename="{filename}"\r\n'
             f'Content-Type: {content_type}\r\n\r\n').encode("utf-8")
        )
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    status, raw = None, b""
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            raw = exc.read()
        except Exception:
            raw = b""
    except Exception as exc:
        raise NetworkError(f"{type(exc).__name__}: {exc}")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise BotError(status or -1, f"پاسخ غیر-JSON (HTTP {status})")

    ok_value = None
    for key, value in payload.items():
        if str(key).lower() == "ok":
            ok_value = value
            break
    if ok_value is True:
        return payload.get("result")

    error_params = payload.get("parameters") or {}
    retry_after = (
        error_params.get("retry_after") if isinstance(error_params, dict) else None
    )
    raise BotError(
        payload.get("error_code", status),
        payload.get("description") or "خطای ناشناخته",
        retry_after,
    )


def send_with_retry(chat_id, text, *, parse_mode=None, reply_markup=None,
                    disable_web_page_preview=False, attempts=3):
    """ارسال پیام متنی با تلاش دوباره برای خطاهای موقت. True/False برمی‌گرداند."""
    params = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": bool(disable_web_page_preview),
    }
    if parse_mode:
        params["parse_mode"] = parse_mode
    if reply_markup is not None:
        params["reply_markup"] = reply_markup
    for attempt in range(1, attempts + 1):
        try:
            api_call("sendMessage", params)
            return True
        except NetworkError as exc:
            delay = RETRY_BACKOFFS[min(attempt - 1, len(RETRY_BACKOFFS) - 1)]
            log("warn", f"ارسال ناموفق (تلاش {attempt}/{attempts}): {exc}")
            time.sleep(delay)
        except BotError as exc:
            if exc.retry_after:
                log("warn", f"محدودیت نرخ — {exc.retry_after} ثانیه صبر می‌کنم")
                time.sleep(exc.retry_after)
            else:
                log("error", f"sendMessage شکست خورد: {exc}")
                return False
    log("error", f"ارسال پیام بعد از {attempts} تلاش ناموفق بود (chat {chat_id})")
    return False


# ---------------------------------------------------------------------------
# config و وضعیت پایدار
# ---------------------------------------------------------------------------

def load_config():
    global CFG
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            for key, value in data.items():
                if value is not None:
                    cfg[key] = value
    except FileNotFoundError:
        pass
    except Exception as exc:
        log("error", f"خواندن config.json ناموفق: {exc}")
    CFG = cfg
    return cfg


def load_state():
    global STATE
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            data.setdefault("learned", {})
            data.setdefault("users", {})
            data.setdefault("tickets", {})
            data.setdefault("blocked", {})
            STATE = data
            return data
    except FileNotFoundError:
        pass
    except Exception as exc:
        log("error", f"خواندن وضعیت ذخیره‌شده ناموفق: {exc}")
    STATE = {"learned": {}, "users": {}, "tickets": {}, "blocked": {}}
    return STATE


def save_state():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(STATE, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE_FILE)
    except Exception as exc:
        log("error", f"ذخیرهٔ وضعیت ناموفق: {exc}")


def get_user_state(user_id):
    key = str(user_id)
    record = STATE["users"].get(key)
    if not isinstance(record, dict):
        record = {"verified": False, "mode": "proof"}
        STATE["users"][key] = record
    return record


def is_start_message(message):
    """فقط وقتی True: دستور /start در چت خصوصی (PV)."""
    chat = message.get("chat") or {}
    if chat.get("type") != "private":
        return False
    text = (message.get("text") or "").strip()
    if not text:
        return False
    head = text.split(None, 1)[0].lower()
    return head == "/start" or head.startswith("/start@")


# ---------------------------------------------------------------------------
# کیبوردها (JSON مطابق Bot API)
# ---------------------------------------------------------------------------

def start_inline_keyboard():
    """دکمه‌های کانال/گروه URL هستند: با کلیک مستقیم داخل چت می‌روند.

    (Bot API کلیک روی دکمهٔ URL را گزارش نمی‌کند؛ به همین دلیل دکمهٔ
    جداگانهٔ «تایید عضویت» callback است و بعد از برگشت کاربر زده می‌شود.)
    """
    return {"inline_keyboard": [
        [{"text": "🔹 کانال روباه", "url": CFG["channel_url"]}],
        [{"text": "🔹 گروه روباه", "url": CFG["group_url"]}],
        [{"text": "✅ تایید عضویت", "callback_data": VERIFY_CALLBACK}],
    ]}


def main_reply_keyboard():
    """۲ دکمه در هر ردیف، ۴ ردیف (مطابق چیدمان خواسته‌شده)."""
    return {"keyboard": [
        [MENU_BUY, MENU_REPORT],
        [MENU_EXTEND, MENU_DEADLINE],
        [MENU_GAME, MENU_GUIDE],
        [MENU_MINIAPP],
    ], "resize_keyboard": True}


def site_inline_keyboard():
    return {"inline_keyboard": [
        [{"text": "💎 صفحه خرید / تمدید", "url": CFG["site_url"]}],
    ]}


# ---------------------------------------------------------------------------
# صفحهٔ شروع
# ---------------------------------------------------------------------------

def send_start_page(user_id):
    keyboard = start_inline_keyboard()
    if WELCOME_PHOTO.exists():
        try:
            data = WELCOME_PHOTO.read_bytes()
            fields = [
                ("chat_id", str(user_id)),
                ("caption", START_CAPTION),
                ("reply_markup", json.dumps(keyboard, ensure_ascii=False)),
            ]
            api_call_multipart(
                "sendPhoto", fields,
                [("photo", WELCOME_PHOTO.name, data, "image/jpeg")],
            )
            log("info", f"صفحهٔ شروع (عکس + دکمه‌ها) ارسال شد — chat {user_id}")
            return
        except NetworkError as exc:
            log("warn", f"sendPhoto ناموفق ({exc}) — ارسال بدون عکس")
        except BotError as exc:
            log("error", f"sendPhoto خطا داد: {exc} — ارسال بدون عکس")
    # جایگزین بدون عکس (فایل عکس موجود نیست یا ارسال شکست)
    send_with_retry(user_id, START_CAPTION, reply_markup=keyboard)
    log("info", f"صفحهٔ شروع (متنی) ارسال شد — chat {user_id}")


def show_main_menu(user_id, note=None):
    text = (note + "\n\n" if note else "") + MAIN_MENU_TEXT
    send_with_retry(user_id, text, reply_markup=main_reply_keyboard())


# ---------------------------------------------------------------------------
# تایید عضویت بر اساس کلیک روی دکمه‌ها
# ---------------------------------------------------------------------------

def click_status_text(user_state):
    return (
        "🔍 برای فعال‌سازی:\n"
        "۱. روی «🔹 کانال روباه» بزنید و وارد کانال شوید\n"
        "۲. روی «🔹 گروه روباه» بزنید و وارد گروه شوید\n"
        "۳. وقتی برگشتید، «✅ تایید عضویت» را بزنید تا ربات فعال شود"
    )


def finish_verification(user_id, user_state):
    user_state["verified"] = True
    user_state["mode"] = "main"
    save_state()
    log("info", f"عضویت کاربر {user_id} تأیید شد")
    show_main_menu(user_id, note="✅ عضویت شما تأیید شد.")


def handle_unverified_message(message, user_id):
    """کاربر هنوز تایید نشده: فقط با زدن دکمهٔ «تایید عضویت» پیش می‌رود."""
    get_user_state(user_id)
    send_with_retry(user_id, click_status_text(None))


def handle_verify_callback(callback):
    """کلیک «✅ تایید عضویت» (بعد از وارد شدن به کانال/گروه و برگشت):
    تأیید فوری + نمایش پنل کیبورد در همان پیام."""
    user = callback.get("from") or {}
    user_id = user.get("id")
    if user_id is None:
        return
    try:
        api_call("answerCallbackQuery", {"callback_query_id": callback.get("id")})
    except (NetworkError, BotError) as exc:
        log("warn", f"answerCallbackQuery ناموفق: {exc}")
    user_state = get_user_state(user_id)
    record_user_name(user, user_id)
    if user_state["verified"]:
        show_main_menu(user_id, note="✅ عضویت شما از قبل تأیید شده است.")
        return
    finish_verification(user_id, user_state)


# ---------------------------------------------------------------------------
# گزارش پشتیبانی + مسیر برگشت Reply
# ---------------------------------------------------------------------------

def is_support_sender(sender):
    sender_id = sender.get("id")
    if sender_id is None:
        return False
    learned_id = STATE["learned"].get("support_user_id")
    if learned_id is not None:
        return sender_id == learned_id
    support_username = str(CFG.get("support_username") or "").lower()
    if not support_username:
        return False
    return (sender.get("username") or "").lower() == support_username


def handle_support_message(message, support_user_id):
    """Reply پشتیبان روی پیام گزارش -> ارسال پاسخ به همان کاربر."""
    reply_to = message.get("reply_to_message") or {}
    reply_to_id = reply_to.get("message_id")
    if reply_to_id is None:
        return False
    target_user = STATE["tickets"].get(str(reply_to_id))
    if target_user is None:
        return False
    reply_text = (message.get("text") or "").strip() or "(پاسخ بدون متن)"
    delivered = send_with_retry(target_user, f"🔔 پاسخ پشتیبانی:\n\n{reply_text}")
    if delivered:
        send_with_retry(support_user_id, "✅ پاسخ برای کاربر ارسال شد.")
        log("info", f"پاسخ پشتیبانی (تیکت {reply_to_id}) -> user {target_user}")
    return True


def handle_report(message, user_id):
    sender = message.get("from") or {}
    report_text = (message.get("text") or "").strip()
    if not report_text:
        send_with_retry(user_id, REPORT_NEED_TEXT, parse_mode="Markdown")
        return
    first_name = sender.get("first_name") or "—"
    last_name = sender.get("last_name") or ""
    username = sender.get("username")
    support_chat_id = (
        STATE["learned"].get("support_user_id")
        or "@" + str(CFG.get("support_username") or "osine2")
    )
    lines = [
        "📥 گزارش جدید از کاربر AIFox",
        f"👤 نام: {first_name} {last_name}".rstrip(),
        f"🆔 نام کاربری: @{username}" if username else "🆔 نام کاربری: —",
        f"🔢 شناسه: {user_id}",
        "──────────────",
        report_text,
    ]
    try:
        result = api_call("sendMessage", {
            "chat_id": support_chat_id,
            "text": "\n".join(lines),
        })
    except (NetworkError, BotError) as exc:
        log("error", f"ارسال گزارش به پشتیبان ناموفق: {exc}")
        send_with_retry(user_id, REPORT_FAIL_TEXT)
        return
    support_message_id = (result or {}).get("message_id")
    if support_message_id is not None:
        STATE["tickets"][str(support_message_id)] = user_id
        save_state()
    user_state = get_user_state(user_id)
    user_state["mode"] = "main"
    send_with_retry(user_id, REPORT_OK_TEXT)
    log("info", f"گزارش user {user_id} -> پشتیبان (پیام {support_message_id})")


# ---------------------------------------------------------------------------
# منوی اصلی
# ---------------------------------------------------------------------------

def send_game_site(user_id):
    """عکس روباه + دستهٔ بازی + دکمهٔ inline URL سایت بازی."""
    keyboard = {"inline_keyboard": [
        [{"text": GAME_BUTTON_TEXT, "url": CFG["game_site_url"]}],
    ]}
    if GAME_PHOTO.exists():
        try:
            data = GAME_PHOTO.read_bytes()
            fields = [
                ("chat_id", str(user_id)),
                ("reply_markup", json.dumps(keyboard, ensure_ascii=False)),
            ]
            api_call_multipart(
                "sendPhoto", fields,
                [("photo", GAME_PHOTO.name, data, "image/jpeg")],
            )
            log("info", f"عکس + دکمهٔ سایت بازی ارسال شد — user {user_id}")
            return
        except NetworkError as exc:
            log("warn", f"sendPhoto سایت بازی ناموفق ({exc}) — ارسال متنی")
        except BotError as exc:
            log("error", f"sendPhoto سایت بازی خطا داد: {exc} — ارسال متنی")
    send_with_retry(user_id, GAME_BUTTON_TEXT, reply_markup=keyboard)


def send_guide_channel(user_id):
    """دکمهٔ inline URL کانال راهنما."""
    keyboard = {"inline_keyboard": [
        [{"text": GUIDE_BUTTON_TEXT, "url": CFG["guide_channel_url"]}],
    ]}
    send_with_retry(user_id, "📚 آموزش‌ها و راهنمای استفاده:\n",
                    reply_markup=keyboard)
    log("info", f"دکمهٔ کانال راهنما ارسال شد — user {user_id}")


def send_miniapp(user_id):
    """دکمهٔ inline URL برنامک روباه پلاس."""
    keyboard = {"inline_keyboard": [
        [{"text": MINIAPP_BUTTON_TEXT, "url": CFG["miniapp_url"]}],
    ]}
    send_with_retry(user_id,
                    "🚀 روباه پلاس — برنامک سروش‌پلاس\n\n"
                    "با کلیک روی دکمهٔ زیر، برنامک روباه پلاس داخل سروش‌پلاس باز می‌شود.\n"
                    "همهٔ بازی‌ها، کیف پول و امکانات در یک‌جا!\n",
                    reply_markup=keyboard)
    log("info", f"دکمهٔ برنامک روباه پلاس ارسال شد — user {user_id}")


def set_menu_button_to_miniapp():
    """تنظیم دکمهٔ منوی بات (کنار ورودی پیام) تا مستقیماً برنامک را باز کند.
    
    اگر سروش‌پلاس از این متد پشتیبانی کند، دکمهٔ منو مستقیماً برنامک را باز می‌کند.
    در غیر این صورت، کاربر می‌تواند از دکمهٔ «روباه پلاس» در منوی اصلی استفاده کند.
    """
    miniapp_url = CFG.get("miniapp_url", "")
    if not miniapp_url:
        log("warn", "آدرس برنامک (miniapp_url) تنظیم نشده — رد شدن از تنظیم دکمه منو")
        return
    
    # تلاش برای تنظیم دکمه منوی بات
    # اگر سروش‌پلاس از setChatMenuButton پشتیبانی کند
    try:
        menu_button = {
            "type": "web_app",
            "text": "🦊 روباه پلاس",
            "web_app": {"url": miniapp_url}
        }
        api_call("setChatMenuButton", {
            "menu_button": menu_button
        })
        log("info", f"✅ دکمهٔ منوی بات به برنامک تنظیم شد: {miniapp_url}")
    except BotError as exc:
        log("warn", f"تنظیم دکمه منو با setChatMenuButton پشتیبانی نمی‌شود: {exc}")
        log("info", "ℹ️ کاربر می‌تواند از دکمه «روباه پلاس» در منوی اصلی استفاده کند")
    except NetworkError as exc:
        log("warn", f"خطای شبکه هنگام تنظیم دکمه منو: {exc}")


# ---------------------------------------------------------------------------
# مهلت گروه -> دکمهٔ سایت استعلام
# ---------------------------------------------------------------------------

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(num):
    return str(num).translate(FA_DIGITS)


def send_deadline_site(user_id):
    """«⏳ مهلت باقی‌مانده گروه» -> متن راهنما + دکمهٔ شیشه‌ای (inline URL)."""
    keyboard = {"inline_keyboard": [
        [{"text": DEADLINE_BUTTON_TEXT, "url": CFG["deadline_site_url"]}],
    ]}
    send_with_retry(user_id, DEADLINE_SITE_TEXT, reply_markup=keyboard)
    log("info", f"دکمهٔ سایت استعلام مهلت ارسال شد — user {user_id}")


def handle_menu_text(user_id, text):
    if text == MENU_BUY:
        # پیام اصلی (HTML: فقط bold — تگ‌های غیرمستند مثل blockquote باعث
        # رد شدن کل پیام می‌شوند) + نقل‌قول پشتیبانی (MarkdownV2)
        send_with_retry(user_id, PURCHASE_MAIN_HTML, parse_mode="HTML")
        send_with_retry(user_id, PURCHASE_QUOTE_TEXT)
        log("info", f"صفحهٔ خرید ارسال شد — user {user_id}")
    elif text == MENU_REPORT:
        user_state = get_user_state(user_id)
        user_state["mode"] = "report"
        save_state()
        send_with_retry(user_id, REPORT_PROMPT_TEXT)
    elif text == MENU_EXTEND:
        send_with_retry(user_id, EXTEND_TEXT,
                        reply_markup=site_inline_keyboard())
        log("info", f"پیام تمدید ارسال شد — user {user_id}")
    elif text == MENU_DEADLINE:
        send_deadline_site(user_id)
    elif text == MENU_GAME:
        send_game_site(user_id)
    elif text == MENU_GUIDE:
        send_guide_channel(user_id)
    elif text == MENU_MINIAPP:
        send_miniapp(user_id)
    else:
        # متن ناشناخته: منوی اصلی دوباره نمایش داده می‌شود
        show_main_menu(user_id)


# ---------------------------------------------------------------------------
# مسیریابی update
# ---------------------------------------------------------------------------

def is_owner(user_id):
    """فقط مالک ربات (owner_user_id از config.json) دستورات مدیریتی دارد."""
    owner = CFG.get("owner_user_id")
    try:
        return owner is not None and int(owner) == int(user_id)
    except (TypeError, ValueError):
        return False


def sanitize_display_name(value):
    """حذف کاراکترهای کنترل/غیرقابل‌چاپ — API پیام‌های پر از آن‌ها را رد می‌کند."""
    return "".join(ch for ch in str(value) if ch.isprintable()).strip()


def record_user_name(sender, user_id):
    """نام فرستنده را در رکوردش ثبت می‌کند (برای لیست اعضا) + رکورد برمی‌گرداند."""
    record = get_user_state(user_id)
    first = sanitize_display_name(sender.get("first_name") or "")
    username = sanitize_display_name(sender.get("username") or "")
    name = (first + (f" (@{username})" if username else "")).strip()
    if name:
        record["name"] = name
    return record


MEMBERS_PAGE_SIZE = 40


def handle_members_list(user_id):
    """دستور «دیدن اعضا» (مدیر): همه‌کسی که /start زده و وارد ربات شده.

    لیست به صفحه‌های کوچک تقسیم می‌شود (محدودیت طول پیام API سروش).
    """
    users = STATE.get("users") or {}
    if not users:
        send_with_retry(user_id, MEMBERS_EMPTY_TEXT)
        return
    ordered = sorted(
        users.items(),
        key=lambda kv: int(kv[0]) if str(kv[0]).lstrip("-").isdigit() else 0,
    )
    pages = [ordered[i:i + MEMBERS_PAGE_SIZE]
             for i in range(0, len(ordered), MEMBERS_PAGE_SIZE)]
    for page_no, page in enumerate(pages, 1):
        if len(pages) > 1:
            header = (f"👥 اعضای ربات ({fa(len(ordered))} نفر) — "
                      f"صفحهٔ {fa(page_no)} از {fa(len(pages))}:")
        else:
            header = f"👥 اعضای ربات ({fa(len(ordered))} نفر):"
        lines = [header]
        unknown = 0
        for index, (uid, record) in enumerate(
                page, (page_no - 1) * MEMBERS_PAGE_SIZE + 1):
            record = record if isinstance(record, dict) else {}
            name = record.get("name")
            mark = "✅" if record.get("verified") else "⬜"
            if name:
                lines.append(f"{fa(index)}. {name} — {mark}")
            else:
                unknown += 1
                lines.append(f"{fa(index)}. {uid} — {mark}")
        if unknown:
            lines.append("")
            lines.append(f"({fa(unknown)} کاربر هنوز نامی ثبت نشده؛ با "
                         f"اولین پیامشان خودکار ثبت می‌شود)")
        send_with_retry(user_id, "\n".join(lines))
    log("info", f"لیست اعضا ({len(ordered)} نفر، {len(pages)} صفحه) "
                f"ارسال شد — admin {user_id}")


def handle_notify_start(user_id):
    """دستور «اطلاع رسانی» (مدیر): درخواست متن بازنشر."""
    user_state = get_user_state(user_id)
    user_state["mode"] = "notify"
    save_state()
    send_with_retry(user_id, NOTIFY_ASK_TEXT)
    log("info", f"درخواست اطلاع‌رسانی — admin {user_id} (در انتظار متن)")


def handle_notify_text(message, user_id):
    """متن بعد از «اطلاع رسانی» -> ارسال PV به همهٔ اعضا (همان‌که استارت زده‌اند)."""
    user_state = get_user_state(user_id)
    text = (message.get("text") or "").strip()
    if not text:
        user_state["mode"] = "notify"
        save_state()
        send_with_retry(user_id, NOTIFY_ASK_TEXT)
        return
    if text in CANCEL_TEXTS:
        user_state["mode"] = "main"
        save_state()
        show_main_menu(user_id)
        return
    user_state["mode"] = "main"
    save_state()

    users = STATE.get("users") or {}
    if not users:
        send_with_retry(user_id, NOTIFY_NO_USERS_TEXT)
        return

    ok = fail = 0
    for uid in users:
        try:
            chat_id = int(uid)
        except ValueError:
            continue
        try:
            api_call("sendMessage", {"chat_id": chat_id, "text": text})
            ok += 1
        except (NetworkError, BotError) as exc:
            fail += 1
            log("warn", f"ارسال اطلاع‌رسانی به {chat_id} ناموفق: {exc}")
    result = f"📢 اطلاع‌رسانی ارسال شد: {fa(ok)} نفر"
    if fail:
        result += f" — {fa(fail)} خطا"
    send_with_retry(user_id, result)
    log("info", f"اطلاع‌رسانی: {ok} موفق / {fail} خطا — admin {user_id}")


def is_blocked(sender):
    """کاربر مسدود است؟ (اید عددی یا @یوزرنیم)"""
    blocked = STATE.get("blocked") or {}
    uid = sender.get("id")
    if uid is not None and str(uid) in blocked:
        return True
    username = str(sender.get("username") or "").lower()
    if username and f"@{username}" in blocked:
        return True
    return False


def normalize_block_target(raw):
    """هدف مسدودی را نرمال می‌کند: '123' -> '123' | '@user'/'user' -> '@user'."""
    raw = str(raw or "").strip()
    if not raw:
        return None
    if raw.startswith("@"):
        raw2 = raw[1:].strip()
        if not raw2:
            return None
        return "@" + raw2.lower()
    if raw.isdigit():
        return str(int(raw))
    if re.fullmatch(r"[A-Za-z0-9_]{3,32}", raw):
        return "@" + raw.lower()
    return None


def handle_block_command(user_id, text):
    """دستور «مسدود ...» (مدیر)."""
    target = text[len(ADMIN_BLOCK_PREFIX):].strip()
    key = normalize_block_target(target)
    if key is None:
        send_with_retry(user_id, BLOCK_USAGE_TEXT)
        return
    blocked = STATE.setdefault("blocked", {})
    if key in blocked:
        send_with_retry(user_id, f"⚠️ {key} از قبل مسدود است.")
        return
    blocked[key] = {"at": datetime.now().isoformat(timespec="seconds")}
    save_state()
    known = (STATE.get("users") or {}).get(key)
    if isinstance(known, dict) and known.get("name"):
        send_with_retry(user_id, f"🚫 {known['name']} ({key}) مسدود شد.")
    else:
        send_with_retry(user_id, f"🚫 {key} مسدود شد.")
    log("info", f"مسدودی {key} — admin {user_id}")


def handle_unblock_command(user_id, text):
    """دستور «رفع مسدودی ...» / «آزاد ...» (مدیر)."""
    prefix = next(p for p in ADMIN_UNBLOCK_PREFIXES if text.startswith(p))
    key = normalize_block_target(text[len(prefix):].strip())
    if key is None:
        send_with_retry(user_id, BLOCK_USAGE_TEXT)
        return
    blocked = STATE.setdefault("blocked", {})
    if key not in blocked:
        send_with_retry(user_id, f"ℹ️ {key} در لیست مسدودی نبود.")
        return
    del blocked[key]
    save_state()
    send_with_retry(user_id, f"✅ {key} دیگر مسدود نیست.")
    log("info", f"رفع مسدودی {key} — admin {user_id}")


def handle_blocklist(user_id):
    """دستور «لیست مسدودشده‌ها» (مدیر)."""
    blocked = STATE.get("blocked") or {}
    if not blocked:
        send_with_retry(user_id, "🚫 هیچ کاربری مسدود نیست.")
        return
    lines = [f"🚫 کاربران مسدود ({fa(len(blocked))} نفر):"]
    for index, key in enumerate(sorted(blocked), 1):
        info = blocked[key]
        when = info.get("at") if isinstance(info, dict) else None
        lines.append(f"{fa(index)}. {key}" + (f"  (از {when})" if when else ""))
    send_with_retry(user_id, "\n".join(lines))


def handle_update(update):
    """فقط پیام‌های PV پردازش می‌شوند؛ بقیه نادیده گرفته می‌شوند."""
    message = update.get("message")
    if message is None:
        callback = update.get("callback_query")
        if callback and callback.get("data") == VERIFY_CALLBACK:
            try:
                handle_verify_callback(callback)
            except (NetworkError, BotError) as exc:
                log("error", f"خطا در callback: {exc}")
        return

    chat = message.get("chat") or {}
    if chat.get("type") != "private":
        return
    sender = message.get("from") or {}
    user_id = sender.get("id")
    if user_id is None:
        return

    preview = str(message.get("text") or "")[:40]
    log("info", f"پیام دریافت شد — user {user_id} ({preview!r})")

    # کاربران مسدود اصلاً نمی‌توانند با ربات پیام دهند (به جز مالک)
    if not is_owner(user_id) and is_blocked(sender):
        send_with_retry(user_id, BLOCK_TEXT)
        return

    # یادگیری شناسهٔ عددی پشتیبان از اولین پیام خودش
    support_username = str(CFG.get("support_username") or "").lower()
    if (support_username
            and (sender.get("username") or "").lower() == support_username
            and STATE["learned"].get("support_user_id") is None):
        STATE["learned"]["support_user_id"] = user_id
        save_state()
        log("info", f"شناسهٔ پشتیبان ثبت شد: {user_id}")

    if is_start_message(message):
        user_state = record_user_name(sender, user_id)
        if user_state["verified"]:
            user_state["mode"] = "main"
            save_state()
            show_main_menu(user_id)
        else:
            user_state["mode"] = "proof"
            save_state()
            send_start_page(user_id)
        return

    text = (message.get("text") or "").strip()

    # دستورات مدیریتی مالک (فقط تایپی) — قبل از شاخهٔ پشتیبان:
    # مالک خودش پشتیبان (@osine2) است؛ اگر اول support بررسی شود،
    # دستوراتش به‌عنوان پیام پشتیبان بلعیده می‌شد. پشتیبانِ غیرمالک
    # به‌عنوان عضو ثبت نمی‌شود.
    if is_owner(user_id):
        user_state = record_user_name(sender, user_id)
        if text in (ADMIN_MEMBERS_CMD, ADMIN_NOTIFY_CMD):
            log("info", f"دستور مدیریتی «{text}» از user {user_id} — "
                        f"owner_user_id={CFG.get('owner_user_id')} "
                        f"-> {'مالک ✓' if is_owner(user_id) else 'مالک نیست ✗'}")
        if text == ADMIN_MEMBERS_CMD:
            if user_state.get("mode") in ("report", "notify", "proof"):
                user_state["mode"] = "main"
                save_state()
            handle_members_list(user_id)
            return
        if text == ADMIN_NOTIFY_CMD:
            if user_state.get("mode") in ("report", "proof"):
                user_state["mode"] = "main"
                save_state()
            handle_notify_start(user_id)
            return
        if text == ADMIN_BLOCK_PREFIX or text.startswith(ADMIN_BLOCK_PREFIX + " "):
            handle_block_command(user_id, text)
            return
        if any(text == pfx or text.startswith(pfx + " ")
               for pfx in ADMIN_UNBLOCK_PREFIXES):
            handle_unblock_command(user_id, text)
            return
        if text == ADMIN_BLOCKLIST_CMD:
            handle_blocklist(user_id)
            return
        if user_state.get("mode") == "notify":
            handle_notify_text(message, user_id)
            return
    elif not is_support_sender(sender):
        user_state = record_user_name(sender, user_id)

    if is_support_sender(sender):
        handled = False
        try:
            handled = handle_support_message(message, user_id)
        except (NetworkError, BotError) as exc:
            log("error", f"خطا در پیام پشتیبان: {exc}")
        # مالک هم پشتیبان است: پیام‌های غیر-تیکتِ او در جریان عادی ادامه می‌یابد
        if handled or not is_owner(user_id):
            return

    if user_state.get("mode") == "report":
        try:
            handle_report(message, user_id)
        except (NetworkError, BotError) as exc:
            log("error", f"خطا در ثبت گزارش: {exc}")
        return

    if not user_state.get("verified"):
        try:
            handle_unverified_message(message, user_id)
        except (NetworkError, BotError) as exc:
            log("error", f"خطا در بررسی عضویت: {exc}")
        return

    try:
        handle_menu_text(user_id, text)
    except (NetworkError, BotError) as exc:
        log("error", f"خطا در منوی اصلی: {exc}")


def wait_backoff(attempt, reason):
    delay = RETRY_BACKOFFS[min(attempt, len(RETRY_BACKOFFS) - 1)]
    log("warn", f"{reason} — {delay} ثانیه دیگر تلاش می‌کنم")
    time.sleep(delay)


def main():
    if not os.environ.get("SPLUS_BOT_TOKEN", "").strip():
        log("error", "متغیر محیطی SPLUS_BOT_TOKEN تنظیم نشده است.")
        log("error", 'مثال: export SPLUS_BOT_TOKEN="123456:ABC-DEF..."')
        sys.exit(1)

    load_config()
    load_state()

    # --- ۱) اعتبارسنجی token با getMe (با تلاش دوباره) -------------------
    attempt = 0
    while True:
        try:
            me = api_call("getMe")
            log("info",
                f"token معتبر — بات: @{me.get('username', '?')} (id: {me.get('id')})")
            break
        except BotError as exc:
            if exc.code in (401, 404):
                log("error", f"token نامعتبر: {exc.description}")
                sys.exit(1)
            if exc.code == 409:
                log("error", "بات در نمونهٔ دیگری اجرا می‌شود (یا webhook فعال است).")
                log("error", "نمونهٔ دیگر را ببندید یا webhook را با deleteWebhook حذف کنید.")
                sys.exit(1)
            attempt += 1
            wait_backoff(attempt - 1, f"getMe ناموفق ({exc})")
        except NetworkError as exc:
            attempt += 1
            wait_backoff(attempt - 1, f"اتصال নে هنگام getMe ({exc})")

    # --- ۲.۵) تنظیم دکمهٔ منوی بات به برنامک روباه پلاس ----------------
    set_menu_button_to_miniapp()

    # --- ۳) حلقهٔ اصلی: long polling با getUpdates ------------------------
    log("info", "ورود به حلقهٔ getUpdates (long polling) ...  برای خروج Ctrl+C")
    offset = 0
    attempt = 0
    try:
        while True:
            try:
                updates = api_call("getUpdates", {
                    "offset": offset,
                    "timeout": LONG_POLL_TIMEOUT_SECONDS,
                    "limit": 100,
                })
                attempt = 0  # اتصال سالم
                if updates:
                    for update in updates:
                        offset = max(offset, int(update.get("update_id", 0)) + 1)
                        try:
                            handle_update(update)
                        except Exception as exc:
                            log("error", f"خطا در پردازش update: {exc!r}")
            except NetworkError as exc:
                attempt += 1
                wait_backoff(attempt - 1, f"اتصال قطع شد ({exc})")
            except BotError as exc:
                if exc.code == 401:
                    log("error", f"token دیگر معتبر نیست: {exc.description}")
                    return
                if exc.code == 409:
                    log("error", "تعارض: بات در نمونهٔ دیگری اجرا می‌شود یا webhook فعال است.")
                    log("error", "نمونهٔ دیگر را ببندید یا webhook را با deleteWebhook حذف کنید.")
                    return
                if exc.retry_after:
                    log("warn", f"محدودیت نرخ — {exc.retry_after} ثانیه صبر می‌کنم")
                    time.sleep(exc.retry_after)
                else:
                    log("error", f"getUpdates شکست خورد: {exc}")
                    time.sleep(5)
    except KeyboardInterrupt:
        log("info", "توقف توسط کاربر. خداحافظ 👋")


if __name__ == "__main__":
    main()
