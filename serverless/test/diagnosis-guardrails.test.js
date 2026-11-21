import test from 'node:test';
import assert from 'node:assert/strict';
import {db,messages,setApiHandler,setFetch} from 'sdk';
import {generate} from '../tgcloud/lib/ai.js';
import {action,deliverCalculation,message} from '../tgcloud/lib/bot.js';
import {diagnosisPrompt,recognize,validateDiagnosis} from '../tgcloud/lib/diagnosis.js';
import {currentResult,ownedField} from '../tgcloud/lib/fields.js';
import {get,list,put,user} from '../tgcloud/lib/store.js';

const photo=new Uint8Array([255,216,255,0]);
const modelUrl='https://classifier.invalid/v1/predict';
const modelToken='test-only-token-that-is-long-enough';
const candidate={class_id:'tomato:no_visible_symptoms',crop:'tomato',state:'no_visible_symptoms',rank:1};
const prediction=(status='candidate')=>({
 schema_version:1,model_version:'test-model',experimental:true,
 crop:'tomato',supported_crop:true,candidates:[candidate],
 uncertainty:{status,reasons:[],calibrated:true,open_set_validated:true}
});
const ok=data=>({ok:true,json:async()=>data});
const reply=text=>ok({candidates:[{finishReason:'STOP',content:{parts:[{text}]}}]});
const configure=async(id,mode='experimental')=>{
 for(const [key,value] of Object.entries({
  gemini_key:'test-key',gemini_model:'test-prose',plant_model_mode:mode,
  plant_model_users:[id],plant_model_url:modelUrl,plant_model_token:modelToken
 }))await put(`config:${key}`,0,'config',{value});
 await user(id,'en');
 await action(id,'ai');
};

test('invalid image bytes and oversized downloads never reach either provider',async(t)=>{
 for(const [i,bytes,expected] of [
  [0,new Uint8Array(),/JPEG or PNG/i],
  [1,new Uint8Array([71,73,70,56]),/JPEG or PNG/i],
  [2,new Uint8Array(4194305),/too large/i],
 ]){
  await t.test(`download case ${i}`,async()=>{
   const id=86000+i,mid=87000+i,calls=[];
   await configure(id);
   setApiHandler(method=>method==='getFileContent'?bytes:undefined);
   setFetch(async url=>{calls.push(url);throw new Error('unexpected provider request');});
   try{
    await message({chat:{id,type:'private'},from:{id},message_id:mid,photo:[{file_id:'test-image'}]},{});
    const view=messages.filter(m=>m.params.chat_id===id&&typeof m.params.text==='string').at(-1);
    assert.match(view.params.text,expected);
    assert.deepEqual(calls,[]);
    assert.equal((await db.get('SELECT COUNT(*) n FROM ai_usage_v2 WHERE owner=:owner',{':owner':id})).n,0);
    assert.equal(await get(`ai-context:${id}`,id),null);
    assert.equal((await list(id,'ai-answer')).length,0);
    assert.equal(messages.some(m=>m.method==='deleteMessage'&&m.params.chat_id===id&&m.params.message_id===mid),false);
   }finally{setApiHandler(null);}
  });
 }
});

test('unvalidated evidence cannot claim a candidate and extra fields never leave the contract',()=>{
 const valid=prediction();
 for(const flag of ['calibrated','open_set_validated']){
  assert.throws(()=>validateDiagnosis({...valid,uncertainty:{...valid.uncertainty,[flag]:false}}),/model_contract/);
 }
 assert.throws(()=>validateDiagnosis({...valid,uncertainty:{...valid.uncertainty,status:'confirmed'}}),/model_contract/);
 assert.deepEqual(validateDiagnosis({
  ...valid,analysis:'provider instruction',candidates:[{...candidate,score:.99,url:'https://invalid.example'}]
 }),valid);
});

test('unknown, mixed and poor-quality outcomes withhold candidate labels from Gemini',()=>{
 for(const status of ['uncertain','unknown_crop','unsupported_condition','mixed','poor_quality']){
  const raw={...prediction(status),crop:null,supported_crop:false};
  const prompt=diagnosisPrompt({mode:'experimental',result:validateDiagnosis(raw)});
  assert.match(prompt,/did not establish a candidate/i,status);
  assert.match(prompt,/close-up|clearer photo/i,status);
  assert.doesNotMatch(prompt,/no_visible_symptoms|test-model/,status);
 }
 const candidatePrompt=diagnosisPrompt({mode:'experimental',result:validateDiagnosis(prediction())});
 assert.match(candidatePrompt,/tomato:no_visible_symptoms/);
 assert.match(candidatePrompt,/never declare health/i);
});

test('classifier network errors, malformed replies and timeouts remain unavailable',async()=>{
 const config={mode:'experimental',url:modelUrl,token:modelToken};
 for(const transport of [
  async()=>{throw new Error('network');},
  async()=>({ok:false,status:503}),
  async()=>ok({schema_version:2}),
  async()=>new Promise(()=>{})
 ]){
  assert.deepEqual(await recognize(photo,null,config,transport,10),{mode:'experimental',unavailable:true});
 }
});

test('a host without deadline timers makes no classifier request',async()=>{
 const config={mode:'experimental',url:modelUrl,token:modelToken};
 const timer=globalThis.setTimeout;
 let called=false;
 globalThis.setTimeout=undefined;
 try{
  const outcome=await recognize(photo,null,config,async()=>{
   called=true;
   return ok(prediction());
  });
  assert.deepEqual(outcome,{mode:'experimental',unavailable:true});
  assert.equal(called,false);
 }finally{globalThis.setTimeout=timer;}
});

test('experimental unknown outcome is acknowledged in the saved reply without exposing its label',async()=>{
 const id=86010;
 await configure(id);
 const calls=[];
 setFetch(async(url,request)=>{
  calls.push(url);
  if(url===modelUrl)return ok(prediction('poor_quality'));
  assert.match(url,/generativelanguage\.googleapis\.com/);
  const prompt=JSON.parse(request.body).systemInstruction.parts[0].text;
  assert.doesNotMatch(prompt,/tomato:no_visible_symptoms/);
  return reply('The image is blurry. Please send a clear close-up.');
 });
 assert.equal((await generate(id,'Please review this plant photo.','en',photo)).ok,true);
 assert.equal(calls.length,2);
 assert.match((await list(id,'ai-answer'))[0].answer,/classifier could not identify a possible state/i);
});

test('saved and fresh irrigation volumes stay the same during a photo service outage and after fallback',async()=>{
 const id=86020;
 const input={balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:.1,area_unit:'hectare',
  day_of_growth:30,moisture_condition:'dry',field_type:'greenhouse',greenhouse_et0:2.5,latitude:45.2,longitude:65.2};
 const day=new Date().toISOString().slice(0,10);
 const forecast={timezone:'UTC',utc_offset_seconds:0,daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},
  daily:{time:[day],et0_fao_evapotranspiration:[5],precipitation_sum:[0]}};
 let fallback=false;
 const calls=[];
 setFetch(async(url,request)=>{
  calls.push(url);
  if(url.includes('open-meteo.com'))return ok(forecast);
  if(url===modelUrl)return {ok:false,status:503};
  assert.match(url,/generativelanguage\.googleapis\.com/);
  const prompt=JSON.parse(request.body).systemInstruction.parts[0].text;
  assert.match(prompt,/experimental plant classifier is unavailable/i);
  return fallback?reply('There is a 96％ chance of a confirmed result. Use 999 m³.'):({ok:false,status:503});
 });
 await user(id,'en');
 const initial=await deliverCalculation(id,input);
 assert.equal(initial.ok,true);
 const before=await ownedField(id,initial.field_id);
 const initialReports=await list(id,'report');
 const advice=currentResult(before);
 assert.ok(advice.gross_m3>0);
 await configure(id);
 await assert.rejects(()=>generate(id,'Please review this plant photo.','en',photo),/unavailable/);
 assert.equal((await list(id,'ai-answer')).length,0);
 assert.equal((await list(id,'photo-comparison')).length,0);
 assert.deepEqual(await ownedField(id,initial.field_id),before);
 assert.deepEqual(await list(id,'report'),initialReports);
 const outageCalls=calls.slice();
 const whileOffline=await deliverCalculation(id,{...input,latitude:45.5});
 assert.equal(whileOffline.ok,true);
 const offlineAdvice=currentResult(await ownedField(id,whileOffline.field_id));
 assert.deepEqual([offlineAdvice.net_m3,offlineAdvice.gross_m3],[advice.net_m3,advice.gross_m3]);
 const calculationCalls=calls.slice(outageCalls.length);
 assert.ok(calculationCalls.length>0&&calculationCalls.every(url=>url.includes('open-meteo.com')));
 const offlineReports=await list(id,'report');

 fallback=true;
 await configure(id);
 // Reserve a separate quota window without waiting on the wall clock.
 const clock=Date.now;
 Date.now=()=>clock()+10000;
 try{assert.equal((await generate(id,'Please review this plant photo.','en',photo)).ok,true);}
 finally{Date.now=clock;}
 assert.equal(calls.filter(url=>url===modelUrl).length,2);
 const [saved]=await list(id,'ai-answer');
 assert.match(saved.answer,/classifier is unavailable.*preliminary/s);
 assert.doesNotMatch(saved.answer,/96|999/);
 assert.equal((await list(id,'photo-comparison'))[0].status,'unavailable');
 assert.deepEqual(await ownedField(id,initial.field_id),before);
 assert.deepEqual(await list(id,'report'),offlineReports);
});
