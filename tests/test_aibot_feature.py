#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the «🧠 خرید ربات هوش مصنوعی» (ai code fox) feature — no network.

Run:
    python3 -m unittest discover -s tests -v
    (or with pytest: python3 -m pytest tests -q)

api_call / api_call_multipart are replaced with a fake that only records calls,
and save_state is disabled so nothing is written to data/. The sendPhoto path
is exercised with a temporary fake jpg.
"""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import splus_test_bot as bot  # noqa: E402

USER_A = 111111
USER_B = 222222
GUIDE_URL = "https://splus.ir/Aiacod"
BUY_URL = "https://acod.osine2.workers.dev"
GROUP_URL = "https://splus.ir/joingroup/AI_hfuzaN9GGKPWF0MsDJg"
EXPECTED_CONTENT_LINES = 10


class FakeAPI:
    """Replacement for api_call / api_call_multipart — only records calls."""

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
    """Base: clean state + fake API + fake photo + no disk writes."""

    def setUp(self):
        bot.STATE = {"learned": {}, "users": {}, "tickets": {}, "blocked": {}}
        self.api = FakeAPI()
        self._real_api_call = bot.api_call
        self._real_multipart = bot.api_call_multipart
        self._real_save_state = bot.save_state
        self._real_log = bot.log
        self._real_photo = bot.AIBOT_PHOTO
        bot.api_call = self.api
        bot.api_call_multipart = self.api.multipart
        bot.save_state = lambda: None
        bot.log = lambda *args, **kwargs: None
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(b"\xff\xd8\xff\xd9")   # fake jpg bytes
        tmp.close()
        bot.AIBOT_PHOTO = Path(tmp.name)

    def tearDown(self):
        bot.api_call = self._real_api_call
        bot.api_call_multipart = self._real_multipart
        bot.save_state = self._real_save_state
        bot.log = self._real_log
        bot.AIBOT_PHOTO = self._real_photo

    def make_verified(self, user_id):
        state = bot.get_user_state(user_id)
        state["verified"] = True
        state["mode"] = "main"
        state["kb_version"] = bot.MENU_KEYBOARD_VERSION
        return state

    def send_text(self, user_id, text):
        """Route a user message through the real handle_update path."""
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
# 1) Keyboard and constants
# ---------------------------------------------------------------------------
class KeyboardTests(BotTestCase):

    def test_button_label_is_exact(self):
        self.assertEqual(bot.MENU_AIBOT, "🧠 خرید ربات هوش مصنوعی")

    def test_button_is_on_main_keyboard(self):
        rows = bot.main_reply_keyboard()["keyboard"]
        flat = [text for row in rows for text in row]
        self.assertIn(bot.MENU_AIBOT, flat)

    def test_button_is_in_menu_buttons_tuple(self):
        """Needed so the button also works as an escape from mid-state modes."""
        self.assertIn(bot.MENU_AIBOT, bot.MENU_BUTTONS)

    def test_keyboard_version_bumped(self):
        self.assertEqual(bot.MENU_KEYBOARD_VERSION, 6)

    def test_row3_has_aibot_and_guide(self):
        rows = bot.main_reply_keyboard()["keyboard"]
        self.assertEqual(rows[2], [bot.MENU_AIBOT, bot.MENU_GUIDE])

    def test_old_game_button_is_gone(self):
        self.assertFalse(hasattr(bot, "MENU_GAME"))
        self.assertFalse(hasattr(bot, "GAME_PHOTO"))
        self.assertFalse(hasattr(bot, "GAME_BUTTON_TEXT"))
        rows = bot.main_reply_keyboard()["keyboard"]
        flat = [text for row in rows for text in row]
        self.assertFalse(any("بازی" in text for text in flat))

    def test_slash_commands_updated(self):
        commands = [item["command"] for item in bot.BOT_COMMANDS]
        self.assertIn("ai", commands)
        self.assertNotIn("game", commands)

    def test_urls_are_in_config(self):
        self.assertEqual(bot.CFG["aibot_guide_url"], GUIDE_URL)
        self.assertEqual(bot.CFG["aibot_buy_url"], BUY_URL)


# ---------------------------------------------------------------------------
# 2) Caption — «تمام متن bold باشه»
# ---------------------------------------------------------------------------
class CaptionTests(BotTestCase):

    def test_caption_has_expected_number_of_lines(self):
        lines = [l for l in bot.AIBOT_CAPTION.split("\n") if l.strip()]
        self.assertEqual(len(lines), EXPECTED_CONTENT_LINES)

    def test_every_line_is_fully_bold(self):
        """Every non-empty line must be wrapped in <b>...</b>."""
        for line in bot.AIBOT_CAPTION.split("\n"):
            if not line.strip():
                continue
            with self.subTest(line=line[:25]):
                self.assertTrue(line.startswith("<b>"), line)
                self.assertTrue(line.endswith("</b>"), line)

    def test_caption_contains_safe_anchors(self):
        for anchor in ("ai code fox", "🗳", "🔕", "🔹", "۱۳"):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, bot.AIBOT_CAPTION)

    def test_caption_has_no_script_glitch(self):
        """Persian lines must not contain Cyrillic or Latin characters."""
        for line in bot.AIBOT_CAPTION.split("\n"):
            if not line.strip():
                continue
            inner = re.sub(r"</?b>", "", line)
            self.assertIsNone(re.search(r"[\u0400-\u04FF]", inner), line)
            has_persian = re.search(r"[\u0600-\u06FF]", inner) is not None
            has_latin = re.search(r"[A-Za-z]", inner) is not None
            if has_persian:
                self.assertFalse(has_latin, line)

    def test_plain_caption_equals_html_without_tags(self):
        stripped = re.sub(r"</?b>", "", bot.AIBOT_CAPTION)
        self.assertEqual(stripped, bot.AIBOT_CAPTION_PLAIN)

    def test_plain_caption_has_no_html(self):
        plain = bot.AIBOT_CAPTION_PLAIN
        self.assertNotIn("<b>", plain)
        self.assertNotIn("</b>", plain)


# ---------------------------------------------------------------------------
# 3) Inline buttons — ۳ دکمهٔ شیشه‌ای
# ---------------------------------------------------------------------------
class ButtonTests(BotTestCase):

    def test_three_inline_buttons(self):
        rows = bot.aibot_inline_keyboard()["inline_keyboard"]
        buttons = [b for row in rows for b in row]
        self.assertEqual(len(buttons), 3)

    def test_button_urls_are_correct(self):
        rows = bot.aibot_inline_keyboard()["inline_keyboard"]
        buttons = [b for row in rows for b in row]
        urls = sorted(b["url"] for b in buttons)
        self.assertEqual(urls, sorted([GUIDE_URL, BUY_URL, GROUP_URL]))

    def test_button_texts_mention_purpose(self):
        rows = bot.aibot_inline_keyboard()["inline_keyboard"]
        buttons = [b for row in rows for b in row]
        texts = " | ".join(b["text"] for b in buttons)
        self.assertIn("راهنما", texts)
        self.assertIn("خرید", texts)
        self.assertIn("گروه", texts)


# ---------------------------------------------------------------------------
# 4) Send flow
# ---------------------------------------------------------------------------
class SendFlowTests(BotTestCase):

    def test_click_sends_photo_with_bold_caption_and_buttons(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_AIBOT)
        photos = self.photo_calls()
        self.assertEqual(len(photos), 1)
        photo = photos[0]
        self.assertEqual(photo["chat_id"], str(USER_A))
        self.assertEqual(photo["parse_mode"], "HTML")
        self.assertIn("<b>ai code fox</b>", photo["caption"])
        self.assertEqual(photo["_files"], ["photo"])
        markup = json.loads(photo["reply_markup"])
        buttons = [b for row in markup["inline_keyboard"] for b in row]
        self.assertEqual(len(buttons), 3)
        urls = sorted(b["url"] for b in buttons)
        self.assertEqual(urls, sorted([GUIDE_URL, BUY_URL, GROUP_URL]))

    def test_slash_ai_command_sends_aibot_info(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, "/ai")
        self.assertEqual(len(self.photo_calls()), 1)

    def test_fallback_to_text_message_when_photo_missing(self):
        bot.AIBOT_PHOTO = Path("/nonexistent/ai_bot.jpg")
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_AIBOT)
        self.assertEqual(self.photo_calls(), [])
        last = self.api.last_sent()
        self.assertIsNotNone(last)
        self.assertEqual(last["parse_mode"], "HTML")
        self.assertIn("<b>ai code fox</b>", last["text"])
        buttons = [b for row in last["reply_markup"]["inline_keyboard"]
                   for b in row]
        self.assertEqual(len(buttons), 3)

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
        self.send_text(USER_A, bot.MENU_AIBOT)
        photos = self.photo_calls()
        self.assertEqual(len(photos), 2)
        self.assertEqual(photos[0]["parse_mode"], "HTML")
        self.assertNotIn("parse_mode", photos[1])
        self.assertNotIn("<b>", photos[1]["caption"])

    def test_unverified_user_does_not_get_aibot_info(self):
        bot.get_user_state(USER_A)   # not verified
        self.send_text(USER_A, bot.MENU_AIBOT)
        self.assertEqual(self.photo_calls(), [])
        self.assertIn("تایید عضویت", self.api.last_sent()["text"])

    def test_font_mode_escape_to_aibot(self):
        self.make_verified(USER_A)
        self.send_text(USER_A, bot.MENU_FONT)
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "font")
        self.api.reset()
        self.send_text(USER_A, bot.MENU_AIBOT)
        self.assertEqual(bot.get_user_state(USER_A)["mode"], "main")
        self.assertEqual(len(self.photo_calls()), 1)

    def test_blocked_user_gets_block_text(self):
        self.make_verified(USER_A)
        bot.STATE["blocked"][str(USER_A)] = {"at": "now"}
        self.send_text(USER_A, bot.MENU_AIBOT)
        self.assertEqual(self.photo_calls(), [])
        self.assertEqual(self.api.last_sent()["text"], bot.BLOCK_TEXT)

    def test_two_users_get_independent_responses(self):
        self.make_verified(USER_A)
        self.make_verified(USER_B)
        self.send_text(USER_A, bot.MENU_AIBOT)
        self.send_text(USER_B, bot.MENU_AIBOT)
        photos = self.photo_calls()
        self.assertEqual(len(photos), 2)
        self.assertEqual(photos[0]["chat_id"], str(USER_A))
        self.assertEqual(photos[1]["chat_id"], str(USER_B))


if __name__ == "__main__":
    unittest.main(verbosity=2)
