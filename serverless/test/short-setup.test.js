import test from 'node:test';
import assert from 'node:assert/strict';
import {setFetch,liveMessages} from 'sdk';
import {user,saveUser,list} from '../tgcloud/lib/store.js';
import {callback,message,action} from '../tgcloud/lib/bot.js';
import {plantingDays,accept,steps} from '../tgcloud/lib/planner.js';

const day=()=>new Date(Date.now()+18000000).toISOString().slice(0,10);
const weather=()=>({timezone:'Asia/Atyrau',utc_offset_seconds:18000,daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},daily:{time:[day()],et0_fao_evapotranspiration:[6],precipitation_sum:[0]}});
const visible=id=>[...liveMessages.values()].filter(m=>m.chat_id===id);

test('planting date: ISO, dotted, no year (never in the future), days; bad dates rejected',()=>{
  const now=Date.UTC(2026,6,1,10);                           // 1 July 2026
  assert.equal(plantingDays('2026-06-01',now),30);assert.equal(plantingDays('01.06.2026',now),30);assert.equal(plantingDays('1.6',now),30);
  assert.equal(plantingDays('01.07',now),0);assert.equal(plantingDays('45',now),45);
  assert.equal(plantingDays('15.12',now),198);                // 15.12 has not happened this year: last year
  for(const bad of ['31.02.2026','2026-08-01','32.01','abc','-3'])assert.throws(()=>plantingDays(bad,now),bad);
  assert.equal(accept('day_of_growth','01.06.2026',{crop:'cotton'},now).day_of_growth,30);
  assert.throws(()=>accept('day_of_growth','01.01.2020',{crop:'cotton'},now));    // longer than the season
  assert.deepEqual(steps({crop:'cotton'}),['crop','area','location','day_of_growth','irrigation_type','confirm']);
  assert.ok(steps({crop:'other'}).includes('custom'));
});
test('five questions, then "We assumed" with refine buttons; defaults are used and one value can be refined',async()=>{
  setFetch(async()=>({ok:true,json:async()=>weather()}));
  const id=9601,u=await user(id);u.lang='en';u.languageChosen=true;await saveUser(id,u);
  const last=()=>visible(id).at(-1),btn=(re)=>JSON.stringify(last().reply_markup).match(new RegExp(`"callback_data":"(p:[^"]*${re}[^"]*)"`))?.[1];
  const press=async data=>callback({id:'q'+Math.random(),from:{id},message:{message_id:last()?.message_id??1,chat:{id,type:'private'}},data},{});
  const say=async text=>message({message_id:Math.floor(Math.random()*1e6),date:Math.floor(Date.now()/1000),chat:{id,type:'private'},from:{id},text});
  await action(id,'plan');assert.match(last().text,/1\/6/);
  await press(btn(':cotton'));assert.match(last().text,/2\/6/);
  await say('2');assert.match(last().text,/3\/6/);
  await say('47.12 51.88');assert.match(last().text,/4\/6/);assert.match(last().text,/date/);
  const planted=new Date(Date.now()-60*86400000),dd=`${String(planted.getUTCDate()).padStart(2,'0')}.${String(planted.getUTCMonth()+1).padStart(2,'0')}.${planted.getUTCFullYear()}`;
  await say(dd);assert.match(last().text,/5\/6/);
  await press(btn(':drip'));
  const t=last().text;assert.match(t,/6\/6/);assert.match(t,/We assumed/);assert.match(t,/Soil: Loam/);assert.match(t,/Salinity: none/);assert.match(t,/not entered, cost is not calculated/);assert.match(t,/FAO-56/);
  assert.ok(btn('refine:soil_type'),'refine buttons exist');assert.ok(btn('calculate'));
  await press(btn('refine:soil_type'));assert.match(last().text,/Refinement/);assert.match(last().text,/rough test/i);
  await press(btn(':clay'));assert.match(last().text,/Soil: Clay/);assert.match(last().text,/6\/6/);
  await press(btn('calculate'));
  const fields=await list(id,'field');assert.equal(fields.length,1);
  const p=fields[0].payload;assert.equal(p.soil_type,'clay');assert.equal(p.moisture_condition,'normal');assert.equal(p.field_type,'open');assert.equal(p.is_saline,'no');
  assert.ok(Math.abs(p.day_of_growth-60)<=1);assert.equal(p.power_price??null,null);
});
