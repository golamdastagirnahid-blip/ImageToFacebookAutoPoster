"""
Telegram notifier - rich, arranged event reporting for the auto-poster.

Setup:
1. Create a bot via @BotFather (/newbot) -> copy bot token
2. Get your chat ID via @userinfobot
3. Send /start to YOUR bot (one-time, lets it message you)
4. Add GitHub Secrets:
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID

Design:
- Each cycle uses add_event() to buffer issues/info
- At cycle end, ONE arranged message goes out (success summary OR issue report)
- Critical errors send their own immediate message
"""
import os
import requests
from datetime import datetime


class TelegramNotifier:
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID', '').strip()
        self.enabled = bool(self.bot_token and self.chat_id)
        # Per-cycle event buffer
        self.session_events = []
        self.session_start = None
        if not self.enabled:
            print("ℹ️  Telegram notifications disabled (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set)")
        else:
            print("📲 Telegram notifications: ENABLED")

    # ------------------------------------------------------------------ #
    # Low-level API
    # ------------------------------------------------------------------ #
    def _api(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def _esc(self, text) -> str:
        return (str(text or '')
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))

    def send_text(self, text: str, parse_mode: str = "HTML", silent: bool = False) -> bool:
        if not self.enabled:
            return False
        # Telegram limit is 4096 chars
        chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
        for chunk in chunks:
            ok = self._post_message(chunk, parse_mode, silent)
            if not ok and parse_mode:
                # Retry without HTML parsing in case of entity parse error
                print("   Retrying Telegram message without HTML parse_mode...")
                # Strip tags for plain-text fallback
                import re
                plain = re.sub(r'<[^>]+>', '', chunk)
                plain = plain.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                ok = self._post_message(plain, None, silent)
            if not ok:
                return False
        return True

    def _post_message(self, text: str, parse_mode, silent: bool) -> bool:
        try:
            data = {
                'chat_id': self.chat_id,
                'text': text,
                'disable_web_page_preview': False,
                'disable_notification': silent,
            }
            if parse_mode:
                data['parse_mode'] = parse_mode
            r = requests.post(self._api("sendMessage"), data=data, timeout=15)
            if not r.ok:
                # Surface the real Telegram error so the user can diagnose
                try:
                    body = r.json()
                    desc = body.get('description', r.text[:200])
                except Exception:
                    desc = r.text[:200]
                print(f"Telegram API {r.status_code}: {desc}")
                # Print actionable hints for common errors
                low = (desc or '').lower()
                if 'chat not found' in low:
                    print("   👉 FIX: TELEGRAM_CHAT_ID is wrong, OR you haven't sent /start to your bot yet.")
                    print("      Open Telegram, find your bot, send /start, then re-run.")
                elif 'bot was blocked' in low:
                    print("   👉 FIX: You blocked the bot. Unblock it in Telegram.")
                elif 'unauthorized' in low or r.status_code == 401:
                    print("   👉 FIX: TELEGRAM_BOT_TOKEN is wrong. Recreate via @BotFather.")
                elif 'parse entities' in low or "can't parse" in low:
                    print("   👉 Will retry as plain text (HTML formatting issue).")
                return False
            return True
        except Exception as e:
            print(f"Telegram send_text exception: {e}")
            return False

    def send_photo(self, image_path: str, caption: str) -> bool:
        if not self.enabled or not image_path or not os.path.exists(image_path):
            return False
        try:
            if len(caption) > 1020:
                caption = caption[:1020] + '...'
            with open(image_path, 'rb') as f:
                r = requests.post(
                    self._api("sendPhoto"),
                    data={
                        'chat_id': self.chat_id,
                        'caption': caption,
                        'parse_mode': 'HTML',
                    },
                    files={'photo': f},
                    timeout=30,
                )
                r.raise_for_status()
            return True
        except Exception as e:
            print(f"Telegram send_photo failed: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Session event buffering (collects events during a cycle)
    # ------------------------------------------------------------------ #
    def start_session(self, sources: list = None):
        self.session_events = []
        self.session_start = datetime.now()
        if sources:
            preview = ', '.join(s.split('/')[-1][:25] for s in sources[:6])
            self.add_event('🚀', f"Cycle started — {len(sources)} source(s): {preview}")

    def add_event(self, emoji: str, message: str):
        """Buffer an event with timestamp. Cheap; printed to console too."""
        ts = datetime.now().strftime('%H:%M:%S')
        self.session_events.append((ts, emoji, message))

    def _format_session_log(self) -> str:
        if not self.session_events:
            return ""
        lines = []
        for ts, emoji, msg in self.session_events:
            lines.append(f"<code>{ts}</code> {emoji} {self._esc(msg)}")
        return '\n'.join(lines)

    # ------------------------------------------------------------------ #
    # High-level events
    # ------------------------------------------------------------------ #
    def send_post_summary(self, image_path: str, post_data: dict) -> bool:
        """Photo + caption with full post details. Sends the cycle log as a follow-up."""
        if not self.enabled:
            return False

        headline = post_data.get('headline') or post_data.get('title') or 'Posted'
        sub = post_data.get('subheadline', '')
        source = post_data.get('source', 'Unknown')
        post_id = post_data.get('post_id', 'unknown')
        fb_url = post_data.get('fb_url') or self._build_fb_url(post_id)
        size = post_data.get('image_size', '?')
        ai_model = post_data.get('ai_model', '')
        identifier = post_data.get('identifier', '')
        when = datetime.now().strftime('%d %b %Y, %H:%M UTC')
        duration = self._cycle_duration()

        cap = ["✅ <b>POSTED TO FACEBOOK</b>", ""]
        cap.append(f"📰 <b>{self._esc(headline)}</b>")
        if sub:
            cap.append(f"<i>{self._esc(sub)}</i>")
        cap.append("")
        cap.append(f"📚 <b>Source:</b> {self._esc(source)}")
        cap.append(f"🖼  <b>Image:</b> {size}")
        if identifier:
            cap.append(f"🆔 <b>ID:</b> <code>{self._esc(identifier)[:60]}</code>")
        if ai_model:
            cap.append(f"🤖 <b>AI:</b> {self._esc(ai_model)}")
        cap.append(f"🕒 <b>Time:</b> {when}")
        if duration:
            cap.append(f"⏱  <b>Cycle:</b> {duration}")
        if fb_url:
            cap.append(f"🔗 <a href='{fb_url}'>View on Facebook</a>")

        caption = '\n'.join(cap)

        ok = self.send_photo(image_path, caption) if image_path else self.send_text(caption)
        if not ok:
            self.send_text(caption)

        # Follow-up: cycle event log if there were notable events beyond the start
        if len(self.session_events) > 1:
            log = self._format_session_log()
            self.send_text(
                f"📋 <b>Cycle Log</b>\n\n{log}",
                silent=True,
            )
        return True

    def send_cycle_skip(self, reason: str, details: dict = None) -> bool:
        """Sent when a cycle ends with no post (no images, all NSFW, etc.)."""
        if not self.enabled:
            return False
        details = details or {}
        when = datetime.now().strftime('%d %b %Y, %H:%M UTC')
        duration = self._cycle_duration()

        lines = ["⏭ <b>CYCLE SKIPPED — NO POST</b>", ""]
        lines.append(f"<b>Reason:</b> {self._esc(reason)}")
        for k, v in details.items():
            lines.append(f"<b>{self._esc(k)}:</b> {self._esc(v)}")
        lines.append(f"<b>Time:</b> {when}")
        if duration:
            lines.append(f"<b>Duration:</b> {duration}")

        if self.session_events:
            lines.append("")
            lines.append("📋 <b>Cycle Log</b>")
            lines.append(self._format_session_log())

        return self.send_text('\n'.join(lines))

    def send_failure_alert(self, error: str, stage: str = "unknown",
                           consecutive_failures: int = 1, extra: dict = None) -> bool:
        if not self.enabled:
            return False
        when = datetime.now().strftime('%d %b %Y, %H:%M UTC')
        urgency = "🚨🚨🚨" if consecutive_failures >= 3 else "⚠️"
        lines = [
            f"{urgency} <b>AUTO-POSTER FAILURE</b>",
            "",
            f"<b>Stage:</b> {self._esc(stage)}",
            f"<b>Error:</b> <code>{self._esc(str(error)[:500])}</code>",
            f"<b>Consecutive failures:</b> {consecutive_failures}",
            f"<b>Time:</b> {when}",
        ]
        if extra:
            for k, v in extra.items():
                lines.append(f"<b>{self._esc(k)}:</b> {self._esc(v)}")
        if consecutive_failures >= 3:
            lines.append("")
            lines.append("❗ <b>3+ consecutive failures — check the repo immediately.</b>")
            lines.append("👉 GitHub Actions tab → latest run → logs")

        if self.session_events:
            lines.append("")
            lines.append("📋 <b>Cycle Log</b>")
            lines.append(self._format_session_log())

        return self.send_text('\n'.join(lines))

    def send_token_warning(self, days_remaining: float) -> bool:
        if not self.enabled:
            return False
        if days_remaining >= 14:
            return False
        if days_remaining < 3:
            urgency = "🚨🚨 CRITICAL"
        elif days_remaining < 7:
            urgency = "🚨 URGENT"
        else:
            urgency = "⚠️ WARNING"
        lines = [
            f"{urgency} <b>FACEBOOK TOKEN EXPIRING</b>",
            "",
            f"Your FB Page Access Token expires in <b>{days_remaining:.1f} days</b>.",
            "",
            "<b>Renew steps:</b>",
            "1. Visit https://developers.facebook.com/tools/explorer/",
            "2. Select your app → Get Page Access Token",
            "3. Convert to long-lived (60-day) via Token Debugger",
            "4. Update GitHub Secret <code>FACEBOOK_ACCESS_TOKEN</code>",
            "",
            "📖 See <code>OPERATIONS.md</code> for the full walkthrough.",
        ]
        return self.send_text('\n'.join(lines))

    def send_startup_alert(self, error: str) -> bool:
        """Used for hard startup failures (FB connection, missing config, etc.)."""
        if not self.enabled:
            return False
        when = datetime.now().strftime('%d %b %Y, %H:%M UTC')
        lines = [
            "💥 <b>STARTUP FAILURE</b>",
            "",
            f"<b>Error:</b> <code>{self._esc(str(error)[:500])}</code>",
            f"<b>Time:</b> {when}",
            "",
            "Automation could not initialize. Check GitHub Actions logs.",
        ]
        return self.send_text('\n'.join(lines))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _cycle_duration(self) -> str:
        if not self.session_start:
            return ""
        delta = (datetime.now() - self.session_start).total_seconds()
        if delta < 60:
            return f"{delta:.0f}s"
        return f"{delta / 60:.1f}m"

    def _build_fb_url(self, post_id: str) -> str:
        if not post_id or post_id == 'unknown':
            return ''
        if '_' in str(post_id):
            page, post = str(post_id).split('_', 1)
            return f"https://facebook.com/{page}/posts/{post}"
        return f"https://facebook.com/{post_id}"
