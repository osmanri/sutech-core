import test from 'node:test';
import assert from 'node:assert/strict';
import {setFetch,liveMessages} from 'sdk';
import {user,saveUser,list} from '../tgcloud/lib/store.js';
import {calculateField,setExpert,ownedField,currentResult,report} from '../tgcloud/lib/fields.js';
import {parseField,cleanExpert} from '../tgcloud/lib/expert.js';
import {fieldCsv} from '../tgcloud/lib/explain.js';
import {callback,message} from '../tgcloud/lib/bot.js';

const payload={balance_version:2,crop:'cotton',soil_type:'loam',irrigation_type:'drip',area:1,area_unit:'hectare',day_of_growth:70,moisture_condition:'normal',latitude:47.12,longitude:51.88,field_type:'open'};
const day=()=>new Date(Date.now()+18000000).toISOString().slice(0,10);
const weather=()=>({timezone:'Asia/Atyrau',utc_offset_seconds:18000,daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},daily:{time:[day()],et0_fao_evapotranspiration:[6],precipitation_sum:[0]}});
const visible=id=>[...liveMessages.values()].filter(m=>m.chat_id===id);

test('expert overrides: validated, applied on top of FAO-56, shown as manual; without them nothing changes',()=>{
  const base=parseField(payload);assert.deepEqual(base.manual,[]);
  const f=parseField({...payload,expert:{p:'0.4',root_depth:.6,kc_factor:1.2}});
  assert.equal(f.p,.4);assert.equal(f.zr,.6);assert.ok(Math.abs(f.kc-base.kc*1.2)<1e-12);assert.deepEqual(f.manual,['kc_factor','root_depth','p']);
  assert.equal(f.fao.p,base.p);
  assert.throws(()=>cleanExpert({p:.95}));assert.throws(()=>cleanExpert({root_depth:0}));assert.throws(()=>cleanExpert({kc_factor:3}));
  assert.deepEqual(parseField({...payload,crop:'rice'}).manual,[]);                    // rice: not applicable
});
test('expert mode through the bot: set a value by text, advice changes, CSV and card say "manual", reset restores FAO',async()=>{
  setFetch(async()=>({ok:true,json:async()=>weather()}));
  const id=9501,u=await user(id);u.lang='en';u.languageChosen=true;await saveUser(id,u);
  const row0=await calculateField(id,payload),fid=row0.id,before=currentResult(row0);
  const send=data=>callback({id:'q'+Math.random(),from:{id},message:{message_id:(visible(id).at(-1)?.message_id??1),chat:{id,type:'private'}},data},{});
  await send(`expert:${fid}`);assert.match(visible(id).at(-1).text,/Expert mode/);assert.doesNotMatch(visible(id).at(-1).text,/✏️ \(FAO/);
  await send(`exset:${fid}:p`);assert.match(visible(id).at(-1).text,/From 0\.1 to 0\.8/);
  await message({message_id:9001,date:Math.floor(Date.now()/1000),chat:{id,type:'private'},from:{id},text:'0,3'});
  assert.match(visible(id).at(-1).text,/Saved, marked “manual”/);assert.match(visible(id).at(-1).text,/✏️ \(FAO/);
  const row=await ownedField(id,fid);assert.deepEqual(row.payload.expert,{p:.3});assert.equal(row.expert_log.length,1);
  assert.ok(currentResult(row).raw<before.raw,'smaller p -> smaller readily available water');
  assert.match(report(row,'en',true),/Changed manually: p 0\.3/);
  const csv=fieldCsv(row);assert.match(csv,/manual_overrides,"\{""p"":0\.3\}"/);assert.match(csv,/expert_changes: time,parameter,from,to/);
  await message({message_id:9002,date:Math.floor(Date.now()/1000),chat:{id,type:'private'},from:{id},text:'x'});   // not in expert mode now: no change
  assert.deepEqual((await ownedField(id,fid)).payload.expert,{p:.3});
  await send(`exset:${fid}:p`);await message({message_id:9003,date:Math.floor(Date.now()/1000),chat:{id,type:'private'},from:{id},text:'2'});
  assert.match(visible(id).at(-1).text,/Enter a number from 0\.1 to 0\.8/);assert.deepEqual((await ownedField(id,fid)).payload.expert,{p:.3});
  await send(`exreset:${fid}`);assert.match(visible(id).at(-1).text,/FAO-56 values restored/);
  const back=await ownedField(id,fid);assert.equal(back.payload.expert,undefined);assert.equal(currentResult(back).raw,before.raw);
});
test('a physical change that restarts the field keeps the expert overrides',async()=>{
  setFetch(async()=>({ok:true,json:async()=>weather()}));
  const id=9502;await user(id,'en');const r=await calculateField(id,payload);await setExpert(id,r.id,'kc_factor',1.1);
  const again=await calculateField(id,{...payload,soil_type:'clay'});
  assert.equal(again.submit,'reset');assert.deepEqual(again.payload.expert,{kc_factor:1.1});
  assert.equal((await list(id,'field')).length,1);
});
