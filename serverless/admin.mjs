// CLI-only maintenance. No administrative HTTP endpoint is ever deployed.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {runFunction,getWebhook} from './node_modules/@tgcloud/cli/src/api/endpoints.js';
const root=fileURLToPath(new URL('.',import.meta.url));
const env={...process.env};
for(const line of fs.readFileSync(path.join(root,'../bot/.env'),'utf8').split(/\r?\n/)){
 const m=line.match(/^([A-Z_]+)=(.*)$/);if(m&&!env[m[1]])env[m[1]]=m[2].trim().replace(/^['"]|['"]$/g,'');
}
const secrets=Object.entries(env).filter(([k,v])=>v&&/TOKEN|SECRET|KEY|DATABASE/.test(k)).map(([,v])=>v);
const sources={};
function scan(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())scan(p);else if(p.endsWith('.js'))sources[path.relative(path.join(root,'tgcloud'),p).replaceAll('\\','/').replace(/\.js$/,'')]=fs.readFileSync(p,'utf8');}}
scan(path.join(root,'tgcloud'));
async function run(code,args={},overrides={}){
 const space={...sources,...overrides,'endpoints/maintenance':code};
 const r=await runFunction(env.TGCLOUD_TOKEN,'endpoints/maintenance',space,args,{});
 if(r.error)throw new Error('Runtime rejected maintenance module: '+JSON.stringify(r.error));
 return r;
}
function resultOf(r){return r.result??r.return_value??r.value??r;}
try {
 const command=process.argv[2];
 if(command==='smoke'){
  const r=await run(`import {api,db} from 'sdk';import {parseField,calculate} from '../lib/balance.js';import {put,get,lock,unlock} from '../lib/store.js';
  export default async function(){const me=await api.getMe();await put('migration-smoke',0,'smoke',{ok:true});const row=await get('migration-smoke',0);const token=await lock('migration-smoke');await unlock('migration-smoke',token);await db.run('DELETE FROM records WHERE id=:id AND owner=0',{':id':'migration-smoke'});return {username:me.username,bot_id:me.id,database:row.ok,lock:!!token,calculation:calculate(parseField({balance_version:2,crop:'tomato',soil_type:'loam',area:.1,area_unit:'hectare',irrigation_type:'drip',day_of_growth:30,moisture_condition:'dry'}),5,0).gross_m3};}`);
  console.log(JSON.stringify(r));
 }else if(command==='ui-smoke'){
  const original=sources['lib/screens'];
  const apiImport="import {api,db} from 'sdk';";
  if(!original.includes(apiImport))throw new Error('Review UI smoke test imports');
  const fakeApi=`export const live=new Map();let mid=1;export let rejectEdit=false;export function failEdit(value){rejectEdit=value;}export const api={async sendMessage(p){const m={...p,message_id:mid++};live.set(m.message_id,m);return m;},async editMessageText(p){if(rejectEdit)throw Object.assign(new Error('Cannot edit'),{code:400,description:'Bad Request: message cannot be edited'});live.set(p.message_id,p);return true;},async deleteMessage(p){live.delete(p.message_id);return true;},async editMessageReplyMarkup(){return true;}};`;
  const code=`import {db} from 'sdk';import {user,saveUser} from '../lib/store.js';import {screen,keyboard} from '../lib/ui.js';import {live,failEdit} from '../lib/ui_smoke_api.js';
  export default async function(){const id=4000000000998000;if(await db.get('SELECT id FROM records WHERE owner=:owner LIMIT 1',{':owner':id}))throw new Error('Test namespace is occupied');try{const old=await user(id);await screen(id,'First',keyboard([]));const current=(await user(id)).screen;old.lang='kz';await saveUser(id,old);const preserved=(await user(id)).screen===current;failEdit(true);await screen(id,'Replacement',keyboard([]));failEdit(false);await Promise.all([screen(id,'Parallel A',keyboard([])),screen(id,'Parallel B',keyboard([]))]);return {database:'telegram-sqlite',pointer_preserved:preserved,visible_messages:live.size,latest_text:[...live.values()][0]?.text,passed:preserved&&live.size===1};}finally{await db.run('DELETE FROM records WHERE owner=:owner',{':owner':id});await db.run('DELETE FROM leases WHERE id=:id',{':id':'ui-render:'+id});}}`;
  console.log(JSON.stringify(await run(code,{}, {'lib/screens':original.replace(apiImport,"import {db} from 'sdk';import {api} from './ui_smoke_api.js';"),'lib/ui_smoke_api':fakeApi})));
 }else if(command==='ai-smoke'){
  console.log(JSON.stringify(await run(`import {providerReply} from '../lib/ai.js';import {setting} from '../lib/store.js';export default async function(input){const key=await setting('gemini_key'),model=await setting('gemini_model');try{const r=await providerReply({key,model,lang:input.lang,text:input.text});return {model,characters:r.answer.length,answer:r.answer};}catch(e){return {model,error:e.message,http_status:e.httpStatus??null};}}`,{lang:'kz',text:'Қызанақтың жапырағы сарғайды. Алдымен нені тексеру керек? Екі қысқа сөйлеммен жауап бер.'})));
 }else if(command==='weather-smoke'){
  console.log(JSON.stringify(await run(`import {weather} from '../lib/weather.js';export default async function(){const w=await weather(47.12,51.88);return {date:w.day,timezone:w.timezone,et0:w.et0,rain:w.rain};}`)));
 }else if(command==='photo-smoke'){
  const bytes=[...Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jX1cAAAAASUVORK5CYII=','base64')];
  console.log(JSON.stringify(await run(`import {providerReply} from '../lib/ai.js';import {setting} from '../lib/store.js';export default async function(input){try{const r=await providerReply({key:await setting('gemini_key'),model:await setting('gemini_model'),lang:'ru',text:'Есть ли на этом изображении растение? Если нет, коротко попроси прислать фото растения.',image:new Uint8Array(input.bytes)});return {characters:r.answer.length,answer:r.answer};}catch(e){return {error:e.message,http_status:e.httpStatus??null};}}`,{bytes})));
 }else if(command==='profile'){
  const users=JSON.parse(fs.readFileSync(path.join(root,'.tgcloud/legacy-backup.json'),'utf8')).users.map(u=>({id:Number(u.user_id),lang:u.lang}));
  console.log(JSON.stringify(await run(`import {api} from 'sdk';import {APP_URL} from '../lib/ui.js';export default async function(input){await api.setChatMenuButton({menu_button:{type:'web_app',text:'Su-Tech',web_app:{url:APP_URL}}});let menus=0;for(const u of input.users){try{await api.setChatMenuButton({chat_id:u.id,menu_button:{type:'web_app',text:'Su-Tech',web_app:{url:APP_URL+'?lang='+u.lang}}});menus++;}catch(e){if(![400,403].includes(e.code))throw e;}}const commands=[{command:'start',description:'Главное меню'},{command:'app',description:'Открыть Su-Tech'},{command:'ai',description:'ИИ-агроном'},{command:'fields',description:'Мои поля'},{command:'history',description:'История'},{command:'language',description:'Язык / Тіл / Language'}];await api.setMyCommands({commands});return {menu_url:APP_URL,commands:commands.length,personal_menus:menus};}`,{users})));
 }else if(command==='provision'){
  const r=await run(`import {put,setting} from '../lib/store.js';export default async function(input){for(const [name,value] of Object.entries(input.settings))await put('config:'+name,0,'config',{value});return {configured:!!(await setting('gemini_key')),models:[await setting('gemini_model'),await setting('gemini_deep_model')]};}`,{settings:{gemini_key:env.GEMINI_API_KEY,gemini_model:env.GEMINI_MODEL||'gemini-3.5-flash-lite',gemini_deep_model:env.GEMINI_DEEP_MODEL||'gemini-3.7-flash'}});
  console.log(JSON.stringify(r));
 }else if(command==='import'){
  const legacy=JSON.parse(fs.readFileSync(path.join(root,'.tgcloud/legacy-backup.json'),'utf8'));
  const records=[];const add=(id,owner,kind,body,updated=Date.now())=>records.push({id,owner:Number(owner),kind,body:JSON.stringify(body),updated});
  for(const [table,rows] of Object.entries(legacy)){
   if(table==='sutech_setup_probe')continue;
   for(const [i,row] of rows.entries())add(`legacy:${table}:${row.id??row.user_id??i}`,Number(row.user_id??0),'legacy:'+table,row);
  }
  for(const row of legacy.users??[])add(`user:${row.user_id}`,row.user_id,'user',{lang:row.lang,mode:'home',screen:null,generation:0});
  const {fieldKey,parseField}=await import('./tgcloud/lib/balance.js');
  for(const f of legacy.fields??[]){
   const daily=(legacy.field_daily_balances??[]).filter(d=>d.field_id===f.id).sort((a,b)=>b.balance_date.localeCompare(a.balance_date))[0];
   if(!daily||f.latitude===null||f.longitude===null)continue;
   const payload={balance_version:2,crop:f.crop_type,soil_type:f.soil_type,irrigation_type:f.irrigation_method,area:f.area_ha,area_unit:'hectare',day_of_growth:Math.round((Date.parse(daily.balance_date)-Date.parse(f.planting_date))/86400000),moisture_condition:'recent',latitude:f.latitude,longitude:f.longitude,field_type:f.field_type||'open',is_saline:f.is_saline?'yes':'no',power_price:f.power_price,pump_power_kw:f.pump_power_kw,pump_productivity_m3h:f.pump_productivity_m3h,greenhouse_et0:f.greenhouse_et0,custom_kc:f.custom_kc,custom_p:f.custom_p,custom_root_depth:f.custom_root_depth};
   if(f.stage_days)payload.stage_days=JSON.parse(f.stage_days);
   const result=JSON.parse(daily.result_json),weather={day:daily.balance_date,timezone:daily.timezone,et0:daily.et0,rain:daily.rain};
   const body={id:f.id,name:f.name,key:fieldKey(payload,parseField(payload)),payload,planting:f.planting_date,deficit:Number(f.accumulated_deficit),last_day:daily.balance_date,result,weather,revision:1,version:daily.calculation_version,events:(legacy.irrigation_events??[]).filter(e=>e.field_id===f.id).map(e=>({time:Date.parse(e.created_at),applied_m3:e.applied_m3,before:e.deficit_before,after:e.deficit_after}))};
   add(`field:${f.id}`,f.user_id,'field',body);
  }
  for(const r of legacy.history??[])add(`legacy-report:${r.id}`,r.user_id,'report',r,Date.parse(r.created_at)||Date.now());
  for(const r of legacy.ai_exchanges??[])add(`ai-answer:legacy-${r.id}`,r.user_id,'ai-answer',{question:r.question,answer:r.answer,model:r.model,has_image:!!r.has_image,created:Number(r.created_at)*1000},Number(r.created_at)*1000);
  for(const r of legacy.ai_conversations??[])add(`ai-context:${r.user_id}`,r.user_id,'ai-context',{history:JSON.parse(r.context_json),model:r.model},Date.now()-1800001);
  for(let start=0;start<records.length;start+=30){
   const r=await run(`import {db} from 'sdk';export default async function(input){let count=0;for(const r of input.rows){const result=await db.run('INSERT OR IGNORE INTO records(id,owner,kind,body,updated) VALUES(:id,:owner,:kind,:body,:updated)',{':id':r.id,':owner':r.owner,':kind':r.kind,':body':r.body,':updated':r.updated});count+=result.rowsAffected;}return {inserted:count};}`,{rows:records.slice(start,start+30)});
   if(r.error)throw new Error('Import batch failed');
   if(start%300===0)console.log(JSON.stringify({import_progress:Math.min(start+30,records.length),total:records.length}));
  }
  const quota=(legacy.ai_usage??[]).filter(r=>Number(r.created_at)*1000>Date.now()-86400000&&r.counted_question);
  if(quota.length)await run(`import {db} from 'sdk';export default async function(input){for(const r of input.rows)await db.run('INSERT OR IGNORE INTO ai_usage_v2(id,owner,created) VALUES(:id,:owner,:created)',{':id':r.id,':owner':r.user_id,':created':Number(r.created_at)*1000});return {ok:true};}`,{rows:quota});
  console.log(JSON.stringify({imported_records:records.length,quota_records:quota.length}));
 }else if(command==='verify'){
  console.log(JSON.stringify(await run(`import {db,api} from 'sdk';import {setting} from '../lib/store.js';export default async function(){const me=await api.getMe();return {username:me.username,storage:await db.all('SELECT kind,COUNT(*) AS count FROM records GROUP BY kind'),ai_configured:!!(await setting('gemini_key')),processed_updates:(await db.get('SELECT COUNT(*) AS n FROM update_receipts')).n,active_screens:(await db.get("SELECT COUNT(*) AS n FROM records WHERE kind='user' AND json_extract(body,'$.screen') IS NOT NULL")).n};}`)));
  const wh=await getWebhook(env.TGCLOUD_TOKEN);console.log(JSON.stringify({webhook_in_sync:wh.in_sync,pending_updates:wh.pending_update_count,last_error:wh.last_error_message??null}));
 }else throw new Error('Unknown maintenance command');
}catch(e){
 let message=e.message??'Maintenance failed';for(const secret of secrets)message=message.split(secret).join('<REDACTED>');
 console.error(message.slice(0,1500));process.exitCode=1;
}
