"""
Quick diagnostic for Facebook + Telegram credentials.

Run locally:
    cd src
    python diagnose.py

Or in GitHub Actions, add a manual workflow_dispatch step.
Reads .env (local) or env vars (CI). Prints clear PASS/FAIL for each.
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()


def check_facebook():
    print("\n=== Facebook ===")
    token = (os.getenv('FACEBOOK_ACCESS_TOKEN') or '').strip()
    page_id = (os.getenv('FACEBOOK_PAGE_ID') or '').strip()
    if not token or not page_id:
        print("❌ Missing FACEBOOK_ACCESS_TOKEN or FACEBOOK_PAGE_ID")
        return False

    # 1. Check token itself (debug_token)
    try:
        r = requests.get(
            'https://graph.facebook.com/debug_token',
            params={'input_token': token, 'access_token': token},
            timeout=15,
        )
        body = r.json()
        data = body.get('data', {})
        if not data.get('is_valid', False):
            print(f"❌ Token INVALID. Reason: {data.get('error', {}).get('message', body)}")
            print("   👉 FIX: Renew token at https://developers.facebook.com/tools/explorer/")
            return False
        expires = data.get('expires_at', 0)
        if expires == 0:
            print("✅ Token valid (never expires)")
        else:
            from datetime import datetime
            exp_dt = datetime.fromtimestamp(expires)
            days = (exp_dt - datetime.now()).days
            print(f"✅ Token valid. Expires: {exp_dt} ({days} days remaining)")
    except Exception as e:
        print(f"❌ debug_token call failed: {e}")
        return False

    # 2. Try to fetch the page
    try:
        r = requests.get(
            f'https://graph.facebook.com/v18.0/{page_id}',
            params={'access_token': token, 'fields': 'id,name,access_token'},
            timeout=15,
        )
        if not r.ok:
            body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
            err = body.get('error', {})
            print(f"❌ Page fetch failed: {r.status_code} — {err.get('message', r.text[:200])}")
            print(f"   Code: {err.get('code')}, Subcode: {err.get('error_subcode')}")
            if err.get('code') == 190:
                print("   👉 Token expired/revoked. Get a new Page Access Token.")
            elif err.get('code') == 100:
                print("   👉 FACEBOOK_PAGE_ID looks wrong, or token doesn't have this page.")
            return False
        info = r.json()
        print(f"✅ Page reachable: {info.get('name')} (id={info.get('id')})")
        # 3. Check token has correct scope by trying /me/accounts style call
        return True
    except Exception as e:
        print(f"❌ Page fetch exception: {e}")
        return False


def check_telegram():
    print("\n=== Telegram ===")
    token = (os.getenv('TELEGRAM_BOT_TOKEN') or '').strip()
    chat_id = (os.getenv('TELEGRAM_CHAT_ID') or '').strip()
    if not token or not chat_id:
        print("ℹ️  TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — Telegram disabled (OK if intentional)")
        return None

    # 1. getMe
    try:
        r = requests.get(f'https://api.telegram.org/bot{token}/getMe', timeout=15)
        if not r.ok:
            print(f"❌ Bot token INVALID: {r.status_code} — {r.text[:200]}")
            print("   👉 FIX: Recreate token via @BotFather (/mybots)")
            return False
        me = r.json().get('result', {})
        print(f"✅ Bot OK: @{me.get('username')} (id={me.get('id')})")
    except Exception as e:
        print(f"❌ getMe failed: {e}")
        return False

    # 2. Try sending a test message
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data={'chat_id': chat_id, 'text': '🧪 Diagnostic test from auto-poster — if you see this, Telegram is working!'},
            timeout=15,
        )
        if not r.ok:
            body = r.json() if 'json' in r.headers.get('content-type', '') else {}
            desc = body.get('description', r.text[:200])
            print(f"❌ sendMessage failed: {r.status_code} — {desc}")
            low = desc.lower()
            if 'chat not found' in low:
                print(f"   👉 FIX: TELEGRAM_CHAT_ID '{chat_id}' is wrong, OR you've never sent /start to your bot.")
                print(f"      1. Open Telegram → search @{me.get('username')} → send /start")
                print(f"      2. Get your real chat ID from @userinfobot")
            elif 'bot was blocked' in low:
                print("   👉 FIX: You blocked the bot. Unblock it in Telegram.")
            return False
        print(f"✅ Test message delivered to chat {chat_id}")
        return True
    except Exception as e:
        print(f"❌ sendMessage exception: {e}")
        return False


if __name__ == '__main__':
    fb = check_facebook()
    tg = check_telegram()
    print("\n=== Summary ===")
    print(f"Facebook : {'PASS' if fb else 'FAIL'}")
    print(f"Telegram : {'PASS' if tg else ('SKIP' if tg is None else 'FAIL')}")
    sys.exit(0 if fb and tg is not False else 1)
