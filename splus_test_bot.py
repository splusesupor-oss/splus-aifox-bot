#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIFox — بات آزمایشی سروش‌پلاس (Bot API رسمی)
================================================
قابلیت (فعلاً فقط همین):
    کاربر در PV دستور /start بفرستد  ->  پیام خوش‌آمدگویی.

ویژگی‌ها:
  * getUpdates با Long Polling — بدون Webhook
  * فقط کتابخانه استاندارد Python (urllib) — هیچ pip install لازم نیست
  * Token از متغیر محیطی SPLUS_BOT_TOKEN خوانده می‌شود (هاردکد نشده)
  * مدیریت خطا: قطع اینترنت / 429 rate-limit / خطاهای موقت -> تلاش دوباره
  * شروع پاک: offset از اولین به‌روزرسانیِ تأییدنشده

اجرا در Termux:
    export SPLUS_BOT_TOKEN="123456:ABC-DEF..."
    python splus_test_bot.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

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

    if payload.get("OK") is True:
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


def is_private_start(message):
    """فقط وقتی True: دستور /start در چت خصوصی (PV)."""
    chat = message.get("chat") or {}
    if chat.get("type") != "private":
        return False
    text = (message.get("text") or "").strip()
    if not text:
        return False
    head = text.split(None, 1)[0].lower()
    return head == "/start" or head.startswith("/start@")


def send_welcome(chat_id):
    """ارسال پیام خوش‌آمد با ۳ تلاش؛ خطای دائمی را لاگ می‌کند و False می‌دهد."""
    if chat_id is None:
        log("error", "chat_id پیدا نشد؛ ارسال انجام نشد")
        return False
    for attempt in range(1, 4):
        try:
            api_call("sendMessage", {
                "chat_id": chat_id,
                "text": WELCOME_TEXT,
                "disable_web_page_preview": True,
            })
            return True
        except NetworkError as exc:
            delay = RETRY_BACKOFFS[min(attempt - 1, len(RETRY_BACKOFFS) - 1)]
            log("warn", f"ارسال ناموفق (تلاش {attempt}/3): {exc} — {delay} ثانیه دیگر")
            time.sleep(delay)
        except BotError as exc:
            if exc.retry_after:
                log("warn", f"محدودیت نرخ — {exc.retry_after} ثانیه صبر می‌کنم")
                time.sleep(exc.retry_after)
            else:
                log("error", f"sendMessage شکست خورد: {exc}")
                return False
    log("error", "ارسال پیام خوش‌آمد بعد از ۳ تلاش ناموفق بود")
    return False


def handle_update(update):
    """فعلاً فقط /start در PV پردازش می‌شود.

    سایر انواع update (edited_message, callback_query, گروه و ...)
    نادیده گرفته می‌شوند؛ offset در حلقهٔ اصلی پیش می‌رود.
    """
    message = update.get("message")
    if message is None:
        return
    if not is_private_start(message):
        return
    chat_id = (message.get("chat") or {}).get("id")
    if send_welcome(chat_id):
        user = (message.get("from") or {}).get("first_name", "?")
        log("info", f"پیام خوش‌آمد ارسال شد — {user} (chat {chat_id})")


def wait_backoff(attempt, reason):
    delay = RETRY_BACKOFFS[min(attempt, len(RETRY_BACKOFFS) - 1)]
    log("warn", f"{reason} — {delay} ثانیه دیگر تلاش می‌کنم")
    time.sleep(delay)


def main():
    if not os.environ.get("SPLUS_BOT_TOKEN", "").strip():
        log("error", "متغیر محیطی SPLUS_BOT_TOKEN تنظیم نشده است.")
        log("error", 'مثال: export SPLUS_BOT_TOKEN="123456:ABC-DEF..."')
        sys.exit(1)

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
