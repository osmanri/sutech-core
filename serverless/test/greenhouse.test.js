import test from 'node:test';
import assert from 'node:assert/strict';
import {calculate,parseField,CROPS} from '../tgcloud/lib/balance.js';
import {currentResult,report,calculateField,refresh,waterField} from '../tgcloud/lib/fields.js';
import {action,message} from '../tgcloud/lib/bot.js';
import {setFetch,messages} from 'sdk';
import {put,user,saveUser} from '../tgcloud/lib/store.js';

const f=(c={})=>parseField({balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:0.1,area_unit:'hectare',day_of_growth:60,moisture_condition:'dry',field_type:'greenhouse',...c});

const payload=(crop,changes={})=>({balance_version:2,crop,soil_type:'loam',irrigation_type:'drip',area:.1,area_unit:'hectare',day_of_growth:20,moisture_condition:'dry',field_type:'greenhouse',custom_kc:.9,custom_root_depth:.5,custom_p:.4,...changes});
const cases=[
 ['soil','no',null,null],['soil','no',0,null],['soil','no',2.5,null],
 ['soil','yes',null,'heated_needs_measurement'],['soil','yes',0,null],['soil','yes',2.5,null],
 ['substrate','no',null,'substrate'],['substrate','no',0,'substrate'],['substrate','no',2.5,'substrate'],
 ['substrate','yes',null,'substrate'],['substrate','yes',0,'substrate'],['substrate','yes',2.5,'substrate']
].flatMap(([medium,heated,measured,reason])=>[
 ['greenhouse',medium,heated,measured,reason],['open',medium,heated,measured,null]
]);

test('all crops obey the same greenhouse limits, including rice and custom crops',()=>{
 for(const crop of [...Object.keys(CROPS),'rice','other'])for(const [field_type,greenhouse_medium,greenhouse_heated,greenhouse_et0,reason] of cases){
  const r=calculate(parseField(payload(crop,{field_type,greenhouse_medium,greenhouse_heated,greenhouse_et0})),6,10);
  const label=JSON.stringify({crop,field_type,greenhouse_medium,greenhouse_heated,greenhouse_et0});
  if(reason)assert.deepEqual([r.status,r.unsupported_reason,r.net_m3,r.gross_m3],['unsupported',reason,0,0],label);
  else assert.notEqual(r.status,'unsupported',label);
 }
});

test('old saved advice cannot bypass greenhouse limits or offer a watering action',async()=>{
 const owner=75001;
 for(const [i,crop] of ['rice','tomato'].entries()){
  const p=payload(crop,{greenhouse_medium:'substrate'}),old=calculate(parseField({...p,field_type:'open'}),6,0);
  const row={id:75010+i,payload:p,result:old,deficit:old.deficit,revision:1,last_day:'2026-11-17',weather:{timezone:'Asia/Almaty'}};
  assert.deepEqual([currentResult(row).status,currentResult(row).gross_m3],['unsupported',0]);
  for(const lang of ['ru','kz','en'])assert.doesNotMatch(report(row,lang),/Apply water|Подать воды|Берілетін су/);
  await put(`field:${row.id}`,owner,'field',row);
  await assert.rejects(()=>waterField(owner,row.id,1,row.deficit,row.revision),/unsupported/);
  await action(owner,`water:${row.id}`);
  const view=messages.filter(m=>['sendMessage','editMessageText'].includes(m.method)).at(-1).params;
  assert.doesNotMatch(view.text,/How much water did you|Сколько воды подали|Нақты қанша су/);
  assert.ok(!view.reply_markup.inline_keyboard.flat().some(b=>b.callback_data?.startsWith('water:')));
 }
});

test('new fields, same-day refresh and bot cards keep unsupported advice blocked',async()=>{
 const owner=75002,day=new Date().toISOString().slice(0,10);
 setFetch(async()=>({ok:true,json:async()=>({timezone:'UTC',utc_offset_seconds:0,daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},daily:{time:[day],et0_fao_evapotranspiration:[6],precipitation_sum:[0]}})}));
 for(const [i,crop] of ['rice','tomato'].entries()){
  const row=await calculateField(owner,payload(crop,{greenhouse_medium:'substrate',latitude:45+i,longitude:65}));
  assert.equal(row.result.status,'unsupported');
  assert.equal((await refresh(owner,row.id)).result.status,'unsupported');
  await action(owner,`field:${row.id}`);
  const view=messages.filter(m=>['sendMessage','editMessageText'].includes(m.method)).at(-1).params;
  assert.doesNotMatch(view.text,/Apply water|Подать воды|Берілетін су/);
  assert.ok(!view.reply_markup.inline_keyboard.flat().some(b=>b.callback_data?.startsWith('water:')));
 }
});

test('an already-open legacy watering conversation exits when the field is unsupported',async()=>{
 const owner=75003,p=payload('rice',{greenhouse_medium:'substrate'});
 const old=calculate(parseField({...p,field_type:'open'}),6,0),row={id:75030,payload:p,result:old,deficit:old.deficit,revision:1,last_day:'2026-11-17',weather:{timezone:'UTC'}};
 await put(`field:${row.id}`,owner,'field',row);
 const u=await user(owner,'en');u.mode='water';u.keyboardReset=true;u.water={id:row.id,expected:row.deficit,revision:row.revision};await saveUser(owner,u);
 await message({from:{id:owner},chat:{id:owner,type:'private'},message_id:75031,date:Math.floor(Date.now()/1000),text:'1'});
 const latest=await user(owner),view=messages.filter(m=>['sendMessage','editMessageText'].includes(m.method)).at(-1).params;
 assert.notEqual(latest.mode,'water');assert.equal(latest.water,undefined);
 assert.match(view.text,/No irrigation advice/);
 assert.ok(!view.reply_markup.inline_keyboard.flat().some(b=>b.callback_data?.startsWith('water:')));
});

test('unheated soil greenhouse gets the estimate; substrate and heated-without-measurement get none',()=>{
  const ok=calculate(f(),6,0);assert.notEqual(ok.status,'unsupported');assert.ok(ok.gross_m3>0);
  const sub=calculate(f({greenhouse_medium:'substrate'}),6,0);
  assert.deepEqual([sub.status,sub.unsupported_reason,sub.gross_m3,sub.net_m3],['unsupported','substrate',0,0]);
  const heated=calculate(f({greenhouse_heated:'yes'}),0.6,0);
  assert.deepEqual([heated.status,heated.unsupported_reason,heated.gross_m3],['unsupported','heated_needs_measurement',0]);
  const measured=calculate(f({greenhouse_heated:'yes',greenhouse_et0:2.5}),0.6,0);assert.notEqual(measured.status,'unsupported');assert.ok(measured.gross_m3>0);
});
test('open field ignores greenhouse settings; invalid values are refused',()=>{
  assert.notEqual(calculate(f({field_type:'open',greenhouse_medium:'substrate',greenhouse_heated:'yes'}),6,0).status,'unsupported');
  for(const bad of [{greenhouse_medium:'peat'},{greenhouse_heated:'maybe'},{greenhouse_heated:true}])assert.throws(()=>f(bad));
});
test('the stored-field view and the report keep "no advice" and explain why in all languages',()=>{
  for(const [change,word] of [[{greenhouse_medium:'substrate'},/rockwool|минвата|минвата/i],[{greenhouse_heated:'yes'},/Heated|Отапливаемая|Жылытылатын/]]){
    const p={balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:0.1,area_unit:'hectare',day_of_growth:60,moisture_condition:'dry',field_type:'greenhouse',...change};
    const r=calculate(parseField(p),6,0),row={payload:p,result:r,deficit:r.deficit,last_day:'2026-01-15',weather:{timezone:'Asia/Almaty'}};
    assert.equal(currentResult(row).status,'unsupported');
    for(const lang of ['ru','kz','en']){const text=report(row,lang);assert.doesNotMatch(text,/Apply water|Подать воды|Берілетін су/);assert.ok(text.length>40);}
    assert.match(report(row,'en'),word);
  }
});
