"""Read-only service/Telegram diagnostics. Credentials never enter stdout."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
values = dict(os.environ)
env_file = root / 'bot' / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values.setdefault(key.strip(), value.strip().strip('"\''))

secrets = [v for k, v in values.items() if v and any(s in k.upper() for s in ('TOKEN', 'SECRET', 'API_KEY', 'DATABASE_URL'))]

def scrub(value):
    message = str(value)
    for secret in secrets:
        message = message.replace(secret, '<REDACTED>')
    return re.sub(r'\b\d{6,}:[A-Za-z0-9_-]{20,}', '<REDACTED>', message)

def probe(name, url, telegram=False):
    start = time.monotonic()
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'SuTech-ReadOnly-Diagnostics/1.0'})
        with urllib.request.urlopen(request, timeout=18) as response:
            body = response.read(50000)
            try:
                payload = json.loads(body)
            except ValueError:
                payload = {}
            result = {'probe': name, 'http_status': response.status, 'seconds': round(time.monotonic()-start, 2)}
            if telegram:
                result['ok'] = payload.get('ok')
                item = payload.get('result', {})
                if name == 'telegram_identity':
                    result['username'] = item.get('username')
                else:
                    result.update(webhook_host=urllib.parse.urlsplit(item.get('url', '')).hostname,
                                  pending_update_count=item.get('pending_update_count'),
                                  last_error_date=item.get('last_error_date'),
                                  last_error_message=item.get('last_error_message'))
                    result['delivery_ready'] = bool(result['webhook_host']) and not item.get('last_error_message')
            else:
                result['body_excerpt'] = scrub(body.decode('utf-8', errors='replace')[:400])
            print(json.dumps(result, ensure_ascii=True), flush=True)
            return response.status == 200 and (not telegram or payload.get('ok') is True) and result.get('delivery_ready', True)
    except urllib.error.HTTPError as exc:
        print(json.dumps({'probe': name, 'http_status': exc.code, 'seconds': round(time.monotonic()-start, 2)}), flush=True)
    except Exception as exc:
        print(json.dumps({'probe': name, 'error': scrub(type(exc).__name__ + ': ' + str(getattr(exc, 'reason', exc))), 'seconds': round(time.monotonic()-start, 2)}), flush=True)
    return False

print(json.dumps({'credentials_present': {key: bool(values.get(key)) for key in ['BOT_TOKEN', 'GEMINI_API_KEY', 'DATABASE_URL', 'TGCLOUD_TOKEN', 'TGCLOUD_ACCESS_TOKEN']}}), flush=True)
health = probe('render_health', 'https://sutech-core.onrender.com/health')
token = values.get('BOT_TOKEN', '')
if token:
    probe('telegram_identity', f'https://api.telegram.org/bot{token}/getMe', True)
    delivery = probe('telegram_delivery', f'https://api.telegram.org/bot{token}/getWebhookInfo', True)
else:
    delivery = False
print(json.dumps({'render_health_pass': health}), flush=True)
print(json.dumps({'bot_delivery_pass': delivery}), flush=True)
raise SystemExit(0 if delivery else 1)
