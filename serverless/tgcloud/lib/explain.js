// "Why this?": input completeness, what was assumed, where each number comes from, and what would change if
// the assumptions were wrong. Pure functions of the stored field: no new calculation, no invented numbers.
import {CROP_STATUS} from './crops-data.js';
import {METHODS,SALT_TOLERANCE} from './balance.js';
import {parseField,describe} from './expert.js';
import {tr,t,fmt,esc,volume} from './i18n.js';

const DAY=86400000;
const latestCheck=row=>(row.checks??[]).filter(c=>!(row.reset_at&&c.time<row.reset_at)).at(-1);
export function confidence(row,field,r,now=Date.now()) {
  const reasons=[],last=latestCheck(row),ageDays=last?(now-last.time)/DAY:null;
  if(r.status==='unsupported'||r.leaching_impossible)return {level:'low',reasons:['unsupported'],raise:'agronomist'};
  if(field.crop!=='rice'&&field.crop!=='other'&&CROP_STATUS[field.crop]!=='FAO-56')reasons.push('crop_stages');
  if(field.crop==='other')reasons.push('crop_custom');
  if(row.payload.growth_estimated===true)reasons.push('estimated_growth');
  if(ageDays===null)reasons.push('no_check');else if(ageDays>7)reasons.push('old_check');
  if(field.saline&&field.water_ec==null&&field.soil_ec==null)reasons.push('saline_unmeasured');
  if(field.field_type==='greenhouse'&&field.greenhouse_et0==null)reasons.push('greenhouse_estimate');
  if((row.gap_days??0)>0)reasons.push('gap');
  if(field.saline&&!(field.crop in SALT_TOLERANCE))reasons.push('no_salt_data');
  const level=((row.gap_days??0)>3||(reasons.includes('crop_custom')&&reasons.includes('no_check')))?'low':reasons.length?'medium':'high';
  const raise=reasons.includes('no_check')||reasons.includes('old_check')?'check':reasons.includes('saline_unmeasured')?'salinity':reasons.includes('gap')?'gap':reasons.length?'assumptions':null;
  return {level,reasons,raise};
}
const LEVEL={high:['🟢','Данные указаны, проверка влажности свежая','Деректер енгізілген, ылғал жақында тексерілген','Inputs provided; soil moisture checked recently'],medium:['🟡','Данные: есть допущения или пропуски','Деректер: болжамдар немесе олқылықтар бар','Inputs: assumptions or gaps remain'],low:['🔴','Нужен агроном или проверка данных','Агроном немесе деректерді тексеру қажет','An agronomist or an input check is needed']};
const RAISE={check:['Подтвердите влажность почвы кнопкой «Проверил влажность почвы».','«Топырақ ылғалын тексердім» батырмасымен ылғалды растаңыз.','Confirm soil moisture with the “I checked the soil moisture” button.'],
  salinity:['Если почва солёная, укажите анализ воды и почвы (ECw, ECe).','Топырақ сортаң болса, су мен топырақ талдауын (ECw, ECe) көрсетіңіз.','If the soil is saline, enter a water and soil analysis (ECw, ECe).'],
  gap:['Проверьте влажность почвы: были дни без данных погоды.','Топырақ ылғалын тексеріңіз: ауа райы деректері жоқ күндер болды.','Check the soil moisture: some days had no weather data.'],
  assumptions:['Уточните допущения ниже.','Төмендегі болжамдарды нақтылаңыз.','Refine the assumptions below.'],
  agronomist:['Для этого случая метод расчёта не подходит: обратитесь к агроному.','Бұл жағдайға есеп әдісі жарамайды: агрономға жүгініңіз.','The calculation method does not fit this case: ask an agronomist.']};
export function confidenceLine(c,lang) {
  const [icon,...text]=LEVEL[c.level],i={ru:0,kz:1,en:2}[lang]??0;
  return `${icon} ${text[i]}`+(c.raise?`\n${tr(lang,...RAISE[c.raise])}`:'');
}
export function assumptions(row,field,r,lang) {
  const lines=[],m=METHODS[field.method];
  if(field.manual?.length)lines.push(tr(lang,'✏️ Изменено вручную: ','✏️ Қолмен өзгертілген: ','✏️ Changed manually: ')+describe(field,lang,tr,fmt).join('; ')+tr(lang,'. Это не значения таблицы FAO-56.','. Бұл FAO-56 кестесінің мәндері емес.','. These are not FAO-56 table values.'));
  const stages=field.stages?.length?field.stages.reduce((a,b)=>a+b,0):null;
  if(stages&&row.payload.stage_days==null)lines.push(tr(lang,`Календарь стадий взят из каталога (${stages} дн.); уточните даты посадки.`,`Кезеңдер күнтізбесі каталогтан алынды (${stages} күн); егу күнін нақтылаңыз.`,`The stage calendar comes from the catalog (${stages} days); refine the planting date.`));
  lines.push(tr(lang,`Почва: ${esc(t(lang,'balance_soil_'+field.soil))}, доступная вода ${fmt(r.taw??0)} мм в слое корней.`,`Топырақ: ${esc(t(lang,'balance_soil_'+field.soil))}, тамыр қабатындағы қолжетімді су ${fmt(r.taw??0)} мм.`,`Soil: ${esc(t(lang,'balance_soil_'+field.soil))}, available water ${fmt(r.taw??0)} mm in the root layer.`));
  if(!field.saline||(field.water_ec==null&&field.soil_ec==null))lines.push(tr(lang,'Засоление не учитывается (анализов нет).','Тұздану ескерілмейді (талдау жоқ).','Salinity is not included (no analysis).'));
  lines.push(tr(lang,`КПД полива ${fmt(m[1]*100)}% и порог технологии ${fmt(m[0])} мм: выбор проекта.`,`Суару ПӘК-і ${fmt(m[1]*100)}% және технология шегі ${fmt(m[0])} мм: жоба таңдауы.`,`Irrigation efficiency ${fmt(m[1]*100)}% and technology threshold ${fmt(m[0])} mm are project choices.`));
  lines.push(tr(lang,'Дождь меньше 5 мм не учитывается, иначе 75%: правило проекта.','5 мм-ден аз жауын ескерілмейді, әйтпесе 75%: жоба ережесі.','Rain under 5 mm is ignored, otherwise 75%: a project rule.'));
  if(field.field_type==='greenhouse'&&field.greenhouse_et0==null)lines.push(tr(lang,'Теплица: ET₀ = 0,70 от уличного (допущение, в теплицах не проверено).','Жылыжай: ET₀ = сыртқының 0,70 бөлігі (болжам, жылыжайда тексерілмеген).','Greenhouse: ET₀ = 0.70 of the outdoor value (an assumption, not checked in greenhouses).'));
  if(!latestCheck(row))lines.push(tr(lang,'Начальная влажность взята по вашему ответу; проверок руками ещё не было.','Бастапқы ылғал сіздің жауабыңыз бойынша алынды; қолмен тексеру әлі болған жоқ.','The starting moisture is your answer; there has been no hand check yet.'));
  return lines;
}
export function sources(field,lang) {
  const st=CROP_STATUS[field.crop];
  const crop=field.crop==='rice'||field.crop==='other'?tr(lang,'Культура: значения вводит пользователь или упрощённый расчёт риса.','Дақыл: мәндерді пайдаланушы енгізеді немесе күрішке жеңілдетілген есеп.','Crop: values entered by the user, or the simplified rice routine.')
    :st==='FAO-56'?tr(lang,'Культура: Kc, p, корни и стадии из таблиц FAO-56.','Дақыл: Kc, p, тамыр және кезеңдер FAO-56 кестелерінен.','Crop: Kc, p, roots and stages from the FAO-56 tables.')
    :tr(lang,'Культура: Kc, p и корни из таблиц FAO-56; календарь стадий выбран проектом.','Дақыл: Kc, p және тамыр FAO-56 кестелерінен; кезеңдер күнтізбесін жоба таңдады.','Crop: Kc, p and roots from the FAO-56 tables; the stage calendar is the project’s own.');
  return [crop,tr(lang,'Баланс воды: FAO-56, глава 8. Почвы: таблица 19. Метод и сверка: docs/METHOD.md, docs/COEFFICIENT_CHECK.md.','Су балансы: FAO-56, 8-тарау. Топырақтар: 19-кесте. Әдіс пен салыстыру: docs/METHOD.md, docs/COEFFICIENT_CHECK.md.','Water balance: FAO-56 chapter 8. Soils: Table 19. Method and check: docs/METHOD.md, docs/COEFFICIENT_CHECK.md.')];
}
// What would change if the real crop or soil differed from the table (no new simulation: the same arithmetic on today's numbers).
export function sensitivity(field,r,lang) {
  if(r.etc===undefined||r.raw===undefined||!r.efficiency)return [];
  const dEtc=.15*r.etc,m3=dEtc*10*field.area_ha/r.efficiency;
  return [tr(lang,`Если растение расходует на 15% больше: +${fmt(dEtc)} мм/сут, это около +${fmt(m3,0)} м³ воды в день на поле.`,`Өсімдік 15%-ға көп жұмсаса: +${fmt(dEtc)} мм/тәул, бұл алқапқа күніне шамамен +${fmt(m3,0)} м³ су.`,`If the crop uses 15% more: +${fmt(dEtc)} mm/day, about +${fmt(m3,0)} m³ of water a day on the field.`),
    tr(lang,`Если почва держит на 20% меньше: запас до стресса ${fmt(r.raw)} → ${fmt(r.raw*.8)} мм, полив нужен раньше.`,`Топырақ 20%-ға аз ұстаса: күйзеліске дейінгі қор ${fmt(r.raw)} → ${fmt(r.raw*.8)} мм, суару ертерек қажет.`,`If the soil holds 20% less: the stock before stress ${fmt(r.raw)} → ${fmt(r.raw*.8)} mm, irrigation is needed earlier.`)];
}
export function whyCard(row,field,r,lang) {
  const c=confidence(row,field,r);
  return [`<b>${tr(lang,'Почему так? Допущения и источники','Неге осылай? Болжамдар мен дереккөздер','Why this? Assumptions and sources')}</b>`,confidenceLine(c,lang),
    tr(lang,'Статус описывает входные данные. Точность модели на этом участке ещё не измерена.','Күй кіріс деректерін сипаттайды. Модельдің осы алқаптағы дәлдігі әлі өлшенбеген.','The status describes the inputs. Model accuracy for this field has not been measured.'),'',
    `<b>${tr(lang,'Мы предположили','Біз болжадық','We assumed')}</b>`,...assumptions(row,field,r,lang).map(x=>'• '+x),'',
    `<b>${tr(lang,'Откуда числа','Сандар қайдан','Where the numbers come from')}</b>`,...sources(field,lang).map(x=>'• '+x),'',
    ...(selfCheckLines(row,r,lang).length?[`<b>${tr(lang,'Самопроверка по полю','Алқап бойынша өзін-өзі тексеру','Field self-check')}</b>`,...selfCheckLines(row,r,lang).map(x=>'• '+x),'']:[]),
    `<b>${tr(lang,'А если мы ошиблись','Ал егер қателессек','What if we are wrong')}</b>`,...sensitivity(field,r,lang).map(x=>'• '+x)].join('\n');
}

// Display helpers: no false precision (a field advice is not good to the last cubic metre).
export const volumeRounded=(n,lang)=>n>=100?volume(Math.round(n),lang):n>=10?volume(Math.round(n*10)/10,lang):volume(n,lang);
const STAGE={initial:['начальная','бастапқы','initial'],development:['развитие','даму','development'],middle:['середина сезона','маусым ортасы','mid-season'],late:['конец сезона','маусым соңы','late season'],custom:['введена вручную','қолмен енгізілген','entered by hand'],rice:['рис','күріш','rice']};
const MMD=lang=>tr(lang,'мм/сут','мм/тәул','mm/day'),MM=lang=>tr(lang,'мм','мм','mm');
const r1=n=>fmt(Math.round(n*10)/10,1);
// A big first volume on drip is the accumulated deficit from the starting moisture, not one day of crop use.
export function firstDayNote(field,r,lang) {
  if(!(r.deficit>3*(r.etc||0))||!r.etc||!['drip','subsurface'].includes(field.method)||r.status==='deferred')return '';
  const daily=r.etc*10*field.area_ha/r.efficiency;
  return tr(lang,`ℹ️ Объём включает накопленный дефицит ${r1(r.deficit)} мм (старт по вашему ответу о влажности). В обычные дни на капле это около ${r1(r.etc)} мм, то есть около ${fmt(Math.round(daily),0)} м³ в сутки.\n`,`ℹ️ Көлемге жиналған ${r1(r.deficit)} мм тапшылық кіреді (бастапқы ылғал бойынша). Әдеттегі күндері тамшылатып суаруда бұл шамамен ${r1(r.etc)} мм, яғни тәулігіне шамамен ${fmt(Math.round(daily),0)} м³.\n`,`ℹ️ The volume includes an accumulated deficit of ${r1(r.deficit)} mm (starting moisture from your answer). On an ordinary day on drip it is about ${r1(r.etc)} mm, i.e. about ${fmt(Math.round(daily),0)} m³ a day.\n`);
}
// The numbers behind the advice, labelled the way an agronomist reads them.
export function detailsBlock(row,field,r,lang) {
  const stage=(STAGE[field.stage]??STAGE.custom)[{ru:0,kz:1,en:2}[lang]??0];
  const L=[`<b>FAO-56</b>`,
    `${tr(lang,'Стадия','Кезең','Stage')}: ${stage} · ${tr(lang,'день','күн','day')} ${field.day} · ${tr(lang,'корни','тамыр','roots')} ${fmt(field.zr,2)} ${tr(lang,'м','м','m')}`,
    `${tr(lang,'Почва','Топырақ','Soil')}: ${esc(t(lang,'balance_soil_'+field.soil))}`,
    `ET₀: ${r1(r.et0)} ${MMD(lang)} · ${tr(lang,'осадки','жауын-шашын','rain')}: ${r1(r.rain)} ${MM(lang)}`,
    `${tr(lang,'Источник погоды','Ауа райы дереккөзі','Weather source')}: Open-Meteo (${tr(lang,'прогноз модели, не метеостанция поля','модель болжамы, алқаптың метеостанциясы емес','a model forecast, not a station at the field')})`,
    `Kc: ${fmt(field.kc,2)}${r.ks!==undefined&&r.ks<1?` · Ks: ${fmt(r.ks,2)}`:''} · ETc: ${r1(r.etc)} ${MMD(lang)}`,
    `${tr(lang,'Дефицит','Тапшылық','Deficit')}: ${r1(row.deficit)} ${MM(lang)} · TAW: ${r1(r.taw??0)} ${MM(lang)} · RAW: ${r1(r.raw)} ${MM(lang)}`,
    `${esc(t(lang,'report_irrig_'+field.method))}: η = ${fmt(Math.round(r.efficiency*100))}%`];
  if(field.manual?.length)L.push('✏️ '+tr(lang,'Изменено вручную','Қолмен өзгертілген','Changed manually')+': '+describe(field,lang,tr,fmt).join('; '));
  if(r.cost!==null&&r.cost!==undefined)L.push(`${tr(lang,'Электроэнергия на этот полив','Осы суаруға электр шығыны','Electricity for this watering')}: ${fmt(Math.round(r.cost),0)} ₸`);
  if(field.field_type==='greenhouse'&&field.greenhouse_et0===null)L.push(tr(lang,'Для теплицы ET₀ оценён как 0,70 наружного значения.','Жылыжай ET₀ сыртқы мәннің 0,70 бөлігімен бағаланды.','Greenhouse ET₀ uses 0.70 of the outdoor value.'));
  return L.join('\n');
}

// CSV for the agronomist: the field's parameters, the engine version, every recorded watering and every soil check.
import {VERSION} from './balance.js';
const cell=v=>{v=v===null||v===undefined?'':String(v);return /[",\r\n]/.test(v)?`"${v.replaceAll('"','""')}"`:v;};
export function fieldCsv(row) {
  const p=row.payload,f=parseField(p),L=[];
  L.push('# Su-Tech field export. Engine '+VERSION+'. Values in the parameter block are inputs; the tables are what was recorded.');
  L.push('parameter,value');
  for(const [k,v] of [['crop',p.crop],['soil',p.soil_type],['irrigation',p.irrigation_type],['area_ha',f.area_ha],['planting_day_of_season',p.day_of_growth],['field_type',p.field_type??'open'],['kc_today',f.kc],['root_depth_m',f.zr],['p',f.p],['stage',f.stage],['water_ec_dSm',p.water_ec],['soil_ec_dSm',p.soil_ec],['weather_source','Open-Meteo forecast'],['last_calculation_day',row.last_day],['deficit_mm',row.deficit],['manual_overrides',JSON.stringify(row.payload.expert??{})]])L.push(`${k},${cell(v)}`);
  L.push('');L.push('expert_changes: time,parameter,from,to');
  for(const e of row.expert_log??[])L.push([new Date(e.time).toISOString(),e.key,e.from,e.to].map(cell).join(','));
  L.push('');L.push('watering: time,applied_m3,deficit_before_mm,deficit_after_mm');
  for(const e of row.events??[])L.push([new Date(e.time).toISOString(),e.applied_m3,e.before,e.after].map(cell).join(','));
  L.push('');L.push('soil_check: time,day,level,value_mm,deficit_before_mm,deficit_after_mm');
  for(const c of row.checks??[])L.push([new Date(c.time).toISOString(),c.day,c.level,c.value_mm,c.before,c.after].map(cell).join(','));
  return L.join('\r\n')+'\r\n';
}

// Self-check from the farmer's soil checks: how far the model was from what the farmer found. Only reports; never changes the field.
// error > 0 means the soil was drier than the model said (the model was too wet).
export function selfCheck(row,r) {
  const cs=(row.checks??[]).filter(c=>Number.isFinite(c.before)&&Number.isFinite(c.value_mm)&&!(row.reset_at&&c.time<row.reset_at)).slice(-4);
  if(!cs.length||!(r.raw>0))return null;
  const errs=cs.map(c=>c.value_mm-c.before),mean=errs.reduce((a,b)=>a+b,0)/errs.length,abs=errs.reduce((a,b)=>a+Math.abs(b),0)/errs.length;
  const share=abs/r.raw,same=errs.length>=3&&(errs.every(e=>e>0.1*r.raw)||errs.every(e=>e<-0.1*r.raw));
  return {n:cs.length,mean_mm:mean,abs_mm:abs,share,bias:same?(mean>0?'model_wetter':'model_drier'):'none'};
}
export function selfCheckLines(row,r,lang) {
  const c=selfCheck(row,r);if(!c)return [];
  const L=[tr(lang,`За последние ${c.n} проверок бот отличался от вашего ответа в среднем на ${r1(c.abs_mm)} мм (${fmt(Math.round(c.share*100))}% запаса RAW).`,`Соңғы ${c.n} тексеру бойынша бот сіздің жауабыңыздан орта есеппен ${r1(c.abs_mm)} мм-ге (RAW қорының ${fmt(Math.round(c.share*100))}%) ерекшеленді.`,`Over the last ${c.n} checks the bot differed from your answer by ${r1(c.abs_mm)} mm on average (${fmt(Math.round(c.share*100))}% of the RAW stock).`)];
  if(c.bias==='model_wetter')L.push(tr(lang,'Почва каждый раз оказывалась суше, чем считал бот. Если так и дальше, культура, возможно, расходует больше воды, чем в таблице: агроном может поднять множитель Kc в режиме эксперта. Бот сам ничего не меняет.','Топырақ әр жолы бот есептегеннен құрғақ болды. Солай жалғасса, дақыл кестеден көп су жұмсауы мүмкін: агроном сарапшы режимінде Kc көбейткішін көтере алады. Бот өзі ештеңе өзгертпейді.','The soil was drier than the bot calculated each time. If this continues, the crop may use more water than the table says: an agronomist can raise the Kc multiplier in expert mode. The bot changes nothing by itself.'));
  if(c.bias==='model_drier')L.push(tr(lang,'Почва каждый раз оказывалась влажнее, чем считал бот. Если так и дальше, расход воды культурой, возможно, ниже табличного: агроном может снизить множитель Kc в режиме эксперта. Бот сам ничего не меняет.','Топырақ әр жолы бот есептегеннен ылғалды болды. Солай жалғасса, дақыл суды кестеден аз жұмсауы мүмкін: агроном сарапшы режимінде Kc көбейткішін төмендете алады. Бот өзі ештеңе өзгертпейді.','The soil was wetter than the bot calculated each time. If this continues, the crop may use less water than the table says: an agronomist can lower the Kc multiplier in expert mode. The bot changes nothing by itself.'));
  return L;
}

// Manual replacement for scheduled reminders (the platform has no scheduler): which fields are overdue for a soil-moisture check.
export const CHECK_DUE_DAYS=7;
export function checkAge(row,now=Date.now()) {
  const last=(row.checks??[]).filter(c=>!(row.reset_at&&c.time<row.reset_at)).at(-1);
  return last?Math.floor((now-last.time)/DAY):null;      // null: never checked
}
export const needsCheck=(row,now=Date.now())=>{
  if(row.payload?.crop==='rice'||row.result?.status==='unsupported')return false;
  const a=checkAge(row,now);return a===null||a>CHECK_DUE_DAYS;
};
export function checkNudge(row,lang,now=Date.now()) {
  if(!needsCheck(row,now))return '';
  const a=checkAge(row,now);
  return '🔔 '+(a===null?tr(lang,'Влажность почвы ещё ни разу не проверяли. Проверьте и нажмите «Проверил влажность почвы»: это обновит оценку влажности по вашему наблюдению.','Топырақ ылғалы әлі тексерілмеген. Тексеріп, «Топырақ ылғалын тексердім» батырмасын басыңыз: бұл ылғал бағасын сіздің бақылауыңыз бойынша жаңартады.','The soil moisture has not been checked yet. Check it and press “I checked the soil moisture”: this updates the moisture estimate from your observation.'):tr(lang,`Влажность почвы проверяли ${a} дн. назад. Проверьте снова и нажмите «Проверил влажность почвы».`,`Топырақ ылғалы ${a} күн бұрын тексерілген. Қайта тексеріп, «Топырақ ылғалын тексердім» батырмасын басыңыз.`,`The soil moisture was checked ${a} days ago. Check again and press “I checked the soil moisture”.`));
}
