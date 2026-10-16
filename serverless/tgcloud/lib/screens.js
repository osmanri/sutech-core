// Durable, coalesced rendering. A single worker edits one message per chat;
// concurrent handlers only replace the desired view in its mailbox.
import {api,db} from 'sdk';
import {get,put,remove,list,user,setScreen,lock,unlock,nonce} from './store.js';
const errorText=e=>String(e.description??e.message??'').toLowerCase().replaceAll('_',' ');
const unchanged=e=>e.code===400&&/not modified/.test(errorText(e));
const unavailableMessage=e=>e.code===400&&/can.?t be edited|cannot be edited|message to edit not found|message (?:id invalid|edit time expired)|not a text message|message not found/.test(errorText(e));

export async function rememberMessage(id,messageId,date=null) {
 if(!Number.isSafeInteger(messageId)||messageId<=0)return;
 const key=`ui-message:${id}:${messageId}`;
 if(!await get(key,id))await put(key,id,'ui-message',{message_id:messageId,created:date?Number(date)*1000:Date.now()});
}
export async function retireMessage(id,messageId) {
 if(!messageId)return true;
 try{await api.deleteMessage({chat_id:id,message_id:messageId});return true;}
 catch(e){
  if(e.code===403)return true;
  if(e.code===400){
   if(/not found|message id invalid/.test(errorText(e)))return true;
   // Telegram cannot delete messages older than 48 hours; disable their buttons.
   try{await api.editMessageReplyMarkup({chat_id:id,message_id:messageId,reply_markup:{inline_keyboard:[]}});return true;}
   catch(editError){return editError.code===400||editError.code===403;}
  }
  return false; // Cleanup failures must not block normal navigation.
 }
}
async function sweep(id,current) {
 for(const row of await list(id,'ui-message',12)){
  if(row.message_id===current)continue;
  if(await retireMessage(id,row.message_id))await remove(row._id,id,'ui-message');
 }
}
async function adoptLegacy(id,current) {
 const marker=`ui-migrated:${id}`;if(await get(marker,id))return;
 // Legacy rows were archived under owner 0. Require the exact chat_id before
 // adopting an ID; no cross-chat cleanup or guessed message IDs is allowed.
 const rows=await db.all("SELECT body FROM records WHERE owner=0 AND kind='legacy:chat_ui_messages' AND json_extract(body,'$.chat_id')=:owner",{':owner':id});
 for(const row of rows){const old=JSON.parse(row.body);if(old.kind==='bot')await rememberMessage(id,Number(old.message_id),Number(old.created_at));}
 if(current)await rememberMessage(id,current);
 await put(marker,id,'ui-migrated',{done:true});
}
async function render(id,view) {
 let current=(await user(id)).screen;
 if(current){
  await rememberMessage(id,current);
  try{await api.editMessageText({...view.params,message_id:current});return current;}
  catch(e){if(unchanged(e))return current;if(!unavailableMessage(e))throw e;}
 }
 const sent=await api.sendMessage(view.params);
 if(!Number.isSafeInteger(sent?.message_id)||sent.message_id<=0)throw new Error('INVALID_SCREEN_RESPONSE');
 await rememberMessage(id,sent.message_id,sent.date);
 await setScreen(id,sent.message_id);
 return sent.message_id;
}
export async function flushScreen(id) {
 const leaseId=`ui-render:${id}`,token=await lock(leaseId,45);
 if(!token)return (await user(id)).screen;
 try{
  const initial=(await user(id)).screen;await adoptLegacy(id,initial);
  for(let pass=0;pass<24;pass++){
   const view=await get(`ui-view:${id}`,id),u=await user(id);
   if(!view)break;
   let current=u.screen;
   if(view.generation===u.generation)current=await render(id,view);
   await sweep(id,current);
   // Atomic release closes the lost-wakeup window: a later view either keeps
   // this worker running, or acquires the lease itself after this DELETE.
   const released=await db.run(`DELETE FROM leases WHERE id=:id AND token=:token
     AND EXISTS(SELECT 1 FROM records WHERE id=:view AND owner=:owner AND json_extract(body,'$.token')=:viewToken) RETURNING id`,{
     ':id':leaseId,':token':token,':view':`ui-view:${id}`,':owner':id,':viewToken':view.token});
   if(released.rows?.length)return current;
  }
  throw new Error('UI_BUSY');
 }finally{await unlock(leaseId,token);}
}
export async function renderScreen(id,params,generation) {
 await user(id);
 const view={params,generation,token:nonce()};
 const saved=await db.run(`INSERT INTO records(id,owner,kind,body,updated)
   SELECT :id,:owner,'ui-view',:body,:time WHERE EXISTS(
     SELECT 1 FROM records WHERE id=:user AND owner=:owner AND json_extract(body,'$.generation')=:generation)
   ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated WHERE records.owner=excluded.owner RETURNING id`,{
   ':id':`ui-view:${id}`,':owner':id,':user':`user:${id}`,':body':JSON.stringify(view),':time':Date.now(),':generation':generation});
 if(!saved.rows?.length)return null;
 return flushScreen(id);
}
