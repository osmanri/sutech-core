import {checkNudge,needsCheck,confidence,confidenceLine,whyCard,volumeRounded,firstDayNote,detailsBlock} from './explain.js';
import {calculate,fieldKey,number,METHODS,VERSION,economics,PUMP_MAX_HOURS_PER_DAY,salinity,applicableResult} from './balance.js';
import {get,putGuarded,list,lock,unlock,ownerId,ownerState,nonce} from './store.js';
import {weather} from './weather.js';
import {parseField,cleanExpert,KEYS} from './expert.js';
import {tr,t,esc,fmt,volume} from './i18n.js';
import {q} from './planner-extra.js';
export async function ownedField(id,fieldId) {
  ownerId(id);const row=await get(`field:${String(fieldId)}`,id);
  if(!row)throw new Error('not_found');return row;
}
export function currentResult(row) {
  const field=parseField(row.payload),base=applicableResult(field,row.result);
  if(field.crop==='rice'||base.status==='unsupported')return base;
  const deficit=row.deficit,threshold=Math.min(METHODS[field.method][0],base.raw);
  const status=deficit-base.raw>1e-9?'critical':deficit>=threshold||Math.abs(deficit-threshold)<1e-9?'irrigate':'deferred';
  const salt=salinity(field,METHODS[field.method][1]),net_m3=status==='deferred'?0:deficit*10*field.area_ha,gross_m3=net_m3/salt.effective_efficiency;
  return {...base,deficit,threshold,status,gross_m3,net_m3,leaching_fraction:salt.leaching_fraction,leaching_impossible:salt.leaching_impossible,salinity_yield_loss_pct:salt.salinity_yield_loss_pct,...economics(gross_m3,deficit,field)};
}
const DAY_MS=86400000;
const addDays=(iso,n)=>new Date(Date.parse(iso+'T00:00:00Z')+n*DAY_MS).toISOString().slice(0,10);
const diffDays=(a,b)=>Math.round((Date.parse(a+'T00:00:00Z')-Date.parse(b+'T00:00:00Z'))/DAY_MS);
const localDayOf=(time,offset)=>new Date(time+(Number(offset)||0)*1000).toISOString().slice(0,10);
// Farmer's own soil check (closed loop): replaces the model's estimate of the root-zone deficit.
// Levels match the setup form: wet = 0, normal = RAW/2, dry = RAW (FAO-56 readily available water).
export const SOIL_LEVELS={wet:0,normal:.5,dry:1};

const fieldOn=(row,day)=>parseField({...row.payload,day_of_growth:diffDays(day,row.planting)});
// Irrigation and soil checks recorded for one field day, in time order (after the last reset).
function eventsOn(row,day) {
  const off=row.weather?.utc_offset_seconds;
  return [...(row.events??[]).map(e=>({...e,kind:'water'})),...(row.checks??[]).map(c=>({...c,kind:'check'}))]
    .filter(e=>(e.day??localDayOf(e.time,off))===day&&!(row.reset_at&&e.time<row.reset_at))
    .sort((a,b)=>a.time-b.time);
}
// One FAO-56 daily step from the start-of-day depletion, then that day's logged actions:
// irrigation subtracts its net depth, a soil check sets the depletion to the observed level.
function stepDay(row,day,start,w) {
  const field=fieldOn(row,day);field.yesterday=start;
  const result=calculate(field,w.et0,w.rain);
  let end=result.deficit;
  for(const e of eventsOn(row,day)){
    if(e.kind==='water')end=Math.max(0,end-(e.net_mm??e.applied_m3*METHODS[field.method][1]/(10*field.area_ha)));
    else end=Math.min(result.taw??Infinity,e.value_mm??SOIL_LEVELS[e.level]*result.raw);
  }
  return {result,end};
}
// Rows saved before the closed-day model stored only "deficit at the end of last_day" (built from
// that day's forecast). A past last_day is accepted as closed; if it is today, the start-of-day
// state is recovered from the stored calculation so today's actions can be replayed.
function migrate(row,today) {
  if(row.closed_day)return;
  if(row.last_day&&row.last_day<today){row.closed_day=row.last_day;row.closed_deficit=row.deficit;}
  else {
    const r=row.result??{};
    row.closed_day=addDays(row.last_day??today,-1);
    row.closed_deficit=r.unbounded!==undefined?Math.max(0,r.unbounded-r.etc+r.peff):row.deficit;
  }
  row.migrated_from=row.version??'legacy';
}
// Close every finished day in order with the provider's values for that day, then build today's
// advice from the forecast without storing the forecast as history.
function recompute(row,w) {
  const hist=new Map((w.history??[]).map(h=>[h.day,h]));let d=row.closed_deficit,gaps=0;
  for(let day=addDays(row.closed_day,1);day<w.day;day=addDays(day,1)){
    const h=hist.get(day);if(!h)gaps++;
    d=stepDay(row,day,d,h??{et0:0,rain:0}).end;  // no data: only that day's logged actions apply
    row.closed_day=day;row.closed_deficit=d;
  }
  const today=stepDay(row,w.day,d,w),{history,...forecast}=w;void history;
  row.result=today.result;row.deficit=today.end;row.last_day=w.day;row.weather=forecast;
  row.payload.day_of_growth=diffDays(w.day,row.planting);row.gap_days=gaps;row.version=VERSION;
}
const PHYSICAL=['crop','soil_type','irrigation_type','water_ec','soil_ec','custom_kc','custom_root_depth','custom_p','stage_days'];
const COSTS=['power_price','pump_power_kw','pump_productivity_m3h'];
const same=(a,b)=>JSON.stringify(a??null)===JSON.stringify(b??null)||(a!==null&&b!==null&&a!==undefined&&b!==undefined&&a!==''&&b!==''&&Number(a)===Number(b));
function physicalChange(previous,payload,parsed) {
  if(PHYSICAL.some(k=>!same(previous[k],payload[k])))return true;
  const before=parseField(previous);
  return Math.abs(before.area_ha-parsed.area_ha)>1e-12||before.field_type!==parsed.field_type||before.saline!==parsed.saline||
    (parsed.field_type==='greenhouse'&&['greenhouse_et0','greenhouse_medium','greenhouse_heated'].some(k=>before[k]!==parsed[k]));
}
function freshRow(fieldId,key,payload,w,parsed) {
  const row={id:fieldId,key,payload,planting:addDays(w.day,-parsed.day),closed_day:addDays(w.day,-1),
    closed_deficit:parsed.yesterday,revision:1,events:[],checks:[],version:VERSION};
  recompute(row,w);return row;
}
export async function calculateField(id,payload,expectedEpoch=null) {
  ownerId(id);const parsed=parseField(payload),key=fieldKey(payload,parsed);
  const {epoch}=await ownerState(id,expectedEpoch);
  const guard=`field-key:${id}:${key}`,token=await lock(guard,45);if(!token)throw new Error('busy');
  try {
    let existing=(await list(id,'field',100)).find(f=>f.key===key);
    const lat=number(payload.latitude??payload.lat,'latitude',-90,90),lon=number(payload.longitude??payload.lon,'longitude',-180,180);
    const w=await weather(lat,lon),clean={...payload,latitude:lat,longitude:lon};
    if(existing){
      // The planting date is kept from the stored field (the form may resend a stale day count from a
      // saved draft); only a change of the field itself restarts the balance.
      if(physicalChange(existing.payload,payload,parsed)||COSTS.some(k=>!same(existing.payload[k],payload[k]))){
        const guard2=`field:${existing.id}`,t2=await lock(guard2,45);if(!t2)throw new Error('busy');
        try{
          // A soil check/watering may have completed while weather was loading.
          existing=await ownedField(id,existing.id);migrate(existing,w.day);
          if(physicalChange(existing.payload,payload,parsed)){
            // The farmer corrected the field itself: start from the new inputs.
            if(existing.payload.expert)clean.expert=existing.payload.expert;
            const row=freshRow(existing.id,key,clean,w,parsed);
            Object.assign(row,{events:existing.events??[],checks:existing.checks??[],reset_at:Date.now(),revision:(existing.revision??1)+1,submit:'reset'});
            const fence={lease:[guard2,t2],parentLease:[guard,token],epoch};
            await putGuarded(`field:${row.id}`,id,'field',row,{...fence,existing:true});await saveCalculation(id,row,fence);return row;
          }
          const row=existing;
          for(const k of COSTS)row.payload[k]=payload[k]??null;
          recompute(row,w);row.revision++;row.submit='costs';
          await putGuarded(`field:${row.id}`,id,'field',row,{lease:[guard2,t2],parentLease:[guard,token],epoch,existing:true});return row;
        } finally {await unlock(guard2,t2);}
      }
      const row=await refresh(id,existing.id,w,[guard,token],epoch);row.submit='existing';return row;
    }
    const row=freshRow(Date.now()*100+Math.floor(Math.random()*100),key,clean,w,parsed);row.submit='new';
    const fence={lease:[guard,token],epoch};
    await putGuarded(`field:${row.id}`,id,'field',row,fence);
    await saveCalculation(id,row,fence);
    return row;
  } finally {await unlock(guard,token);}
}
export async function refresh(id,fieldId,w=null,parentLease=null,expectedEpoch=null) {
  const {epoch}=await ownerState(id,expectedEpoch);
  const guard=`field:${fieldId}`,token=await lock(guard,45);if(!token)throw new Error('busy');
  try {
    const row=await ownedField(id,fieldId);w??=await weather(row.payload.latitude,row.payload.longitude);
    const legacy=!row.closed_day;migrate(row,w.day);
    // Same day and same forecast: nothing to do. A changed forecast only changes today's advice,
    // because today is always rebuilt from the closed state and never accumulates twice.
    if(!legacy&&row.last_day===w.day&&row.weather?.et0===w.et0&&row.weather?.rain===w.rain)return row;
    const newDay=row.last_day!==w.day;
    recompute(row,w);row.revision++;
    const fence={lease:[guard,token],parentLease,epoch};
    await putGuarded(`field:${fieldId}`,id,'field',row,{...fence,existing:true});if(newDay)await saveCalculation(id,row,fence);return row;
  } finally {await unlock(guard,token);}
}
export async function waterField(id,fieldId,applied,expected,revision=null,expectedEpoch=null) {
  const {epoch}=await ownerState(id,expectedEpoch);
  applied=number(applied,'applied_m3',.000001,1e9);expected=number(expected,'expected_deficit',.00000001,3000);
  const guard=`field:${fieldId}`,token=await lock(guard,30);if(!token)throw new Error('busy');
  try {
    const row=await ownedField(id,fieldId);
    if(currentResult(row).status==='unsupported')throw new Error('unsupported');
    if(Math.abs(row.deficit-expected)>1e-8||(revision!==null&&row.revision!==revision))throw new Error('balance_changed');
    migrate(row,row.last_day);
    const f=parseField(row.payload),before=row.deficit,net_mm=applied*METHODS[f.method][1]/(10*f.area_ha);
    row.events=[...(row.events??[]),{time:Date.now(),day:row.last_day,applied_m3:applied,net_mm,before}].slice(-365);
    row.deficit=stepDay(row,row.last_day,row.closed_deficit,row.weather).end;row.events.at(-1).after=row.deficit;row.revision++;
    await putGuarded(`field:${fieldId}`,id,'field',row,{lease:[guard,token],epoch,existing:true});return row;
  } finally {await unlock(guard,token);}
}
export async function checkMoisture(id,fieldId,level,revision=null,expectedEpoch=null) {
  const {epoch}=await ownerState(id,expectedEpoch);
  if(!Object.hasOwn(SOIL_LEVELS,level))throw new Error('bad_level');
  const guard=`field:${fieldId}`,token=await lock(guard,30);if(!token)throw new Error('busy');
  try {
    const row=await ownedField(id,fieldId);
    if(revision!==null&&row.revision!==revision)throw new Error('balance_changed');
    const f=parseField(row.payload);if(f.crop==='rice')throw new Error('not_applicable');
    migrate(row,row.last_day);
    const base=currentResult(row),before=row.deficit,value_mm=Math.min(base.taw,SOIL_LEVELS[level]*base.raw);
    row.checks=[...(row.checks??[]),{time:Date.now(),day:row.last_day,level,value_mm,before}].slice(-365);
    row.deficit=stepDay(row,row.last_day,row.closed_deficit,row.weather).end;row.checks.at(-1).after=row.deficit;row.revision++;
    await putGuarded(`field:${fieldId}`,id,'field',row,{lease:[guard,token],epoch,existing:true});return row;
  } finally {await unlock(guard,token);}
}
export async function saveCalculation(id,row,fence) {
  await putGuarded(`report:${nonce()}`,id,'report',{field_id:row.id,payload:row.payload,result:row.result,weather:row.weather,created:Date.now()},fence);
}
export async function card(id,fieldId) {
  const row=await refresh(id,fieldId),f=parseField(row.payload),r=currentResult(row);
  return {id:row.id,name:row.name??'',crop:f.crop,area_ha:f.area_ha,status:r.status,date:row.last_day,timezone:row.weather.timezone,deficit:row.deficit,raw:r.raw,threshold:r.threshold,volume_m3:r.gross_m3,rain_mm:r.rain,etc_mm:r.etc,revision:row.revision,gap_days:row.gap_days??0};
}
export function report(row,lang,details=false) {
  const field=parseField(row.payload),r=currentResult(row);
  const state={critical:tr(lang,'Полив нужен: запас влаги ниже порога','Суару қажет: ылғал қоры шектен төмен','Water now: moisture is below the threshold'),
    irrigate:tr(lang,'Сегодня нужен полив','Бүгін суару қажет','Irrigation is needed today'),
    deferred:tr(lang,'Сегодня можно не поливать','Бүгін суармаса болады','No irrigation needed today'),rice:tr(lang,'Расчёт для риса','Күрішке арналған есеп','Rice water estimate'),unsupported:tr(lang,'Совет по поливу не выдаётся','Суару кеңесі берілмейді','No irrigation advice is given')}[r.status];
  let s=`<b>${esc(state)}</b>\n${esc(t(lang,'report_crop_'+field.crop))} · ${fmt(field.area_ha,6)} ${tr(lang,'га','га','ha')}\n${esc(row.last_day)} · ${esc(row.weather.timezone??'')}\n\n`;
  if(r.status==='unsupported')return s+(r.unsupported_reason==='substrate'?tr(lang,'Теплица на субстрате (минвата, кокос): метод водного баланса почвы не подходит. Поливом на субстрате управляют по доле дренажа, обратитесь к агроному.','Субстраттағы жылыжай (минвата, кокос): топырақ су балансы әдісі жарамайды. Субстратта суаруды дренаж үлесімен басқарады, агрономға жүгініңіз.','Greenhouse on a substrate (rockwool, coco): the soil water balance does not apply. Substrate irrigation is managed by the drainage fraction; ask an agronomist.'):tr(lang,'Отапливаемая теплица: оценка по уличной погоде здесь неверна (растения пьют из-за отопления и света, а не уличной жары). Введите измеренный ET₀ теплицы или обратитесь к агроному; пока совет не выдаётся.','Жылытылатын жылыжай: сыртқы ауа райымен бағалау мұнда дұрыс емес (өсімдік жылыту мен жарыққа байланысты су ішеді). Жылыжайдың өлшенген ET₀ мәнін енгізіңіз немесе агрономға жүгініңіз; әзірге кеңес берілмейді.','Heated greenhouse: an estimate from outdoor weather is wrong here (the crop drinks because of heating and light, not outdoor heat). Enter a measured greenhouse ET₀ or ask an agronomist; no advice is given for now.'));
  if(r.status!=='deferred')s+=`<b>${tr(lang,'Подать воды','Берілетін су','Apply water')}: ≈ ${volumeRounded(r.gross_m3,lang)}</b>\n`+firstDayNote(field,r,lang);
  if(row.payload.growth_estimated===true)s+=esc(q(lang,'growth_estimated'))+'\n';
  if(r.irrigation_days>1)s+=tr(lang,`⚠️ Насос за сутки подаёт не больше ${fmt(r.max_daily_m3,0)} м³ (${PUMP_MAX_HOURS_PER_DAY} ч работы). Объём больше: разделите полив на ${r.irrigation_days} дн., около ${fmt(r.gross_m3/r.irrigation_days,0)} м³ в день.\n`,`⚠️ Сорғы тәулігіне ${fmt(r.max_daily_m3,0)} м³-ден артық бере алмайды (${PUMP_MAX_HOURS_PER_DAY} сағ жұмыс). Көлем одан көп: суаруды ${r.irrigation_days} күнге бөліңіз, күніне шамамен ${fmt(r.gross_m3/r.irrigation_days,0)} м³.\n`,`⚠️ The pump delivers at most ${fmt(r.max_daily_m3,0)} m³ per day (${PUMP_MAX_HOURS_PER_DAY} h of running). The volume is larger: split the watering over ${r.irrigation_days} days, about ${fmt(r.gross_m3/r.irrigation_days,0)} m³ a day.\n`);
  if(!details&&r.status!=='unsupported'){const c=confidence(row,field,r);s+=confidenceLine(needsCheck(row)&&c.raise==='check'?{...c,raise:null}:c,lang)+'\n\n';}
  s+=tr(lang,'После полива отметьте фактический объём.','Суарғаннан кейін нақты көлемді белгілеңіз.','After watering, record the actual amount.');
  if(!details){const n=checkNudge(row,lang);if(n)s+='\n\n'+n;}
  if(row.gap_days)s+=`\n\n${tr(lang,`Пропуск наблюдений: ${row.gap_days} дн. Проверьте влажность почвы перед поливом.`,`Бақылау үзілісі: ${row.gap_days} күн. Суармас бұрын топырақ ылғалын тексеріңіз.`,`Observation gap: ${row.gap_days} days. Check soil moisture before watering.`)}`;
  if(r.leaching_impossible)s+='\n\n'+tr(lang,`🧂 Вода ${fmt(field.water_ec)} дСм/м слишком солёная для этой культуры: обычная промывка невозможна. Нужен агроном.`,`🧂 ${fmt(field.water_ec)} дСм/м су бұл дақыл үшін тым тұзды: әдеттегі шаю мүмкін емес. Агроном қажет.`,`🧂 Water of ${fmt(field.water_ec)} dS/m is too salty for this crop: usual leaching is not possible. An agronomist is needed.`);
  else if(r.leaching_fraction!==null&&r.leaching_fraction!==undefined)s+='\n\n'+tr(lang,`🧂 Вода для промывки солей: вода ${fmt(field.water_ec)} дСм/м, доля промывки ${fmt(r.leaching_fraction*100)}%. Объём увеличен, чтобы вымывать соли (FAO-29).`,`🧂 Тұзды шаю суы: су ${fmt(field.water_ec)} дСм/м, шаю үлесі ${fmt(r.leaching_fraction*100)}%. Тұзды шаю үшін көлем арттырылды (FAO-29).`,`🧂 Leaching water: irrigation water ${fmt(field.water_ec)} dS/m, leaching fraction ${fmt(r.leaching_fraction*100)}%. The volume is increased to wash out salts (FAO-29).`);
  if(r.salinity_yield_loss_pct!==null&&r.salinity_yield_loss_pct!==undefined)s+='\n\n'+tr(lang,`🧂 При солёности почвы ${fmt(field.soil_ec)} дСм/м ожидаемая потеря урожая от соли около ${fmt(r.salinity_yield_loss_pct)}% (FAO-56, табл. 23).`,`🧂 Топырақ тұздылығы ${fmt(field.soil_ec)} дСм/м болғанда тұздан өнім шамамен ${fmt(r.salinity_yield_loss_pct)}% кемиді (FAO-56, 23-кесте).`,`🧂 At a soil salinity of ${fmt(field.soil_ec)} dS/m the expected salt yield loss is about ${fmt(r.salinity_yield_loss_pct)}% (FAO-56, Table 23).`);
  if(field.saline)s+='\n\n'+tr(lang,'Засолённая почва: промывной режим определяет агроном.','Тұзданған топырақ: шаю режимін агроном анықтайды.','Saline soil: an agronomist must set the leaching regime.');
  if(details){
    s+='\n\n'+detailsBlock(row,field,r,lang);
    s+=`\n${VERSION}`;
    s+='\n\n'+whyCard(row,field,r,lang);
  }
  return s;
}

// Expert mode: set one override (value) or remove it (null). Past closed days stay as they were; the change applies from today.
export async function setExpert(id,fieldId,key,value,expectedEpoch=null) {
  const {epoch}=await ownerState(id,expectedEpoch);
  if(!KEYS.includes(key))throw new Error('bad_key');
  const guard=`field:${fieldId}`,token=await lock(guard,45);if(!token)throw new Error('busy');
  try {
    const row=await ownedField(id,fieldId),was=cleanExpert(row.payload.expert),next={...was};
    if(value===null)delete next[key];else next[key]=cleanExpert({[key]:value})[key];
    const w=await weather(row.payload.latitude,row.payload.longitude);migrate(row,w.day);
    row.payload.expert=next;if(!Object.keys(next).length)delete row.payload.expert;
    parseField(row.payload);
    row.expert_log=[...(row.expert_log??[]),{time:Date.now(),key,from:was[key]??null,to:next[key]??null}].slice(-100);
    recompute(row,w);row.revision++;
    await putGuarded(`field:${fieldId}`,id,'field',row,{lease:[guard,token],epoch,existing:true});return row;
  } finally {await unlock(guard,token);}
}
