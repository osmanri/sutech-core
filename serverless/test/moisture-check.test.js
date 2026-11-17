import test from 'node:test';
import assert from 'node:assert/strict';
import {setFetch,liveMessages} from 'sdk';
import {user} from '../tgcloud/lib/store.js';
import {calculateField,ownedField,checkMoisture,currentResult,SOIL_LEVELS} from '../tgcloud/lib/fields.js';
import {callback} from '../tgcloud/lib/bot.js';
const payload={balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:.1,area_unit:'hectare',day_of_growth:30,moisture_condition:'dry',latitude:47.12,longitude:51.88,field_type:'open'};
const day=()=>new Date(Date.now()+18000000).toISOString().slice(0,10);
const weather=()=>({timezone:'Asia/Atyrau',utc_offset_seconds:18000,daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},daily:{time:[day()],et0_fao_evapotranspiration:[5],precipitation_sum:[0]}});
const visible=id=>[...liveMessages.values()].filter(m=>m.chat_id===id);

test('a soil check replaces the deficit with 0, RAW/2 or RAW and keeps an audit trail',async()=>{
 setFetch(async()=>({ok:true,json:async()=>weather()}));
 const id=9101,row=await calculateField(id,payload),raw=row.result.raw;
 const wet=await checkMoisture(id,row.id,'wet');assert.equal(wet.deficit,0);assert.equal(currentResult(wet).status,'deferred');
 const normal=await checkMoisture(id,row.id,'normal');assert.ok(Math.abs(normal.deficit-raw/2)<1e-9);
 const dry=await checkMoisture(id,row.id,'dry');assert.ok(Math.abs(dry.deficit-raw)<1e-9);assert.notEqual(currentResult(dry).status,'deferred');
 const saved=await ownedField(id,row.id);
 assert.equal(saved.checks.length,3);assert.deepEqual(saved.checks.map(c=>c.level),['wet','normal','dry']);
 assert.ok(saved.revision>row.revision);
});
test('soil check rejects unknown levels, other owners, stale revisions and rice',async()=>{
 setFetch(async()=>({ok:true,json:async()=>weather()}));
 const id=9102,row=await calculateField(id,payload);
 await assert.rejects(()=>checkMoisture(id,row.id,'__proto__'),/bad_level/);
 await assert.rejects(()=>checkMoisture(id,row.id,'constructor'),/bad_level/);
 await assert.rejects(()=>checkMoisture(9103,row.id,'wet'),/not_found/);
 await assert.rejects(()=>checkMoisture(id,row.id,'wet',row.revision+5),/balance_changed/);
 const rice=await calculateField(id,{...payload,crop:'rice',latitude:47.5});
 await assert.rejects(()=>checkMoisture(id,rice.id,'wet'),/not_applicable/);
 assert.deepEqual(Object.keys(SOIL_LEVELS),['wet','normal','dry']);
});
test('buttons: field card offers the check, answering it updates the screen in the user language',async()=>{
 setFetch(async()=>({ok:true,json:async()=>weather()}));
 const id=9104,u=await user(id);u.lang='en';u.languageChosen=true;const {saveUser}=await import('../tgcloud/lib/store.js');await saveUser(id,u);
 const row=await calculateField(id,payload),send=data=>callback({id:'q'+Math.random(),from:{id},message:{message_id:(visible(id).at(-1)?.message_id??1),chat:{id,type:'private'}},data},{});
 await send(`field:${row.id}`);
 assert.ok(JSON.stringify(visible(id).at(-1).reply_markup).includes(`soil:${row.id}`));
 await send(`soil:${row.id}`);
 assert.match(visible(id).at(-1).text,/How moist is the soil/);
 assert.match(visible(id).at(-1).text,/about \d+ cm deep/);                       // sampling depth for this crop and day
 assert.match(visible(id).at(-1).text,/Wet:.*Normal:.*Dry:/s);                      // the feel test for each level
 assert.match(visible(id).at(-1).text,/not a laboratory measurement/);
 await send(`soilset:${row.id}:wet`);
 assert.match(visible(id).at(-1).text,/Balance corrected from your check/);
 assert.equal((await ownedField(id,row.id)).deficit,0);
 await send(`soilset:${row.id}:bogus`);
 assert.equal((await ownedField(id,row.id)).deficit,0);
});
