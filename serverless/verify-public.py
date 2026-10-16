"""Read-only deployment checks plus an unauthenticated request that must fail."""
import json
import sys
import urllib.error
import urllib.request

checks=[]
for name,url,marker in (
    ('telegram_app','https://app8796056339.tgcloud.ai/','js/serverless-transport.js'),
    ('telegram_transport','https://app8796056339.tgcloud.ai/js/app.js',"SuTechServerless.request('analyze'"),
    ('old_link_redirect','https://frontend-2-mauve.vercel.app/js/serverless-location.js','https://app8796056339.tgcloud.ai/'),
):
    try:
        with urllib.request.urlopen(url,timeout=15) as response:
            body=response.read(300000).decode('utf8')
            checks.append({'check':name,'ok':response.status==200 and marker in body})
    except Exception as exc:
        checks.append({'check':name,'ok':False,'error':type(exc).__name__})
try:
    request=urllib.request.Request('https://app8796056339.tgcloud.ai/api/analyze',data=b'{"payload":{}}',headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=15) as response:
        checks.append({'check':'reject_anonymous','ok':False,'status':response.status})
except urllib.error.HTTPError as exc:
    checks.append({'check':'reject_anonymous','ok':exc.code==401,'status':exc.code})
except Exception as exc:
    checks.append({'check':'reject_anonymous','ok':False,'error':type(exc).__name__})
print(json.dumps({'checks':checks},ensure_ascii=True))
sys.exit(0 if all(r['ok'] for r in checks) else 1)
