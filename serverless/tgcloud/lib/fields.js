import {parseField,calculate,fieldKey,number,METHODS,VERSION,economics} from './balance.js';
import {get,put,list,lock,unlock,ownerId,nonce} from './store.js';
import {weather} from './weather.js';
import {tr,t,esc,fmt,volume} from './i18n.js';
export async function ownedField(id,fieldId) {
  ownerId(id);const row=await get(`field:${String(fieldId)}`,id);
  if(!row)throw new Error('not_found');return row;
}
export function currentResult(row) {
  const field=parseField(row.payload),base=row.result;
  if(field.crop==='rice')return base;
  const deficit=row.deficit,threshold=Math.min(METHODS[field.method][0],base.raw);
  const status=deficit-base.raw>1e-9?'critical':deficit>=threshold||Math.abs(deficit-threshold)<1e-9?'irrigate':'deferred';
  const gross_m3=status==='deferred'?0:deficit*10*field.area_ha/METHODS[field.method][1];
  return {...base,deficit,threshold,status,gross_m3,net_m3:gross_m3*METHODS[field.method][1],...economics(gross_m3,deficit,field)};
}
export async function calculateField(id,payload) {
  ownerId(id);const parsed=parseField(payload),key=fieldKey(payload,parsed);
  const guard=`field-key:${id}:${key}`,token=await lock(guard,45);if(!token)throw new Error('busy');
  try {
    const existing=(await list(id,'field',100)).find(f=>f.key===key);
    const lat=number(payload.latitude??payload.lat,'latitude',-90,90),lon=number(payload.longitude??payload.lon,'longitude',-180,180);
    const w=await weather(lat,lon);
    if(existing)return refresh(id,existing.id,w);
    const result=calculate(parsed,w.et0,w.rain),fieldId=Date.now()*100+Math.floor(Math.random()*100);
    const planting=new Date(Date.parse(w.day+'T00:00:00Z')-parsed.day*86400000).toISOString().slice(0,10);
    const row={id:fieldId,key,payload:{...payload,latitude:lat,longitude:lon},planting,deficit:result.deficit,last_day:w.day,result,weather:w,revision:1,events:[],version:VERSION};
    await put(`field:${fieldId}`,id,'field',row);
    await saveCalculation(id,row);
    return row;
  } finally {await unlock(guard,token);}
}
export async function refresh(id,fieldId,w=null) {
  const guard=`field:${fieldId}`,token=await lock(guard,45);if(!token)throw new Error('busy');
  try {
    const row=await ownedField(id,fieldId);w??=await weather(row.payload.latitude,row.payload.longitude);
    if(row.last_day===w.day)return row;
    // A daily forecast must not be multiplied across unobserved days.
    const days=Math.round((Date.parse(w.day+'T00:00:00Z')-Date.parse(row.last_day+'T00:00:00Z'))/86400000);
    const day=Math.round((Date.parse(w.day+'T00:00:00Z')-Date.parse(row.planting+'T00:00:00Z'))/86400000);
    const field=parseField({...row.payload,day_of_growth:day});field.yesterday=row.deficit;
    row.result=calculate(field,w.et0,w.rain);row.deficit=row.result.deficit;row.payload.day_of_growth=day;
    row.last_day=w.day;row.weather=w;row.revision++;row.gap_days=Math.max(0,days-1);
    await put(`field:${fieldId}`,id,'field',row);await saveCalculation(id,row);return row;
  } finally {await unlock(guard,token);}
}
export async function waterField(id,fieldId,applied,expected,revision=null) {
  applied=number(applied,'applied_m3',.000001,1e9);expected=number(expected,'expected_deficit',.00000001,3000);
  const guard=`field:${fieldId}`,token=await lock(guard,30);if(!token)throw new Error('busy');
  try {
    const row=await ownedField(id,fieldId);
    if(Math.abs(row.deficit-expected)>1e-8||(revision!==null&&row.revision!==revision))throw new Error('balance_changed');
    const f=parseField(row.payload),before=row.deficit;
    row.deficit=Math.max(0,before-applied*METHODS[f.method][1]/(10*f.area_ha));row.revision++;
    row.events=[...(row.events??[]),{time:Date.now(),applied_m3:applied,before,after:row.deficit}].slice(-365);
    await put(`field:${fieldId}`,id,'field',row);return row;
  } finally {await unlock(guard,token);}
}
export async function saveCalculation(id,row) {
  await put(`report:${nonce()}`,id,'report',{field_id:row.id,payload:row.payload,result:row.result,weather:row.weather,created:Date.now()});
}
export async function card(id,fieldId) {
  const row=await refresh(id,fieldId),f=parseField(row.payload),r=currentResult(row);
  return {id:row.id,name:row.name??'',crop:f.crop,area_ha:f.area_ha,status:r.status,date:row.last_day,timezone:row.weather.timezone,deficit:row.deficit,raw:r.raw,threshold:r.threshold,volume_m3:r.gross_m3,rain_mm:r.rain,etc_mm:r.etc,revision:row.revision,gap_days:row.gap_days??0};
}
export function report(row,lang,details=false) {
  const field=parseField(row.payload),r=currentResult(row);
  const state={critical:tr(lang,'Полив нужен: запас влаги ниже порога','Суару қажет: ылғал қоры шектен төмен','Water now: moisture is below the threshold'),
    irrigate:tr(lang,'Сегодня нужен полив','Бүгін суару қажет','Irrigation is needed today'),
    deferred:tr(lang,'Сегодня можно не поливать','Бүгін суармаса болады','No irrigation needed today'),rice:tr(lang,'Расчёт для риса','Күрішке арналған есеп','Rice water estimate')}[r.status];
  let s=`<b>${esc(state)}</b>\n${esc(t(lang,'report_crop_'+field.crop))} · ${fmt(field.area_ha,6)} ha\n${esc(row.last_day)} · ${esc(row.weather.timezone??'')}\n\n`;
  if(r.status!=='deferred')s+=`<b>${tr(lang,'Подать воды','Берілетін су','Apply water')}: ${volume(r.gross_m3,lang)}</b>\n`;
  s+=tr(lang,'После полива отметьте фактический объём.','Суарғаннан кейін нақты көлемді белгілеңіз.','After watering, record the actual amount.');
  if(row.gap_days)s+=`\n\n${tr(lang,`Пропуск наблюдений: ${row.gap_days} дн. Проверьте влажность почвы перед поливом.`,`Бақылау үзілісі: ${row.gap_days} күн. Суармас бұрын топырақ ылғалын тексеріңіз.`,`Observation gap: ${row.gap_days} days. Check soil moisture before watering.`)}`;
  if(field.saline)s+='\n\n'+tr(lang,'Засолённая почва: промывной режим определяет агроном.','Тұзданған топырақ: шаю режимін агроном анықтайды.','Saline soil: an agronomist must set the leaching regime.');
  if(details){
    s+=`\n\n<b>FAO-56</b>\nET0: ${fmt(r.et0)} mm/day\nKc: ${fmt(field.kc)}\nETc: ${fmt(r.etc)} mm/day\n${tr(lang,'Осадки','Жауын-шашын','Rain')}: ${fmt(r.rain)} mm\n${tr(lang,'Дефицит','Тапшылық','Deficit')}: ${fmt(row.deficit)} mm\nTAW: ${fmt(r.taw??0)} mm · RAW: ${fmt(r.raw)} mm\n${esc(t(lang,'report_irrig_'+field.method))}: η = ${fmt(r.efficiency*100)}%`;
    if(r.cost!==null)s+=`\n${tr(lang,'Электроэнергия на этот полив','Осы суаруға электр шығыны','Electricity for this watering')}: ${fmt(r.cost)} ₸`;
    if(field.field_type==='greenhouse'&&field.greenhouse_et0===null)s+='\n'+tr(lang,'Для теплицы ET0 оценён как 0,70 наружного значения.','Жылыжай ET0 сыртқы мәннің 0,70 бөлігімен бағаланды.','Greenhouse ET0 uses 0.70 of the outdoor value.');
    s+=`\n${VERSION}`;
  }
  return s;
}
