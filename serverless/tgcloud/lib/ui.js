import {user,navigateUser} from './store.js';
import {tr,t,a,esc,language} from './i18n.js';
import {renderScreen,retireMessage} from './screens.js';
export const APP_URL='https://app8796056339.tgcloud.ai/';
export const button=(text,data)=>({text,callback_data:data});
export const keyboard=rows=>({inline_keyboard:rows.filter(row=>row.length)});
export const back=lang=>[button(tr(lang,'‹ Назад','‹ Артқа','‹ Back'),'home')];
export function homeKeys(lang) {return keyboard([
  [{text:t(lang,'btn_webapp'),web_app:{url:`${APP_URL}?lang=${language(lang)}`}}],
  [button(a(lang,'button'),'ai')],
  [button(t(lang,'btn_fields'),'fields'),button(t(lang,'btn_history'),'history')],
  [button(tr(lang,'Ещё','Тағы','More'),'more')]
]);}
export const ignoreDelete=(chat,id)=>retireMessage(chat,id);
export async function screen(id,text,markup,expectedGeneration=null,plain=false) {
  let u=await user(id);if(expectedGeneration!==null && u.generation!==expectedGeneration)return null;
  const params={chat_id:id,text:text.slice(0,4000),...(plain?{}:{parse_mode:'HTML'}),reply_markup:markup??keyboard([back(u.lang)]),link_preview_options:{is_disabled:true}};
  return renderScreen(id,params,expectedGeneration??u.generation);
}
export const navigate=(id,mode='home')=>navigateUser(id,mode);
export const home=(id,lang,generation=null)=>screen(id,tr(lang,'<b>Su-Tech</b>\nПолив, поля и помощь по растениям. Выберите действие.','<b>Su-Tech</b>\nСуару, алқаптар және өсімдіктерге көмек. Әрекетті таңдаңыз.','<b>Su-Tech</b>\nIrrigation, fields and plant advice. Choose an action.'),homeKeys(lang),generation);
export function languages(lang) {return keyboard([[button('Русский','lang:ru'),button('Қазақша','lang:kz'),button('English','lang:en')],back(lang)]);}
export function aiKeys(lang){return keyboard([[button(a(lang,'new_button'),'ai:new'),button(tr(lang,'История ИИ','ЖИ тарихы','AI history'),'ai:history')],[button(a(lang,'deep_button'),'ai:deep')],[button(tr(lang,'Рассчитать полив в чате','Чатта суару есебі','Calculate in chat'),'plan')],back(lang)]);}
