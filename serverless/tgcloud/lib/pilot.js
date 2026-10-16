import {db} from 'sdk';
import {get,put,list,remove} from './store.js';
import {ownedField} from './fields.js';
import {PILOT_COPY} from './pilot-copy.js';
import {button,keyboard,back,APP_URL,screen} from './ui.js';
import {tr} from './i18n.js';
export const p=(lang,key,values={})=>(PILOT_COPY[lang]??PILOT_COPY.ru)[key].replace(/\{(\w+)\}/g,(m,k)=>values[k]??m);
export async function pilot(id,lang,action,generation){
 if(action==='join')await put(`pilot:${id}`,id,'pilot',{lang,joined:Date.now()});
 if(action==='delete'){
  await remove(`pilot:${id}`,id,'pilot');
  await db.run("DELETE FROM records WHERE owner=:owner AND kind='feedback'",{':owner':id});
  return screen(id,p(lang,'deleted'),keyboard([back(lang)]),generation);
 }
 if(action==='leave')return screen(id,p(lang,'deletePrompt'),keyboard([[button(p(lang,'confirmDelete'),'pilot:delete'),button(p(lang,'cancel'),'pilot:back')]]),generation);
 const joined=await get(`pilot:${id}`,id),stats=await db.get("SELECT COUNT(*) AS reviews,COALESCE(SUM(json_extract(body,'$.useful')),0) AS useful FROM records WHERE owner=:owner AND kind='feedback'",{':owner':id});
 return screen(id,joined?p(lang,'joined',stats):p(lang,'invite'),keyboard([
  [button(p(lang,joined?'leave':'join'),joined?'pilot:leave':'pilot:join')],
  [{text:p(lang,'back'),web_app:{url:APP_URL+'?lang='+lang}}],back(lang)]),generation);
}
export async function feedback(id,fieldId,useful){
 if(typeof useful!=='boolean')throw new Error('invalid');const row=await ownedField(id,fieldId);
 await put(`feedback:${id}:${row.id}:${row.last_day}`,id,'feedback',{field_id:row.id,date:row.last_day,useful,created:Date.now()});
}
