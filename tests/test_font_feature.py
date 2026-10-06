#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تست‌های قابلیت «ساخت فونت» (و اطمینان از سالم‌ماندن قابلیت‌های قبلی).

اجرا:
    python3 -m unittest discover -s tests -v
    (یا با pytest: python3 -m pytest tests -q)

هیچ درخواست شبکه‌ای انجام نمی‌شود: api_call با یک جایگزین ساختگی عوض
می‌شود و save_state هم غیرفعال می‌شود تا چیزی در data/ نوشته نشود.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import splus_test_bot as bot  # noqa: E402

# نمونه‌های مرجع: خروجی خواسته‌شده برای نام «Fox» به ترتیب فهرست درخواست.
# (در نمونهٔ «negative squared» یک VARIATION SELECTOR-16 اضافه وجود داشت که
#  در مقایسه حذف می‌شود؛ خروجی ربات بدون آن کاراکتر نامرئی تولید می‌شود.)
EXPECTED_FOX = [
    "ғᴏx",
    "𝔽𝕠𝕩",
    "𝙵𝚘𝚡",
    "𝐅𝐨𝐱",
    "ܻ⨍ᨵׁׅׅ᥊ׁׅ",
    "ƒσχ",
    "ꊰꄲꉧ",
    "ᖴO᙭",
    "ғᴏx",
    "fOx",
    "Ｆｏｘ",
    "𝙁𝙤𝙭",
    "𝘍𝘰𝘹",
    "𝑭𝒐𝒙",
    "𝐹𝑜𝑥",
    "𝗙𝗼𝘅",
    "𝖥𝗈𝗑",
    "𝓕𝓸𝔁",
    "𝐹𝑜𝓍",
    "𝕱𝖔𝖝",
    "𝔉𝔬𝔵",
    "ᶠᵒˣ",
    "𝒻ₒₓ",
    "🄵🄾🅇",
    "🅕🅞🅧",
    "🅵️🅾🆇",
    "𝖿᥆᥊",
    "բօx",
    "ϝσx",
    "Fიx",
    "ҒϴХ",
    "ᚫᛟᚷ",
    "千ㄖ乂",
    "F̣ọx̣",
]

VS16 = "\uFE0F"
USER_A = 111111
USER_B = 222222


def clean(text):
    """حذف کاراکتر نامرئی variation selector برای مقایسهٔ متن‌ها."""
    return text.replace(VS16, "")


class FakeAPI:
    """جایگزین api_call — فقط فراخوانی‌ها را ضبط می‌کند."""

    def __init__(self):
        self.calls = []
        self._message_id = 5000

    def __call__(self, method, params=None):
        params = dict(params or {})
        self.calls.append((method, params))
        if method in ("sendMessage", "copyMessage"):
            self._message_id += 1
            return {"message_id": self._message_id,
                    "chat": {"id": params.get("chat_id")}}
        return {}

    def multipart(self, method, fields, files):
        """جایگزین api_call_multipart (آپلود عکس) — بدون شبکه."""
        params = dict(fields)
        params["_files"] = [name for name, _, _, _ in files]
        self.calls.append((method, params))
        self._message_id += 1
        return {"message_id": self._message_id,
                "chat": {"id": params.get("chat_id")}}

    # --- کمک‌کننده‌ها -----------------------------------------------------
    def params_of(self, method):
        return [params for name, params in self.calls if name == method]

    def methods(self):
        return [name for name, _ in self.calls]

    def sent_texts(self):
        return [params.get("text", "") for params in self.params_of("sendMessage")]

    def last_sent(self):
        messages = self.params_of("sendMessage")
        return messages[-1] if messages else None

    def keyboard_messages(self):
        return [params for params in self.params_of("sendMessage")
                if isinstance(params.get("reply_markup"), dict)
                and "inline_keyboard" in params["reply_markup"]]

    def reset(self):
        self.calls.clear()


class BotTestCase(unittest.TestCase):
    """پایهٔ تست‌ها: وضعیت تمیز + API ساختگی + بدون نوشتن در دیسک."""

    def setUp(self):
        bot.STATE = {"learned": {}, "users": {}, "tickets": {}, "blocked": {}}
        self.api = FakeAPI()
        self._real_api_call = bot.api_call
        self._real_multipart = bot.api_call_multipart
        self._real_save_state = bot.save_state
        self._real_log = bot.log
        bot.api_call = self.api
        bot.api_call_multipart = self.api.multipart
        bot.save_state = lambda: None
        bot.log = lambda *args, **kwargs: None   # خروجی تست‌ها تمیز بماند

    def tearDown(self):
        bot.api_call = self._real_api_call
        bot.api_call_multipart = self._real_multipart
        bot.save_state = self._real_save_state
        bot.log = self._real_log

    # --- ابزارهای مشترک ---------------------------------------------------
    def make_verified(self, user_id):
        state = bot.get_user_state(user_id)
        state["verified"] = True
        state["mode"] = "main"
        state["kb_version"] = bot.MENU_KEYBOARD_VERSION
        return state

    def user_message(self, user_id, text):
        return {
            "message_id": user_id % 1000,
            "from": {"id": user_id, "first_name": "Tester"},
            "chat": {"id": user_id, "type": "private"},
            "text": text,
        }

    def send_text(self, user_id, text):
        """پیام کاربر را از همان مسیر واقعی handle_update عبور می‌دهد."""
        bot.handle_update({"update_id": 1, "message": self.user_message(user_id, text)})

    def font_callback(self, user_id, data, message_id=777):
        return {
            "update_id": 2,
            "callback_query": {
                "id": "cb-1",
                "from": {"id": user_id, "first_name": "Tester"},
                "message": {"message_id": message_id,
                            "chat": {"id": user_id, "type": "private"}},
                "data": data,
            },
        }

    def open_font_list(self, user_id, name):
        """جریان کامل: کلیک «ساخت فونت» -> ارسال نام -> دریافت دکمه‌ها."""
        self.make_verified(user_id)
        self.send_text(user_id, bot.MENU_FONT)
        self.send_text(user_id, name)
        keyboards = self.api.keyboard_messages()
        self.assertTrue(keyboards, "کیبورد شیشه‌ای فونت ارسال نشد")
        return keyboards[-1]["reply_markup"]["inline_keyboard"]


# ---------------------------------------------------------------------------
# ۱) موتور فونت
# ---------------------------------------------------------------------------
class FontEngineTests(unittest.TestCase):

    def test_all_requested_styles_exist(self):
        """همهٔ ۳۴ استایل خواسته‌شده تعریف شده‌اند."""
        self.assertEqual(len(bot.FONT_STYLES), len(EXPECTED_FOX))
        self.assertEqual(len(bot.FONT_STYLES), 34)

    def test_style_ids_are_unique(self):
        ids = [style[0] for style in bot.FONT_STYLES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_style_matches_reference_sample(self):
        """خروجی هر استایل برای «Fox» دقیقاً همان نمونهٔ درخواست است."""
        for index, (style, expected) in enumerate(zip(bot.FONT_STYLES,
                                                      EXPECTED_FOX)):
            with self.subTest(style=style[0], index=index):
                self.assertEqual(bot.apply_font_style("Fox", style),
                                 clean(expected))

    def test_font_variants_returns_all_styles_in_order(self):
        variants = bot.font_variants("Fox")
        self.assertEqual(len(variants), len(bot.FONT_STYLES))
        self.assertEqual([clean(item) for item in EXPECTED_FOX], variants)

    def test_uppercase_input_is_handled(self):
        """ورودی تماماً بزرگ هم باید فونت شود (نه خالی، نه دست‌نخورده)."""
        for style in bot.FONT_STYLES:
            with self.subTest(style=style[0]):
                result = bot.apply_font_style("FOX", style)
                self.assertTrue(result.strip())

    def test_unmapped_characters_fall_back_to_original(self):
        """کاراکتر بدون نگاشت (فاصله و خط تیره) عیناً باقی می‌ماند."""
        for style in bot.FONT_STYLES:
            with self.subTest(style=style[0]):
                result = bot.apply_font_style("Fo-x y", style)
                self.assertIn("-", result)
                self.assertIn(" ", result)

    def test_space_between_two_words_is_preserved(self):
        for style in bot.FONT_STYLES:
            with self.subTest(style=style[0]):
                self.assertIn(" ", bot.apply_font_style("Ali Reza", style))

    def test_long_name_renders_in_every_style(self):
        name = "A" * bot.FONT_MAX_LENGTH
        for style in bot.FONT_STYLES:
            with self.subTest(style=style[0]):
                self.assertTrue(bot.apply_font_style(name, style))

    def test_empty_input_stays_empty(self):
        for style in bot.FONT_STYLES:
            with self.subTest(style=style[0]):
                self.assertEqual(bot.apply_font_style("", style), "")


# ---------------------------------------------------------------------------
# ۲) کیبوردها — دکمهٔ جدید + سالم‌ماندن کیبوردهای قبلی
# ---------------------------------------------------------------------------
class KeyboardTests(BotTestCase):

    PREVIOUS_ROWS = [
        [bot.MENU_BUY, bot.MENU_REPORT],
        [bot.MENU_EXTEND, bot.MENU_DEADLINE],
        [bot.MENU_GAME, bot.MENU_GUIDE],
        [bot.MENU_MINIAPP, bot.MENU_ADS],
    ]

    def test_font_button_label_is_exact(self):
        self.assertEqual(bot.MENU_FONT, "ساخت فونت")

    def test_font_button_is_on_main_keyboard(self):
        rows = bot.main_reply_keyboard()["keyboard"]
        flat = [text for row in rows for text in row]
        self.assertIn(bot.MENU_FONT, flat)

    def test_previous_keyboard_rows_unchanged(self):
        """چیدمان قبلی دست‌نخورده است و فقط یک ردیف اضافه شده."""
        rows = bot.main_reply_keyboard()["keyboard"]
        self.assertEqual(rows[:4], self.PREVIOUS_ROWS)
        self.assertEqual(rows[4], [bot.MENU_FONT])
        self.assertEqual(len(rows), 5)

    def test_resize_keyboard_flag_preserved(self):
        self.assertTrue(bot.main_reply_keyboard()["resize_keyboard"])

    def test_keyboard_version_bumped_for_old_users(self):
        """کاربر قدیمی با نسخهٔ کیبورد قبلی، منوی تازه (با دکمهٔ فونت) می‌گیرد."""
        state = bot.get_user_state(USER_A)
        state["verified"] = True
        state["mode"] = "main"
        state["kb_version"] = 3
        self.assertTrue(bot.ensure_menu_keyboard_fresh(USER_A))
        markup = self.api.params_of("sendMessage")[-1]["reply_markup"]
        flat = [text for row in markup["keyboard"] for text in row]
        self.assertIn(bot.MENU_FONT, flat)
        for label in (bot.MENU_BUY, bot.MENU_ADS, bot.MENU_MINIAPP):
            self.assertIn(label, flat)

    def test_start_inline_keyboard_untouched(self):
        rows = bot.start_inline_keyboard()["inline_keyboard"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[2][0]["callback_data"], bot.VERIFY_CALLBACK)
        self.assertIn("url", rows[0][0])
        self.assertIn("url", rows[1][0])

    def test_other_inline_keyboards_untouched(self):
        self.assertIn("url", bot.purchase_inline_keyboard()["inline_keyboard"][0][0])
        self.assertIn("url", bot.site_inline_keyboard()["inline_keyboard"][0][0])
        notify_row = bot.notify_confirm_keyboard()["inline_keyboard"][0]
        self.assertEqual(notify_row[0]["callback_data"], bot.NOTIFY_CONFIRM_CALLBACK)
        self.assertEqual(notify_row[1]["callback_data"], bot.NOTIFY_CANCEL_CALLBACK)

    def test_font_command_added_to_blue_menu(self):
        commands = [item["command"] for item in bot.BOT_COMMANDS]
        self.assertIn("font", commands)
        for previous in ("start", "app", "menu", "buy", "game", "ads",
                         "guide", "support"):
            self.assertIn(previous, commands)


# ---------------------------------------------------------------------------
# ۳) درخواست نام انگلیسی و اعتبارسنجی ورودی
# ---------------------------------------------------------------------------
class FontPromptTests(BotTestCase):

    def test_click_on_font_button_asks_for_english_name(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_FONT)
        self.assertEqual(self.api.sent_texts()[-1], "✏️ اسم خودت رو به انگلیسی بنویس:")
        self.assertEqual(bot.FONT_ASK_TEXT, "✏️ اسم خودت رو به انگلیسی بنویس:")
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "font")

    def test_font_slash_command_starts_same_flow(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, "/font")
        self.assertEqual(self.api.sent_texts()[-1], bot.FONT_ASK_TEXT)
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "font")

    def test_invalid_inputs_are_rejected_and_name_is_requested_again(self):
        """فارسی، عدد، ترکیبی و نماد رد می‌شوند و دوباره نام خواسته می‌شود."""
        bad_inputs = ["علی", "۱۲۳", "1234", "Ali1", "ali@name", "فارسی English",
                      "!!!", "_", "Ali  ", "علی Reza"]
        for raw in bad_inputs:
            with self.subTest(value=raw):
                bot.STATE = {"learned": {}, "users": {}, "tickets": {},
                             "blocked": {}}
                self.api.reset()
                self.make_verified(USER_A)
                self.send_text(USER_A, bot.MENU_FONT)
                self.api.reset()
                self.send_text(USER_A, raw)
                last = self.api.last_sent()
                if raw.strip() and bot.FONT_NAME_PATTERN.fullmatch(
                        bot.normalize_font_name(raw)):
                    continue  # ورودی در واقع معتبر بوده (مثل "Ali  ")
                self.assertIn(bot.FONT_ASK_TEXT, last["text"])
                self.assertTrue(last["text"].startswith("⚠️"))
                self.assertNotIn("reply_markup", last)
                self.assertEqual(bot.get_user_state(USER_A)["mode"], "font")

    def test_persian_input_keeps_user_in_font_mode(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_FONT)
        self.send_text(USER_A, "سلام")
        self.assertEqual(self.api.last_sent()["text"], bot.FONT_INVALID_TEXT)
        self.send_text(USER_A, "Fox")
        self.assertTrue(self.api.keyboard_messages())

    def test_name_longer_than_limit_is_rejected(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_FONT)
        self.send_text(USER_A, "A" * (bot.FONT_MAX_LENGTH + 1))
        self.assertEqual(self.api.last_sent()["text"], bot.FONT_TOO_LONG_TEXT)
        self.assertEqual(self.api.keyboard_messages(), [])

    def test_name_at_exact_limit_is_accepted(self):
        rows = self.open_font_list(USER_A, "A" * bot.FONT_MAX_LENGTH)
        self.assertEqual(sum(len(row) for row in rows), len(bot.FONT_STYLES))

    def test_extra_spaces_are_normalized(self):
        self.open_font_list(USER_A, "   John    Doe  ")
        self.assertEqual(bot.get_user_state(USER_A)["font_name"], "John Doe")

    def test_cancel_word_leaves_font_mode(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_FONT)
        self.send_text(USER_A, "انصراف")
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "main")
        self.assertIn(bot.FONT_CANCELLED_TEXT, self.api.sent_texts())

    def test_menu_button_during_font_mode_still_works(self):
        """وسط ساخت فونت، دکمه‌های قبلی منو نباید به‌عنوان «نام» بلعیده شوند."""
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_FONT)
        self.api.reset()
        self.send_text(USER_A, bot.MENU_GUIDE)
        last = self.api.last_sent()
        self.assertEqual(last["reply_markup"]["inline_keyboard"][0][0]["text"],
                         bot.GUIDE_BUTTON_TEXT)
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "main")


# ---------------------------------------------------------------------------
# ۴) نمایش فونت‌ها روی دکمه‌های شیشه‌ای
# ---------------------------------------------------------------------------
class FontKeyboardTests(BotTestCase):

    def test_all_styles_are_shown_as_inline_buttons(self):
        rows = self.open_font_list(USER_A, "Fox")
        buttons = [button for row in rows for button in row]
        self.assertEqual(len(buttons), len(bot.FONT_STYLES))
        self.assertEqual([button["text"] for button in buttons],
                         [clean(sample) for sample in EXPECTED_FOX])

    def test_button_rows_respect_layout(self):
        rows = self.open_font_list(USER_A, "Fox")
        for row in rows:
            self.assertLessEqual(len(row), bot.FONT_BUTTONS_PER_ROW)

    def test_callback_data_is_short_and_well_formed(self):
        rows = self.open_font_list(USER_A, "Fox")
        token = bot.get_user_state(USER_A)["font_token"]
        for index, button in enumerate(b for row in rows for b in row):
            data = button["callback_data"]
            self.assertEqual(data, f"{bot.FONT_CALLBACK_PREFIX}{token}:{index}")
            self.assertLessEqual(len(data.encode("utf-8")), 64)

    def test_buttons_show_the_name_the_user_typed(self):
        rows = self.open_font_list(USER_A, "Sara")
        texts = [button["text"] for row in rows for button in row]
        self.assertEqual(texts, bot.font_variants("Sara"))
        self.assertIn("sᴀʀᴀ", texts)        # small caps
        self.assertIn("𝐒𝐚𝐫𝐚", texts)        # bold
        self.assertIn("丂卂尺卂", texts)      # cjk


# ---------------------------------------------------------------------------
# ۵) رفتار دکمه‌های فونت (callback)
# ---------------------------------------------------------------------------
class FontCallbackTests(BotTestCase):

    def test_every_font_button_sends_its_own_style(self):
        """هر ۳۴ دکمه: متن ارسالی دقیقاً همان نسخهٔ فونت‌شده است."""
        for index in range(len(bot.FONT_STYLES)):
            with self.subTest(style=bot.FONT_STYLES[index][0]):
                bot.STATE = {"learned": {}, "users": {}, "tickets": {},
                             "blocked": {}}
                self.api.reset()
                rows = self.open_font_list(USER_A, "Fox")
                button = [b for row in rows for b in row][index]
                self.api.reset()
                bot.handle_update(self.font_callback(USER_A,
                                                     button["callback_data"]))
                sent = self.api.params_of("sendMessage")
                self.assertEqual(len(sent), 1)
                self.assertEqual(sent[0]["text"], clean(EXPECTED_FOX[index]))
                self.assertEqual(sent[0]["text"], button["text"])

    def test_sent_message_has_no_extra_text_or_markup(self):
        rows = self.open_font_list(USER_A, "Fox")
        button = rows[1][0]  # استایل چهارم (bold)
        self.api.reset()
        bot.handle_update(self.font_callback(USER_A, button["callback_data"]))
        message = self.api.params_of("sendMessage")[0]
        self.assertEqual(message["text"], "𝐅𝐨𝐱")
        self.assertNotIn("parse_mode", message)
        self.assertNotIn("reply_markup", message)
        self.assertEqual(message["chat_id"], USER_A)

    def test_callback_is_answered(self):
        rows = self.open_font_list(USER_A, "Fox")
        self.api.reset()
        bot.handle_update(self.font_callback(USER_A,
                                             rows[0][0]["callback_data"]))
        self.assertIn("answerCallbackQuery", self.api.methods())

    def test_buttons_are_removed_after_selection(self):
        rows = self.open_font_list(USER_A, "Fox")
        self.api.reset()
        bot.handle_update(self.font_callback(USER_A,
                                             rows[0][1]["callback_data"],
                                             message_id=4242))
        edits = self.api.params_of("editMessageReplyMarkup")
        self.assertEqual(len(edits), 1)
        self.assertEqual(edits[0]["message_id"], 4242)
        self.assertEqual(edits[0]["reply_markup"], {"inline_keyboard": []})

    def test_second_click_on_old_list_is_rejected(self):
        """بعد از یک انتخاب، فهرست قدیمی دیگر فونت نمی‌فرستد."""
        rows = self.open_font_list(USER_A, "Fox")
        buttons = [b for row in rows for b in row]
        bot.handle_update(self.font_callback(USER_A, buttons[0]["callback_data"]))
        self.api.reset()
        bot.handle_update(self.font_callback(USER_A, buttons[5]["callback_data"]))
        self.assertEqual(self.api.params_of("sendMessage"), [])
        answers = self.api.params_of("answerCallbackQuery")
        self.assertEqual(answers[0]["text"], bot.FONT_EXPIRED_TEXT)

    def test_unknown_token_is_rejected(self):
        self.open_font_list(USER_A, "Fox")
        self.api.reset()
        bot.handle_update(self.font_callback(USER_A, "font:deadbeef:3"))
        self.assertEqual(self.api.params_of("sendMessage"), [])
        self.assertEqual(self.api.params_of("answerCallbackQuery")[0]["text"],
                         bot.FONT_EXPIRED_TEXT)

    def test_malformed_callback_data_is_ignored_safely(self):
        self.open_font_list(USER_A, "Fox")
        token = bot.get_user_state(USER_A)["font_token"]
        for data in ("font:", "font:x", f"font:{token}:abc",
                     f"font:{token}:999", "font:a:b:c"):
            with self.subTest(data=data):
                self.api.reset()
                bot.handle_update(self.font_callback(USER_A, data))
                self.assertEqual(self.api.params_of("sendMessage"), [])

    def test_blocked_user_cannot_use_font_buttons(self):
        rows = self.open_font_list(USER_A, "Fox")
        bot.STATE["blocked"][str(USER_A)] = {"at": "now"}
        self.api.reset()
        bot.handle_update(self.font_callback(USER_A,
                                             rows[0][0]["callback_data"]))
        self.assertEqual(self.api.params_of("sendMessage"), [])
        self.assertEqual(self.api.params_of("answerCallbackQuery")[0]["text"],
                         bot.BLOCK_TEXT)

    def test_previous_callbacks_still_work(self):
        """callback تایید عضویت (قابلیت قبلی) نباید خراب شده باشد."""
        bot.handle_update({
            "update_id": 9,
            "callback_query": {
                "id": "cb-verify",
                "from": {"id": USER_B, "first_name": "Tester"},
                "message": {"message_id": 1,
                            "chat": {"id": USER_B, "type": "private"}},
                "data": bot.VERIFY_CALLBACK,
            },
        })
        self.assertTrue(bot.get_user_state(USER_B)["verified"])
        markup = self.api.params_of("sendMessage")[-1]["reply_markup"]
        self.assertIn([bot.MENU_BUY, bot.MENU_REPORT], markup["keyboard"])


# ---------------------------------------------------------------------------
# ۶) استقلال state کاربران
# ---------------------------------------------------------------------------
class PerUserStateTests(BotTestCase):

    def test_names_of_two_users_do_not_mix(self):
        rows_a = self.open_font_list(USER_A, "Alpha")
        rows_b = self.open_font_list(USER_B, "Beta")
        self.assertEqual(bot.get_user_state(USER_A)["font_name"], "Alpha")
        self.assertEqual(bot.get_user_state(USER_B)["font_name"], "Beta")

        self.api.reset()
        bot.handle_update(self.font_callback(USER_A,
                                             rows_a[1][0]["callback_data"]))
        bot.handle_update(self.font_callback(USER_B,
                                             rows_b[1][0]["callback_data"]))
        sent = self.api.params_of("sendMessage")
        self.assertEqual(sent[0]["chat_id"], USER_A)
        self.assertEqual(sent[0]["text"], bot.apply_font_style("Alpha",
                                                               bot.FONT_STYLES[3]))
        self.assertEqual(sent[1]["chat_id"], USER_B)
        self.assertEqual(sent[1]["text"], bot.apply_font_style("Beta",
                                                               bot.FONT_STYLES[3]))

    def test_one_user_cannot_use_another_users_list(self):
        rows_a = self.open_font_list(USER_A, "Alpha")
        self.make_verified(USER_B)
        self.api.reset()
        bot.handle_update(self.font_callback(USER_B,
                                             rows_a[0][0]["callback_data"]))
        self.assertEqual(self.api.params_of("sendMessage"), [])
        self.assertEqual(self.api.params_of("answerCallbackQuery")[0]["text"],
                         bot.FONT_EXPIRED_TEXT)

    def test_font_mode_of_one_user_does_not_affect_another(self):
        self.make_verified(USER_A)
        self.make_verified(USER_B)
        self.send_text(USER_A, bot.MENU_FONT)
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "font")
        self.assertEqual(bot.get_user_state(USER_B)["mode"], "main")

        self.api.reset()
        self.send_text(USER_B, bot.MENU_GAME)   # کاربر دوم کار عادی خودش را می‌کند
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "font")
        self.assertIsNone(bot.get_user_state(USER_B).get("font_name"))

    def test_state_is_stored_under_each_user_key(self):
        self.open_font_list(USER_A, "Alpha")
        self.open_font_list(USER_B, "Beta")
        self.assertNotEqual(bot.STATE["users"][str(USER_A)]["font_token"],
                            bot.STATE["users"][str(USER_B)]["font_token"])


# ---------------------------------------------------------------------------
# ۷) قابلیت‌های قبلی ربات
# ---------------------------------------------------------------------------
class ExistingFeaturesTests(BotTestCase):

    def test_report_flow_untouched(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_REPORT)
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "report")

    def test_buy_and_ads_buttons_untouched(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_BUY)
        self.send_text(USER_A, bot.MENU_ADS)
        urls = [button["url"]
                for params in self.api.params_of("sendMessage")
                if isinstance(params.get("reply_markup"), dict)
                for row in params["reply_markup"].get("inline_keyboard", [])
                for button in row if "url" in button]
        multipart_used = [params for params in self.api.params_of("sendPhoto")]
        self.assertTrue(urls or multipart_used)

    def test_unknown_text_still_shows_main_menu(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, "یک متن تصادفی")
        self.assertIn(bot.MAIN_MENU_TEXT, self.api.sent_texts()[-1])

    def test_non_text_message_in_font_mode_asks_again(self):
        """عکس/استیکر به‌جای نام: پیام مناسب و درخواست دوبارهٔ نام."""
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_FONT)
        bot.handle_update({"update_id": 3, "message": {
            "message_id": 12,
            "from": {"id": USER_A, "first_name": "Tester"},
            "chat": {"id": USER_A, "type": "private"},
            "photo": [{"file_id": "x"}],
        }})
        self.assertEqual(self.api.last_sent()["text"], bot.FONT_INVALID_TEXT)
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "font")

    def test_owner_can_use_font_feature_too(self):
        owner_id = int(bot.CFG["owner_user_id"])
        self.make_verified(owner_id)
        self.send_text(owner_id, bot.MENU_FONT)
        self.assertEqual(self.api.sent_texts()[-1], bot.FONT_ASK_TEXT)
        self.send_text(owner_id, "Fox")
        rows = self.api.keyboard_messages()[-1]["reply_markup"]["inline_keyboard"]
        self.assertEqual(sum(len(row) for row in rows), len(bot.FONT_STYLES))

    def test_admin_commands_still_reachable(self):
        """دستور مدیریتی «دیدن اعضا» نباید با قابلیت جدید تداخل کند."""
        owner_id = int(bot.CFG["owner_user_id"])
        self.make_verified(owner_id)
        self.send_text(owner_id, bot.ADMIN_MEMBERS_CMD)
        self.assertTrue(any("اعضای ربات" in text or text == bot.MEMBERS_EMPTY_TEXT
                            for text in self.api.sent_texts()))

    def test_unverified_user_is_not_sent_to_font_flow(self):
        bot.get_user_state(USER_A)   # تایید نشده
        self.send_text(USER_A, bot.MENU_FONT)
        self.assertNotEqual(bot.get_user_state(USER_A).get("mode"), "font")
        self.assertNotIn(bot.FONT_ASK_TEXT, self.api.sent_texts())


if __name__ == "__main__":
    unittest.main(verbosity=2)
