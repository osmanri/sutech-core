import test from 'node:test';
import assert from 'node:assert/strict';
import {messages,liveMessages,setApiHandler} from 'sdk';
import {user,saveUser,get,put} from '../tgcloud/lib/store.js';
import {screen,navigate,keyboard} from '../tgcloud/lib/ui.js';
import {message,callback} from '../tgcloud/lib/bot.js';
const visible=id=>[...liveMessages.values()].filter(m=>m.chat_id===id);
test('uneditable old menu is replaced and removed instead of stacking',async()=>{
 const id=1201;await user(id);await screen(id,'Old menu',keyboard([]));
 setApiHandler(async(method)=>{if(method==='editMessageText')throw Object.assign(new Error('Cannot edit'),{code:400,description:"Bad Request: message can't be edited"});});
 try{await screen(id,'New menu',keyboard([]));assert.equal(visible(id).length,1);assert.equal(visible(id)[0].text,'New menu');}
 finally{setApiHandler(null);}
});
test('parallel initial screens settle on one current message',async()=>{
 const id=1202;await user(id);let release,started;
 const firstSending=new Promise(r=>started=r),barrier=new Promise(r=>release=r);let n=0;
 setApiHandler(async(method,params)=>{if(method==='sendMessage'&&params.chat_id===id&&++n===1){started();await barrier;}});
 try{
  const first=screen(id,'Older',keyboard([]));await firstSending;
  const second=screen(id,'Newer',keyboard([]));release();await Promise.all([first,second]);
  assert.equal(visible(id).length,1);assert.equal(visible(id)[0].text,'Newer');
 }finally{setApiHandler(null);}
});
test('saving an older conversation snapshot cannot lose a new screen pointer',async()=>{
 const id=1204,stale=await user(id);await screen(id,'Current menu',keyboard([]));const current=(await user(id)).screen;
 stale.lang='kz';await saveUser(id,stale);assert.equal((await user(id)).screen,current);
 await screen(id,'Next menu',keyboard([]));assert.equal(visible(id).length,1);
});
test('Telegram MESSAGE_NOT_MODIFIED never creates a new menu',async()=>{
 const id=1205;await screen(id,'Menu',keyboard([]));const current=(await user(id)).screen;
 setApiHandler(async(method)=>{if(method==='editMessageText')throw Object.assign(new Error('Unchanged'),{code:400,description:'Bad Request: MESSAGE_NOT_MODIFIED'});});
 try{await screen(id,'Menu',keyboard([]));assert.equal(visible(id).length,1);assert.equal((await user(id)).screen,current);}
 finally{setApiHandler(null);}
});

test('temporary edit failure keeps one menu and releases renderer for retry',async()=>{
 const id=1211;await screen(id,'Menu',keyboard([]));
 setApiHandler(async(method)=>{if(method==='editMessageText')throw Object.assign(new Error('Unavailable'),{code:500});});
 try{await assert.rejects(screen(id,'Next menu',keyboard([])),/Unavailable/);assert.equal(visible(id).length,1);}
 finally{setApiHandler(null);}
 await screen(id,'Recovered menu',keyboard([]));assert.equal(visible(id).length,1);assert.equal(visible(id)[0].text,'Recovered menu');
});

test('clicking an orphan menu removes it while retaining the current screen',async()=>{
 const id=1212;await user(id,'en');await screen(id,'Current',keyboard([]));
 const orphan=await import('sdk').then(({api})=>api.sendMessage({chat_id:id,text:'Old language menu'}));
 await callback({id:'orphan-menu',from:{id},message:{message_id:orphan.message_id,chat:{id,type:'private'}},data:'home'},{});
 assert.equal(visible(id).length,1);assert.ok(visible(id)[0].text.includes('Choose an action'));
});
test('start reuses chosen language and existing menu',async()=>{
 const id=1206;await user(id,'en');await screen(id,'Menu',keyboard([]));const u=await user(id);u.languageChosen=true;u.keyboardReset=true;await saveUser(id,u);
 await message({message_id:900,chat:{id,type:'private'},from:{id},text:'/start'},{});
 await message({message_id:901,chat:{id,type:'private'},from:{id},text:'/start'},{});
 assert.equal(visible(id).length,1);assert.ok(visible(id)[0].text.includes('Choose an action'));assert.equal((await user(id)).lang,'en');
});
test('cleanup imports only known menus of the same chat',async()=>{
 const id=1207,other=1208;
 const first=await import('sdk').then(({api})=>api.sendMessage({chat_id:id,text:'Legacy'}));
 const second=await import('sdk').then(({api})=>api.sendMessage({chat_id:other,text:'Other farmer'}));
 await put('legacy-menu-one',0,'legacy:chat_ui_messages',{chat_id:id,message_id:first.message_id,kind:'bot'});
 await put('legacy-menu-two',0,'legacy:chat_ui_messages',{chat_id:other,message_id:second.message_id,kind:'bot'});
 await screen(id,'Current',keyboard([]));assert.equal(visible(id).length,1);assert.equal(visible(other).length,1);
});
test('stale planner buttons recover to a usable menu',async()=>{
 const id=1209;await user(id,'en');await screen(id,'Old planner',keyboard([]));const u=await user(id);
 await callback({id:'old-plan',from:{id},message:{message_id:u.screen,chat:{id,type:'private'}},data:'p:0:1:drip'},{});
 assert.equal(visible(id).length,1);assert.ok(visible(id)[0].text.includes('Choose an action'));
});
test('cleanup failures do not prevent menu or button transitions',async()=>{
 const id=1210;await user(id,'en');await screen(id,'Menu',keyboard([]));
 setApiHandler(async(method)=>{if(method==='deleteMessage')throw Object.assign(new Error('Rate limit'),{code:429});});
 try{await message({message_id:902,chat:{id,type:'private'},from:{id},text:'/menu'},{});assert.ok(visible(id).some(m=>m.text.includes('Choose an action')));}
 finally{setApiHandler(null);}
});
test('expired callback acknowledgement does not require start to navigate',async()=>{
 const id=1203;await user(id,'kz');await screen(id,'Old',keyboard([]));const u=await user(id);
 setApiHandler(async(method)=>{if(method==='answerCallbackQuery')throw Object.assign(new Error('Query expired'),{code:400,description:'Bad Request: query is too old and response timeout expired or query ID is invalid'});});
 try{await callback({id:'expired',from:{id},message:{message_id:u.screen,chat:{id,type:'private'}},data:'home'},{});assert.ok(visible(id)[0].text.includes('Әрекетті таңдаңыз'));}
 finally{setApiHandler(null);}
});
