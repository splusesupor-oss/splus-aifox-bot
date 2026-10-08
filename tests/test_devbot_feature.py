#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تست‌های قابلیت «🤖 ربات برنامه نویس» (@acodai) — بدون شبکه.

اجرا:
    python3 -m unittest discover -s tests -v
    (یا با pytest: python3 -m pytest tests -q)

api_call / api_call_multipart با جایگزین ساختگی عوض می‌شوند و save_state
غیرفعال می‌شود تا چیزی در data/ نوشته نشود. عکس مسیر sendPhoto هم با یک
فایل jpg ساختگی (temp) جایگزین می‌شود.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import splus_test_bot as bot  # noqa: E402

USER_A = 111111
USER_B = 222222
GROUP_URL = "https://splus.ir/joingroup/AI_hfuzaN9GGKPWF0MsDJg"
DEVBOT_URL = "https://splus.ir/acodai"

# خطوط فارسیِ متن publicity — باید کامل داخل <b>...</b> باشند
PERSIAN_LINES = [
    "ربات",
    "یک ربات راهنمای برنامه نویس دارای هوش مصنوعی برای سوالات در مورد "
    "برنامه نویسی با بهترین راهنمایی ها",
    "«🗳 » ربات اشتراکی می‌باشد و فقط برای افراد برنامه نویس مناسبه "
    "برای تست وارد گروه زیر شوید",
]


class FakeAPI:
    """جایگزین api_call / api_call_multipart — فقط فراخوانی‌ها را ضبط می‌کند."""

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
        params = dict(fields)
        params["_files"] = [name for name, _, _, _ in files]
        self.calls.append((method, params))
        self._message_id += 1
        return {"message_id": self._message_id,
                "chat": {"id": params.get("chat_id")}}

    def params_of(self, method):
        return [params for name, params in self.calls if name == method]

    def last_sent(self):
        messages = self.params_of("sendMessage")
        return messages[-1] if messages else None

    def reset(self):
        self.calls.clear()


class BotTestCase(unittest.TestCase):
    """پایهٔ تست‌ها: وضعیت تمیز + API ساختگی + عکس ساختگی + بدون نوشتن در دیسک."""

    def setUp(self):
        bot.STATE = {"learned": {}, "users": {}, "tickets": {}, "blocked": {}}
        self.api = FakeAPI()
        self._real_api_call = bot.api_call
        self._real_multipart = bot.api_call_multipart
        self._real_save_state = bot.save_state
        self._real_log = bot.log
        self._real_photo = bot.DEVBOT_PHOTO
        bot.api_call = self.api
        bot.api_call_multipart = self.api.multipart
        bot.save_state = lambda: None
        bot.log = lambda *args, **kwargs: None
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(b"\xff\xd8\xff\xd9")   # هدرهای jpg ساختگی
        tmp.close()
        bot.DEVBOT_PHOTO = Path(tmp.name)

    def tearDown(self):
        bot.api_call = self._real_api_call
        bot.api_call_multipart = self._real_multipart
        bot.save_state = self._real_save_state
        bot.log = self._real_log
        bot.DEVBOT_PHOTO = self._real_photo

    def make_verified(self, user_id):
        state = bot.get_user_state(user_id)
        state["verified"] = True
        state["mode"] = "main"
        state["kb_version"] = bot.MENU_KEYBOARD_VERSION
        return state

    def send_text(self, user_id, text):
        """پیام کاربر را از همان مسیر واقعی handle_update عبور می‌دهد."""
        bot.handle_update({
            "update_id": 1,
            "message": {
                "message_id": user_id % 1000,
                "from": {"id": user_id, "first_name": "Tester"},
                "chat": {"id": user_id, "type": "private"},
                "text": text,
            },
        })

    def photo_calls(self):
        return self.api.params_of("sendPhoto")


# ---------------------------------------------------------------------------
# ۱) کیبورد و ثابت‌ها
# ---------------------------------------------------------------------------
class KeyboardTests(BotTestCase):

    def test_button_label_is_exact(self):
        self.assertEqual(bot.MENU_DEVBOT, "🤖 ربات برنامه نویس")

    def test_button_is_on_main_keyboard(self):
        rows = bot.main_reply_keyboard()["keyboard"]
        flat = [text for row in rows for text in row]
        self.assertIn(bot.MENU_DEVBOT, flat)

    def test_button_is_in_menu_buttons_tuple(self):
        """برای Escape از حالت‌های میانی (فونت/گزارش) لازم است."""
        self.assertIn(bot.MENU_DEVBOT, bot.MENU_BUTTONS)

    def test_keyboard_version_bumped(self):
        self.assertEqual(bot.MENU_KEYBOARD_VERSION, 5)

    def test_font_row_now_has_two_buttons(self):
        rows = bot.main_reply_keyboard()["keyboard"]
        self.assertEqual(rows[4], [bot.MENU_FONT, bot.MENU_DEVBOT])
        self.assertEqual(len(rows), 5)

    def test_devbot_url_is_in_config(self):
        self.assertEqual(bot.CFG["devbot_url"], DEVBOT_URL)


# ---------------------------------------------------------------------------
# ۲) کپشن — متن publicity و بولد بودن فارسی‌ها
# ---------------------------------------------------------------------------
class CaptionTests(BotTestCase):

    def test_caption_contains_all_given_parts(self):
        caption = bot.devbot_caption()
        self.assertIn("acod.ai » @acodai", caption)
        self.assertIn(GROUP_URL, caption)
        for line in PERSIAN_LINES:
            with self.subTest(line=line[:20]):
                self.assertIn(line, caption)

    def test_all_persian_lines_are_fully_bold(self):
        caption = bot.devbot_caption()
        for line in PERSIAN_LINES:
            with self.subTest(line=line[:20]):
                self.assertIn(f"<b>{line}</b>", caption)

    def test_group_link_is_html_anchor(self):
        caption = bot.devbot_caption()
        self.assertIn(f'<a href="{GROUP_URL}">{GROUP_URL}</a>', caption)

    def test_non_persian_lines_are_not_bold(self):
        caption = bot.devbot_caption()
        self.assertIn("\nacod.ai » @acodai\n", caption)

    def test_plain_caption_has_no_html_tags(self):
        plain = bot.devbot_caption_plain()
        self.assertNotIn("<b>", plain)
        self.assertNotIn("</b>", plain)
        self.assertNotIn("<a href", plain)
        self.assertIn(GROUP_URL, plain)
        self.assertIn("@acodai", plain)
        for line in PERSIAN_LINES:
            with self.subTest(line=line[:20]):
                self.assertIn(line, plain)

    def test_group_link_comes_from_config(self):
        self.assertEqual(bot.CFG["group_url"], GROUP_URL)


# ---------------------------------------------------------------------------
# ۳) جریان ارسال (send flow)
# ---------------------------------------------------------------------------
class SendFlowTests(BotTestCase):

    def test_click_sends_photo_with_bold_caption_and_button(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_DEVBOT)
        photos = self.photo_calls()
        self.assertEqual(len(photos), 1)
        photo = photos[0]
        self.assertEqual(photo["chat_id"], str(USER_A))
        self.assertEqual(photo["parse_mode"], "HTML")
        self.assertIn("<b>ربات</b>", photo["caption"])
        self.assertIn(GROUP_URL, photo["caption"])
        self.assertEqual(photo["_files"], ["photo"])
        markup = json.loads(photo["reply_markup"])
        button = markup["inline_keyboard"][0][0]
        self.assertEqual(button["url"], DEVBOT_URL)
        self.assertIn("@acodai", button["text"])

    def test_fallback_to_text_message_when_photo_missing(self):
        bot.DEVBOT_PHOTO = Path("/nonexistent/programmer_bot.jpg")
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_DEVBOT)
        self.assertEqual(self.photo_calls(), [])
        last = self.api.last_sent()
        self.assertIsNotNone(last)
        self.assertEqual(last["parse_mode"], "HTML")
        self.assertIn("<b>ربات</b>", last["text"])
        self.assertIn(GROUP_URL, last["text"])
        button = last["reply_markup"]["inline_keyboard"][0][0]
        self.assertEqual(button["url"], DEVBOT_URL)

    def test_fallback_to_plain_caption_when_html_rejected(self):
        real_multipart = self.api.multipart

        def rejecting_multipart(method, fields, files):
            params = dict(fields)
            if params.get("parse_mode") == "HTML":
                params["_files"] = [name for name, _, _, _ in files]
                self.api.calls.append((method, params))
                raise bot.BotError(400, "can't parse entities")
            return real_multipart(method, fields, files)

        bot.api_call_multipart = rejecting_multipart
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_DEVBOT)
        photos = self.photo_calls()
        self.assertEqual(len(photos), 2)
        self.assertEqual(photos[0]["parse_mode"], "HTML")
        self.assertNotIn("parse_mode", photos[1])
        self.assertNotIn("<b>", photos[1]["caption"])
        self.assertIn(GROUP_URL, photos[1]["caption"])

    def test_unverified_user_does_not_get_devbot_info(self):
        bot.get_user_state(USER_A)   # تایید نشده
        self.send_text(USER_A, bot.MENU_DEVBOT)
        self.assertEqual(self.photo_calls(), [])
        self.assertNotEqual(bot.get_user_state(USER_A).get("mode"), "main")
        # فقط پیام راهنمای تایید عضویت ارسال شده
        self.assertIn("تایید عضویت", self.api.last_sent()["text"])

    def test_font_mode_escape_to_devbot(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_FONT)
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "font")
        self.api.reset()
        self.send_text(USER_A, bot.MENU_DEVBOT)
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "main")
        self.assertEqual(len(self.photo_calls()), 1)

    def test_old_keyboard_user_gets_fresh_menu(self):
        state = bot.get_user_state(USER_A)
        state["verified"] = True
        state["mode"] = "main"
        state["kb_version"] = 4   # نسخهٔ قبلی (بدون دکمهٔ ربات برنامه نویس)
        self.assertTrue(bot.ensure_menu_keyboard_fresh(USER_A))
        markup = self.api.params_of("sendMessage")[-1]["reply_markup"]
        flat = [text for row in markup["keyboard"] for text in row]
        self.assertIn(bot.MENU_DEVBOT, flat)
        self.assertIn(bot.MENU_FONT, flat)

    def test_two_users_get_independent_responses(self):
        self.make_verified(USER_A)
        self.make_verified(USER_B)
        self.send_text(USER_A, bot.MENU_DEVBOT)
        self.send_text(USER_B, bot.MENU_DEVBOT)
        photos = self.photo_calls()
        self.assertEqual(len(photos), 2)
        self.assertEqual(photos[0]["chat_id"], str(USER_A))
        self.assertEqual(photos[1]["chat_id"], str(USER_B))

    def test_blocked_user_gets_block_text(self):
        self.make_verified(USER_A)
        bot.STATE["blocked"][str(USER_A)] = {"at": "now"}
        self.send_text(USER_A, bot.MENU_DEVBOT)
        self.assertEqual(self.photo_calls(), [])
        self.assertEqual(self.api.last_sent()["text"], bot.BLOCK_TEXT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
