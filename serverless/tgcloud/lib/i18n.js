import {STRINGS,AI_STRINGS} from './copy.js';
export const language=v=>['ru','kz','en'].includes(v)?v:v==='kk'?'kz':'ru';
export const tr=(lang,ru,kz,en)=>({ru,kz,en}[language(lang)]);
export function t(lang,key,params={}) {
  const text=STRINGS[language(lang)]?.[key]??STRINGS.ru[key]??key;
  return typeof text==='string'?text.replace(/\{(\w+)\}/g,(m,k)=>Object.hasOwn(params,k)?String(params[k]):m):text;
}
export const a=(lang,key)=>AI_STRINGS[language(lang)]?.[key]??AI_STRINGS.ru[key]??key;
export const esc=v=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
export function fmt(n,d=2){return Number(n).toLocaleString('en-US',{maximumFractionDigits:d,useGrouping:false});}
export const volume=(n,lang)=>n>0&&n<1?`${fmt(n*1000,1)} ${tr(lang,'л','л','L')}`:`${fmt(n)} ${tr(lang,'м³','м³','m³')}`;
