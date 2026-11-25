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
  assert.deepEqual(steps({crop:'cotton'}),['crop','area','location','day_of_growth','irrigation_type','field_type','confirm']);
  assert.ok(steps({crop:'other'}).includes('custom'));
});
function chat(id){
  const last=()=>visible(id).at(-1);
  const buttons=()=>last().reply_markup.inline_keyboard.flat();
  const press=async suffix=>{
    const choice=buttons().find(b=>b.callback_data?.endsWith(suffix));assert.ok(choice,`button ${suffix}`);
    await callback({id:'q'+Math.random(),from:{id},message:{message_id:last().message_id,chat:{id,type:'private'}},data:choice.callback_data},{});
  };
  const say=async input=>message({message_id:Math.floor(Math.random()*1e6),date:Math.floor(Date.now()/1000),chat:{id,type:'private'},from:{id},...(typeof input==='string'?{text:input}:input)});
  return {last,buttons,press,say};
}

test('different area units convert to the same engine input',()=>{
  for(const value of ['0,06 га','6 соток','600 м²','20×30','600 m2','6 сотық','0.06 ha']){
    assert.equal(accept('area',value,{}).area,.06,value);
  }
  for(const value of ['600 bananas','20×0','-6 соток','2 га 6 соток'])assert.throws(()=>accept('area',value,{}));
});

test('home opens the short setup, which requires a field type and applies the selected soil',async()=>{
  setFetch(async()=>({ok:true,json:async()=>weather()}));
  const id=9601,u=await user(id);u.lang='en';u.languageChosen=true;await saveUser(id,u);
  const {last,buttons,press,say}=chat(id);
  await action(id,'home');assert.ok(buttons().some(b=>b.text==='Calculate irrigation'&&b.callback_data==='plan'));
  await press('plan');assert.match(last().text,/1\/7/);
  await press(':cotton');assert.match(last().text,/2\/7/);
  await say('2');assert.match(last().text,/3\/7/);assert.match(last().text,/location/i);
  await say('47.12 51.88');assert.match(last().text,/4\/7/);assert.match(last().text,/date/);
  const planted=new Date(Date.now()-60*86400000),dd=`${String(planted.getUTCDate()).padStart(2,'0')}.${String(planted.getUTCMonth()+1).padStart(2,'0')}.${planted.getUTCFullYear()}`;
  await say(dd);assert.match(last().text,/5\/7/);
  await press(':drip');assert.match(last().text,/6\/7/);
  assert.ok(!buttons().some(b=>b.callback_data?.endsWith(':calculate')));
  await press(':open');
  const t=last().text;assert.match(t,/7\/7/);assert.match(t,/We assumed/);assert.match(t,/Soil: Loam/);assert.match(t,/Salinity: not included/);
  await press('refine:soil_type');assert.match(last().text,/Refinement/);assert.match(last().text,/rough test/i);
  await press(':clay');assert.match(last().text,/Soil: Clay/);assert.match(last().text,/7\/7/);
  await press(':calculate');
  const fields=await list(id,'field');assert.equal(fields.length,1);
  const p=fields[0].payload;assert.equal(p.soil_type,'clay');assert.equal(p.moisture_condition,'normal');assert.equal(p.field_type,'open');assert.equal(p.is_saline,'no');
  assert.ok(Math.abs(p.day_of_growth-60)<=1);assert.equal(p.power_price??null,null);
});

test('short setup accepts a map pin and a growth stage, and gives no dose for greenhouse substrate',async()=>{
  setFetch(async()=>({ok:true,json:async()=>weather()}));
  const id=9602,u=await user(id);u.lang='ru';u.languageChosen=true;await saveUser(id,u);
  const {last,press,say}=chat(id);
  await say('/start plan_ru');
  await press(':tomato');await say('6 соток');await say({location:{latitude:47.13,longitude:51.88}});
  await press(':stage:middle');await press(':drip');await press(':substrate');
  assert.match(last().text,/возраст приблизительный/i);
  await press(':calculate');
  const [field]=await list(id,'field');
  assert.equal(field.payload.area,.06);assert.equal(field.payload.latitude,47.13);
  assert.equal(field.payload.greenhouse_medium,'substrate');assert.equal(field.payload.growth_estimated,true);
  assert.equal(field.result.status,'unsupported');
  assert.match(last().text,/Совет по поливу не выдаётся/);
  assert.doesNotMatch(last().text,/Подать воды|м³/);
});

test('heated and unheated greenhouses cannot carry a stale indoor weather value between them',()=>{
  const selected=accept('field_type','heated',{field_type:'greenhouse',greenhouse_medium:'soil',greenhouse_heated:'no',greenhouse_et0:2.5});
  assert.deepEqual(selected,{field_type:'greenhouse',greenhouse_medium:'soil',greenhouse_heated:'yes',greenhouse_et0:null});
});

test('heated greenhouse chat asks for an indoor measurement and continues only with the supported advice',async()=>{
  setFetch(async()=>({ok:true,json:async()=>weather()}));
  for(const [id,measured] of [[9604,false],[9605,true]]){
    const u=await user(id);u.lang='en';u.languageChosen=true;await saveUser(id,u);
    const {last,press,say}=chat(id);
    await say('/plan');await press(':tomato');await say('600 m2');await say('47.15 51.88');
    await press(':stage:development');await press(':drip');await press(':heated');await press('refine:greenhouse_et0');
    assert.match(last().text,/inside this greenhouse/);assert.doesNotMatch(last().text,/0\.70/);
    if(measured)await say('2.5');else await press(':skip');
    await press(':calculate');
    const [field]=await list(id,'field');
    assert.equal(field.payload.greenhouse_et0,measured?2.5:null);
    assert.equal(field.result.status==='unsupported',!measured);
    assert.match(last().text,measured?/age is approximate/:/No irrigation advice/);
  }
});

test('the chat reproduces the reference wheat calculation and records an actual dose in litres',async()=>{
  setFetch(async()=>{const data=weather();data.daily.et0_fao_evapotranspiration=[5];return {ok:true,json:async()=>data};});
  const id=9603,u=await user(id,'ru');u.languageChosen=true;await saveUser(id,u);
  const {last,press,say}=chat(id);
  await say('/plan');await press(':wheat');await say('10 соток');await say('47.14 51.88');
  await say('60');await press(':drip');await press(':open');await press('refine:moisture_condition');await press(':dry');
  await press(':calculate');
  const [field]=await list(id,'field');
  const expected=(1250*(0.25-0.10)*0.55+1.15*5)*10*0.1/0.9;
  assert.ok(Math.abs(field.result.gross_m3-expected)<1e-9);
  assert.match(last().text,/≈\s*121 м³/);
  await press(`water:${field.id}`);
  assert.match(last().text,/200 л/);
  await say('200 л');
  const [saved]=await list(id,'field');
  assert.equal(saved.events.at(-1).applied_m3,0.2);
  assert.ok(Math.abs(saved.deficit-(field.deficit-0.18))<1e-9);
});
