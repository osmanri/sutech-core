import {api,db,InputFile} from 'sdk';
import {user,saveUser,get,put,list,remove,ownerId,eraseUserData} from './store.js';
import {tr,t,a,esc,volume,fmt,language} from './i18n.js';
import {STRINGS,AI_STRINGS} from './copy.js';
import {screen,navigate,home,homeKeys,languages,aiKeys,button,keyboard,back,ignoreDelete,APP_URL} from './ui.js';
import {generate,aiHistory} from './ai.js';
import {calculateField,ownedField,refresh,report,currentResult,waterField,card,checkMoisture,setExpert,SOIL_LEVELS} from './fields.js';
import {parseField,LIMITS} from './expert.js';
import {fieldCsv,needsCheck} from './explain.js';
import {planScreen,planInput} from './planner.js';
import {pilot,feedback,p} from './pilot.js';
import {rememberMessage} from './screens.js';
import {aiIntro} from './conversation.js';
import {demoScreen,demoSteps} from './demo.js';
import {CROP_IDS} from './diagnosis.js';
const fieldButtons=(row,lang)=>keyboard([
 [button(t(lang,'btn_explain'),`explain:${row.id}`)],
 [button(p(lang,'useful'),`vote:${row.id}:y`),button(p(lang,'unhelpful'),`vote:${row.id}:n`)],
 ...(currentResult(row).gross_m3>0?[[button(tr(lang,'Отметить полив','Суаруды белгілеу','Record watering'),`water:${row.id}`)]]:[]),
 ...(parseField(row.payload).crop!=='rice'?[[button(tr(lang,'Проверил влажность почвы','Топырақ ылғалын тексердім','I checked the soil moisture'),`soil:${row.id}`)]]:[]),
 [button(t(lang,'btn_field_update'),`field:${row.id}`),button(t(lang,'btn_export_field'),`export:${row.id}`)],
 [button(tr(lang,'🧑‍🌾 Режим эксперта','🧑‍🌾 Сарапшы режимі','🧑‍🌾 Expert mode'),`expert:${row.id}`)],
 [button(tr(lang,'Удалить поле','Алқапты жою','Delete field'),`delete:${row.id}`)],
 [button(t(lang,'btn_fields'),'fields')],back(lang)]);
const NAME={p:['p (доля доступной воды до стресса)','p (күйзеліске дейінгі қолжетімді су үлесі)','p (share of available water before stress)'],root_depth:['Глубина корней, м','Тамыр тереңдігі, м','Root depth, m'],kc_factor:['Множитель Kc','Kc көбейткіші','Kc multiplier']};
export async function expertScreen(id,lang,row,show,notice='') {
 const f=parseField(row.payload);
 if(!f.fao)return show(tr(lang,'Для этой культуры режим эксперта недоступен (рис или своя культура: значения вводятся при создании поля).','Бұл дақыл үшін сарапшы режимі қолжетімсіз (күріш немесе өз дақылыңыз: мәндер алқап құрғанда енгізіледі).','Expert mode is not available for this crop (rice or a custom crop: the values are entered when the field is created).'),keyboard([[button(t(lang,'btn_cancel'),`field:${row.id}`)]]));
 const fmtv=n=>String(Math.round(n*100)/100);
 const rows=['p','root_depth','kc_factor'].map(k=>{const v=k==='p'?f.p:k==='root_depth'?f.zr:(f.expert.kc_factor??1),d=k==='p'?f.fao.p:k==='root_depth'?f.fao.zr:1;
  return `• ${tr(lang,...NAME[k])}: ${fmtv(v)}${f.manual.includes(k)?` ✏️ (FAO ${fmtv(d)})`:''}`;});
 const text=(notice?notice+'\n\n':'')+tr(lang,'<b>Режим эксперта</b>\nЗначения для этого поля. Изменённое помечается «вручную» и считается от сегодняшнего дня; прошлые дни не пересчитываются.\n','<b>Сарапшы режимі</b>\nОсы алқап үшін мәндер. Өзгертілгені «қолмен» деп белгіленеді және бүгіннен бастап есептеледі; өткен күндер қайта есептелмейді.\n','<b>Expert mode</b>\nValues for this field. Anything changed is marked “manual” and applies from today; past days are not recalculated.\n')+'\n'+rows.join('\n');
 return show(text,keyboard([
  ...['p','root_depth','kc_factor'].map(k=>[button(tr(lang,...NAME[k]),`exset:${row.id}:${k}`)]),
  ...(f.manual.length?[[button(tr(lang,'↩️ Вернуть значения FAO','↩️ FAO мәндерін қайтару','↩️ Back to FAO values'),`exreset:${row.id}`)]]:[]),
  [button(t(lang,'btn_cancel'),`field:${row.id}`)]]));
}
export async function deliverCalculation(id,payload) {
 const u=await user(id);const generation=u.generation;
 await put(`pending:${id}`,id,'pending',{payload});
 await screen(id,tr(u.lang,'Считаю по погоде поля…','Алқап ауа райы бойынша есептеп жатырмын…','Calculating with field weather…'),keyboard([back(u.lang)]),generation);
 try {
  const row=await calculateField(id,payload);
  const notice={reset:tr(u.lang,'Параметры поля изменились — расчёт начат заново по новым данным.','Алқап параметрлері өзгерді — есеп жаңа деректермен басынан басталды.','The field parameters changed, so the balance was restarted from the new data.'),
   costs:tr(u.lang,'Данные насоса обновлены, запас влаги сохранён.','Сорғы деректері жаңартылды, ылғал қоры сақталды.','Pump data updated; the soil-water balance was kept.'),
   existing:tr(u.lang,'Это поле уже сохранено, расчёт продолжается. Чтобы поправить влажность, нажмите «Проверил влажность почвы».','Бұл алқап сақталған, есеп жалғасады. Ылғалды түзету үшін «Топырақ ылғалын тексердім» батырмасын басыңыз.','This field is already saved and the balance continues. To correct the moisture, use "I checked the soil moisture".')}[row.submit];
  await screen(id,(notice?esc(notice)+'\n\n':'')+report(row,u.lang),fieldButtons(row,u.lang),generation);
  return {ok:true,bot_replied:true,field_id:row.id};
 } catch(e) {
  const recoverable=e.message==='weather'||e.message==='busy';
  await screen(id,recoverable?tr(u.lang,'Сейчас не удалось получить погоду. Ввод сохранён — можно повторить.','Ауа райын алу мүмкін болмады. Енгізілген деректер сақталды — қайталауға болады.','Weather is unavailable. Your inputs are saved; you can retry.'):tr(u.lang,'Проверьте параметры участка: культуру, возраст, площадь и координаты.','Алқап параметрлерін тексеріңіз: дақыл, жас, аудан және координаттар.','Check the crop, age, area and coordinates.'),keyboard([[button(tr(u.lang,'Повторить','Қайталау','Retry'),'retry')],back(u.lang)]),generation);
  return {ok:false,bot_replied:true,recoverable};
 }
}
async function fieldsScreen(id,lang,page=0,generation=null) {
 const fields=await list(id,'field',8,page*8);
 const rows=fields.map(f=>[button(`${needsCheck(f)?'🔔 ':''}${t(lang,'report_crop_'+f.payload.crop)} · ${fmt(parseField(f.payload).area_ha,6)} ha`,`field:${f.id}`)]);
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
 const u=await navigate(id,['ai','ai:new','ai:deep','ai:crop','ai:photo-data'].includes(data)||data.startsWith('ai:crop:')?'ai':'home'),lang=u.lang;
 const show=(text,markup,plain=false)=>screen(id,text,markup,u.generation,plain);
 if(data==='home')return home(id,lang,u.generation);
 if(data==='languages')return show('Русский / Қазақша / English',languages(lang));
 if(data.startsWith('lang:')){const selected=data.slice(5);if(!['ru','kz','en'].includes(selected))return;u.lang=selected;u.languageChosen=true;await saveUser(id,u);await api.setChatMenuButton({chat_id:id,menu_button:{type:'web_app',text:'Su-Tech',web_app:{url:APP_URL+'?lang='+selected}}});return home(id,selected,u.generation);}
 if(data==='app')return show(tr(lang,'Настройте участок — расчёт придёт сюда.','Алқапты баптаңыз — есеп осы чатқа келеді.','Set up a field; the result will arrive here.'),keyboard([[{text:t(lang,'btn_webapp'),web_app:{url:APP_URL+'?lang='+lang}}],[button(tr(lang,'Расчёт в чате','Чатта есептеу','Plan in chat'),'plan')],back(lang)]));
 if(data==='ai'||data==='ai:new'){
  if(data==='ai:new')await remove(`ai-context:${id}`,id,'ai-context');
  return show(esc(data==='ai:new'?a(lang,'cleared'):aiIntro(lang)),aiKeys(lang));
 }
 if(data==='ai:deep'){u.aiDeep=true;await saveUser(id,u);return show(esc(a(lang,'deep_hint')),aiKeys(lang));}
 if(data==='ai:crop')return show(tr(lang,'Подтвердите культуру на следующих фото. При смене растения выберите её заново.','Келесі фотолардағы дақылды растаңыз. Өсімдік ауысса, қайта таңдаңыз.','Confirm the crop in your next photos. Select again when the plant changes.'),keyboard([
  [button(tr(lang,'Томат','Қызанақ','Tomato'),'ai:crop:tomato'),button(tr(lang,'Картофель','Картоп','Potato'),'ai:crop:potato')],
  [button(tr(lang,'Кукуруза','Жүгері','Maize'),'ai:crop:maize'),button(tr(lang,'Другая / не знаю','Басқа / білмеймін','Other / unsure'),'ai:crop:unknown')],[button(tr(lang,'Назад','Артқа','Back'),'ai')]]));
 if(data.startsWith('ai:crop:')){
  const crop=data.slice(8);if(![...CROP_IDS,'unknown'].includes(crop))return;
  u.photoCrop=crop;await saveUser(id,u);
  return show(tr(lang,'Выбор сохранён. Пришлите чёткое фото одного листа и опишите симптомы.','Таңдау сақталды. Бір жапырақтың анық фотосын жіберіп, белгілерді сипаттаңыз.','Choice saved. Send a clear photo of one leaf and describe the symptoms.'),aiKeys(lang));
 }
 if(data==='ai:photo-data')return show(tr(lang,
  'Сбор фото для обучения выключен. Фото из чата не сохраняются в обучающий набор. После настройки приватного хранилища потребуется отдельное добровольное согласие с возможностью отзыва и удаления.',
  'Оқыту үшін фото жинау өшірулі. Чат фотолары оқыту жиынына сақталмайды. Жеке сақтау орны дайын болған соң, қайтарып алу және жою мүмкіндігі бар бөлек ерікті келісім қажет болады.',
  'Training photo collection is disabled. Chat photos are not saved to a training set. Once private storage is configured, separate voluntary consent with withdrawal and deletion will be required.'),aiKeys(lang));
 if(data==='ai:delete')return show(esc(a(lang,'delete_confirm')),keyboard([[button(a(lang,'delete_yes'),'ai:delete:yes')],[button(a(lang,'delete_no'),'ai:history')]]));
 if(data==='ai:delete:yes'){
  await db.run("DELETE FROM records WHERE owner=:owner AND kind IN ('ai-answer','ai-context','photo-comparison','legacy:ai_exchanges','legacy:ai_conversations')",{':owner':id});
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
 if(data==='demo'||data==='demo:steps'){const d=data==='demo'?demoScreen(lang):demoSteps(lang);return show(d.text,d.markup);}
 if(data==='more')return show(tr(lang,'Настройки и помощь','Баптаулар мен көмек','Settings and help'),keyboard([[button(t(lang,'btn_lang'),'languages'),button(t(lang,'btn_help'),'help')],[button(t(lang,'btn_about'),'about'),button(p(lang,'join'),'pilot')],[button(tr(lang,'Демо для жюри','Қазылар үшін демо','Jury demo'),'demo'),button(tr(lang,'🔒 Мои данные','🔒 Деректерім','🔒 My data'),'privacy')],back(lang)]));
 if(data==='privacy')return show(tr(lang,'<b>Какие данные хранит Su-Tech</b>\n• Ваш номер в Telegram и язык.\n• Поля: культура, площадь, почва, способ полива, точка на карте, отметки о поливе и проверке влажности.\n• Расчёты и погода за эти дни.\n• Запросы к ИИ-агроному на время обработки; в историю чата попадают ваши вопросы и ответы.\n\nКоординаты уходят в Open-Meteo за погодой, вопросы и фото ИИ-агроному в Google Gemini. Данные не продаются и не передаются рекламным сервисам.\n\nКнопка ниже удаляет всё, что хранится о вас, без возможности вернуть. Полная политика: сайт, страница «Конфиденциальность».','<b>Su-Tech қандай деректерді сақтайды</b>\n• Telegram нөміріңіз және тіл.\n• Алқаптар: дақыл, аудан, топырақ, суару тәсілі, картадағы нүкте, суару мен ылғал тексеру белгілері.\n• Осы күндердегі есептер мен ауа райы.\n• ЖИ-агрономға сұраулар өңдеу уақытында; чат тарихына сұрақтарыңыз бен жауаптар түседі.\n\nКоординаттар ауа райы үшін Open-Meteo-ға, сұрақтар мен фото ЖИ-агрономға Google Gemini-ге жіберіледі. Деректер сатылмайды және жарнама қызметтеріне берілмейді.\n\nТөмендегі түйме сіз туралы сақталғанның бәрін қайтарусыз өшіреді. Толық саясат: сайт, «Құпиялылық» беті.','<b>What Su-Tech stores</b>\n• Your Telegram id and language.\n• Fields: crop, area, soil, irrigation method, map point, watering and soil-check marks.\n• Calculations and weather for those days.\n• AI agronomist requests while they are processed; your questions and answers enter the chat history.\n\nCoordinates go to Open-Meteo for weather, questions and photos to Google Gemini for the AI agronomist. Data is not sold and not shared with advertisers.\n\nThe button below deletes everything stored about you and cannot be undone. Full policy: the website, page “Privacy”.'),keyboard([[button(tr(lang,'🗑 Удалить мои данные','🗑 Деректерімді жою','🗑 Delete my data'),'wipe','danger')],back(lang)]));
 if(data==='wipe')return show(tr(lang,'Удалить все ваши данные: поля, расчёты, историю и настройки? Это нельзя отменить.','Барлық деректеріңізді жою керек пе: алқаптар, есептер, тарих және баптаулар? Мұны қайтару мүмкін емес.','Delete all your data: fields, calculations, history and settings? This cannot be undone.'),keyboard([[button(tr(lang,'Да, удалить всё','Иә, бәрін жою','Yes, delete everything'),'wipe:yes','danger')],[button(t(lang,'btn_cancel'),'privacy')]]));
 if(data==='wipe:yes'){const n=await eraseUserData(id);const next=await user(id,lang);return screen(id,tr(lang,`Готово: удалено записей — ${n}. Бот снова пуст, как при первом запуске.`,`Дайын: жазбалар жойылды — ${n}. Бот алғашқы іске қосудағыдай бос.`,`Done: ${n} records deleted. The bot is empty again, as on first start.`),keyboard([back(next.lang)]),null);}
 if(data==='help'||data==='about')return show(data==='help'?tr(lang,'1. Добавьте участок: культура, площадь, почва и точка на карте.\n2. Откройте «Мои поля» для актуального расчёта.\n3. После полива отметьте объём.\n4. Для вопросов и фото растений откройте ИИ-агронома.','1. Алқап қосыңыз: дақыл, аудан, топырақ және картадағы нүкте.\n2. Жаңа есеп үшін «Менің алқаптарым» бөліміне өтіңіз.\n3. Суарған соң көлемін белгілеңіз.\n4. Өсімдік фотосы мен сұрақтар үшін ЖИ-агрономды ашыңыз.','1. Add a field: crop, area, soil and map location.\n2. Open My fields for a current calculation.\n3. After watering, record the amount.\n4. Open AI agronomist for plant photos and questions.'):tr(lang,'Su-Tech рассчитывает потребность в поливе по погоде Open-Meteo, культуре и почве. Методика: FAO-56. ИИ помогает с уходом и видимыми симптомами растений.','Su-Tech Open-Meteo ауа райы, дақыл және топырақ бойынша суару қажеттілігін есептейді. Әдістеме: FAO-56. ЖИ өсімдік күтімі мен көрінетін белгілерді түсіндіреді.','Su-Tech estimates irrigation needs using Open-Meteo weather, crop and soil. Method: FAO-56. AI helps with plant care and visible symptoms.'),keyboard([back(lang)]));
 if(data.startsWith('soil:')||data.startsWith('soilset:')){
  const [kind,fid,level]=data.split(':');
  if(kind==='soil'){
   const row=await ownedField(id,fid);
   const cm=Math.max(10,Math.round(parseField(row.payload).zr*100/2/5)*5);  // middle of the root zone, rounded to 5 cm
   return show(tr(lang,`Какая сейчас влажность почвы? Возьмите горсть земли с глубины около ${cm} см (середина корнеобитаемого слоя) и сожмите в кулаке.\n\n💧 Влажная: комок держит форму, на ладони влажный след, при сильном сжатии выступает вода.\n🌱 Нормальная: комок держит форму, влажного следа нет, земля прохладная.\n🏜 Сухая: рассыпается, пылит, форму не держит.\n\nЭто ориентир, а не лабораторное измерение. Ответ исправляет расчёт и снижает накопленную ошибку прогноза.`,`Топырақ ылғалы қандай? Шамамен ${cm} см тереңдіктен (тамыр қабатының ортасы) бір уыс топырақ алып, жұдырықпен қысыңыз.\n\n💧 Ылғалды: кесек пішінін сақтайды, алақанда ылғал ізі қалады, қатты қысқанда су шығады.\n🌱 Қалыпты: кесек пішінін сақтайды, ылғал ізі жоқ, топырақ салқын.\n🏜 Құрғақ: ұсақталады, шаң болады, пішінін сақтамайды.\n\nБұл ориентир, зертханалық өлшем емес. Жауап есепті түзетеді және болжамның жиналған қатесін азайтады.`,`How moist is the soil? Take a handful from about ${cm} cm deep (the middle of the root zone) and squeeze it in your fist.\n\n💧 Wet: the ball keeps its shape, leaves a damp mark on the palm, water shows under a hard squeeze.\n🌱 Normal: the ball keeps its shape, no damp mark, the soil feels cool.\n🏜 Dry: it crumbles, makes dust, does not hold a shape.\n\nThis is a guide, not a laboratory measurement. Your answer corrects the calculation and removes accumulated forecast error.`),keyboard([
    [button(tr(lang,'💧 Влажная','💧 Ылғалды','💧 Wet'),`soilset:${fid}:wet`)],
    [button(tr(lang,'🌱 Нормальная','🌱 Қалыпты','🌱 Normal'),`soilset:${fid}:normal`)],
    [button(tr(lang,'🏜 Сухая','🏜 Құрғақ','🏜 Dry'),`soilset:${fid}:dry`)],
    [button(t(lang,'btn_cancel'),`field:${row.id}`)]]));
  }
  if(!Object.hasOwn(SOIL_LEVELS,level))return home(id,lang,u.generation);
  const row=await checkMoisture(id,fid,level);
  return show(tr(lang,'✅ Баланс скорректирован по вашей проверке.','✅ Баланс сіздің тексеруіңіз бойынша түзетілді.','✅ Balance corrected from your check.')+'\n\n'+report(row,lang),fieldButtons(row,lang));
 }
 const [exk,exid,exkey]=data.split(':');
 if(exk==='expert'){const row=await ownedField(id,exid);return expertScreen(id,lang,row,show);}
 if(exk==='exset'){
  const [lo,hi]=LIMITS[exkey]??[];if(lo===undefined)return home(id,lang,u.generation);
  u.mode='expert';u.expert={id:exid,key:exkey};await saveUser(id,u);
  return show(tr(lang,`Введите значение: ${NAME[exkey][0]}. От ${lo} до ${hi}. Например: ${exkey==='kc_factor'?'1.1':exkey==='p'?'0.5':'0.8'}`,`Мәнді енгізіңіз: ${NAME[exkey][1]}. ${lo}-ден ${hi}-ге дейін. Мысалы: ${exkey==='kc_factor'?'1.1':exkey==='p'?'0.5':'0.8'}`,`Enter a value: ${NAME[exkey][2]}. From ${lo} to ${hi}. For example: ${exkey==='kc_factor'?'1.1':exkey==='p'?'0.5':'0.8'}`),keyboard([[button(t(lang,'btn_cancel'),`expert:${exid}`)]]));
 }
 if(exk==='exreset'){
  let row=await ownedField(id,exid);for(const k of Object.keys(row.payload.expert??{}))row=await setExpert(id,exid,k,null);
  return expertScreen(id,lang,row,show,tr(lang,'✅ Возвращены значения FAO-56.','✅ FAO-56 мәндері қайтарылды.','✅ FAO-56 values restored.'));
 }
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
   const csv=fieldCsv(row);
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
   return fresh.mode==='ai'?screen(id,esc(aiIntro(fresh.lang)),aiKeys(fresh.lang),fresh.generation):home(id,fresh.lang,fresh.generation);
  }
  if(!['not_found','season_ended','weather','busy','not_applicable','bad_level'].includes(e.message))throw e;
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
  const entry=text.split(/\s+/)[1]??'',match=entry.match(/^(app|ai|pilot|demo)_(ru|kz|en)$/);
  if(match){u.lang=match[2];await saveUser(id,u);return action(id,match[1]);}
  if(u.languageChosen||u.screen)return action(id,'home');
  const initial=await navigate(id);return screen(id,'Su-Tech\nРусский / Қазақша / English',languages(u.lang),initial.generation);
 }
 const command=text.split(/\s|@/)[0].toLowerCase();
 const route=matchingButton(text)??({'/menu':'home','/exit':'home','/cancel':'home','/app':'app','/help':'help','/about':'about','/language':'languages','/ai':'ai','/newchat':'ai:new','/pilot':'pilot','/demo':'demo','/plan':'plan','/fields':'fields','/history':'history'}[command]);
 if(route)return action(id,route);
 if(m.web_app_data){let payload;try{payload=JSON.parse(m.web_app_data.data);}catch{return action(id,'app');}return deliverCalculation(id,payload);}
 if(u.mode==='plan'){
  const input=m.location?`${m.location.latitude} ${m.location.longitude}`:text;
  const payload=await planInput(id,input);if(payload)return deliverCalculation(id,payload);return;
 }
 if(u.mode==='expert'&&u.expert){
  try{
   const row=await setExpert(id,u.expert.id,u.expert.key,String(text).replace(',','.'));u.mode='home';u.expert=null;await saveUser(id,u);await navigate(id);
   return expertScreen(id,u.lang,row,(tx,kb)=>screen(id,tx,kb),tr(u.lang,'✅ Сохранено, отмечено «вручную».','✅ Сақталды, «қолмен» деп белгіленді.','✅ Saved, marked “manual”.'));
  }catch(e){const [lo,hi]=LIMITS[u.expert.key];return screen(id,e.message==='busy'?tr(u.lang,'Поле занято, повторите.','Алқап бос емес, қайталаңыз.','The field is busy, try again.'):tr(u.lang,`Введите число от ${lo} до ${hi}.`,`${lo}-ден ${hi}-ге дейінгі санды енгізіңіз.`,`Enter a number from ${lo} to ${hi}.`),keyboard([[button(t(u.lang,'btn_cancel'),`expert:${u.expert.id}`)]]),u.generation);}
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
  const deep=!!u.aiDeep;
  await generate(id,text||(a(u.lang,'photo_prompt')),u.lang,image,deep);
 }catch(e){
  const known=['large_image','bad_image','long_text','busy','cooldown','daily_limit','quota','configuration','not_configured','no_answer','unsupported'];
  const answer=e.message==='off_topic'?tr(u.lang,'С этим не помогу, зато могу подсказать по растениям, поливу и Su-Tech 🌱 Что хочешь узнать?','Бұл сұраққа көмектесе алмаймын, бірақ өсімдік, суару және Su-Tech туралы айта аламын 🌱 Не білгің келеді?','That’s outside my area, but I can help with plants, watering and Su-Tech 🌱 What would you like to know?'):a(u.lang,known.includes(e.message)?e.message:'unavailable');
  await screen(id,esc(answer),aiKeys(u.lang),u.generation);
 }
}
