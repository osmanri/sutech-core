"""Export public dictionaries and reference scenarios; never reads credentials."""
import ast
import json
import random
import re
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from bot.water_balance import CROPS, METHODS, SOILS, parse_field, calculate_balance
from bot.i18n import STRINGS
from bot.ai_i18n import AI_STRINGS
scope=ast.parse((root/'bot/services/agronomy_scope.py').read_text(encoding='utf8'))
DOMAIN_ROOTS=next(ast.literal_eval(node.value) for node in scope.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DOMAIN_ROOTS' for t in node.targets))
lib=root/'serverless/tgcloud/lib'
lib.mkdir(parents=True,exist_ok=True)
strings={lang:{k:re.sub(r'</?tg-emoji[^>]*>','',v) if isinstance(v,str) else v for k,v in pairs.items()} for lang,pairs in STRINGS.items()}
(lib/'copy.js').write_text('export const STRINGS = '+json.dumps(strings,ensure_ascii=False)+';\nexport const AI_STRINGS = '+json.dumps(AI_STRINGS,ensure_ascii=False)+';\nexport const DOMAIN_ROOTS = '+json.dumps(DOMAIN_ROOTS,ensure_ascii=False)+';\n',encoding='utf8')
source=ast.parse((root/'bot/services/agronomist.py').read_text(encoding='utf8'))
prompt=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='system_prompt')
scope={'project_knowledge':lambda:(root/'bot/knowledge/project_report.md').read_text(encoding='utf8')}
exec(compile(ast.Module(body=[prompt],type_ignores=[]),'public_prompt','exec'),scope)
prompts={lang:scope['system_prompt'](lang).replace('Python irrigation calculation service','JavaScript irrigation calculation engine on Telegram Serverless').replace('Web Mini App on Vercel','Web Mini App hosted on Telegram Serverless') for lang in ('ru','kz','en')}
(lib/'knowledge.js').write_text('export const PROMPTS = '+json.dumps(prompts,ensure_ascii=False)+';\n',encoding='utf8')
planner=ast.parse((root/'bot/handlers/chat_planner.py').read_text(encoding='utf8'))
planner_copy=next(ast.literal_eval(n.value) for n in planner.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='COPY' for t in n.targets))
(lib/'planner-copy.js').write_text('export const COPY = '+json.dumps(planner_copy,ensure_ascii=False)+';\n',encoding='utf8')
random.seed(20261016)
fixtures=[]
for crop in [*CROPS,'rice','other']:
 for soil in SOILS:
  for method in METHODS:
   p=dict(balance_version=2,crop=crop,soil_type=soil,irrigation_type=method,area='0.1',area_unit='hectare',day_of_growth=random.randint(0,50),moisture_condition=random.choice(['recent','normal','dry']),field_type=random.choice(['open','greenhouse']),is_saline='no',custom_kc=.9,custom_root_depth=.5,custom_p=.4)
   if random.choice([0,1]):p.update(power_price=25,pump_power_kw=2,pump_productivity_m3h=20)
   for et0,rain in [(0,0),(6.4,0),(5,4.9),(3,5),(10,50)]:
    fixtures.append(dict(payload=p,et0=et0,rain=rain,result=calculate_balance(parse_field(p),et0,rain)))
out=root/'serverless/test';out.mkdir(exist_ok=True)
(out/'balance-fixtures.json').write_text(json.dumps(fixtures),encoding='utf8')
print(f'Exported {len(fixtures)} Python reference scenarios and public UI copy')
