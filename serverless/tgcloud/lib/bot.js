import {api,db,InputFile} from 'sdk';
import {user,saveUser,get,put,list,remove,ownerId} from './store.js';
import {tr,t,a,esc,volume,fmt,language} from './i18n.js';
import {STRINGS,AI_STRINGS} from './copy.js';
import {screen,navigate,home,homeKeys,languages,aiKeys,button,keyboard,back,ignoreDelete,APP_URL} from './ui.js';
import {generate,aiHistory} from './ai.js';
import {calculateField,ownedField,refresh,report,currentResult,waterField,card} from './fields.js';
import {parseField} from './balance.js';
import {planScreen,planInput} from './planner.js';
import {pilot,feedback,p} from './pilot.js';
import {rememberMessage} from './screens.js';
const fieldButtons=(row,lang)=>keyboard([
 [button(t(lang,'btn_explain'),`explain:${row.id}`)],
 [button(p(lang,'useful'),`vote:${row.id}:y`),button(p(lang,'unhelpful'),`vote:${row.id}:n`)],
 ...(currentResult(row).gross_m3>0?[[button(tr(lang,'Отметить полив','Суаруды белгілеу','Record watering'),`water:${row.id}`)]]:[]),
 [button(t(lang,'btn_field_update'),`field:${row.id}`),button(t(lang,'btn_export_field'),`export:${row.id}`)],
 [button(tr(lang,'Удалить поле','Алқапты жою','Delete field'),`delete:${row.id}`)],
 [button(t(lang,'btn_fields'),'fields')],back(lang)]);
export async function deliverCalculation(id,payload) {
 const u=await user(id);const generation=u.generation;
 await put(`pending:${id}`,id,'pending',{payload});
 await screen(id,tr(u.lang,'Считаю по погоде поля…','Алқап ауа райы бойынша есептеп жатырмын…','Calculating with field weather…'),keyboard([back(u.lang)]),generation);
 try {
  const row=await calculateField(id,payload);
  await screen(id,report(row,u.lang),fieldButtons(row,u.lang),generation);
  return {ok:true,bot_replied:true,field_id:row.id};
 } catch(e) {
  const recoverable=e.message==='weather'||e.message==='busy';
  await screen(id,recoverable?tr(u.lang,'Сейчас не удалось получить погоду. Ввод сохранён — можно повторить.','Ауа райын алу мүмкін болмады. Енгізілген деректер сақталды — қайталауға болады.','Weather is unavailable. Your inputs are saved; you can retry.'):tr(u.lang,'Проверьте параметры участка: культуру, возраст, площадь и координаты.','Алқап параметрлерін тексеріңіз: дақыл, жас, аудан және координаттар.','Check the crop, age, area and coordinates.'),keyboard([[button(tr(u.lang,'Повторить','Қайталау','Retry'),'retry')],back(u.lang)]),generation);
  return {ok:false,bot_replied:true,recoverable};
 }
}
async function fieldsScreen(id,lang,page=0,generation=null) {
 const fields=await list(id,'field',8,page*8);
 const rows=fields.map(f=>[button(`${t(lang,'report_crop_'+f.payload.crop)} · ${fmt(parseField(f.payload).area_ha,6)} ha`,`field:${f.id}`)]);
 if(page>0||fields.length===8)rows.push([...(page>0?[button('‹',`fields:${page-1}`)]:[]),...(fields.length===8?[button('›',`fields:${page+1}`)]:[])]);
 rows.push([{text:t(lang,'btn_recalculate'),web_app:{url:APP_URL+'?lang='+lang}}],back(lang));
 await screen(id,fields.length?`<b>${esc(t(lang,'btn_fields'))}</b>`:tr(lang,'Пока нет сохранённых полей. Добавьте участок через расчёт.','Сақталған алқап жоқ. Есеп арқылы алқап қосыңыз.','No saved fields yet. Add a field using the calculator.'),keyboard(rows),generation);
}
async function historyScreen(id,lang,page=0,generation=null) {
 const rows=await list(id,'report',5,page*5);
 const keys=rows.map((r,i)=>[button(`${page*5+i+1}. ${r.weather?.day??r.created_at??''} · ${r.payload?t(lang,'report_crop_'+r.payload.crop):r.crop_name}`,`rh:${encodeURIComponent(r._id).slice(0,55)}`)]);
 if(page||rows.length===5)keys.push([...(page?[button('‹',`history:${page-1}`)]:[]),...(rows.length===5?[button('›',`history:${page+1}`)]:[])]);
 keys.push(back(lang));await screen(id,rows.length?`<b>${esc(t(lang,'btn_history'))}</b>`:tr(lang,'Расчётов пока нет.','Әзірге есеп жоқ.','No calculations yet.'),keyboard(keys),generation);
}
export async function action(id,data) {
 const u=await navigate(id,['ai','ai:new','ai:deep'].includes(data)?'ai':'home'),lang=u.lang;
 const show=(text,markup,plain=false)=>screen(id,text,markup,u.generation,plain);
 if(data==='home')return home(id,lang,u.generation);
 if(data==='languages')return show('Русский / Қазақша / English',languages(lang));
 if(data.startsWith('lang:')){const selected=data.slice(5);if(!['ru','kz','en'].includes(selected))return;u.lang=selected;u.languageChosen=true;await saveUser(id,u);await api.setChatMenuButton({chat_id:id,menu_button:{type:'web_app',text:'Su-Tech',web_app:{url:APP_URL+'?lang='+selected}}});return home(id,selected,u.generation);}
 if(data==='app')return show(tr(lang,'Настройте участок — расчёт придёт сюда.','Алқапты баптаңыз — есеп осы чатқа келеді.','Set up a field; the result will arrive here.'),keyboard([[{text:t(lang,'btn_webapp'),web_app:{url:APP_URL+'?lang='+lang}}],[button(tr(lang,'Расчёт в чате','Чатта есептеу','Plan in chat'),'plan')],back(lang)]));
 if(data==='ai'||data==='ai:new'){
  if(data==='ai:new')await remove(`ai-context:${id}`,id,'ai-context');
  return show(esc(a(lang,data==='ai:new'?'cleared':'intro')),aiKeys(lang));
 }
 if(data==='ai:deep'){u.aiDeep=true;await saveUser(id,u);return show(esc(a(lang,'deep_hint')),aiKeys(lang));}
 if(data==='ai:delete')return show(esc(a(lang,'delete_confirm')),keyboard([[button(a(lang,'delete_yes'),'ai:delete:yes')],[button(a(lang,'delete_no'),'ai:history')]]));
 if(data==='ai:delete:yes'){
  await db.run("DELETE FROM records WHERE owner=:owner AND kind IN ('ai-answer','ai-context','legacy:ai_exchanges','legacy:ai_conversations')",{':owner':id});
  return show(esc(a(lang,'deleted')),aiKeys(lang));
 }
 if(data==='pilot'||data.startsWith('pilot:'))return pilot(id,lang,data.split(':')[1]??'back',u.generation);
 if(data==='ai:history'||data.startsWith('aih:')){
  const page=data==='ai:history'?0:Math.max(0,Number(data.slice(4))||0),items=await aiHistory(id,lang,page);
  return show(items.length?tr(lang,'Сохранённые ответы ИИ','ЖИ сақталған жауаптары','Saved AI answers'):tr(lang,'История пока пуста.','Тарих әзірге бос.','No AI history yet.'),keyboard([...items.map((r,i)=>[button(`${page*5+i+1}. ${r.text.replace(/<[^>]+>/g,'').slice(0,65)}`,`ah:${r.id}`)]),[...(page?[button('‹',`aih:${page-1}`)]:[]),...(items.length===5?[button('›',`aih:${page+1}`)]:[])],[button(a(lang,'new_button'),'ai:new')],[button(a(lang,'history_delete'),'ai:delete')],back(lang)]));
 }
 if(data.startsWith('ah:')){
  const row=await get(data.slice(3),id);if(!row)return home(id,lang,u.generation);
  return show(row.answer,keyboard([[button(tr(lang,'История ИИ','ЖИ тарихы','AI history'),'ai:history')],back(lang)]),true);
 }
 if(data==='plan'){u.mode='plan';u.draft={step:0,values:{}};await saveUser(id,u);return planScreen(id);}
 if(data==='retry'){const row=await get(`pending:${id}`,id);return row?deliverCalculation(id,row.payload):home(id,lang,u.generation);}
 if(data==='fields'||data.startsWith('fields:'))return fieldsScreen(id,lang,Number(data.split(':')[1])||0,u.generation);
 if(data==='history'||data.startsWith('history:'))return historyScreen(id,lang,Number(data.split(':')[1])||0,u.generation);
 if(data.startsWith('rh:')){
  const row=await get(decodeURIComponent(data.slice(3)),id);if(!row)return home(id,lang,u.generation);
  if(row.field_id)return show(report({result:row.result,deficit:row.result.deficit,last_day:row.weather.day,weather:row.weather,payload:row.payload},lang),keyboard([[button(t(lang,'btn_history'),'history')],back(lang)]));
  return show(esc([row.crop_name,row.area_text,row.irrigation_text,row.volume_text,row.savings_text].filter(Boolean).join('\n')),keyboard([[button(t(lang,'btn_history'),'history')],back(lang)]));
 }
 if(data==='more')return show(tr(lang,'Настройки и помощь','Баптаулар мен көмек','Settings and help'),keyboard([[button(t(lang,'btn_lang'),'languages'),button(t(lang,'btn_help'),'help')],[button(t(lang,'btn_about'),'about'),button(p(lang,'join'),'pilot')],back(lang)]));
 if(data==='help'||data==='about')return show(data==='help'?tr(lang,'1. Добавьте участок: культура, площадь, почва и точка на карте.\n2. Откройте «Мои поля» для актуального расчёта.\n3. После полива отметьте объём.\n4. Для вопросов и фото растений откройте ИИ-агронома.','1. Алқап қосыңыз: дақыл, аудан, топырақ және картадағы нүкте.\n2. Жаңа есеп үшін «Менің алқаптарым» бөліміне өтіңіз.\n3. Суарған соң көлемін белгілеңіз.\n4. Өсімдік фотосы мен сұрақтар үшін ЖИ-агрономды ашыңыз.','1. Add a field: crop, area, soil and map location.\n2. Open My fields for a current calculation.\n3. After watering, record the amount.\n4. Open AI agronomist for plant photos and questions.'):tr(lang,'Su-Tech рассчитывает потребность в поливе по погоде Open-Meteo, культуре и почве. Методика: FAO-56. ИИ помогает с уходом и видимыми симптомами растений.','Su-Tech Open-Meteo ауа райы, дақыл және топырақ бойынша суару қажеттілігін есептейді. Әдістеме: FAO-56. ЖИ өсімдік күтімі мен көрінетін белгілерді түсіндіреді.','Su-Tech estimates irrigation needs using Open-Meteo weather, crop and soil. Method: FAO-56. AI helps with plant care and visible symptoms.'),keyboard([back(lang)]));
 const [type,value]=data.split(':');
 if(type==='vote'){await feedback(id,value,data.split(':')[2]==='y');const row=await ownedField(id,value);return show(p(lang,'thanks')+'\n\n'+report(row,lang),fieldButtons(row,lang));}
 if(['field','explain','water','delete','confirmdelete','export'].includes(type)){
  const row=type==='field'?await refresh(id,value):await ownedField(id,value);
  if(type==='delete')return show(tr(lang,'Удалить это поле?','Бұл алқап жойылсын ба?','Delete this field?'),keyboard([[button(tr(lang,'Удалить','Жою','Delete'),`confirmdelete:${value}`),button(t(lang,'btn_cancel'),`field:${value}`)]]));
  if(type==='confirmdelete'){await remove(`field:${value}`,id,'field');return fieldsScreen(id,lang,0,u.generation);}
  if(type==='water'){
   u.mode='water';u.water={id:row.id,expected:row.deficit,revision:row.revision};await saveUser(id,u);
   return show(tr(lang,'Сколько воды подали на самом деле? Введите объём в м³. Например: 0.2\n\nПодтверждайте только выполненный полив.','Нақты қанша су берілді? Көлемді м³-пен жазыңыз. Мысалы: 0.2\n\nТек орындалған суаруды растаңыз.','How much water did you actually apply? Enter m³, for example: 0.2.\n\nRecord only completed irrigation.'),keyboard([[button(t(lang,'btn_cancel'),`field:${value}`)]]));
  }
  if(type==='export'){
   const csv='date,applied_m3,deficit_before_mm,deficit_after_mm\r\n'+(row.events??[]).map(e=>[new Date(e.time).toISOString(),e.applied_m3,e.before,e.after].join(',')).join('\r\n');
   const bytes=new Uint8Array([...csv].map(c=>c.charCodeAt(0)));const doc=await api.sendDocument({chat_id:id,document:new InputFile(bytes,'Su-Tech-irrigation.csv',{type:'text/csv'})});
   u.attachments=[...(u.attachments??[]),doc.message_id];await saveUser(id,u);
  }
  return show(report(row,lang,type==='explain'),fieldButtons(row,lang));
 }
 return home(id,lang,u.generation);
}
export async function callback(q,ctx) {
 if(q.message?.chat?.type!=='private'||q.message.chat.id!==q.from?.id)return;
 const id=ownerId(q.from.id);
 // Expired callback spinners must not prevent the actual button action.
 try{await api.answerCallbackQuery({callback_query_id:q.id});}catch{}
 await rememberMessage(id,q.message.message_id,q.message.date);
 const u=await user(id,q.from.language_code),data=String(q.data??'');
 if(data.startsWith('p:')){
  if(u.mode!=='plan'||!u.draft)return action(id,'home');
  const [,generation,step,...raw]=data.split(':');
  if(u.generation!==Number(generation)||u.draft.step!==Number(step))return planScreen(id);
  const payload=await planInput(id,raw.join(':'),{generation:Number(generation),step:Number(step)});
  if(payload)await deliverCalculation(id,payload);return;
 }
 for(const mid of u.attachments??[])await ignoreDelete(id,mid);
 if(u.attachments?.length){u.attachments=[];await saveUser(id,u);}
 try{await action(id,data);}
 catch(e){
  if(e.message==='stale'){
   const fresh=await user(id);
   if(fresh.mode==='plan'&&fresh.draft)return planScreen(id);
   return fresh.mode==='ai'?screen(id,esc(a(fresh.lang,'intro')),aiKeys(fresh.lang),fresh.generation):home(id,fresh.lang,fresh.generation);
  }
  if(!['not_found','season_ended','weather','busy'].includes(e.message))throw e;
  await screen(id,tr(u.lang,'Не удалось открыть актуальный расчёт. Вернитесь к списку полей или повторите позже.','Жаңа есеп ашылмады. Алқаптар тізіміне оралыңыз немесе кейін қайталаңыз.','Could not open a current calculation. Return to your fields or try again later.'),keyboard([[button(t(u.lang,'btn_fields'),'fields')],back(u.lang)]));}
}
function matchingButton(text){
 for(const lang of ['ru','kz','en']){
  for(const [key,action] of Object.entries({btn_webapp:'app',btn_fields:'fields',btn_history:'history',btn_more:'more',btn_lang:'languages',btn_help:'help',btn_about:'about',btn_back:'home'}))if(text===STRINGS[lang]?.[key])return action;
  if(text===AI_STRINGS[lang]?.button)return 'ai';
 }
 return null;
}
export async function message(m,ctx) {
 if(m.chat?.type!=='private'||m.chat.id!==m.from?.id)return;
 const id=ownerId(m.from.id),text=(m.text??m.caption??'').trim();let u=await user(id,m.from.language_code);
 if(!u.keyboardReset){
  const notice=await api.sendMessage({chat_id:id,text:'Su-Tech',reply_markup:{remove_keyboard:true}});
  await ignoreDelete(id,notice.message_id);u.keyboardReset=true;await saveUser(id,u);
 }
 if(!await ignoreDelete(id,m.message_id))await rememberMessage(id,m.message_id,m.date);
 if(text.startsWith('/start')){
  const entry=text.split(/\s+/)[1]??'',match=entry.match(/^(app|ai|pilot)_(ru|kz|en)$/);
  if(match){u.lang=match[2];await saveUser(id,u);return action(id,match[1]);}
  if(u.languageChosen||u.screen)return action(id,'home');
  const initial=await navigate(id);return screen(id,'Su-Tech\nРусский / Қазақша / English',languages(u.lang),initial.generation);
 }
 const command=text.split(/\s|@/)[0].toLowerCase();
 const route=matchingButton(text)??({'/menu':'home','/exit':'home','/cancel':'home','/app':'app','/help':'help','/about':'about','/language':'languages','/ai':'ai','/newchat':'ai:new','/pilot':'pilot','/plan':'plan','/fields':'fields','/history':'history'}[command]);
 if(route)return action(id,route);
 if(m.web_app_data){let payload;try{payload=JSON.parse(m.web_app_data.data);}catch{return action(id,'app');}return deliverCalculation(id,payload);}
 if(u.mode==='plan'){
  const input=m.location?`${m.location.latitude} ${m.location.longitude}`:text;
  const payload=await planInput(id,input);if(payload)return deliverCalculation(id,payload);return;
 }
 if(u.mode==='water'){
  try{const f=await waterField(id,u.water.id,text,u.water.expected,u.water.revision);await navigate(id);return screen(id,report(f,u.lang),fieldButtons(f,u.lang));}
  catch(e){return screen(id,e.message==='balance_changed'?tr(u.lang,'Баланс изменился. Откройте поле снова.','Баланс өзгерді. Алқапты қайта ашыңыз.','The balance changed. Reopen the field.'):tr(u.lang,'Введите фактический объём в м³, например 0.2.','Нақты көлемді м³-пен жазыңыз, мысалы 0.2.','Enter the actual volume in m³, such as 0.2.'),keyboard([back(u.lang)]));}
 }
 if(u.mode!=='ai'){
  u=await navigate(id,'ai');
 }
 let photo=m.photo?.slice(-1)[0],image=null;
 if(!photo&&m.document&&['image/jpeg','image/png'].includes(m.document.mime_type))photo=m.document;
 try{
  if(photo){if(photo.file_size>4194304)throw new Error('large_image');image=await api.getFileContent(photo.file_id);}
  else if(!text)throw new Error('unsupported');
  const deep=!!u.aiDeep;if(deep){u.aiDeep=false;await saveUser(id,u);}
  await generate(id,text||(a(u.lang,'photo_prompt')),u.lang,image,deep);
 }catch(e){
  const known=['large_image','bad_image','long_text','busy','cooldown','daily_limit','quota','configuration','not_configured','no_answer','unsupported'];
  const answer=e.message==='off_topic'?tr(u.lang,'Помогаю с растениями, поливом и Su-Tech. Задайте вопрос по этим темам.','Өсімдіктер, суару және Su-Tech бойынша көмектесемін. Осы тақырыптарда сұрақ қойыңыз.','I help with plants, irrigation and Su-Tech. Please ask about these topics.'):a(u.lang,known.includes(e.message)?e.message:'unavailable');
  await screen(id,esc(answer),aiKeys(u.lang),u.generation);
 }
}
