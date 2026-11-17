// "Why this?": how much to trust today's advice, what was assumed, where each number comes from, and what would change if
// the assumptions were wrong. Pure functions of the stored field: no new calculation, no invented numbers.
import {CROP_STATUS} from './crops-data.js';
import {METHODS,SALT_TOLERANCE} from './balance.js';
import {tr,fmt,esc} from './i18n.js';

const DAY=86400000;
export function confidence(row,field,r,now=Date.now()) {
  const reasons=[],last=row.checks?.at(-1),ageDays=last?(now-last.time)/DAY:null;
  if(r.status==='unsupported'||r.leaching_impossible)return {level:'low',reasons:['unsupported'],raise:'agronomist'};
  if(field.crop!=='rice'&&field.crop!=='other'&&CROP_STATUS[field.crop]!=='FAO-56')reasons.push('crop_stages');
  if(field.crop==='other')reasons.push('crop_custom');
  if(ageDays===null)reasons.push('no_check');else if(ageDays>7)reasons.push('old_check');
  if(field.saline&&field.water_ec==null&&field.soil_ec==null)reasons.push('saline_unmeasured');
  if(field.field_type==='greenhouse'&&field.greenhouse_et0==null)reasons.push('greenhouse_estimate');
  if((row.gap_days??0)>0)reasons.push('gap');
  if(field.saline&&!(field.crop in SALT_TOLERANCE))reasons.push('no_salt_data');
  const level=((row.gap_days??0)>3||(reasons.includes('crop_custom')&&reasons.includes('no_check')))?'low':reasons.length?'medium':'high';
  const raise=reasons.includes('no_check')||reasons.includes('old_check')?'check':reasons.includes('saline_unmeasured')?'salinity':reasons.includes('gap')?'gap':reasons.length?'assumptions':null;
  return {level,reasons,raise};
}
const LEVEL={high:['🟢','Доверие высокое','Сенімділік жоғары','Confidence: high'],medium:['🟡','Доверие среднее: есть допущения','Сенімділік орташа: болжамдар бар','Confidence: medium, there are assumptions'],low:['🔴','Нужен агроном или проверка','Агроном немесе тексеру қажет','An agronomist or a check is needed']};
const RAISE={check:['Подтвердите влажность почвы кнопкой «Проверил влажность почвы».','«Топырақ ылғалын тексердім» батырмасымен ылғалды растаңыз.','Confirm soil moisture with the “I checked the soil moisture” button.'],
  salinity:['Если почва солёная, укажите анализ воды и почвы (ECw, ECe).','Топырақ сортаң болса, су мен топырақ талдауын (ECw, ECe) көрсетіңіз.','If the soil is saline, enter a water and soil analysis (ECw, ECe).'],
  gap:['Проверьте влажность почвы: были дни без данных погоды.','Топырақ ылғалын тексеріңіз: ауа райы деректері жоқ күндер болды.','Check the soil moisture: some days had no weather data.'],
  assumptions:['Уточните допущения ниже, чтобы поднять доверие.','Сенімділікті көтеру үшін төмендегі болжамдарды нақтылаңыз.','Refine the assumptions below to raise confidence.'],
  agronomist:['Для этого случая метод расчёта не подходит: обратитесь к агроному.','Бұл жағдайға есеп әдісі жарамайды: агрономға жүгініңіз.','The calculation method does not fit this case: ask an agronomist.']};
export function confidenceLine(c,lang) {
  const [icon,...text]=LEVEL[c.level],i={ru:0,kz:1,en:2}[lang]??0;
  return `${icon} ${text[i]}`+(c.raise?`\n${tr(lang,...RAISE[c.raise])}`:'');
}
export function assumptions(row,field,r,lang) {
  const lines=[],m=METHODS[field.method];
  const stages=field.stages?.length?field.stages.reduce((a,b)=>a+b,0):null;
  if(stages&&row.payload.stage_days==null)lines.push(tr(lang,`Календарь стадий взят из каталога (${stages} дн.); уточните даты посадки.`,`Кезеңдер күнтізбесі каталогтан алынды (${stages} күн); егу күнін нақтылаңыз.`,`The stage calendar comes from the catalog (${stages} days); refine the planting date.`));
  lines.push(tr(lang,`Почва: ${esc(field.soil)}, доступная вода ${fmt(r.taw??0)} мм в слое корней.`,`Топырақ: ${esc(field.soil)}, тамыр қабатындағы қолжетімді су ${fmt(r.taw??0)} мм.`,`Soil: ${esc(field.soil)}, available water ${fmt(r.taw??0)} mm in the root layer.`));
  if(!field.saline||(field.water_ec==null&&field.soil_ec==null))lines.push(tr(lang,'Засоление не учитывается (анализов нет).','Тұздану ескерілмейді (талдау жоқ).','Salinity is not included (no analysis).'));
  lines.push(tr(lang,`КПД полива ${fmt(m[1]*100)}% и порог технологии ${fmt(m[0])} мм: выбор проекта.`,`Суару ПӘК-і ${fmt(m[1]*100)}% және технология шегі ${fmt(m[0])} мм: жоба таңдауы.`,`Irrigation efficiency ${fmt(m[1]*100)}% and technology threshold ${fmt(m[0])} mm are project choices.`));
  lines.push(tr(lang,'Дождь меньше 5 мм не учитывается, иначе 75%: правило проекта.','5 мм-ден аз жауын ескерілмейді, әйтпесе 75%: жоба ережесі.','Rain under 5 mm is ignored, otherwise 75%: a project rule.'));
  if(field.field_type==='greenhouse'&&field.greenhouse_et0==null)lines.push(tr(lang,'Теплица: ET₀ = 0,70 от уличного (допущение, в теплицах не проверено).','Жылыжай: ET₀ = сыртқының 0,70 бөлігі (болжам, жылыжайда тексерілмеген).','Greenhouse: ET₀ = 0.70 of the outdoor value (an assumption, not checked in greenhouses).'));
  if(!row.checks?.length)lines.push(tr(lang,'Начальная влажность взята по вашему ответу; проверок руками ещё не было.','Бастапқы ылғал сіздің жауабыңыз бойынша алынды; қолмен тексеру әлі болған жоқ.','The starting moisture is your answer; there has been no hand check yet.'));
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
  return [`<b>${tr(lang,'Почему так? Допущения и источники','Неге осылай? Болжамдар мен дереккөздер','Why this? Assumptions and sources')}</b>`,confidenceLine(c,lang),'',
    `<b>${tr(lang,'Мы предположили','Біз болжадық','We assumed')}</b>`,...assumptions(row,field,r,lang).map(x=>'• '+x),'',
    `<b>${tr(lang,'Откуда числа','Сандар қайдан','Where the numbers come from')}</b>`,...sources(field,lang).map(x=>'• '+x),'',
    `<b>${tr(lang,'А если мы ошиблись','Ал егер қателессек','What if we are wrong')}</b>`,...sensitivity(field,r,lang).map(x=>'• '+x)].join('\n');
}
