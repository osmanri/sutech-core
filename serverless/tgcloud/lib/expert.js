// Expert mode: an agronomist may override the table values for ONE field (p, root depth, a Kc multiplier).
// The override is stored on the field with who/when, applied on top of the FAO-56 numbers, and always shown as
// "changed manually" so nobody mistakes it for the table. Nothing here touches the shared engine in balance.js.
import {parseField as baseParse,CROPS,InputError,number} from './balance.js';
export const LIMITS={p:[.1,.8],root_depth:[.1,3],kc_factor:[.5,1.5]};
export const KEYS=Object.keys(LIMITS);
export function cleanExpert(e) {
  const out={};
  for(const k of KEYS){const v=e?.[k];if(v!==null&&v!==undefined&&v!=='')out[k]=number(v,k,...LIMITS[k]);}
  return out;
}
// Same as parseField, plus the overrides. `fao` keeps the table values for display; `manual` lists what was changed.
export function parseField(payload) {
  const f=baseParse(payload);
  if(!Object.hasOwn(CROPS,f.crop))return {...f,manual:[],fao:null};
  const e=cleanExpert(payload.expert),fao={kc:f.kc,zr:f.zr,p:f.p},manual=[];
  if(e.kc_factor!==undefined){f.kc=fao.kc*e.kc_factor;manual.push('kc_factor');}
  if(e.root_depth!==undefined){f.zr=e.root_depth;manual.push('root_depth');}
  if(e.p!==undefined){f.p=e.p;manual.push('p');}
  return {...f,manual,fao,expert:e};
}
export function describe(field,lang,tr,fmt) {
  const L=[];
  if(field.manual.includes('p'))L.push(`p ${fmt(field.p,2)} (${tr(lang,'таблица','кесте','table')} ${fmt(field.fao.p,2)})`);
  if(field.manual.includes('root_depth'))L.push(`${tr(lang,'корни','тамыр','roots')} ${fmt(field.zr,2)} ${tr(lang,'м','м','m')} (${tr(lang,'таблица','кесте','table')} ${fmt(field.fao.zr,2)})`);
  if(field.manual.includes('kc_factor'))L.push(`Kc × ${fmt(field.expert.kc_factor,2)} (${tr(lang,'таблица','кесте','table')} ${fmt(field.fao.kc,2)} → ${fmt(field.kc,2)})`);
  return L;
}
export {InputError};
