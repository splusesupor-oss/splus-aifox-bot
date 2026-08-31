#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIFox — ربات سروش‌پلاس (Bot API رسمی) — @Aifox_bot
====================================================
قابلیت‌ها (فقط در PV):
  1. /start -> عکس خوش‌آمد + متن عضویت + دکمه‌های کانال/گروه
     + دکمه «✅ تایید عضویت»
  2. تایید عضویت بر اساس کلیک روی دکمه‌ها (طبق خواست مالک):
     تا کاربر روی هر دو دکمه «کانال روباه» و «گروه روباه» کلیک نکرده
     باشد، «تایید عضویت» او را فعال نمی‌کند.
     (توضیح فنی: Bot API کلیک روی دکمه‌های لینک/URL را به سرور گزارش
     نمی‌کند؛ برای همین دکمه‌ها callback هستند. با هر کلیک، ثبت می‌شود
     و لینک واقعی همان لحظه برای کاربر ارسال می‌شود.)
  3. منوی اصلی (Reply Keyboard در پایین چت):
     خرید ربات / ارسال گزارش به پشتیبانی / تمدید اشتراک
  4. ارسال گزارش کاربر به پشتیبان (@osine2) همراه با نام/username/
     شناسهٔ کاربر + نگاشت پایدار تیکت برای برگشت دقیق Reply
     پشتیبان به همان کاربر.
  5. تمدید اشتراک -> هدایت به صفحهٔ خرید/تمدید سایت.

زیرساخت:
  * getUpdates با Long Polling — بدون Webhook
  * فقط کتابخانهٔ استاندارد Python (urllib) — بدون pip install
  * Token از متغیر محیطی SPLUS_BOT_TOKEN — هرگز در کد/لاگ/git
  * وضعیت کاربران و تیکت‌ها در data/ (خارج از git)
"""

import json
import os
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

START_CAPTION = "برای فعال سازی ربات باید عضو گروه و کانال روباه باشید"

VERIFY_CALLBACK = "verify_membership"
VISIT_CHANNEL_CALLBACK = "visit_channel"
VISIT_GROUP_CALLBACK = "visit_group"
MENU_BUY = "🦊 خرید ربات روباه"
MENU_REPORT = "🎧 ارسال گزارش به پشتیبانی"
MENU_EXTEND = "🔄 تمدید اشتراک ربات"
MAIN_MENU_BUTTONS = (MENU_BUY, MENU_REPORT, MENU_EXTEND)
MAIN_MENU_TEXT = "🦊 منوی اصلی AIFox\n\nیکی از گزینه‌های زیر را انتخاب کنید:"

PURCHASE_TEXT_HTML = (
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
    "سایت خرید پلن ربات\n\n"
    "<blockquote>در صورت وجود هر مشکل یا پشتیبانی پیام بدهید\n@osine2"
    "</blockquote>"
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

VISIT_DONE_TEXT = "🔹 {title}:\n{url}\n\nروی لینک بالا بزنید؛ کلیک شما ثبت شد."

# مقادیر پیش‌فرض (config.json می‌تواند روی آن‌ها برسد)
DEFAULT_CONFIG = {
    "channel_url": "https://splus.ir/ai_fox",
    "channel_username": "ai_fox",
    "channel_title": "کانال روباه",
    "group_url": "https://splus.ir/joingroup/AI_hfuzaN9GGKPWF0MsDJg",
    "group_title": "گروه روباه",
    "support_username": "osine2",
    "site_url": "https://fox-bot.aifox-chat.workers.dev",
}

CFG = dict(DEFAULT_CONFIG)
STATE = {"learned": {}, "users": {}, "tickets": {}}


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
            STATE = data
            return data
    except FileNotFoundError:
        pass
    except Exception as exc:
        log("error", f"خواندن وضعیت ذخیره‌شده ناموفق: {exc}")
    STATE = {"learned": {}, "users": {}, "tickets": {}}
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
        record = {"verified": False, "channel_clicked": False,
                  "group_clicked": False, "mode": "proof"}
        STATE["users"][key] = record
        return record
    # سازگاری با وضعیت‌های نسخهٔ قبل (کلیک‌های ثبت‌شده به‌شمار می‌روند)
    if "channel_clicked" not in record:
        record["channel_clicked"] = bool(record.get("channel_ok"))
    if "group_clicked" not in record:
        record["group_clicked"] = bool(record.get("group_ok"))
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
    return {"inline_keyboard": [
        [{"text": "🔹 کانال روباه", "callback_data": VISIT_CHANNEL_CALLBACK}],
        [{"text": "🔹 گروه روباه", "callback_data": VISIT_GROUP_CALLBACK}],
        [{"text": "✅ تایید عضویت", "callback_data": VERIFY_CALLBACK}],
    ]}


def main_reply_keyboard():
    return {"keyboard": [[label] for label in MAIN_MENU_BUTTONS],
            "resize_keyboard": True}


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
    lines = [
        "🔍 برای فعال‌سازی، باید روی هر دو دکمهٔ «کانال روباه» و "
        "«گروه روباه» کلیک کنید.",
        "",
    ]
    if user_state["channel_clicked"]:
        lines.append("✅ کانال روباه: کلیک ثبت شد")
    else:
        lines.append("⬜ کانال روباه: هنوز کلیک نشده")
    if user_state["group_clicked"]:
        lines.append("✅ گروه روباه: کلیک ثبت شد")
    else:
        lines.append("⬜ گروه روباه: هنوز کلیک نشده")
    lines.append("")
    lines.append("روی دکمه‌های باقی‌مانده در پیام شروع بزنید و بعد «✅ تایید عضویت» را دوباره بزنید.")
    return "\n".join(lines)


def finish_verification(user_id, user_state):
    user_state["verified"] = True
    user_state["mode"] = "main"
    save_state()
    log("info", f"عضویت کاربر {user_id} تأیید شد")
    show_main_menu(user_id, note="✅ عضویت شما تأیید شد.")


def handle_unverified_message(message, user_id):
    """کاربر هنوز تایید نشده: فقط با کلیک روی دکمه‌ها پیش می‌رود."""
    user_state = get_user_state(user_id)
    send_with_retry(user_id, click_status_text(user_state))


def handle_visit_callback(callback, kind):
    """کلیک روی دکمهٔ کانال/گروه: ثبت کلیک + ارسال لینک واقعی."""
    user = callback.get("from") or {}
    user_id = user.get("id")
    if user_id is None:
        return
    user_state = get_user_state(user_id)
    if kind == "channel":
        user_state["channel_clicked"] = True
        title, url = "کانال روباه", CFG["channel_url"]
    else:
        user_state["group_clicked"] = True
        title, url = "گروه روباه", CFG["group_url"]
    save_state()
    try:
        api_call("answerCallbackQuery", {
            "callback_query_id": callback.get("id"),
            "text": "ثبت شد 👍",
        })
    except (NetworkError, BotError) as exc:
        log("warn", f"answerCallbackQuery ناموفق: {exc}")
    send_with_retry(user_id, VISIT_DONE_TEXT.format(title=title, url=url))
    log("info", f"کلیک {kind} ثبت شد — user {user_id}")


def handle_verify_callback(callback):
    user = callback.get("from") or {}
    user_id = user.get("id")
    if user_id is None:
        return
    try:
        api_call("answerCallbackQuery", {"callback_query_id": callback.get("id")})
    except (NetworkError, BotError) as exc:
        log("warn", f"answerCallbackQuery ناموفق: {exc}")
    user_state = get_user_state(user_id)
    if user_state["verified"]:
        show_main_menu(user_id, note="✅ عضویت شما از قبل تأیید شده است.")
        return
    if user_state["channel_clicked"] and user_state["group_clicked"]:
        finish_verification(user_id, user_state)
        return
    # هنوز هر دو کلیک ثبت نشده -> تایید نمی‌شود
    user_state["mode"] = "proof"
    save_state()
    send_with_retry(user_id, click_status_text(user_state))
    log("info", f"درخواست تایید بدون کلیک کامل — user {user_id}")


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

def handle_menu_text(user_id, text):
    if text == MENU_BUY:
        send_with_retry(user_id, PURCHASE_TEXT_HTML, parse_mode="HTML")
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
    else:
        # متن ناشناخته: منوی اصلی دوباره نمایش داده می‌شود
        show_main_menu(user_id)


# ---------------------------------------------------------------------------
# مسیریابی update
# ---------------------------------------------------------------------------

def handle_update(update):
    """فقط پیام‌های PV پردازش می‌شوند؛ بقیه نادیده گرفته می‌شوند."""
    message = update.get("message")
    if message is None:
        callback = update.get("callback_query")
        data = callback.get("data") if callback else None
        if data == VERIFY_CALLBACK:
            try:
                handle_verify_callback(callback)
            except (NetworkError, BotError) as exc:
                log("error", f"خطا در callback: {exc}")
        elif data in (VISIT_CHANNEL_CALLBACK, VISIT_GROUP_CALLBACK):
            try:
                handle_visit_callback(
                    callback,
                    "channel" if data == VISIT_CHANNEL_CALLBACK else "group")
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

    # یادگیری شناسهٔ عددی پشتیبان از اولین پیام خودش
    support_username = str(CFG.get("support_username") or "").lower()
    if (support_username
            and (sender.get("username") or "").lower() == support_username
            and STATE["learned"].get("support_user_id") is None):
        STATE["learned"]["support_user_id"] = user_id
        save_state()
        log("info", f"شناسهٔ پشتیبان ثبت شد: {user_id}")

    if is_start_message(message):
        user_state = get_user_state(user_id)
        if user_state["verified"]:
            show_main_menu(user_id)
        else:
            user_state["mode"] = "proof"
            save_state()
            send_start_page(user_id)
        return

    if is_support_sender(sender):
        try:
            handle_support_message(message, user_id)
        except (NetworkError, BotError) as exc:
            log("error", f"خطا در پیام پشتیبان: {exc}")
        return

    text = (message.get("text") or "").strip()
    user_state = get_user_state(user_id)

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

    # --- ۲) حلقهٔ اصلی: long polling با getUpdates ------------------------
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
