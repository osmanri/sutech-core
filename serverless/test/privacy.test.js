import test from 'node:test';
import assert from 'node:assert/strict';
import {setFetch,liveMessages,db} from 'sdk';
import {user,saveUser,put,get,list,eraseUserData,reserveAI} from '../tgcloud/lib/store.js';
import {calculateField} from '../tgcloud/lib/fields.js';
import {callback} from '../tgcloud/lib/bot.js';

const payload={balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:.1,area_unit:'hectare',day_of_growth:30,moisture_condition:'dry',latitude:47.12,longitude:51.88,field_type:'open'};
const day=()=>new Date(Date.now()+18000000).toISOString().slice(0,10);
const weather=()=>({timezone:'Asia/Atyrau',utc_offset_seconds:18000,daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},daily:{time:[day()],et0_fao_evapotranspiration:[5],precipitation_sum:[0]}});
const visible=id=>[...liveMessages.values()].filter(m=>m.chat_id===id);

test('erasing one user removes every record of that user and leaves the others untouched',async()=>{
 setFetch(async()=>({ok:true,json:async()=>weather()}));
 const a=9301,b=9302;await user(a,'ru');await user(b,'ru');
 await calculateField(a,payload);await calculateField(b,payload);
 await put('feedback:x',a,'feedback',{useful:true});
 assert.ok((await list(a,'field')).length>=1);
 const n=await eraseUserData(a);
 assert.ok(n>=3,`records deleted: ${n}`);                                   // profile, field, report/weather ...
 for(const kind of ['field','report','weather','feedback','pilot','pending'])assert.equal((await list(a,kind)).length,0,kind);
 assert.equal(await get(`user:${a}`,a),null);
 assert.ok((await list(b,'field')).length>=1,'another user is untouched');
 assert.ok(await get(`user:${b}`,b));
 assert.ok((await user(a,'en')).lang==='en','the bot starts clean after erasure');
});
test('AI quota window survives erasure so deleting data cannot reset the daily limit',async()=>{
 const id=9303;await user(id,'ru');
 for(let i=0;i<20;i++){await db.run('INSERT INTO ai_usage_v2(id,owner,created) VALUES(:id,:o,:t)',{':id':`q${i}`,':o':id,':t':Date.now()-10000-i});}
 await db.run('INSERT INTO ai_usage_v2(id,owner,created) VALUES(:id,:o,:t)',{':id':'old',':o':id,':t':Date.now()-2*86400000});
 await eraseUserData(id);
 const left=await db.get('SELECT COUNT(*) AS n FROM ai_usage_v2 WHERE owner=:o',{':o':id});
 assert.equal(left.n,20,'the last 24 h stay, the old row is gone');
 await assert.rejects(()=>reserveAI(id),/daily_limit/);
});
test('buttons: privacy screen explains what is stored, deletion asks twice and then empties the bot',async()=>{
 setFetch(async()=>({ok:true,json:async()=>weather()}));
 const id=9304,u=await user(id);u.lang='en';u.languageChosen=true;await saveUser(id,u);
 await calculateField(id,payload);
 const send=data=>callback({id:'q'+Math.random(),from:{id},message:{message_id:(visible(id).at(-1)?.message_id??1),chat:{id,type:'private'}},data},{});
 await send('more');assert.ok(JSON.stringify(visible(id).at(-1).reply_markup).includes('privacy'));
 await send('privacy');
 assert.match(visible(id).at(-1).text,/What Su-Tech stores/);assert.match(visible(id).at(-1).text,/Open-Meteo/);assert.match(visible(id).at(-1).text,/Gemini/);
 await send('wipe');assert.match(visible(id).at(-1).text,/cannot be undone/);
 assert.ok((await list(id,'field')).length>=1,'nothing is deleted before the second confirmation');
 const confirm=visible(id).at(-1).reply_markup.inline_keyboard[0][0].callback_data;
 await send('privacy');await send(confirm);
 assert.equal((await list(id,'field')).length,1,'old confirmation cannot delete a field');
 await send('wipe');await send(visible(id).at(-1).reply_markup.inline_keyboard[0][0].callback_data);
 assert.match(visible(id).at(-1).text,/records deleted/);
 assert.equal((await list(id,'field')).length,0);
});
