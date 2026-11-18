import test from 'node:test';
import assert from 'node:assert/strict';
import {db,setFetch,messages} from 'sdk';
import {get,put,list,user,lock,unlock} from '../tgcloud/lib/store.js';
import {navigate} from '../tgcloud/lib/ui.js';
import {generate} from '../tgcloud/lib/ai.js';
import {deliverCalculation,message,action} from '../tgcloud/lib/bot.js';
import {calculateField,checkMoisture,ownedField} from '../tgcloud/lib/fields.js';

const clock=Date.now.bind(Date);
const payload={balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:.1,area_unit:'hectare',day_of_growth:30,moisture_condition:'dry',latitude:43.123,longitude:65.456,field_type:'open'};
const forecast=()=>({timezone:'UTC',utc_offset_seconds:0,daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},daily:{time:[new Date(Date.now()).toISOString().slice(0,10)],et0_fao_evapotranspiration:[5],precipitation_sum:[0]}});
const answer=()=>({candidates:[{finishReason:'STOP',content:{parts:[{text:'Water according to the soil check.'}]}}]});
const config=async()=>{await put('config:gemini_key',0,'config',{value:'test-key'});await put('config:gemini_model',0,'config',{value:'gemini-test'});await put('config:gemini_deep_model',0,'config',{value:'gemini-deep-test'});};

for(const phase of ['headers','body'])test(`late weather ${phase} cannot create advice; saved input can be retried without duplicate balance`,async()=>{
 const id=7001+(phase==='body'?1:0),p={...payload,latitude:payload.latitude+(phase==='body'?.01:0)};
 await user(id,'en');let calls=0,shift=0;Date.now=()=>clock()+shift;
 setFetch(async()=>{calls++;if(phase==='headers')shift=20000;return {ok:true,json:async()=>{if(phase==='body')shift=20000;return forecast();}};});
 try{
  const result=await deliverCalculation(id,p);
  assert.equal(result.ok,false);assert.equal(result.recoverable,true);
  assert.deepEqual((await get(`pending:${id}`,id)).payload,p);
  assert.equal((await list(id,'field')).length,0);assert.equal((await list(id,'report')).length,0);
  assert.equal(await get(`weather:v2:${p.latitude.toFixed(4)}:${p.longitude.toFixed(4)}`,0),null);
  assert.equal(calls,1,'no hidden retry while the first request may still be running');
  setFetch(async()=>({ok:true,json:async()=>forecast()}));
  const retry=await deliverCalculation(id,p),again=await deliverCalculation(id,p);
  assert.equal(retry.ok,true);assert.equal(retry.field_id,again.field_id);
  assert.equal((await list(id,'field')).length,1);assert.equal((await list(id,'report')).length,1);
 }finally{Date.now=clock;}
});

for(const phase of ['headers','body'])test(`late Gemini ${phase} is rejected before history is changed`,async()=>{
 await config();const id=7010+(phase==='body'?1:0);await navigate(id,'ai');
 const history=[{role:'user',parts:[{text:'Earlier tomato question'}]},{role:'model',parts:[{text:'Earlier answer'}]}];
 await put(`ai-context:${id}`,id,'ai-context',{history,model:'gemini-test'});
 let calls=0,shift=0;Date.now=()=>clock()+shift;
 setFetch(async()=>{calls++;if(phase==='headers')shift=30000;return {ok:true,json:async()=>{if(phase==='body')shift=30000;return answer();}};});
 try{
  await assert.rejects(()=>generate(id,'How to water tomatoes?','en'),/unavailable/);
  assert.deepEqual((await get(`ai-context:${id}`,id)).history,history);assert.equal((await list(id,'ai-answer')).length,0);
  assert.equal(calls,1);const token=await lock(`ai:${id}`);assert.ok(token,'failed request released its lease');await unlock(`ai:${id}`,token);
 }finally{Date.now=clock;}
});

test('deep mode does not retry quota, auth, unknown network errors or an elapsed response',async()=>{
 await config();let id=7020;
 for(const fail of ['quota','auth','network','late']){
  id++;await navigate(id,'ai');let calls=0,shift=0;Date.now=()=>clock()+shift;
  setFetch(async()=>{calls++;if(fail==='network')throw new Error('network');if(fail==='late'){shift=30000;return {ok:true,json:async()=>answer()};}return {ok:false,status:fail==='quota'?429:401};});
  try{await assert.rejects(()=>generate(id,'How to water tomatoes?','en',null,true));assert.equal(calls,1,fail);}
  finally{Date.now=clock;}
 }
});

test('two transient failures produce only two provider calls and one quota reservation',async()=>{
 await config();const id=7030;await navigate(id,'ai');let calls=0;
 setFetch(async()=>{calls++;return {ok:false,status:503};});
 await assert.rejects(()=>generate(id,'How to water tomatoes?','en'),/unavailable/);
 assert.equal(calls,2);assert.equal((await db.get('SELECT COUNT(*) n FROM ai_usage_v2 WHERE owner=:owner',{':owner':id})).n,1);
});

for(const kind of ['text','photo'])test(`failed AI ${kind} stays in Telegram so it can be resent`,async()=>{
 await config();const id=7040+(kind==='photo'?1:0);await user(id,'en');await action(id,'ai');
 const mid=9000+id;messages.length=0;setFetch(async()=>({ok:false,status:503}));
 await message({chat:{id,type:'private'},from:{id},message_id:mid,...(kind==='photo'?{photo:[{file_id:'private-photo',file_size:4}],caption:'Tomato leaves are yellow'}:{text:'How to water tomatoes?'})},{});
 assert.equal(messages.some(m=>m.method==='deleteMessage'&&m.params.message_id===mid),false);
 assert.equal((await list(id,'ui-message')).some(m=>m.message_id===mid),false,'cleanup must not delete failed input on the next view');
 assert.equal((await list(id,'ai-answer')).length,0);
});

test('successful AI text can still be cleaned up after its answer is saved',async()=>{
 await config();const id=7050;await user(id,'en');await action(id,'ai');messages.length=0;
 setFetch(async()=>({ok:true,json:async()=>answer()}));
 await message({chat:{id,type:'private'},from:{id},message_id:16050,text:'How to water tomatoes?'},{});
 assert.equal((await list(id,'ai-answer')).length,1);
 assert.ok(messages.some(m=>m.method==='deleteMessage'&&m.params.message_id===16050));
});

test('an expired calculation cannot write after a retry has acquired its lease',async()=>{
 const id=7060,p={...payload,latitude:44.456};await user(id,'en');
 setFetch(async()=>({ok:true,json:async()=>forecast()}));
 const run=db.run;let release,entered,paused=false,shift=0;
 const waiting=new Promise(r=>release=r),started=new Promise(r=>entered=r);Date.now=()=>clock()+shift;
 db.run=async(q,params)=>{
  if(!paused&&params?.[':kind']==='field'){
   paused=true;entered();await waiting;
  }
  return run(q,params);
 };
 try{
  const old=deliverCalculation(id,p);await started;shift=50000;
  const retry=await deliverCalculation(id,p);assert.equal(retry.ok,true);
  release();const stale=await old;assert.equal(stale.ok,false);
  assert.equal((await list(id,'field')).length,1);assert.equal((await list(id,'report')).length,1);
  const current=messages.filter(m=>m.params.chat_id===id&&typeof m.params.text==='string').at(-1);
  assert.match(current.params.text,/Apply water|No irrigation needed/,'a stale failure must not replace the successful retry');
 }finally{release();db.run=run;Date.now=clock;}
});

test('a parameter reset retains soil checks recorded while weather was loading',async()=>{
 const id=7070,p={...payload,latitude:44.789};setFetch(async()=>({ok:true,json:async()=>forecast()}));
 const first=await calculateField(id,p);
 await put(`weather:v2:${p.latitude.toFixed(4)}:${p.longitude.toFixed(4)}`,0,'weather',{day:'2000-01-01'});
 let release,entered;const waiting=new Promise(r=>release=r),started=new Promise(r=>entered=r);
 setFetch(async()=>{entered();await waiting;return {ok:true,json:async()=>forecast()};});
 const resetting=calculateField(id,{...p,soil_type:'clay'});await started;
 await checkMoisture(id,first.id,'wet');release();await resetting;
 const row=await ownedField(id,first.id);assert.equal(row.checks.length,1);assert.equal(row.checks[0].level,'wet');
});

test('navigation between an AI response and its database write cannot restore a cleared conversation',async()=>{
 await config();const id=7080;await navigate(id,'ai');setFetch(async()=>({ok:true,json:async()=>answer()}));
 const run=db.run;let release,entered,paused=false;const waiting=new Promise(r=>release=r),started=new Promise(r=>entered=r);
 db.run=async(q,params)=>{if(!paused&&params?.[':kind']==='ai-context'){paused=true;entered();await waiting;}return run(q,params);};
 try{
  const old=generate(id,'How to water tomatoes?','en');await started;await action(id,'ai:new');release();
  assert.equal((await old).cancelled,true);
  assert.equal(await get(`ai-context:${id}`,id),null);assert.equal((await list(id,'ai-answer')).length,0);
 }finally{release();db.run=run;}
});

test('an expired outer field lease cannot overwrite newer parameters using a new inner lease',async()=>{
 const id=7090,p={...payload,latitude:45.321};setFetch(async()=>({ok:true,json:async()=>forecast()}));await calculateField(id,p);
 const run=db.run;let release,entered,paused=false,shift=0;const waiting=new Promise(r=>release=r),started=new Promise(r=>entered=r);Date.now=()=>clock()+shift;
 db.run=async(q,params)=>{const result=await run(q,params);if(!paused&&params?.[':id']?.startsWith(`field-key:${id}:`)){paused=true;entered();await waiting;}return result;};
 try{
  const old=calculateField(id,{...p,soil_type:'clay'});const rejected=assert.rejects(old,/busy/);await started;shift=50000;
  const retry=await calculateField(id,{...p,soil_type:'sand'});release();await rejected;
  assert.equal((await ownedField(id,retry.id)).payload.soil_type,'sand');
 }finally{release();db.run=run;Date.now=clock;}
});

test('a delayed pending-input write cannot overwrite the newer calculation input',async()=>{
 const id=7100,p={...payload,latitude:45.654},newer={...p,soil_type:'clay'};await user(id,'en');setFetch(async()=>({ok:true,json:async()=>forecast()}));
 const run=db.run;let release,entered,paused=false;const waiting=new Promise(r=>release=r),started=new Promise(r=>entered=r);
 db.run=async(q,params)=>{if(!paused&&params?.[':kind']==='pending'){paused=true;entered();await waiting;}return run(q,params);};
 try{
  const old=deliverCalculation(id,p);await started;const retry=await deliverCalculation(id,newer);assert.equal(retry.ok,true);release();
  assert.equal((await old).cancelled,true);assert.deepEqual((await get(`pending:${id}`,id)).payload,newer);
  assert.equal((await list(id,'field')).length,1);assert.equal((await ownedField(id,retry.field_id)).payload.soil_type,'clay');
 }finally{release();db.run=run;}
});
