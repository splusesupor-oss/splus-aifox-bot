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
     ردیف ۴: روباه پلاس (برنامک) | خرید تبلیغات
     ردیف ۵: ساخت فونت
  4. خرید ربات -> عکس خرید ربات روباه + متن سایت جدید + دکمهٔ شیشه‌ای
     ورود مستقیم به سایت
  5. مهلت باقی‌ماندهٔ گروه -> پیام راهنمای Bold (HTML، بدون دکمه):
     خریداران ربات (مالک یا ادمین) دستور «مهلت گروه» را داخل گروه
     می‌فرستند تا ربات مهلت باقی‌مانده را نشان دهد.
  6. سایت بازی روباه -> عکس + دکمهٔ inline URL
  7. کانال راهنما -> دکمهٔ inline URL
  7.5 خرید تبلیغات -> عکس «روباه تبلیغ‌گر» + دکمهٔ شیشه‌ای «سایت خرید
      تبلیغات» (آدرس از ads_site_url در config.json)
  7.6 ساخت فونت -> ربات نام انگلیسی کاربر را می‌گیرد (حداکثر ۳۰ کاراکتر،
      فقط A-Z) و همان نام را با ۳۴ استایل یونیکد روی دکمه‌های شیشه‌ای
      نشان می‌دهد؛ با کلیک روی هر دکمه، فقط همان متن فونت‌شده در چت
      ارسال و دکمه‌ها جمع می‌شوند. وضعیت (نام + توکن فهرست) برای هر
      کاربر جداگانه در data/ نگهداری می‌شود.
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
import unicodedata
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
BUY_PHOTO = BASE_DIR / "assets" / "buy_site.jpg"
GAME_PHOTO = BASE_DIR / "assets" / "game_site.jpg"
ADS_PHOTO = BASE_DIR / "assets" / "ads_site.jpg"

START_CAPTION = "برای فعال سازی ربات باید عضو گروه و کانال روباه باشید"

VERIFY_CALLBACK = "verify_membership"
MENU_BUY = "🦊 خرید ربات روباه"
MENU_REPORT = "🎧 ارسال گزارش به پشتیبانی"
MENU_EXTEND = "🔄 تمدید اشتراک ربات"
MENU_DEADLINE = "⏳ مهلت باقی‌مانده گروه"
MENU_GAME = "🎮 سایت بازی روباه"
MENU_GUIDE = "📚 کانال راهنما"
MENU_MINIAPP = "🚀 روباه پلاس (برنامک)"
MENU_ADS = "📣 خرید تبلیغات"
MENU_FONT = "ساخت فونت"
# همهٔ دکمه‌های منوی اصلی (برای تشخیص «کاربر دکمهٔ منو زد» در حالت‌های میانی)
MENU_BUTTONS = (
    MENU_BUY, MENU_REPORT, MENU_EXTEND, MENU_DEADLINE,
    MENU_GAME, MENU_GUIDE, MENU_MINIAPP, MENU_ADS, MENU_FONT,
)
MAIN_MENU_TEXT = "🦊 منوی اصلی AIFox\n\nیکی از گزینه‌های زیر را انتخاب کنید:"
# نسخهٔ چیدمان منوی reply-keyboard. هر بار دکمه‌ای اضافه/حذف شد این عدد را
# یک واحد زیاد کنید تا کیبورد کاربران قدیمی هم به‌روز شود (کیبورد reply در
# کلاینت کش می‌شود و فقط با ارسال دوبارهٔ reply_markup عوض می‌شود).
MENU_KEYBOARD_VERSION = 4
MENU_UPDATED_NOTE = "🔄 منوی ربات به‌روزرسانی شد (دکمهٔ «ساخت فونت» اضافه شد)."

PURCHASE_CAPTION = (
    "سایت جدید خرید ربات روباه\n\n"
    "🔘 برای ورود مستقیم روی دکمه زیر کلیک کنید\n\n"
    "🔘 و برای نصب برنامه، سایت رو کپی و وارد مرورگر کنید؛ "
    "بعد سه نقطه رو بزنید و گزینه نصب\n\n"
    "https://foxbot.osine2.workers.dev/"
)
PURCHASE_BUTTON_TEXT = "🦊 ورود مستقیم به سایت خرید ربات روباه"

EXTEND_TEXT = (
    "🔄 تمدید اشتراک ربات\n\n"
    "برای تمدید اشتراک، وارد سایت خرید روباه شوید و همان مراحل خرید را "
    "برای تمدید اشتراک خود طی کنید."
)

REPORT_LINE_MAIN = (
    "🎧 گزارش یا پیام خود را همین‌جا ارسال کنید تا برای پشتیبانی ارسال شود"
)
REPORT_LINE_WARN = (
    "⚠️ - ارسال موارد بی مربوط و تکراری و یا توهین و فحاشی "
    "باعث مسدودی شما از ربات خواهد شد"
)
# تلاش ۱: خط هشدار هم Bold و هم داخل نقل‌قول شیشه‌ای (blockquote)
REPORT_PROMPT_HTML_QUOTE = (
    f"{REPORT_LINE_MAIN}\n\n<blockquote><b>{REPORT_LINE_WARN}</b></blockquote>"
)
# تلاش ۲ (fallback): فقط Bold — اگر سرور سروش‌پلاس blockquote را رد کند
REPORT_PROMPT_HTML_BOLD = f"{REPORT_LINE_MAIN}\n\n<b>{REPORT_LINE_WARN}</b>"
# تلاش ۳ (fallback): متن ساده بدون parse_mode
REPORT_PROMPT_PLAIN = f"{REPORT_LINE_MAIN}\n\n{REPORT_LINE_WARN}"
REPORT_PROMPT_TEXT = REPORT_PROMPT_PLAIN  # سازگاری با کد قدیمی
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

# HTML: فقط bold
DEADLINE_SITE_TEXT = (
    "<b>🔸 اگر ربات روباه رو خریدد و مالک یا ادمین هستید داخل گروه دستور "
    "«مهلت گروه» را بفرستید ربات نمایش خواهد داد چقدر دیگر مهلت مانده</b>"
)

MEMBERS_EMPTY_TEXT = "👥 هنوز کاربری استارت را نزده است."
NOTIFY_ASK_TEXT = (
    "📢 متن اطلاع‌رسانی را بفرستید تا به پیوی همهٔ اعضا ارسال شود.\n"
    "(برای لغو: «انصراف»)"
)
NOTIFY_NO_USERS_TEXT = "📢 هنوز عضوی برای اطلاع‌رسانی وجود ندارد."
NOTIFY_CONFIRM_CALLBACK = "notify_send"
NOTIFY_CANCEL_CALLBACK = "notify_cancel"
NOTIFY_PREVIEW_TEXT = "👁 پیش‌نمایش پیام (دقیقاً به همین شکل به اعضا می‌رسد):"
NOTIFY_CONFIRM_BTN = "✅ تایید ارسال"
NOTIFY_CANCEL_BTN = "❌ لغو"
NOTIFY_CANCELLED_TEXT = "❌ ارسال اطلاع‌رسانی لغو شد."
NOTIFY_EXPIRED_TEXT = "⚠️ پیامی برای ارسال پیدا نشد؛ دوباره «اطلاع رسانی» را بزنید."
NOTIFY_ONLY_OWNER_TEXT = "⛔️ فقط مالک ربات می‌تواند این دکمه‌ها را بزند."
NOTIFY_USE_BUTTONS_TEXT = (
    "لطفاً با دکمه‌های «✅ تایید ارسال» یا «❌ لغو» زیر پیش‌نمایش پاسخ دهید "
    "(یا «انصراف» را بفرستید)."
)
NOTIFY_STARTED_TEXT = "🚀 ارسال اطلاع‌رسانی آغاز شد…"
NOTIFY_PROGRESS_TEXT = "🚀 در حال ارسال… {ok}/{target} ({percent}٪)"
NOTIFY_PROGRESS_EVERY = 25          # هر چند ارسال موفق، پیام پیشرفت به‌روز شود
NOTIFY_SEND_DELAY = 0.05            # فاصلهٔ کوتاه بین ارسال‌ها (ضد فلاد)
NOTIFY_SKIPPED_BLOCKED_TEXT = "🚫 {n} کاربر مسدود از فهرست گیرندگان کنار گذاشته شد"
NOTIFY_ALL_CALLBACK = "notify_all"
NOTIFY_ALL_BTN = "👥 همهٔ اعضا"
NOTIFY_COUNT_ASK_TEXT = (
    "🔢 به چند نفر ارسال شود؟\n"
    "عدد را بفرستید (مثلاً ۲۰۸) یا دکمهٔ «👥 همهٔ اعضا» را بزنید.\n"
    "کل اعضای فعلی: {total} نفر\n\n"
    "ℹ️ اگر ارسال به کسی خطا بخورد، ربات سراغ نفر بعدی می‌رود تا دقیقاً "
    "{example} ارسال موفق کامل شود.\n"
    "(برای لغو: «انصراف»)"
)
NOTIFY_COUNT_BAD_TEXT = (
    "⚠️ لطفاً فقط یک عدد صحیح بزرگ‌تر از صفر بفرستید (مثلاً ۲۰۸) "
    "یا دکمهٔ «👥 همهٔ اعضا» را بزنید."
)
NOTIFY_COUNT_CAPPED_TEXT = (
    "ℹ️ عدد درخواستی ({want}) از تعداد اعضا ({total}) بیشتر است؛ "
    "به همهٔ {total} عضو ارسال می‌شود."
)
NOTIFY_PARTIAL_TEXT = (
    "⚠️ فقط {ok} ارسال موفق انجام شد (هدف: {want}) — اعضای قابل‌ارسال تمام شدند."
)

# پیام اطلاع‌رسانیِ در انتظار تایید — {owner_id: message dict}
PENDING_NOTIFY = {}
# تعداد گیرندگانِ انتخاب‌شده — {owner_id: int}
NOTIFY_LIMIT = {}
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
# --- ساخت فونت -------------------------------------------------------------
FONT_ASK_TEXT = "✏️ اسم خودت رو به انگلیسی بنویس:"
FONT_INVALID_TEXT = (
    "⚠️ فقط حروف انگلیسی (A تا Z) قابل قبول است؛ فارسی، عدد یا نماد نفرست.\n\n"
    + FONT_ASK_TEXT
)
FONT_MAX_LENGTH = 30
FONT_TOO_LONG_TEXT = (
    "⚠️ حداکثر ۳۰ کاراکتر انگلیسی مجاز است.\n\n" + FONT_ASK_TEXT
)
FONT_CHOOSE_TEXT = (
    "🎨 اسم «{name}» آماده است.\n"
    "روی هر فونتی که دوست داری بزن تا همان‌جا برایت ارسال شود 👇"
)
FONT_DONE_TEXT = "✅ فونت انتخاب شد."
FONT_EXPIRED_TEXT = (
    "⚠️ این فهرست فونت دیگر معتبر نیست؛ دوباره دکمهٔ «ساخت فونت» را بزنید."
)
FONT_CANCELLED_TEXT = "❌ ساخت فونت لغو شد."
FONT_CALLBACK_PREFIX = "font:"
FONT_BUTTONS_PER_ROW = 3

GAME_BUTTON_TEXT = "🎮 ورود به سایت بازی روباه"
GUIDE_BUTTON_TEXT = "📚 ورود به کانال راهنما"
MINIAPP_BUTTON_TEXT = "🚀 ورود به روباه پلاس"
ADS_BUTTON_TEXT = "📣 سایت خرید تبلیغات"
ADS_CAPTION = (
    "📣 روباه تبلیغ‌گر\n\n"
    "تبلیغ خود را در شبکهٔ روباه ثبت کنید و دیده شوید!\n"
    "برای ثبت سفارش و مشاهدهٔ تعرفه‌ها، دکمهٔ زیر را بزنید 👇"
)

# مقادیر پیش‌فرض (config.json می‌تواند روی آن‌ها برسد)
DEFAULT_CONFIG = {
    "channel_url": "https://splus.ir/ai_fox",
    "channel_username": "ai_fox",
    "channel_title": "کانال روباه",
    "group_url": "https://splus.ir/joingroup/AI_hfuzaN9GGKPWF0MsDJg",
    "group_title": "گروه روباه",
    "support_username": "osine2",
    "site_url": "https://foxbot.osine2.workers.dev/",
    "game_site_url": "https://ai-fox.aifox-bot.workers.dev/",
    "deadline_site_url": "https://fox-robah.aifox-bot.workers.dev/",
    "guide_channel_url": "https://splus.ir/Plunfox",
    "ads_site_url": "https://soroush-ads.osine2.workers.dev/",
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


def send_report_prompt(chat_id):
    """پیام راهنمای «ارسال گزارش» با fallback سه‌مرحله‌ای.

    ۱) blockquote + bold (HTML)  ->  ۲) فقط bold (HTML)  ->  ۳) متن ساده
    اگر سرور سروش‌پلاس تگ blockquote را نشناسد (400: can't parse entities /
    unsupported tag) خودکار به مرحلهٔ بعد سقوط می‌کند.
    """
    attempts = (
        ("blockquote+bold", REPORT_PROMPT_HTML_QUOTE, "HTML"),
        ("bold", REPORT_PROMPT_HTML_BOLD, "HTML"),
        ("plain", REPORT_PROMPT_PLAIN, None),
    )
    for label, text, mode in attempts:
        params = {"chat_id": chat_id, "text": text}
        if mode:
            params["parse_mode"] = mode
        try:
            api_call("sendMessage", params)
            log("info", f"پیام راهنمای گزارش ارسال شد ({label}) — chat {chat_id}")
            return True
        except BotError as exc:
            log("warn", f"راهنمای گزارش «{label}» رد شد: {exc}")
            continue
        except NetworkError as exc:
            log("warn", f"خطای شبکه در راهنمای گزارش ({label}): {exc}")
            continue
    log("error", f"ارسال راهنمای گزارش کامل ناموفق بود — chat {chat_id}")
    return False


def notify_confirm_keyboard():
    """دو دکمهٔ شیشه‌ای تایید/لغو اطلاع‌رسانی."""
    return {"inline_keyboard": [[
        {"text": NOTIFY_CONFIRM_BTN, "callback_data": NOTIFY_CONFIRM_CALLBACK},
        {"text": NOTIFY_CANCEL_BTN, "callback_data": NOTIFY_CANCEL_CALLBACK},
    ]]}


def notify_count_keyboard(total):
    """دکمهٔ شیشه‌ای «همهٔ اعضا» + لغو، برای مرحلهٔ انتخاب تعداد."""
    return {"inline_keyboard": [[
        {"text": f"{NOTIFY_ALL_BTN} ({fa(total)})",
         "callback_data": NOTIFY_ALL_CALLBACK},
        {"text": NOTIFY_CANCEL_BTN, "callback_data": NOTIFY_CANCEL_CALLBACK},
    ]]}


def parse_count(text):
    """عدد فارسی/عربی/انگلیسی -> int مثبت. در غیر این صورت None."""
    digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    cleaned = str(text or "").translate(digits).strip()
    cleaned = cleaned.replace(",", "").replace("،", "").replace(" ", "")
    cleaned = cleaned.replace("نفر", "").strip()
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    return value if value > 0 else None


def deliver_preserving_format(target_chat_id, message):
    """پیام مالک را با حفظ کامل قالب‌بندی (Bold، نقل‌قول و…) بازنشر می‌کند.

    ترتیب تلاش: copyMessage  ->  sendMessage + entities  ->  متن ساده.
    نام روش موفق برمی‌گردد؛ در صورت شکست کامل "failed".
    """
    src_chat = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    text = message.get("text") or message.get("caption") or ""
    entities = message.get("entities") or message.get("caption_entities")

    def call(method, params):
        """یک تلاش، با احترام به retry_after سرور (کنترل فلاد)."""
        for _ in range(3):
            try:
                api_call(method, params)
                return True
            except BotError as exc:
                if exc.retry_after:
                    log("warn", f"محدودیت نرخ — {exc.retry_after} ثانیه صبر")
                    time.sleep(min(exc.retry_after, 60))
                    continue
                raise
            except NetworkError as exc:
                log("warn", f"خطای شبکه ({method}): {exc} — تلاش دوباره")
                time.sleep(2)
                continue
        return False

    # ۱) copyMessage — قالب‌بندی و مدیا را عیناً منتقل می‌کند
    if src_chat is not None and message_id is not None:
        try:
            if call("copyMessage", {
                "chat_id": target_chat_id,
                "from_chat_id": src_chat,
                "message_id": message_id,
            }):
                return "copyMessage"
        except (NetworkError, BotError) as exc:
            log("warn", f"copyMessage برای {target_chat_id} نشد: {exc}")

    if not text:
        return "failed"

    # ۲) sendMessage + entities — قالب‌بندی دقیقاً با آفست‌های اصلی
    if entities:
        try:
            if call("sendMessage", {
                "chat_id": target_chat_id,
                "text": text,
                "entities": json.dumps(entities, ensure_ascii=False),
            }):
                return "entities"
        except (NetworkError, BotError) as exc:
            log("warn", f"entities برای {target_chat_id} نشد: {exc}")

    # ۳) متن ساده
    try:
        if call("sendMessage", {"chat_id": target_chat_id, "text": text}):
            return "plain"
    except (NetworkError, BotError) as exc:
        log("warn", f"ارسال ساده برای {target_chat_id} نشد: {exc}")
    return "failed"


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
    """۲ دکمه در هر ردیف (چیدمان قبلی دست‌نخورده) + ردیف «ساخت فونت»."""
    return {"keyboard": [
        [MENU_BUY, MENU_REPORT],
        [MENU_EXTEND, MENU_DEADLINE],
        [MENU_GAME, MENU_GUIDE],
        [MENU_MINIAPP, MENU_ADS],
        [MENU_FONT],
    ], "resize_keyboard": True}


def site_inline_keyboard():
    return {"inline_keyboard": [
        [{"text": "💎 صفحه خرید / تمدید", "url": CFG["site_url"]}],
    ]}


def purchase_inline_keyboard():
    return {"inline_keyboard": [
        [{"text": PURCHASE_BUTTON_TEXT, "url": CFG["site_url"]}],
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
    user_state = get_user_state(user_id)
    if user_state.get("kb_version") != MENU_KEYBOARD_VERSION:
        user_state["kb_version"] = MENU_KEYBOARD_VERSION
        save_state()


def ensure_menu_keyboard_fresh(user_id):
    """اگر کاربر قدیمی هنوز کیبورد نسخهٔ قبلی را دارد، منوی جدید را می‌فرستد.

    کاربرانی که قبل از اضافه‌شدن دکمهٔ «روباه پلاس» ربات را داشتند، هرگز
    reply_markup جدید را دریافت نکرده بودند (فقط در /start ارسال می‌شد)؛
    بنابراین با اولین پیام بعدی، کیبورد به‌روز برایشان ارسال می‌شود.
    """
    user_state = get_user_state(user_id)
    if user_state.get("kb_version") == MENU_KEYBOARD_VERSION:
        return False
    show_main_menu(user_id, note=MENU_UPDATED_NOTE)
    log("info", f"کیبورد منو برای کاربر قدیمی به‌روز شد — user {user_id}")
    return True


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
    report_text = (message.get("text") or message.get("caption") or "").strip()
    has_media = any(k in message for k in
                    ("photo", "video", "document", "audio", "voice",
                     "sticker", "animation"))
    if not report_text and not has_media:
        send_with_retry(user_id, REPORT_NEED_TEXT, parse_mode="Markdown")
        return
    first_name = sender.get("first_name") or "—"
    last_name = sender.get("last_name") or ""
    username = sender.get("username")
    support_chat_id = (
        STATE["learned"].get("support_user_id")
        or "@" + str(CFG.get("support_username") or "osine2")
    )
    header = "\n".join([
        "📥 گزارش جدید از کاربر AIFox",
        f"👤 نام: {first_name} {last_name}".rstrip(),
        f"🆔 نام کاربری: @{username}" if username else "🆔 نام کاربری: —",
        f"🔢 شناسه: {user_id}",
        "──────────────",
    ])
    try:
        # سربرگ تیکت: Reply پشتیبان روی همین پیام به کاربر می‌رسد
        result = api_call("sendMessage", {
            "chat_id": support_chat_id,
            "text": header + ("\n" + report_text if report_text else ""),
        })
    except (NetworkError, BotError) as exc:
        log("error", f"ارسال گزارش به پشتیبان ناموفق: {exc}")
        send_with_retry(user_id, REPORT_FAIL_TEXT)
        return
    # نسخهٔ اصلی گزارش با حفظ قالب‌بندی/مدیا (اگر متن ساده نبوده)
    if has_media or message.get("entities") or message.get("caption_entities"):
        deliver_preserving_format(support_chat_id, message)
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

def send_purchase_site(user_id):
    """«🦊 خرید ربات روباه» -> عکس خرید ربات + متن جدید + دکمهٔ شیشه‌ای سایت."""
    keyboard = purchase_inline_keyboard()
    if BUY_PHOTO.exists():
        try:
            data = BUY_PHOTO.read_bytes()
            fields = [
                ("chat_id", str(user_id)),
                ("caption", PURCHASE_CAPTION),
                ("reply_markup", json.dumps(keyboard, ensure_ascii=False)),
            ]
            api_call_multipart(
                "sendPhoto", fields,
                [("photo", BUY_PHOTO.name, data, "image/jpeg")],
            )
            log("info", f"عکس + دکمهٔ خرید ربات روباه ارسال شد — user {user_id}")
            return
        except NetworkError as exc:
            log("warn", f"sendPhoto خرید ربات ناموفق ({exc}) — ارسال متنی")
        except BotError as exc:
            log("error", f"sendPhoto خرید ربات خطا داد: {exc} — ارسال متنی")
    # جایگزین بدون عکس (فایل موجود نیست یا آپلود شکست خورد)
    send_with_retry(user_id, PURCHASE_CAPTION, reply_markup=keyboard)
    log("info", f"پیام متنی خرید ربات روباه ارسال شد — user {user_id}")


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


def send_ads_site(user_id):
    """«📣 خرید تبلیغات» -> عکس روباه تبلیغ‌گر + دکمهٔ شیشه‌ای سایت تبلیغات."""
    keyboard = {"inline_keyboard": [
        [{"text": ADS_BUTTON_TEXT, "url": CFG["ads_site_url"]}],
    ]}
    if ADS_PHOTO.exists():
        try:
            data = ADS_PHOTO.read_bytes()
            fields = [
                ("chat_id", str(user_id)),
                ("caption", ADS_CAPTION),
                ("reply_markup", json.dumps(keyboard, ensure_ascii=False)),
            ]
            api_call_multipart(
                "sendPhoto", fields,
                [("photo", ADS_PHOTO.name, data, "image/jpeg")],
            )
            log("info", f"عکس + دکمهٔ خرید تبلیغات ارسال شد — user {user_id}")
            return
        except NetworkError as exc:
            log("warn", f"sendPhoto تبلیغات ناموفق ({exc}) — ارسال متنی")
        except BotError as exc:
            log("error", f"sendPhoto تبلیغات خطا داد: {exc} — ارسال متنی")
    # جایگزین بدون عکس (فایل موجود نیست یا آپلود شکست خورد)
    send_with_retry(user_id, ADS_CAPTION, reply_markup=keyboard)
    log("info", f"پیام متنی خرید تبلیغات ارسال شد — user {user_id}")


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


# ---------------------------------------------------------------------------
# ساخت فونت — موتور تبدیل حروف انگلیسی به استایل‌های یونیکد
#
# همهٔ نگاشت‌ها داخلی‌اند (بدون وابستگی بیرونی). هر استایل یا یک دیکشنری
# «کاراکتر -> کاراکتر» است یا یک تابع؛ هر کاراکتری که نگاشت نداشته باشد
# عیناً (fallback) در خروجی می‌ماند.
# ---------------------------------------------------------------------------

FONT_ASCII_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
FONT_ASCII_LOWER = "abcdefghijklmnopqrstuvwxyz"
FONT_ASCII_DIGITS = "0123456789"


def font_block_map(upper_start=None, lower_start=None, digit_start=None,
                   extra=None):
    """نگاشت A-Z / a-z / 0-9 روی یک بلوک پیوستهٔ یونیکد (+ استثناها)."""
    table = {}
    if upper_start is not None:
        for index, char in enumerate(FONT_ASCII_UPPER):
            table[char] = chr(upper_start + index)
    if lower_start is not None:
        for index, char in enumerate(FONT_ASCII_LOWER):
            table[char] = chr(lower_start + index)
    if digit_start is not None:
        for index, char in enumerate(FONT_ASCII_DIGITS):
            table[char] = chr(digit_start + index)
    if extra:
        table.update(extra)
    return table


def font_letter_map(values, digits=None):
    """یک گلیف مشترک برای حرف بزرگ و کوچک؛ None یعنی «نگاشت ندارد»."""
    table = {}
    for char, value in zip(FONT_ASCII_LOWER, values):
        if value is None:
            continue
        table[char] = value
        table[char.upper()] = value
    if digits:
        for char, value in zip(FONT_ASCII_DIGITS, digits):
            table[char] = value
    return table


def font_alternating_case(text):
    """یکی‌درمیان کوچک/بزرگ — مثل fOx."""
    out, index = [], 0
    for char in text:
        if char.isalpha():
            out.append(char.lower() if index % 2 == 0 else char.upper())
            index += 1
        else:
            out.append(char)
    return "".join(out)


def font_dotted_below(text):
    """نقطه‌دار زیر حرف — مثل F̣ọx̣ (ترکیب NFC تا حرف آماده ساخته شود)."""
    return "".join(
        unicodedata.normalize("NFC", char + "\u0323") if char.isalnum() else char
        for char in text
    )


# پایهٔ استایل «تزئینی» + علامت‌های تزئینی عبری که روی گلیف می‌نشینند
FONT_DECORATED_BASE = font_letter_map([
    "ᥲ", "ᑲ", "ᥴ", "ᑯ", "ᥱ", "⨍", "ᧁ", "ᑋ", "ι", "ᒎ", "ᛕ", "ᥣ", "ᨆ",
    "ᨶ", "ᨵ", "ᑭ", "ᑫ", "ᥬ", "ᦓ", "ᝨ", "ᥙ", "ꪜ", "ᥕ", "᥊", "ᥡ", "ᤁ",
])
FONT_DECORATION = "\u05C1\u05C5"


def font_decorated(text):
    """استایل تزئینی — مثل ܻ⨍ᨵׁׅׅ᥊ׁׅ"""
    out = []
    for char in text:
        base = FONT_DECORATED_BASE.get(char)
        if base is None:
            out.append(char)
        elif char in ("f", "F"):
            out.append("\u073B" + base)
        elif char in ("o", "O"):
            out.append(base + "\u05C1\u05C5\u05C5")
        else:
            out.append(base + FONT_DECORATION)
    return "".join(out)


FONT_SMALL_CAPS = font_letter_map("ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ")

# هر عضو: (شناسه، نگاشت یا None، تابع یا None)
FONT_STYLES = [
    ("smallcaps", FONT_SMALL_CAPS, None),                       # ғᴏx
    ("doublestruck", font_block_map(0x1D538, 0x1D552, 0x1D7D8, extra={
        "C": "\u2102", "H": "\u210D", "N": "\u2115", "P": "\u2119",
        "Q": "\u211A", "R": "\u211D", "Z": "\u2124"}), None),    # 𝔽𝕠𝕩
    ("monospace", font_block_map(0x1D670, 0x1D68A, 0x1D7F6), None),   # 𝙵𝚘𝚡
    ("bold", font_block_map(0x1D400, 0x1D41A, 0x1D7CE), None),        # 𝐅𝐨𝐱
    ("decorated", None, font_decorated),                              # ܻ⨍ᨵׁׅׅ᥊ׁׅ
    ("greekmix", font_letter_map("αв¢∂єƒgнιנкℓмησρqяѕтυνωχуz"), None),  # ƒσχ
    ("yi", font_letter_map(
        "ꋬꃳꉔ꒯ꏂꊰꍌꃅꂑꀭꀘ꒒ꂵꋊꄲꉣꆰꋪꇙ꓄꒤ꏝꅏꉧꌦꑉ"), None),            # ꊰꄲꉧ
    ("canadian", font_letter_map(
        "ᗩᗷᑕᗪEᖴGᕼIᒍKᒪᗰᑎOᑭᑫᖇᔕTᑌᐯᗯ᙭Yᘔ"), None),                      # ᖴO᙭
    ("smallcaps2", FONT_SMALL_CAPS, None),                      # ғᴏx (تکرار فهرست)
    ("alternating", None, font_alternating_case),                     # fOx
    ("fullwidth", font_block_map(0xFF21, 0xFF41, 0xFF10), None),      # Ｆｏｘ
    ("sansbolditalic", font_block_map(0x1D63C, 0x1D656, 0x1D7EC), None),  # 𝙁𝙤𝙭
    ("sansitalic", font_block_map(0x1D608, 0x1D622, 0x1D7E2), None),  # 𝘍𝘰𝘹
    ("bolditalic", font_block_map(0x1D468, 0x1D482, 0x1D7CE), None),  # 𝑭𝒐𝒙
    ("italic", font_block_map(0x1D434, 0x1D44E, extra={
        "h": "\u210E"}), None),                                       # 𝐹𝑜𝑥
    ("sansbold", font_block_map(0x1D5D4, 0x1D5EE, 0x1D7EC), None),    # 𝗙𝗼𝘅
    ("sans", font_block_map(0x1D5A0, 0x1D5BA, 0x1D7E2), None),        # 𝖥𝗈𝗑
    ("boldscript", font_block_map(0x1D4D0, 0x1D4EA), None),           # 𝓕𝓸𝔁
    # حروفی که در بلوک script جا افتاده‌اند با معادل italic پر می‌شوند
    ("script", font_block_map(0x1D49C, 0x1D4B6, extra={
        "B": "\U0001D435", "E": "\U0001D438", "F": "\U0001D439",
        "H": "\U0001D43B", "I": "\U0001D43C", "L": "\U0001D43F",
        "M": "\U0001D440", "R": "\U0001D445", "e": "\U0001D452",
        "g": "\U0001D454", "o": "\U0001D45C"}), None),                # 𝐹𝑜𝓍
    ("boldfraktur", font_block_map(0x1D56C, 0x1D586), None),          # 𝕱𝖔𝖝
    ("fraktur", font_block_map(0x1D504, 0x1D51E, extra={
        "C": "\u212D", "H": "\u210C", "I": "\u2111", "R": "\u211C",
        "Z": "\u2128"}), None),                                       # 𝔉𝔬𝔵
    ("superscript", font_letter_map(
        ["ᵃ", "ᵇ", "ᶜ", "ᵈ", "ᵉ", "ᶠ", "ᵍ", "ʰ", "ⁱ", "ʲ", "ᵏ", "ˡ", "ᵐ",
         "ⁿ", "ᵒ", "ᵖ", None, "ʳ", "ˢ", "ᵗ", "ᵘ", "ᵛ", "ʷ", "ˣ", "ʸ", "ᶻ"],
        digits="⁰¹²³⁴⁵⁶⁷⁸⁹"), None),                                  # ᶠᵒˣ
    ("subscript", font_letter_map(
        ["ₐ", "𝒷", "𝒸", "𝒹", "ₑ", "𝒻", "ℊ", "ₕ", "ᵢ", "ⱼ", "ₖ", "ₗ", "ₘ",
         "ₙ", "ₒ", "ₚ", "𝓆", "ᵣ", "ₛ", "ₜ", "ᵤ", "ᵥ", "𝓌", "ₓ", "𝓎", "𝓏"],
        digits="₀₁₂₃₄₅₆₇₈₉"), None),                                  # 𝒻ₒₓ
    ("squared", font_letter_map(
        [chr(0x1F130 + i) for i in range(26)]), None),                # 🄵🄾🅇
    ("negativecircled", font_letter_map(
        [chr(0x1F150 + i) for i in range(26)]), None),                # 🅕🅞🅧
    ("negativesquared", font_letter_map(
        [chr(0x1F170 + i) for i in range(26)]), None),                # 🅵🅾🆇
    ("soft", font_letter_map(
        ["ᥲ", "𝖻", "ᥴ", "𝖽", "ᥱ", "𝖿", "𝗀", "𝗁", "𝗂", "𝗃", "𝗄", "ᥣ", "𝗆",
         "ᥒ", "᥆", "𝗉", "𝗊", "𝗋", "𝗌", "𝗍", "ᥙ", "𝗏", "ᥕ", "᥊", "ᥡ", "𝗓"]),
     None),                                                           # 𝖿᥆᥊
    ("armenian", font_letter_map(
        ["ɑ", "ҍ", "ϲ", "ԃ", "ҽ", "բ", "ɠ", "հ", "ι", "ʝ", "ƙ", "ʅ", "ʍ",
         "ղ", "օ", "ρ", "զ", "ɾ", "ʂ", "ƚ", "υ", "ѵ", "ɯ", None, "ყ", "ȥ"]),
     None),                                                           # բօx
    ("greek", font_letter_map(
        ["α", "β", "ς", "δ", "ε", "ϝ", "γ", "η", "ι", "ϳ", "κ", "λ", "μ",
         "ν", "σ", "ρ", "ϙ", "г", "ϛ", "τ", "υ", "ʋ", "ω", None, "ψ", "ζ"]),
     None),                                                           # ϝσx
    ("georgian", font_letter_map(
        ["ა", "ბ", "ც", "დ", "ე", None, "გ", "ჰ", None, "ჯ", "კ", "ლ", "მ",
         "ნ", "ი", "პ", "ქ", "რ", "ს", "ტ", "უ", "ვ", None, None, "ყ", "ზ"]),
     None),                                                           # Fიx
    ("cyrillic", font_letter_map(
        ["А", "Б", "Ϲ", "Д", "Є", "Ғ", "Г", "Н", "І", "Ј", "К", "Л", "М",
         "И", "ϴ", "Р", "Ԛ", "Я", "Ѕ", "Т", "Ц", "Ѵ", "Ш", "Х", "Ү", "З"]),
     None),                                                           # ҒϴХ
    ("runic", font_letter_map(
        ["ᚨ", "ᛒ", "ᚲ", "ᛞ", "ᛖ", "ᚫ", "ᚵ", "ᚺ", "ᛁ", "ᛃ", "ᚴ", "ᛚ", "ᛗ",
         "ᚾ", "ᛟ", "ᛈ", "ᛩ", "ᚱ", "ᛊ", "ᛏ", "ᚢ", "ᚡ", "ᚹ", "ᚷ", "ᛇ", "ᛉ"]),
     None),                                                           # ᚫᛟᚷ
    ("cjk", font_letter_map(
        ["卂", "乃", "匚", "ᗪ", "乇", "千", "Ꮆ", "卄", "丨", "フ", "Ҝ", "ㄥ",
         "爪", "几", "ㄖ", "卩", "Ɋ", "尺", "丂", "ㄒ", "ㄩ", "ᐯ", "山", "乂",
         "丫", "乙"]), None),                                          # 千ㄖ乂
    ("dotted", None, font_dotted_below),                              # F̣ọx̣
]


def apply_font_style(name, style):
    """نام را با یک استایل تبدیل می‌کند؛ کاراکتر بدون نگاشت دست‌نخورده می‌ماند."""
    _, table, func = style
    if func is not None:
        return func(name)
    out = []
    for char in name:
        mapped = table.get(char)
        if mapped is None and char.isalpha():
            mapped = table.get(char.lower())
            if mapped is None:
                mapped = table.get(char.upper())
        out.append(char if mapped is None else mapped)
    return "".join(out)


def font_variants(name):
    """همهٔ نسخه‌های فونت‌شدهٔ نام، به ترتیب FONT_STYLES."""
    return [apply_font_style(name, style) for style in FONT_STYLES]


# ---------------------------------------------------------------------------
# ساخت فونت — اعتبارسنجی ورودی، کیبورد شیشه‌ای و هندلرها
# ---------------------------------------------------------------------------

FONT_NAME_PATTERN = re.compile(r"[A-Za-z]+(?: [A-Za-z]+)*")


def normalize_font_name(raw):
    """فاصله‌های اضافی را جمع می‌کند (ورودی کاربر معمولاً تمیز نیست)."""
    return re.sub(r"\s+", " ", str(raw or "")).strip()


def font_name_error(name):
    """اگر نام معتبر نباشد، متن خطای مناسب برمی‌گرداند؛ وگرنه None."""
    if not name:
        return FONT_INVALID_TEXT
    if not FONT_NAME_PATTERN.fullmatch(name):
        return FONT_INVALID_TEXT
    if len(name) > FONT_MAX_LENGTH:
        return FONT_TOO_LONG_TEXT
    return None


def font_inline_keyboard(name, token):
    """دکمه‌های شیشه‌ای: متن هر دکمه = همان نام با یک استایل."""
    rows, row = [], []
    for index, style in enumerate(FONT_STYLES):
        row.append({
            "text": apply_font_style(name, style),
            "callback_data": f"{FONT_CALLBACK_PREFIX}{token}:{index}",
        })
        if len(row) == FONT_BUTTONS_PER_ROW:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}


def start_font_flow(user_id):
    """«ساخت فونت» -> درخواست نام انگلیسی (state همین کاربر روی font)."""
    user_state = get_user_state(user_id)
    user_state["mode"] = "font"
    user_state.pop("font_name", None)
    user_state.pop("font_token", None)
    save_state()
    send_with_retry(user_id, FONT_ASK_TEXT)
    log("info", f"شروع ساخت فونت — user {user_id} (در انتظار نام انگلیسی)")


def send_font_options(user_id, name):
    """نام معتبر -> نمایش همهٔ استایل‌ها روی دکمه‌های شیشه‌ای."""
    token = uuid.uuid4().hex[:8]
    user_state = get_user_state(user_id)
    user_state["font_name"] = name
    user_state["font_token"] = token
    user_state["mode"] = "main"
    save_state()
    send_with_retry(
        user_id,
        FONT_CHOOSE_TEXT.format(name=name),
        reply_markup=font_inline_keyboard(name, token),
    )
    log("info", f"{len(FONT_STYLES)} فونت برای «{name}» ارسال شد — user {user_id}")


def handle_font_name_message(message, user_id):
    """پیام کاربر در حالت «font».

    True  = پیام مصرف شد (نام گرفته شد یا خطا نشان داده شد)
    False = پیام مربوط به منو/دستور است و باید مثل قبل پردازش شود
    """
    user_state = get_user_state(user_id)
    text = (message.get("text") or "").strip()

    if text in CANCEL_TEXTS:
        user_state["mode"] = "main"
        save_state()
        send_with_retry(user_id, FONT_CANCELLED_TEXT)
        show_main_menu(user_id)
        return True
    if text == MENU_FONT:            # دوباره زدن همان دکمه
        start_font_flow(user_id)
        return True
    if text.startswith("/") or text in MENU_BUTTONS:
        # کاربر وسط کار دکمهٔ دیگری زد: از حالت فونت خارج شو و عادی ادامه بده
        user_state["mode"] = "main"
        save_state()
        return False

    name = normalize_font_name(text)
    error = font_name_error(name)
    if error is not None:
        send_with_retry(user_id, error)
        log("info", f"نام نامعتبر برای فونت — user {user_id} ({text[:20]!r})")
        return True

    send_font_options(user_id, name)
    return True


def font_remove_keyboard(chat_id, message_id):
    """دکمه‌های فونت را جمع می‌کند تا انتخاب دوباره/اشتباه ممکن نباشد."""
    if message_id is None:
        return False
    try:
        api_call("editMessageReplyMarkup", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": {"inline_keyboard": []},
        })
        return True
    except (NetworkError, BotError) as exc:
        log("warn", f"جمع‌کردن دکمه‌های فونت با editMessageReplyMarkup نشد: {exc}")
    try:
        api_call("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": FONT_DONE_TEXT,
        })
        return True
    except (NetworkError, BotError) as exc:
        log("warn", f"جمع‌کردن دکمه‌های فونت ناموفق بود: {exc}")
    return False


def handle_font_callback(callback):
    """کلیک روی یکی از دکمه‌های فونت -> ارسال همان نام با همان استایل."""
    cb_id = callback.get("id")
    data = str(callback.get("data") or "")
    sender = callback.get("from") or {}
    user_id = sender.get("id")
    if user_id is None:
        return
    cb_message = callback.get("message") or {}
    chat_id = (cb_message.get("chat") or {}).get("id") or user_id
    message_id = cb_message.get("message_id")

    def answer(text="", alert=False):
        params = {"callback_query_id": cb_id}
        if text:
            params["text"] = text
        if alert:
            params["show_alert"] = True
        try:
            api_call("answerCallbackQuery", params)
        except (NetworkError, BotError) as exc:
            log("warn", f"answerCallbackQuery فونت نشد: {exc}")

    if not is_owner(user_id) and is_blocked(sender):
        answer(BLOCK_TEXT, alert=True)
        return

    parts = data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        answer(FONT_EXPIRED_TEXT, alert=True)
        return
    token, index = parts[1], int(parts[2])

    user_state = get_user_state(user_id)
    name = user_state.get("font_name")
    # توکن = فهرست فونتِ همین کاربر؛ فهرست‌های قدیمی/کاربر دیگر پذیرفته نمی‌شوند
    if not name or user_state.get("font_token") != token:
        answer(FONT_EXPIRED_TEXT, alert=True)
        font_remove_keyboard(chat_id, message_id)
        return
    if not 0 <= index < len(FONT_STYLES):
        answer(FONT_EXPIRED_TEXT, alert=True)
        return

    styled = apply_font_style(name, FONT_STYLES[index])
    answer()
    # فقط متن فونت‌شده؛ بدون هیچ توضیح اضافه
    send_with_retry(chat_id, styled)
    user_state["font_token"] = None
    user_state["mode"] = "main"
    save_state()
    font_remove_keyboard(chat_id, message_id)
    log("info", f"فونت «{FONT_STYLES[index][0]}» برای user {user_id} ارسال شد")


BOT_COMMANDS = [
    {"command": "start", "description": "🦊 شروع / نمایش منوی اصلی"},
    {"command": "app", "description": "🚀 ورود به روباه پلاس (برنامک)"},
    {"command": "menu", "description": "📋 نمایش دوبارهٔ منوی اصلی"},
    {"command": "buy", "description": "💎 خرید / تمدید اشتراک ربات"},
    {"command": "game", "description": "🎮 سایت بازی روباه"},
    {"command": "ads", "description": "📣 خرید تبلیغات"},
    {"command": "font", "description": "🔤 ساخت فونت"},
    {"command": "guide", "description": "📚 کانال راهنما"},
    {"command": "support", "description": "🎧 ارسال گزارش به پشتیبانی"},
]


def register_bot_commands():
    """ثبت فهرست دستورات بات (دکمهٔ آبی «منو» کنار کادر پیام — مثل BotFather).

    این دکمه سمت کلاینت است و به کش کیبورد ربطی ندارد؛ بنابراین برای کاربران
    قدیمی و جدید یکسان نمایش داده می‌شود.
    """
    try:
        api_call("setMyCommands", {"commands": BOT_COMMANDS})
        log("info", f"✅ فهرست دستورات بات ثبت شد ({len(BOT_COMMANDS)} دستور)")
    except BotError as exc:
        log("warn", f"setMyCommands پشتیبانی نشد: {exc}")
    except NetworkError as exc:
        log("warn", f"خطای شبکه هنگام setMyCommands: {exc}")


def handle_slash_command(user_id, text):
    """دستورهای اسلش‌دار منوی آبی. True اگر پردازش شد."""
    cmd = text.split()[0].lower().split("@")[0] if text.startswith("/") else ""
    if cmd == "/app":
        send_miniapp(user_id)
    elif cmd == "/menu":
        show_main_menu(user_id)
    elif cmd == "/buy":
        handle_menu_text(user_id, MENU_BUY)
    elif cmd == "/game":
        send_game_site(user_id)
    elif cmd == "/ads":
        send_ads_site(user_id)
    elif cmd == "/font":
        start_font_flow(user_id)
    elif cmd == "/guide":
        send_guide_channel(user_id)
    elif cmd == "/support":
        handle_menu_text(user_id, MENU_REPORT)
    else:
        return False
    return True


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
    """«⏳ مهلت باقی‌مانده گروه» -> متن راهنمای Bold (بدون دکمه)."""
    send_with_retry(user_id, DEADLINE_SITE_TEXT, parse_mode="HTML")
    log("info", f"متن راهنمای مهلت گروه ارسال شد — user {user_id}")


def handle_menu_text(user_id, text):
    if text == MENU_BUY:
        send_purchase_site(user_id)
    elif text == MENU_REPORT:
        user_state = get_user_state(user_id)
        user_state["mode"] = "report"
        save_state()
        send_report_prompt(user_id)
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
    elif text == MENU_ADS:
        send_ads_site(user_id)
    elif text == MENU_FONT:
        start_font_flow(user_id)
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


def notify_ask_count(user_id, total):
    """مرحلهٔ ۲: پرسیدن تعداد گیرندگان."""
    user_state = get_user_state(user_id)
    user_state["mode"] = "notify_count"
    save_state()
    send_with_retry(
        user_id,
        NOTIFY_COUNT_ASK_TEXT.format(total=fa(total), example=fa(min(208, total))),
        reply_markup=notify_count_keyboard(total),
    )


def notify_ask_confirm(user_id, limit, total):
    """مرحلهٔ ۳: پیش‌نمایش + دکمه‌های تایید/لغو."""
    message = PENDING_NOTIFY.get(user_id)
    if message is None:
        send_with_retry(user_id, NOTIFY_EXPIRED_TEXT)
        return
    NOTIFY_LIMIT[user_id] = limit
    user_state = get_user_state(user_id)
    user_state["mode"] = "notify_confirm"
    save_state()
    send_with_retry(user_id, NOTIFY_PREVIEW_TEXT)
    deliver_preserving_format(user_id, message)
    scope = (f"همهٔ {fa(total)} عضو" if limit >= total
             else f"{fa(limit)} نفر از {fa(total)} عضو")
    send_with_retry(
        user_id,
        f"این پیام برای {scope} ارسال شود؟",
        reply_markup=notify_confirm_keyboard(),
    )
    log("info", f"پیش‌نمایش اطلاع‌رسانی — admin {user_id}، هدف {limit}/{total}")


def handle_notify_text(message, user_id):
    """متن بعد از «اطلاع رسانی» -> پرسیدن تعداد گیرندگان."""
    user_state = get_user_state(user_id)
    text = (message.get("text") or "").strip()
    has_media = any(k in message for k in
                    ("photo", "video", "document", "audio", "voice", "sticker",
                     "animation", "caption"))
    if not text and not has_media:
        user_state["mode"] = "notify"
        save_state()
        send_with_retry(user_id, NOTIFY_ASK_TEXT)
        return
    if text in CANCEL_TEXTS:
        PENDING_NOTIFY.pop(user_id, None)
        NOTIFY_LIMIT.pop(user_id, None)
        user_state["mode"] = "main"
        save_state()
        show_main_menu(user_id)
        return

    targets, _ = notify_recipients()
    if not targets:
        user_state["mode"] = "main"
        save_state()
        send_with_retry(user_id, NOTIFY_NO_USERS_TEXT)
        return

    # پیام را نگه می‌داریم تا بعد از تایید، عیناً بازنشر شود
    PENDING_NOTIFY[user_id] = message
    notify_ask_count(user_id, len(targets))


def handle_notify_count(message, user_id):
    """عدد گیرندگان را می‌گیرد و می‌رود سراغ پیش‌نمایش/تایید."""
    user_state = get_user_state(user_id)
    text = (message.get("text") or "").strip()
    if text in CANCEL_TEXTS:
        PENDING_NOTIFY.pop(user_id, None)
        NOTIFY_LIMIT.pop(user_id, None)
        user_state["mode"] = "main"
        save_state()
        send_with_retry(user_id, NOTIFY_CANCELLED_TEXT)
        show_main_menu(user_id)
        return

    total = len(notify_recipients()[0])
    want = parse_count(text)
    if want is None:
        send_with_retry(user_id, NOTIFY_COUNT_BAD_TEXT,
                        reply_markup=notify_count_keyboard(total))
        return
    if want > total:
        send_with_retry(user_id, NOTIFY_COUNT_CAPPED_TEXT.format(
            want=fa(want), total=fa(total)))
        want = total
    notify_ask_confirm(user_id, want, total)


def notify_recipients():
    """فهرست گیرندگان: اعضای استارت‌زده منهای کاربران مسدود."""
    users = list((STATE.get("users") or {}).keys())
    blocked = STATE.get("blocked") or {}
    targets, skipped = [], 0
    for uid in users:
        if str(uid) in blocked:
            skipped += 1
            continue
        try:
            targets.append(int(uid))
        except (TypeError, ValueError):
            continue
    return targets, skipped


def run_notify_broadcast(owner_id, message, limit=None, progress_message_id=None):
    """ارسال اطلاع‌رسانی تا رسیدن به «limit» ارسالِ موفق.

    خطاها شمرده می‌شوند ولی جای یک ارسال موفق را نمی‌گیرند: اگر ارسال به
    کسی شکست بخورد سراغ نفر بعدی می‌رویم تا دقیقاً به تعداد خواسته‌شده
    ارسال موفق برسیم (تا جایی که عضو باقی باشد). کاربران مسدود کنار
    گذاشته می‌شوند و محدودیت نرخ سرور رعایت می‌شود.
    """
    targets, skipped = notify_recipients()
    target = len(targets) if limit is None else min(limit, len(targets))
    ok = fail = 0
    methods = {}

    def show_progress():
        if progress_message_id is None:
            return
        percent = int(ok * 100 / target) if target else 100
        try:
            api_call("editMessageText", {
                "chat_id": owner_id,
                "message_id": progress_message_id,
                "text": NOTIFY_PROGRESS_TEXT.format(
                    ok=fa(ok), target=fa(target), percent=fa(percent)),
            })
        except (NetworkError, BotError):
            pass

    for chat_id in targets:
        if ok >= target:
            break
        method = deliver_preserving_format(chat_id, message)
        if method == "failed":
            fail += 1
        else:
            ok += 1
            methods[method] = methods.get(method, 0) + 1
            if ok % NOTIFY_PROGRESS_EVERY == 0:
                show_progress()
        time.sleep(NOTIFY_SEND_DELAY)
    show_progress()

    result = f"📢 اطلاع‌رسانی ارسال شد: {fa(ok)} نفر"
    if limit is not None:
        result += f" (هدف: {fa(target)})"
    if fail:
        result += f"\n↩️ {fa(fail)} ارسال ناموفق رد شد و جایگزین شد"
    if skipped:
        result += "\n" + NOTIFY_SKIPPED_BLOCKED_TEXT.format(n=fa(skipped))
    if methods:
        result += "\n🛠 روش ارسال: " + "، ".join(
            f"{k}: {fa(v)}" for k, v in methods.items())
    if ok < target:
        result += "\n" + NOTIFY_PARTIAL_TEXT.format(ok=fa(ok), want=fa(target))
    send_with_retry(owner_id, result)
    log("info", f"اطلاع‌رسانی: {ok}/{target} موفق، {fail} خطا، "
                f"{skipped} مسدود — admin {owner_id}")


def handle_notify_callback(callback):
    """دکمه‌های شیشه‌ای اطلاع‌رسانی — فقط برای مالک."""
    cb_id = callback.get("id")
    data = callback.get("data")
    sender = callback.get("from") or {}
    user_id = sender.get("id")
    cb_message = callback.get("message") or {}
    chat_id = (cb_message.get("chat") or {}).get("id") or user_id
    message_id = cb_message.get("message_id")

    def answer(text="", alert=False):
        params = {"callback_query_id": cb_id}
        if text:
            params["text"] = text
        if alert:
            params["show_alert"] = True
        try:
            api_call("answerCallbackQuery", params)
        except (NetworkError, BotError) as exc:
            log("warn", f"answerCallbackQuery نشد: {exc}")

    # فقط مالک اجازهٔ زدن این دکمه‌ها را دارد
    if not is_owner(user_id):
        answer(NOTIFY_ONLY_OWNER_TEXT, alert=True)
        log("warn", f"تلاش غیرمجاز برای دکمهٔ اطلاع‌رسانی — user {user_id}")
        return

    def edit(text):
        if message_id is None:
            send_with_retry(chat_id, text)
            return
        try:
            api_call("editMessageText", {
                "chat_id": chat_id, "message_id": message_id, "text": text,
            })
        except (NetworkError, BotError):
            send_with_retry(chat_id, text)

    user_state = get_user_state(user_id)

    if data == NOTIFY_CANCEL_CALLBACK:
        PENDING_NOTIFY.pop(user_id, None)
        NOTIFY_LIMIT.pop(user_id, None)
        user_state["mode"] = "main"
        save_state()
        answer("لغو شد")
        edit(NOTIFY_CANCELLED_TEXT)
        show_main_menu(user_id)
        log("info", f"اطلاع‌رسانی لغو شد — admin {user_id}")
        return

    if data == NOTIFY_ALL_CALLBACK:
        total = len(notify_recipients()[0])
        if user_id not in PENDING_NOTIFY or total == 0:
            answer(NOTIFY_EXPIRED_TEXT, alert=True)
            return
        answer(f"همهٔ {total} عضو")
        edit(f"👥 گیرندگان: همهٔ {fa(total)} عضو")
        notify_ask_confirm(user_id, total, total)
        return

    # تایید ارسال
    pending = PENDING_NOTIFY.pop(user_id, None)
    limit = NOTIFY_LIMIT.pop(user_id, None)
    user_state["mode"] = "main"
    save_state()
    if pending is None:
        answer(NOTIFY_EXPIRED_TEXT, alert=True)
        return
    answer("در حال ارسال…")
    edit(NOTIFY_STARTED_TEXT)
    run_notify_broadcast(user_id, pending, limit, progress_message_id=message_id)


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
        data = (callback or {}).get("data")
        if callback and data == VERIFY_CALLBACK:
            try:
                handle_verify_callback(callback)
            except (NetworkError, BotError) as exc:
                log("error", f"خطا در callback: {exc}")
        elif callback and data in (NOTIFY_CONFIRM_CALLBACK,
                                   NOTIFY_CANCEL_CALLBACK,
                                   NOTIFY_ALL_CALLBACK):
            try:
                handle_notify_callback(callback)
            except (NetworkError, BotError) as exc:
                log("error", f"خطا در callback اطلاع‌رسانی: {exc}")
        elif callback and str(data or "").startswith(FONT_CALLBACK_PREFIX):
            try:
                handle_font_callback(callback)
            except (NetworkError, BotError) as exc:
                log("error", f"خطا در callback فونت: {exc}")
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
            if user_state.get("mode") in ("report", "notify", "proof",
                                          "notify_confirm", "notify_count"):
                user_state["mode"] = "main"
                save_state()
            handle_members_list(user_id)
            return
        if text == ADMIN_NOTIFY_CMD:
            PENDING_NOTIFY.pop(user_id, None)
            NOTIFY_LIMIT.pop(user_id, None)
            if user_state.get("mode") in ("report", "proof", "notify_confirm",
                                          "notify_count"):
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
        if user_state.get("mode") == "notify_count":
            handle_notify_count(message, user_id)
            return
        if user_state.get("mode") == "notify_confirm":
            # تایید فقط با دکمهٔ شیشه‌ای؛ ولی «انصراف» تایپی هم کار می‌کند
            if text in CANCEL_TEXTS:
                PENDING_NOTIFY.pop(user_id, None)
                NOTIFY_LIMIT.pop(user_id, None)
                user_state["mode"] = "main"
                save_state()
                send_with_retry(user_id, NOTIFY_CANCELLED_TEXT)
                show_main_menu(user_id)
                return
            send_with_retry(user_id, NOTIFY_USE_BUTTONS_TEXT)
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

    # در انتظار نام انگلیسی برای ساخت فونت (اگر دکمهٔ منو زد، عادی ادامه می‌دهیم)
    if user_state.get("mode") == "font":
        try:
            if handle_font_name_message(message, user_id):
                return
        except (NetworkError, BotError) as exc:
            log("error", f"خطا در ساخت فونت: {exc}")
            return

    try:
        # کاربران قدیمی: کیبورد کش‌شده‌شان دکمهٔ جدید را ندارد → ارسال منوی تازه
        ensure_menu_keyboard_fresh(user_id)
        if handle_slash_command(user_id, text):
            return
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
    register_bot_commands()
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
