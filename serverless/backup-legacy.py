"""Read-only, consistent PostgreSQL export into ignored local migration storage."""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'.test-deps'))
import psycopg2
from psycopg2.extras import RealDictCursor
env={}
for line in (root/'bot/.env').read_text(encoding='utf-8-sig').splitlines():
 if '=' in line and not line.lstrip().startswith('#'):
  k,v=line.split('=',1);env[k.strip()]=v.strip().strip('"\'')
try:
 with psycopg2.connect(env['DATABASE_URL'],connect_timeout=15,sslmode='require') as conn:
  conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
  with conn.cursor(cursor_factory=RealDictCursor) as cur:
   cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
   tables=[r['tablename'] for r in cur.fetchall()]
   out={}
   from psycopg2 import sql
   for table in tables:
    cur.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(table)))
    out[table]=[dict(r) for r in cur.fetchall()]
 blob=json.dumps(out,ensure_ascii=False,default=str,sort_keys=True).encode('utf8')
 folder=root/'serverless/.tgcloud';folder.mkdir(exist_ok=True)
 target=folder/'legacy-backup.json'
 if target.exists():raise RuntimeError('Backup already exists; refusing to overwrite')
 target.write_bytes(blob)
 print(json.dumps({'backup':'saved in ignored migration storage','counts':{k:len(v) for k,v in out.items()},'sha256':hashlib.sha256(blob).hexdigest()}))
except Exception as e:
 print(json.dumps({'error':type(e).__name__,'credentials':'not logged'}));sys.exit(1)
