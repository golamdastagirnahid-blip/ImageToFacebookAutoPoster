"""
Telegram notifier - sends post summaries with image preview to your Telegram chat.

Setup:
1. Create a bot: message @BotFather on Telegram, send /newbot, follow prompts
2. Get your chat ID: message @userinfobot, it replies with your chat ID
3. Add GitHub Secrets:
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID

That's it. Free, no rate limits for personal use.
"""
import os
import requests
from datetime import datetime


class TelegramNotifier:
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID', '').strip()
        self.enabled = bool(self.bot_token and self.chat_id)
        if not self.enabled:
            print("ℹ️  Telegram notifications disabled (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set)")

    def _api(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def send_text(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.enabled:
            return False
        try:
            r = requests.post(
                self._api("sendMessage"),
                data={
                    'chat_id': self.chat_id,
                    'text': text[:4000],
                    'parse_mode': parse_mode,
                    'disable_web_page_preview': False,
                },
                timeout=15,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            print(f"Telegram send_text failed: {e}")
            return False

    def send_post_summary(self, image_path: str, post_data: dict) -> bool:
        """
        Send a rich post summary with image preview.
        post_data expected keys:
          headline, subheadline, title, source, post_id, fb_url,
          image_size, ai_model, identifier, hashtags
        """
        if not self.enabled:
            return False

        # Build the caption (Telegram captions max ~1024 chars)
        headline = post_data.get('headline') or post_data.get('title') or 'Posted'
        sub = post_data.get('subheadline', '')
        source = post_data.get('source', 'Unknown')
        post_id = post_data.get('post_id', 'unknown')
        fb_url = post_data.get('fb_url') or self._build_fb_url(post_id)
        size = post_data.get('image_size', '?')
        when = datetime.now().strftime('%d %b %Y, %H:%M UTC')

        caption_lines = [
            "✅ <b>Posted to Facebook</b>",
            "",
            f"📰 <b>{self._escape(headline)}</b>",
        ]
        if sub:
            caption_lines.append(f"<i>{self._escape(sub)}</i>")
        caption_lines.extend([
            "",
            f"📚 <b>Source:</b> {self._escape(source)}",
            f"🖼  <b>Image:</b> {size}",
            f"🕒 <b>Time:</b> {when}",
        ])
        if fb_url:
            caption_lines.append(f"🔗 <a href='{fb_url}'>View on Facebook</a>")
        
        caption = '\n'.join(caption_lines)
        if len(caption) > 1020:
            caption = caption[:1020] + '...'

        # Try sending photo with caption
        try:
            if image_path and os.path.exists(image_path):
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
                    print("📲 Telegram: post summary sent with image")
                    return True
            else:
                # Fallback to text-only
                return self.send_text(caption)
        except Exception as e:
            print(f"Telegram send_post_summary failed: {e}")
            # Try text-only fallback
            return self.send_text(caption)

    def send_failure_alert(self, error: str, stage: str = "unknown",
                           consecutive_failures: int = 1) -> bool:
        if not self.enabled:
            return False
        when = datetime.now().strftime('%d %b %Y, %H:%M UTC')
        urgency = "🚨🚨🚨" if consecutive_failures >= 3 else "⚠️"
        text = (
            f"{urgency} <b>Auto-Poster Failure</b>\n\n"
            f"<b>Stage:</b> {self._escape(stage)}\n"
            f"<b>Error:</b> <code>{self._escape(str(error)[:300])}</code>\n"
            f"<b>Consecutive failures:</b> {consecutive_failures}\n"
            f"<b>Time:</b> {when}\n\n"
        )
        if consecutive_failures >= 3:
            text += "❗ <b>3+ consecutive failures - check repo immediately</b>"
        return self.send_text(text)

    def send_token_warning(self, days_remaining: float) -> bool:
        if not self.enabled:
            return False
        if days_remaining < 7:
            urgency = "🚨 CRITICAL"
        elif days_remaining < 14:
            urgency = "⚠️ WARNING"
        else:
            return False  # Don't spam if not urgent
        text = (
            f"{urgency} <b>Facebook Token Expiring</b>\n\n"
            f"Your FB Page Access Token expires in <b>{days_remaining:.1f} days</b>.\n\n"
            f"Renew at: https://developers.facebook.com/tools/explorer/\n"
            f"See OPERATIONS.md for step-by-step instructions."
        )
        return self.send_text(text)

    def _build_fb_url(self, post_id: str) -> str:
        if not post_id or post_id == 'unknown':
            return ''
        # post_id format: PAGEID_POSTID
        if '_' in str(post_id):
            page, post = str(post_id).split('_', 1)
            return f"https://facebook.com/{page}/posts/{post}"
        return f"https://facebook.com/{post_id}"

    def _escape(self, text: str) -> str:
        """Escape HTML special chars for Telegram."""
        return (str(text or '')
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))
