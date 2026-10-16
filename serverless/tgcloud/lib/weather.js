import {fetch} from 'sdk';
import {number} from './balance.js';
import {get,put} from './store.js';
export function validateWeather(data) {
  const day=data?.daily?.time?.[0],units=data?.daily_units;
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day??'')||units?.et0_fao_evapotranspiration!=='mm'||units?.precipitation_sum!=='mm')throw new Error('weather');
  const et0=number(data.daily.et0_fao_evapotranspiration?.[0],'weather',0,50),rain=number(data.daily.precipitation_sum?.[0],'weather',0,3000);
  const localDay=new Date(Date.now()+(Number(data.utc_offset_seconds)||0)*1000).toISOString().slice(0,10);
  if(localDay!==day)throw new Error('weather');
  return {day,et0,rain,timezone:data.timezone,utc_offset_seconds:data.utc_offset_seconds};
}
export async function weather(lat,lon) {
  lat=number(lat,'latitude',-90,90);lon=number(lon,'longitude',-180,180);
  const id=`weather:${lat.toFixed(4)}:${lon.toFixed(4)}`,cached=await get(id,0);
  if(cached&&Date.now()-cached._updated<900000&&new Date(Date.now()+(cached.utc_offset_seconds??0)*1000).toISOString().slice(0,10)===cached.day)return cached;
  const url=`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&daily=et0_fao_evapotranspiration,precipitation_sum&timezone=auto&forecast_days=1`;
  try {const r=await fetch(url);if(!r.ok)throw new Error('weather');const data=validateWeather(await r.json());await put(id,0,'weather',data);return data;}
  catch {throw new Error('weather');}
}
