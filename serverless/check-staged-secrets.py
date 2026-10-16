"""Fail closed if local credential values appear in staged Git objects."""
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
env={}
for line in (root/'bot/.env').read_text(encoding='utf-8-sig').splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key,value=line.split('=',1)
        if any(part in key.upper() for part in ('TOKEN','SECRET','API_KEY','DATABASE_URL')):
            value=value.strip().strip('"\'')
            if len(value)>12:env[key]=value.encode('utf8')
git=['git','-c','safe.directory='+root.as_posix(),'-C',str(root)]
files=subprocess.check_output([*git,'diff','--cached','--name-only','--diff-filter=ACMR','-z']).split(b'\0')
count=0
for raw in files:
    if not raw:continue
    file=raw.decode('utf8')
    # A submodule stages a commit pointer, not file contents.
    if (root/file).is_dir():continue
    blob=subprocess.check_output([*git,'show',':'+file])
    if any(value in blob for value in env.values()):
        print('Credential detected in staged file:',file);sys.exit(1)
    count+=1
print(f'Credential scan passed for {count} staged files; no secret values printed.')
