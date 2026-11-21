import {CROPS,number} from './balance.js';
import {COPY} from './planner-copy.js';
import {user,saveUser} from './store.js';
import {screen,button,keyboard,back} from './ui.js';
import {tr,t,esc} from './i18n.js';
import {DEFAULTS,REFINE,REFINE_LABEL,QUESTION,q,assumedLines} from './planner-extra.js';
export const ENUMS={crop:[...Object.keys(CROPS),'rice','other'],soil_type:['sand','loam','clay'],moisture_condition:['recent','normal','dry'],irrigation_type:['drip','sprinkler','pivot','furrow','subsurface'],field_type:['open','greenhouse'],is_saline:['no','yes']};
export const steps=v=>['crop','area','location','day_of_growth','irrigation_type',...(v.crop==='other'?['custom']:[]),'confirm'];
const phrase=(lang,key)=>(QUESTION[key]??COPY[key])[{ru:0,kz:1,en:2}[lang]??0];
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
 if(key==='area')return {area:number(raw,'area',.000001,49999.999)};
 if(key==='day_of_growth'){
  const day=plantingDays(raw,now);if(!Number.isInteger(day)||(CROPS[values.crop]&&day>CROPS[values.crop][4].reduce((a,b)=>a+b,0)))throw new Error('invalid');return {[key]:day};
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
 let text=`<b>Su-Tech · ${d.refine?q(lang,'refining'):`${d.step+1}/${total}`}</b>\n\n${esc(phrase(lang,key))}`;
 if(key==='soil_type')text+='\n\n'+esc(q(lang,'soil_type_hint'));
 if(error)text+='\n\n'+esc(phrase(lang,'invalid'));
 if(key==='confirm'){
  const v=d.values;
  text+='\n\n'+esc([t(lang,'report_crop_'+v.crop),v.area+' ha',`${v.latitude}, ${v.longitude}`,v.day_of_growth+' '+tr(lang,'дн. с посадки','күн отырғызудан','days since planting'),label(lang,'irrigation_type',v.irrigation_type)].join(' · '));
  text+='\n\n<b>'+esc(q(lang,'assumed_title'))+'</b>\n'+assumedLines(lang,v,label).map(x=>'• '+esc(x)).join('\n');
 }
 const cb=x=>`p:${u.generation}:${d.step}:${x}`;
 const rows=(ENUMS[key]??[]).map(x=>[button(label(lang,key,x),cb(x))]);
 if(key==='crop'){const pairs=[];for(let i=0;i<rows.length;i+=2)pairs.push(rows.slice(i,i+2).flat());rows.splice(0,rows.length,...pairs);}  // 19 crops: two per row
 if(['pump','greenhouse_et0'].includes(key))rows.push([button(phrase(lang,key==='pump'?'skip':'estimate'),cb('skip'))]);
 if(key==='confirm'){
  rows.push([button(phrase(lang,'calculate'),cb('calculate'))]);
  rows.push(...REFINE.map(k=>[button(`${q(lang,'refine')} ${tr(lang,...REFINE_LABEL[k])}`,cb('refine:'+k))]));
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
 if(key==='confirm'&&raw==='calculate')return {...DEFAULTS,...d.values,balance_version:2,area_unit:'hectare',lang:u.lang};
 if(key==='confirm'&&String(raw).startsWith('refine:')){
  const k=String(raw).slice(7);if(REFINE.includes(k)){d.refine=k;await saveUser(id,u);await planScreen(id);return null;}
 }
 try{
  Object.assign(d.values,accept(key,raw,d.values));
  if(d.refine)d.refine=d.refine==='field_type'&&d.values.field_type==='greenhouse'&&key==='field_type'?'greenhouse_et0':null;else d.step++;
  await saveUser(id,u);await planScreen(id);
 }
 catch{await planScreen(id,true);}
 return null;
}
