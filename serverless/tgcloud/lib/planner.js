import {CROPS,number} from './balance.js';
import {COPY} from './planner-copy.js';
import {user,saveUser} from './store.js';
import {screen,button,keyboard,back} from './ui.js';
import {tr,t,esc} from './i18n.js';
export const ENUMS={crop:[...Object.keys(CROPS),'rice','other'],soil_type:['sand','loam','clay'],moisture_condition:['recent','normal','dry'],irrigation_type:['drip','sprinkler','pivot','furrow','subsurface'],field_type:['open','greenhouse'],is_saline:['no','yes']};
export const steps=v=>['crop','area','location','day_of_growth','soil_type','moisture_condition','irrigation_type','field_type','is_saline',...(v.crop==='other'?['custom']:[]),...(v.field_type==='greenhouse'?['greenhouse_et0']:[]),'pump','confirm'];
const phrase=(lang,key)=>COPY[key][{ru:0,kz:1,en:2}[lang]??0];
export function label(lang,key,value){
 if(key==='crop')return t(lang,'report_crop_'+value);
 if(key==='irrigation_type')return t(lang,'report_irrig_'+value);
 const labels={sand:['Песок','Құм','Sand'],loam:['Суглинок','Саздақ','Loam'],clay:['Глина','Саз','Clay'],recent:['Недавно поливали / дождь','Жақында суарылды / жаңбыр','Recently watered / rain'],normal:['Обычная влажность','Қалыпты ылғал','Normal moisture'],dry:['Сухая','Құрғақ','Dry'],open:['Открытое поле','Ашық алқап','Open field'],greenhouse:['Теплица','Жылыжай','Greenhouse'],no:['Нет','Жоқ','No'],yes:['Да','Иә','Yes']};
 return labels[value]?.[{ru:0,kz:1,en:2}[lang]]??value;
}
export function accept(key,raw,values) {
 if(ENUMS[key]){if(!ENUMS[key].includes(raw))throw new Error('invalid');return {[key]:raw};}
 if(key==='area')return {area:number(raw,'area',.000001,49999.999)};
 if(key==='day_of_growth'){
  const day=number(raw,'day',0,3650);if(!Number.isInteger(day)||(CROPS[values.crop]&&day>CROPS[values.crop][4].reduce((a,b)=>a+b,0)))throw new Error('invalid');return {[key]:day};
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
 const u=await user(id),d=u.draft,key=steps(d.values)[d.step],lang=u.lang;
 let text=`<b>Su-Tech · ${d.step+1}/${steps(d.values).length}</b>\n\n${esc(phrase(lang,key))}`;
 if(error)text+='\n\n'+esc(phrase(lang,'invalid'));
 if(key==='confirm')text+='\n\n'+esc([t(lang,'report_crop_'+d.values.crop),d.values.area+' ha',`${d.values.latitude}, ${d.values.longitude}`,d.values.day_of_growth+' d',label(lang,'soil_type',d.values.soil_type),label(lang,'moisture_condition',d.values.moisture_condition),t(lang,'report_irrig_'+d.values.irrigation_type),label(lang,'field_type',d.values.field_type)].join('\n'));
 const cb=v=>`p:${u.generation}:${d.step}:${v}`;
 const rows=(ENUMS[key]??[]).map(v=>[button(label(lang,key,v),cb(v))]);
 if(['pump','greenhouse_et0'].includes(key))rows.push([button(phrase(lang,key==='pump'?'skip':'estimate'),cb('skip'))]);
 if(key==='confirm')rows.push([button(phrase(lang,'calculate'),cb('calculate'))]);
 if(d.step>0)rows.push([button(phrase(lang,'back'),cb('back'))]);
 rows.push(back(lang));await screen(id,text,keyboard(rows));
}
export async function planInput(id,raw,expected=null) {
 const u=await user(id);if(u.mode!=='plan'||!u.draft)throw new Error('stale');
 if(expected&&(u.generation!==expected.generation||u.draft.step!==expected.step))throw new Error('stale');
 const d=u.draft,key=steps(d.values)[d.step];
 if(raw==='back'){d.step=Math.max(0,d.step-1);await saveUser(id,u);await planScreen(id);return;}
 if(key==='confirm'&&raw==='calculate')return {...d.values,balance_version:2,area_unit:'hectare',lang:u.lang};
 try{Object.assign(d.values,accept(key,raw,d.values));d.step++;await saveUser(id,u);await planScreen(id);}
 catch{await planScreen(id,true);}
 return null;
}
