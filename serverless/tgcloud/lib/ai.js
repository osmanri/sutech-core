import {fetch,api} from 'sdk';
import {get,put,list,lock,unlock,setting,reserveAI,user,nonce} from './store.js';
import {inScope} from './scope.js';
import {PROMPTS} from './knowledge.js';
import {screen,aiKeys} from './ui.js';
import {a,tr,esc} from './i18n.js';
function base64(bytes){
 const chars='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';let out='';
 for(let i=0;i<bytes.length;i+=3){const n=(bytes[i]<<16)|((bytes[i+1]??0)<<8)|(bytes[i+2]??0);out+=chars[(n>>>18)&63]+chars[(n>>>12)&63]+(i+1<bytes.length?chars[(n>>>6)&63]:'=')+(i+2<bytes.length?chars[n&63]:'=');}
 return out;
}
export function imageMime(bytes){
 if(!bytes.length||bytes.length>4194304)throw new Error(bytes.length?'large_image':'bad_image');
 if(bytes[0]===255&&bytes[1]===216&&bytes[2]===255)return 'image/jpeg';
 if([137,80,78,71,13,10,26,10].every((x,i)=>bytes[i]===x))return 'image/png';
 throw new Error('bad_image');
}
export async function providerReply({key,model,text,lang,history=[],image=null,deep=false}) {
 if(!/^[A-Za-z0-9._-]+$/.test(model??''))throw new Error('configuration');
 const parts=[{text}];
 if(image)parts.unshift({inlineData:{mimeType:imageMime(image),data:base64(image)}});
 const gen=model.startsWith('gemini-3')?{maxOutputTokens:4096,thinkingConfig:{thinkingLevel:deep?'MEDIUM':'LOW'}}:{temperature:.25,maxOutputTokens:1200};
 const response=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,{
  method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':key},
  body:JSON.stringify({systemInstruction:{parts:[{text:PROMPTS[lang]??PROMPTS.ru}]},contents:[...history,{role:'user',parts}],generationConfig:gen})});
 if(!response.ok){const error=new Error(response.status===429?'quota':[400,401,403,404].includes(response.status)?'configuration':'unavailable');error.httpStatus=response.status;throw error;}
 const data=await response.json(),candidate=data.candidates?.[0];
 if(!candidate||!['STOP','MAX_TOKENS',undefined].includes(candidate.finishReason))throw new Error('no_answer');
 const answer=(candidate.content?.parts??[]).filter(p=>typeof p.text==='string'&&!p.thought).map(p=>p.text).join('\n').trim().slice(0,3500);
 if(!answer)throw new Error('no_answer');
 const responseParts=candidate.content.parts.filter(p=>typeof p.text==='string'||p.thoughtSignature).map(p=>Object.fromEntries(Object.entries(p).filter(([k])=>['text','thought','thoughtSignature'].includes(k))));
 return {answer,responseParts};
}
export async function generate(id,text,lang,image=null,deep=false) {
 if(text.length>2000)throw new Error('long_text');
 const guard=`ai:${id}`,token=await lock(guard,75);if(!token)throw new Error('busy');
 try {
  const u=await user(id),generation=u.generation;
  const session=await get(`ai-context:${id}`,id);
  let history=session&&Date.now()-session._updated<1800000?session.history??[]:[];
  if(image)history=[];
  if(!inScope(text,history,!!image))throw new Error('off_topic');
  const key=await setting('gemini_key');if(!key)throw new Error('not_configured');
  let model=await setting(deep?'gemini_deep_model':'gemini_model');
  if(session?.model!==model)history=[];
  if(image)imageMime(image);
  await reserveAI(id);
  await screen(id,esc(a(lang,image?'working':'thinking')),aiKeys(lang),generation);
  await api.sendChatAction({chat_id:id,action:'typing'});
  let reply;
  try{reply=await providerReply({key,model,text,lang,history,image,deep});}
  catch(e){
   if(!deep&&![500,502,503,504].includes(e.httpStatus))throw e;
   if((await user(id)).generation!==generation)return {cancelled:true};
   if(deep){model=await setting('gemini_model');history=session?.model===model?session.history:[];reply=await providerReply({key,model,text,lang,history,image,deep:false});reply.answer=a(lang,'deep_fallback')+'\n\n'+reply.answer;}
   else reply=await providerReply({key,model,text,lang,history,image,deep});
  }
  const {answer,responseParts}=reply;
  const latest=await user(id);
  // A late AI response must not replace a screen the farmer has navigated to.
  if(latest.generation!==generation||latest.mode!=='ai')return {cancelled:true};
  history=[...history,{role:'user',parts:[{text:(image?'[new plant photo] ':'')+text}]},{role:'model',parts:responseParts}].slice(-8);
  await put(`ai-context:${id}`,id,'ai-context',{history,model});
  await put(`ai-answer:${nonce()}`,id,'ai-answer',{question:text,answer,model,has_image:!!image,created:Date.now()});
  await screen(id,answer,aiKeys(lang),generation,true);return {ok:true,characters:answer.length};
 } finally {await unlock(guard,token);}
}
export async function aiHistory(id,lang,page=0) {
 const items=await list(id,'ai-answer',5,page*5);
 return items.map((x,i)=>({id:x._id,text:`<b>${i+1+page*5}. ${esc(x.question.slice(0,80))}</b>\n${esc(x.answer)}`}));
}
