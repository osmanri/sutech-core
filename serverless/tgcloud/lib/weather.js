import {fetch} from 'sdk';
import {number} from './balance.js';
import {get,put} from './store.js';
// Completed days are taken from the provider's past days (model analysis, not a field sensor),
// so missed days can be closed in order instead of being skipped.
export const PAST_DAYS=30;
export function validateWeather(data) {
  const times=data?.daily?.time,units=data?.daily_units;
  if(!Array.isArray(times)||!times.length||times.some(d=>!/^\d{4}-\d{2}-\d{2}$/.test(d??''))||units?.et0_fao_evapotranspiration!=='mm'||units?.precipitation_sum!=='mm')throw new Error('weather');
  const localDay=new Date(Date.now()+(Number(data.utc_offset_seconds)||0)*1000).toISOString().slice(0,10);
  const i=times.indexOf(localDay);if(i<0)throw new Error('weather');
  const et0s=data.daily.et0_fao_evapotranspiration??[],rains=data.daily.precipitation_sum??[];
  const et0=number(et0s[i],'weather',0,50),rain=number(rains[i],'weather',0,3000);
  const history=[];
  for(let k=0;k<i;k++){
    if(et0s[k]===null||et0s[k]===undefined||rains[k]===null||rains[k]===undefined)continue; // a missing day stays a gap
    history.push({day:times[k],et0:number(et0s[k],'weather',0,50),rain:number(rains[k],'weather',0,3000)});
  }
  return {day:localDay,et0,rain,timezone:data.timezone,utc_offset_seconds:data.utc_offset_seconds,history};
}
export async function weather(lat,lon) {
  lat=number(lat,'latitude',-90,90);lon=number(lon,'longitude',-180,180);
  const id=`weather:v2:${lat.toFixed(4)}:${lon.toFixed(4)}`,cached=await get(id,0);
  if(cached&&Date.now()-cached._updated<900000&&new Date(Date.now()+(cached.utc_offset_seconds??0)*1000).toISOString().slice(0,10)===cached.day)return cached;
  const url=`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&daily=et0_fao_evapotranspiration,precipitation_sum&timezone=auto&forecast_days=1&past_days=${PAST_DAYS}`;
  try {const r=await fetch(url);if(!r.ok)throw new Error('weather');const data=validateWeather(await r.json());await put(id,0,'weather',data);return data;}
  catch {throw new Error('weather');}
}
