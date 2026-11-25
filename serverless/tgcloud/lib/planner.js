import {CROPS,number} from './balance.js';
import {COPY} from './planner-copy.js';
import {user,saveUser} from './store.js';
import {screen,button,keyboard,back} from './ui.js';
import {tr,t,esc,fmt} from './i18n.js';
import {DEFAULTS,REFINE,REFINE_LABEL,QUESTION,q,assumedLines,FIELD_LABELS,STAGE_LABELS,fieldChoice} from './planner-extra.js';
export const ENUMS={crop:[...Object.keys(CROPS),'rice','other'],soil_type:['sand','loam','clay'],moisture_condition:['recent','normal','dry'],irrigation_type:['drip','sprinkler','pivot','furrow','subsurface'],is_saline:['no','yes']};
export const steps=v=>['crop','area','location','day_of_growth','irrigation_type',...(v.crop==='other'?['custom']:[]),'field_type','confirm'];
const phrase=(lang,key)=>(QUESTION[key]??COPY[key])[{ru:0,kz:1,en:2}[lang]??0];
const refinements=v=>v.field_type==='greenhouse'&&v.greenhouse_medium==='soil'?[...REFINE,'greenhouse_et0']:REFINE;
const AREA_NUMBER='([0-9]+(?:[.,][0-9]+)?)';
const AREA_UNIT=new RegExp(`^${AREA_NUMBER}\\s*(га|ha|сот(?:\\.|ка|ки|ок)?|сотық|sotkas?|[мm][²2])$`,'iu');
const PLOT_SIDES=new RegExp(`^${AREA_NUMBER}\\s*[мm]?\\s*(?:[xх×*]|на)\\s*${AREA_NUMBER}\\s*[мm]?$`,'iu');
function areaInput(raw){
 const text=typeof raw==='string'?raw.trim().toLowerCase():'',units=AREA_UNIT.exec(text),sides=PLOT_SIDES.exec(text);
 let hectares=raw;
 if(units){const [,value,unit]=units;hectares=number(value,'area')/(/^(га|ha)$/.test(unit)?1:/^[мm]/.test(unit)?10000:100);}
 if(sides)hectares=number(sides[1],'length')*number(sides[2],'width')/10000;
 return number(hectares,'area',.000001,49999.999);
}
export function label(lang,key,value){
 if(key==='crop')return t(lang,'report_crop_'+value);
 if(key==='irrigation_type')return t(lang,'report_irrig_'+value);
 const labels={sand:['Песок','Құм','Sand'],loam:['Суглинок','Саздақ','Loam'],clay:['Глина','Саз','Clay'],recent:['Недавно поливали / дождь','Жақында суарылды / жаңбыр','Recently watered / rain'],normal:['Обычная влажность','Қалыпты ылғал','Normal moisture'],dry:['Сухая','Құрғақ','Dry'],open:['Открытое поле','Ашық алқап','Open field'],greenhouse:['Теплица','Жылыжай','Greenhouse'],no:['Нет','Жоқ','No'],yes:['Да','Иә','Yes']};
 return labels[value]?.[{ru:0,kz:1,en:2}[lang]]??value;
}
// A planting date (2026-05-15, 15.05.2026, 15.05) or a plain number of days since planting.
export function plantingDays(raw,now=Date.now()) {
 const text=String(raw).trim(),m=text.match(/^(\d{4})-(\d{2})-(\d{2})$/)??null,r=text.match(/^(\d{1,2})[./](\d{1,2})(?:[./](\d{4}))?$/);
 if(!m&&!r)return number(raw,'day',0,3650);
 const today=new Date(now);let y,mo,d;
 if(m){y=+m[1];mo=+m[2];d=+m[3];}else{d=+r[1];mo=+r[2];y=r[3]?+r[3]:today.getUTCFullYear();}
 let t=Date.UTC(y,mo-1,d);if(new Date(t).getUTCMonth()!==mo-1)throw new Error('invalid');
 if(!m&&!r[3]&&t>now)t=Date.UTC(y-1,mo-1,d);   // 15.05 typed in January means last year
 const days=Math.floor((Date.UTC(today.getUTCFullYear(),today.getUTCMonth(),today.getUTCDate())-t)/86400000);
 if(days<0)throw new Error('invalid');return days;
}
export function accept(key,raw,values,now=Date.now()) {
 if(ENUMS[key]){if(!ENUMS[key].includes(raw))throw new Error('invalid');return {[key]:raw};}
 if(key==='area')return {area:areaInput(raw)};
 if(key==='day_of_growth'){
  const stageDays=Object.hasOwn(CROPS,values.crop)?CROPS[values.crop][4]:null;
  if(typeof raw==='string'&&raw.startsWith('stage:')){
   const i=Object.keys(STAGE_LABELS).indexOf(raw.slice(6));
   if(!stageDays||i<0)throw new Error('invalid');
   return {[key]:stageDays.slice(0,i).reduce((a,b)=>a+b,0)+Math.ceil(stageDays[i]/2),growth_estimated:true};
  }
  const day=plantingDays(raw,now);if(!Number.isInteger(day)||(stageDays&&day>stageDays.reduce((a,b)=>a+b,0)))throw new Error('invalid');return {[key]:day,growth_estimated:false};
 }
 if(key==='field_type'){
  if(!Object.hasOwn(FIELD_LABELS,raw))throw new Error('invalid');
  if(raw==='open')return {field_type:'open',greenhouse_medium:'soil',greenhouse_heated:'no',greenhouse_et0:null};
  const unchanged=values.field_type==='greenhouse'&&fieldChoice(values)===raw;
  return {field_type:'greenhouse',greenhouse_medium:raw==='substrate'?'substrate':'soil',greenhouse_heated:raw==='heated'?'yes':'no',greenhouse_et0:unchanged&&raw!=='substrate'?values.greenhouse_et0??null:null};
 }
 if(key==='greenhouse_et0')return {[key]:raw==='skip'?null:number(raw,key,0,50)};
 if(key==='pump'&&raw==='skip')return {power_price:null,pump_power_kw:null,pump_productivity_m3h:null};
 const nums=String(raw).trim().replaceAll(';',' ').split(/\s+/);
 if(key==='location'&&nums.length===2)return {latitude:number(nums[0],'lat',-90,90),longitude:number(nums[1],'lon',-180,180)};
 if(key==='custom'&&nums.length===3)return {custom_kc:number(nums[0],'kc',.05,2),custom_root_depth:number(nums[1],'zr',.05,3),custom_p:number(nums[2],'p',.1,.8)};
 if(key==='pump'&&nums.length===3)return {power_price:number(nums[0],'tariff',0,10000),pump_power_kw:number(nums[1],'power',.000001,100000),pump_productivity_m3h:number(nums[2],'flow',.000001,1e6)};
 throw new Error('invalid');
}
export async function planScreen(id,error=false) {
 const u=await user(id),d=u.draft;if(!d||u.mode!=='plan')return;
 const key=d.refine??steps(d.values)[d.step],lang=u.lang,total=steps(d.values).length;
 const heated=d.values.greenhouse_heated==='yes';
 const prompt=key==='greenhouse_et0'&&heated?'heated_measurement':key;
 let text=`<b>Su-Tech · ${d.refine?q(lang,'refining'):`${d.step+1}/${total}`}</b>\n\n${esc(phrase(lang,prompt))}`;
 const stagePicker=key==='day_of_growth'&&Object.hasOwn(CROPS,d.values.crop);
 if(stagePicker)text+='\n\n'+esc(q(lang,'stage_pick'));
 if(key==='soil_type')text+='\n\n'+esc(q(lang,'soil_type_hint'));
 if(error)text+='\n\n'+esc(phrase(lang,'invalid'));
 if(key==='confirm'){
  const v=d.values;
  const area=v.area<1?`${fmt(v.area*10000,2)} ${tr(lang,'м²','м²','m²')}`:`${fmt(v.area,6)} ${tr(lang,'га','га','ha')}`;
  text+='\n\n'+esc([t(lang,'report_crop_'+v.crop),area,`${v.latitude}, ${v.longitude}`,v.day_of_growth+' '+tr(lang,'дн. с посадки','күн отырғызудан','days since planting'),label(lang,'irrigation_type',v.irrigation_type)].join(' · '));
  text+='\n'+esc(tr(lang,...FIELD_LABELS[fieldChoice(v)]));
  if(v.growth_estimated)text+='\n'+esc(q(lang,'growth_estimated'));
  text+='\n\n<b>'+esc(q(lang,'assumed_title'))+'</b>\n'+assumedLines(lang,v,label).map(x=>'• '+esc(x)).join('\n');
 }
 const cb=x=>`p:${u.generation}:${d.step}:${x}`;
 const rows=(ENUMS[key]??[]).map(x=>[button(label(lang,key,x),cb(x))]);
 if(stagePicker)rows.push(...Object.entries(STAGE_LABELS).map(([stage,labels])=>[button(tr(lang,...labels),cb(`stage:${stage}`))]));
 if(key==='field_type')rows.push(...Object.entries(FIELD_LABELS).map(([choice,labels])=>[button(tr(lang,...labels),cb(choice))]));
 if(key==='crop'){const pairs=[];for(let i=0;i<rows.length;i+=2)pairs.push(rows.slice(i,i+2).flat());rows.splice(0,rows.length,...pairs);}  // 19 crops: two per row
 if(key==='pump')rows.push([button(phrase(lang,'skip'),cb('skip'))]);
 if(key==='greenhouse_et0')rows.push([button(phrase(lang,heated?'no_measurement':'estimate'),cb('skip'))]);
 if(key==='confirm'){
  rows.push([button(phrase(lang,'calculate'),cb('calculate'))]);
  rows.push(...refinements(d.values).map(k=>[button(`${q(lang,'refine')} ${tr(lang,...REFINE_LABEL[k])}`,cb('refine:'+k))]));
 }
 if(d.refine)rows.push([button(q(lang,'done'),cb('back'))]);
 else if(d.step>0)rows.push([button(phrase(lang,'back'),cb('back'))]);
 rows.push(back(lang));await screen(id,text,keyboard(rows),u.generation);
}
export async function planInput(id,raw,expected=null,expectedEpoch=null) {
 const u=await user(id,null,expectedEpoch);if(u.mode!=='plan'||!u.draft)throw new Error('stale');
 if(expected&&(u.generation!==expected.generation||u.draft.step!==expected.step))throw new Error('stale');
 const d=u.draft,key=d.refine??steps(d.values)[d.step];
 if(raw==='back'){if(d.refine)d.refine=null;else d.step=Math.max(0,d.step-1);await saveUser(id,u);await planScreen(id);return;}
 if(key==='confirm'&&raw==='calculate'&&d.values.field_type)return {...DEFAULTS,...d.values,balance_version:2,area_unit:'hectare',lang:u.lang};
 if(key==='confirm'&&String(raw).startsWith('refine:')){
  const k=String(raw).slice(7);if(refinements(d.values).includes(k)){d.refine=k;await saveUser(id,u);await planScreen(id);return null;}
 }
 try{
  Object.assign(d.values,accept(key,raw,d.values));
  if(d.refine)d.refine=null;else d.step++;
  await saveUser(id,u);await planScreen(id);
 }
 catch{await planScreen(id,true);}
 return null;
}
