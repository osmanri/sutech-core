import test from 'node:test';
import assert from 'node:assert/strict';
import {liveMessages} from 'sdk';
import {user} from '../tgcloud/lib/store.js';
import {message,callback} from '../tgcloud/lib/bot.js';
import {demoCalculation,demoScreen,demoSteps} from '../tgcloud/lib/demo.js';
import {list} from '../tgcloud/lib/store.js';
const visible=id=>[...liveMessages.values()].filter(m=>m.chat_id===id);

test('demo scenario reproduces the audited reference case',()=>{
 const {result:r}=demoCalculation();
 assert.ok(Math.abs(r.taw-187.5)<1e-9&&Math.abs(r.raw-103.125)<1e-9);
 assert.ok(Math.abs(r.deficit-108.875)<1e-9);
 assert.equal(r.status,'critical');
 assert.ok(Math.abs(r.gross_m3-1209.7222)<1e-3);
});
test('demo screens render in all languages and show the formula steps with real numbers',()=>{
 for(const lang of ['ru','kz','en']){
  const main=demoScreen(lang),steps=demoSteps(lang);
  assert.match(main.text,/1210 m³/);assert.match(steps.text,/TAW/);assert.match(steps.text,/108\.88|108\.87|108\.9/);
  assert.doesNotMatch(main.text+steps.text,/undefined|NaN/);
 }
 assert.match(demoScreen('en').text,/model scenario/);
});
test('/start demo_en opens the demo in English, stores nothing, and steps are reachable',async()=>{
 const id=7301;await user(id);
 await message({chat:{id,type:'private'},from:{id,language_code:'ru'},message_id:1,date:1,text:'/start demo_en'},{});
 assert.match(visible(id).at(-1).text,/DEMO · model scenario/);
 const screenId=(await user(id)).screen;
 await callback({id:'d1',from:{id},message:{message_id:screenId,chat:{id,type:'private'}},data:'demo:steps'},{});
 assert.match(visible(id).at(-1).text,/How it is calculated/);
 assert.equal((await list(id,'field',10)).length,0);
 assert.equal((await list(id,'report',10)).length,0);
});
