import test from 'node:test';
import assert from 'node:assert/strict';
import {db,setFetch,setApiHandler,messages} from 'sdk';
import {user,put,list,get,eraseUserData} from '../tgcloud/lib/store.js';
import {calculateField} from '../tgcloud/lib/fields.js';
import {generate} from '../tgcloud/lib/ai.js';
import {feedback} from '../tgcloud/lib/pilot.js';
import {navigate} from '../tgcloud/lib/ui.js';
import {deliverCalculation,message} from '../tgcloud/lib/bot.js';
import {renderScreen} from '../tgcloud/lib/screens.js';

const p={balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:.1,area_unit:'hectare',day_of_growth:30,moisture_condition:'dry',latitude:42.345,longitude:60.123,field_type:'open'};
const weather=()=>({utc_offset_seconds:0,timezone:'UTC',daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},daily:{time:[new Date().toISOString().slice(0,10)],et0_fao_evapotranspiration:[5],precipitation_sum:[0]}});
const serve=()=>setFetch(async()=>({ok:true,json:async()=>weather()}));
function pauseWrite(kind){
 const run=db.run;let release,entered,paused=false;
 const waiting=new Promise(r=>release=r),started=new Promise(r=>entered=r);
 db.run=async(q,params)=>{if(!paused&&params?.[':kind']===kind){paused=true;entered();await waiting;}return run(q,params);};
 return {started,release:()=>release(),restore:()=>{release();db.run=run;}};
}

test('a late field calculation cannot recreate data after deletion and a fresh start',async()=>{
 const id=81001;await user(id,'en');serve();const blocked=pauseWrite('field');
 try{
  const work=calculateField(id,p);const rejected=assert.rejects(work,/stale|busy/);await blocked.started;
  await eraseUserData(id);await user(id,'en');blocked.release();await rejected;
  assert.equal((await list(id,'field')).length,0);assert.equal((await list(id,'report')).length,0);
 }finally{blocked.restore();}
});

test('a late AI write cannot revive deleted history after the user reopens AI',async()=>{
 const id=81002;await put('config:gemini_key',0,'config',{value:'test-key'});await put('config:gemini_model',0,'config',{value:'gemini-test'});await navigate(id,'ai');
 setFetch(async()=>({ok:true,json:async()=>({candidates:[{content:{parts:[{text:'old private answer'}]}}]})}));
 const blocked=pauseWrite('ai-context');
 try{
  const work=generate(id,'How to water tomatoes?','en');await blocked.started;await eraseUserData(id);await navigate(id,'ai');blocked.release();
  assert.equal((await work).cancelled,true);assert.equal(await get(`ai-context:${id}`,id),null);assert.equal((await list(id,'ai-answer')).length,0);
 }finally{blocked.restore();}
});

test('feedback already in progress cannot restore a deleted field reference',async()=>{
 const id=81003;serve();const field=await calculateField(id,{...p,latitude:42.346});const blocked=pauseWrite('feedback');
 try{
  const work=feedback(id,field.id,true);const rejected=assert.rejects(work,/stale|busy/);await blocked.started;await eraseUserData(id);await user(id);blocked.release();await rejected;
  assert.equal((await list(id,'feedback')).length,0);
 }finally{blocked.restore();}
});

test('interrupted deletion is completed before the owner can use old data again',async()=>{
 const id=81004;serve();await user(id);await calculateField(id,{...p,latitude:42.347});const run=db.run;let failed=false;
 db.run=async(q,params)=>{if(!failed&&q.startsWith('DELETE FROM records WHERE owner=')){failed=true;throw new Error('interrupted');}return run(q,params);};
 try{await assert.rejects(()=>eraseUserData(id),/interrupted/);}finally{db.run=run;}
 await user(id,'en');assert.equal((await list(id,'field')).length,0);assert.equal((await list(id,'report')).length,0);
});

test('deletion removes archived chat-id rows while preserving another owner and the minimal marker',async()=>{
 const id=81005;await user(id);await put('legacy:chat:mine',0,'legacy:chat_ui_messages',{chat_id:String(id),message_id:10});
 await put('legacy:chat:other',0,'legacy:chat_ui_messages',{chat_id:id+1,message_id:11});
 await eraseUserData(id);assert.equal(await get('legacy:chat:mine',0),null);assert.ok(await get('legacy:chat:other',0));
 const marker=await get(`lifecycle:${id}`,0);assert.equal(marker.deleting,false);assert.equal(Object.keys(marker).filter(k=>!k.startsWith('_')).sort().join(','),'deleting,epoch,generation');
});

test('a delivery waiting after its progress screen cannot borrow the post-deletion epoch',async()=>{
 const id=81006;await user(id);serve();const run=db.run;let release,entered,paused=false;const waiting=new Promise(r=>release=r),started=new Promise(r=>entered=r);
 db.run=async(q,params)=>{const result=await run(q,params);if(!paused&&q.startsWith('DELETE FROM leases')&&params?.[':id']===`ui-render:${id}`){paused=true;entered();await waiting;}return result;};
 try{
  const work=deliverCalculation(id,{...p,latitude:42.348});await started;await eraseUserData(id);await user(id);release();
  assert.equal((await work).cancelled,true);assert.equal((await list(id,'field')).length,0);assert.equal((await list(id,'report')).length,0);
 }finally{release();db.run=run;}
});

test('a photo download started before deletion cannot submit the old image to Gemini afterwards',async()=>{
 await put('config:gemini_key',0,'config',{value:'test-key'});await put('config:gemini_model',0,'config',{value:'gemini-test'});
 const id=81007;await navigate(id,'ai');let release,entered,calls=0;const waiting=new Promise(r=>release=r),started=new Promise(r=>entered=r);
 setApiHandler(async method=>{if(method==='getFileContent'){entered();await waiting;return new Uint8Array([255,216,255,0]);}});
 setFetch(async()=>{calls++;return {ok:true,json:async()=>({candidates:[{content:{parts:[{text:'private old photo answer'}]}}]})};});
 try{
  const work=message({chat:{id,type:'private'},from:{id},message_id:91,photo:[{file_id:'synthetic',file_size:4}],caption:'Tomato leaf symptoms'},{});
  await started;await eraseUserData(id);await navigate(id,'ai');release();await work;
  assert.equal(calls,0);assert.equal((await list(id,'ai-answer')).length,0);
 }finally{release();setApiHandler(null);}
});

test('a renderer paused with an old view cannot display it using a fresh profile epoch',async()=>{
 const id=81008;await user(id);const original=db.get;let reads=0,release,entered,paused=false;const waiting=new Promise(r=>release=r),started=new Promise(r=>entered=r);
 db.get=async(q,params)=>{const row=await original(q,params);if(!paused&&params?.[':id']===`user:${id}`&&++reads===3){paused=true;entered();await waiting;}return row;};
 try{
  const work=renderScreen(id,{chat_id:id,text:'private old field coordinates'},0);const rejected=assert.rejects(work,/stale/);
  await started;await eraseUserData(id);await user(id);release();await rejected;
  assert.equal(messages.some(m=>m.params.chat_id===id&&m.params.text==='private old field coordinates'),false);
  assert.equal((await user(id)).screen,null);assert.equal((await list(id,'ui-message')).length,0);
 }finally{release();db.get=original;}
});
