// FAO-56.5 calculation engine, ported from bot/water_balance.py.
export const VERSION = 'fao56.5';
export const SOILS = {sand:[.12,.05],loam:[.33,.18],clay:[.45,.30]};
export const CROPS = {
  wheat:[.55,.25,1.25,[.30,1.15,.35],[20,25,60,30]],
  cotton:[.65,.25,1.35,[.35,1.18,.65],[30,50,60,55]],
  corn:[.55,.25,1.35,[.30,1.20,.50],[20,35,40,30]],
  alfalfa:[.55,.30,1.50,[.40,1.20,1.15],[10,20,20,10]],
  melon:[.45,.25,1.15,[.45,1.05,.75],[25,35,40,20]],
  tomato:[.40,.25,1.10,[.60,1.15,.80],[30,40,45,30]],
  potato:[.35,.20,.50,[.50,1.15,.75],[25,30,45,30]]
};
export const METHODS = {drip:[5,.90],subsurface:[5,.90],sprinkler:[20,.75],pivot:[20,.75],furrow:[40,.50]};
export class InputError extends Error {}
export function number(v,name,min=0,max=1e6) {
  if (v === null || v === undefined || typeof v === 'boolean' || !['string','number'].includes(typeof v) || String(v).trim()==='') throw new InputError(name);
  const n = Number(String(v).trim().replace(',','.'));
  if (!Number.isFinite(n) || n<min || n>max) throw new InputError(name);
  return n;
}
export function capacity(soil,zr,p) {const [fc,pwp]=SOILS[soil];const taw=1000*(fc-pwp)*zr;return [taw,p*taw];}
export function parameters(crop,day,stages) {
  const [p,zmin,zmax,[ini,mid,end]]=CROPS[crop];const [a,b,c,d]=stages;
  let kc,stage;
  if(day<=a){kc=ini;stage='initial';}
  else if(day<=a+b){kc=ini+(mid-ini)*(day-a)/b;stage='development';}
  else if(day<=a+b+c){kc=mid;stage='middle';}
  else {kc=mid+(end-mid)*Math.min((day-a-b-c)/d,1);stage='late';}
  return {kc,zr:zmin+(zmax-zmin)*Math.min(day/(a+b),1),p,stage};
}
export function parseField(data) {
  if(!data || data.balance_version!==2) throw new InputError('version');
  const crop=data.crop,soil=data.soil_type,method=data.irrigation_type;
  if(!Object.hasOwn(CROPS,crop) && !['rice','other'].includes(crop)) throw new InputError('crop');
  if(!Object.hasOwn(SOILS,soil) || !Object.hasOwn(METHODS,method)) throw new InputError('soil_method');
  const area=number(data.area,'area',.000001,50000),day=number(data.day_of_growth,'day',0,3650);
  if(area>=50000 || !['hectare','sotka'].includes(data.area_unit))throw new InputError('area');
  if(!Number.isInteger(day))throw new InputError('day');
  let stages=[],profile={kc:0,zr:0,p:0,stage:'rice'};
  if(Object.hasOwn(CROPS,crop)) {
    stages=data.stage_days ?? CROPS[crop][4];
    if(!Array.isArray(stages)||stages.length!==4)throw new InputError('stages');
    stages=stages.map(v=>number(v,'stages',1,730));
    if(stages.some(v=>!Number.isInteger(v)))throw new InputError('stages');
    if(day>stages.reduce((a,b)=>a+b,0))throw new InputError('season_ended');
    profile=parameters(crop,day,stages);
  } else if(crop==='other') {
    profile={kc:number(data.custom_kc,'custom_kc',.05,2),zr:number(data.custom_root_depth,'custom_root_depth',.05,3),p:number(data.custom_p,'custom_p',.1,.8),stage:'custom'};
  }
  const factors={recent:0,normal:.5,dry:1};
  if(!Object.hasOwn(factors,data.moisture_condition))throw new InputError('moisture_condition');
  const field_type=data.field_type??'open',saline=data.is_saline??'no';
  if(!['open','greenhouse'].includes(field_type)||!['yes','no'].includes(saline))throw new InputError('field');
  const opt=(k,min,max)=>data[k]===null||data[k]===undefined||data[k]===''?null:number(data[k],k,min,max);
  return {crop,soil,method,area_ha:data.area_unit==='hectare'?area:area/100,day,stages,...profile,
    yesterday:capacity(soil,profile.zr,profile.p)[1]*factors[data.moisture_condition],
    moisture_condition:data.moisture_condition,field_type,saline:saline==='yes',
    power_price:opt('power_price',0,10000),pump_power_kw:opt('pump_power_kw',.000001,100000),
    pump_productivity_m3h:opt('pump_productivity_m3h',.000001,1e6),greenhouse_et0:opt('greenhouse_et0',0,50)};
}
export function economics(gross,deficit,field) {
  const traditional_m3=deficit*10*field.area_ha/METHODS.furrow[1];
  if([field.power_price,field.pump_power_kw,field.pump_productivity_m3h].some(x=>x===null))
    return {traditional_m3,ai_time_hours:null,traditional_time_hours:null,cost:null,traditional_cost:null,savings:null,saved_kwh:null};
  const ai_time_hours=gross/field.pump_productivity_m3h,traditional_time_hours=traditional_m3/field.pump_productivity_m3h;
  const cost=ai_time_hours*field.pump_power_kw*field.power_price,traditional_cost=traditional_time_hours*field.pump_power_kw*field.power_price;
  return {traditional_m3,ai_time_hours,traditional_time_hours,cost,traditional_cost,savings:traditional_cost-cost,saved_kwh:(traditional_time_hours-ai_time_hours)*field.pump_power_kw};
}
export function calculate(field,et0,rain) {
  et0=number(et0,'et0',0,50);rain=number(rain,'rain',0,3000);
  if(field.field_type==='greenhouse'){et0=field.greenhouse_et0??et0*.70;rain=0;}
  if(field.crop==='rice'){
    const seepage={clay:3,loam:6,sand:12}[field.soil],etc=Math.round(et0*1.25*100)/100,peff=rain<5?0:rain*.85;
    const net_mm=Math.max(0,etc+seepage-peff),efficiency=.50,net_m3=net_mm*10*field.area_ha,gross_m3=net_m3/efficiency;
    return {status:'rice',is_rice:true,water_layer_cm:12,seepage,etc,et0,rain,peff,net_mm,efficiency,net_m3,gross_m3,raw:0,deficit:net_mm,threshold:net_mm,...economics(gross_m3,net_mm,field)};
  }
  const [taw,raw]=capacity(field.soil,field.zr,field.p),peff=rain<5?0:rain*.75,etc=et0*field.kc;
  const unbounded=field.yesterday+(etc-peff),deficit=Math.min(taw,Math.max(0,unbounded));
  const [tech_threshold,efficiency]=METHODS[field.method],threshold=Math.min(tech_threshold,raw);
  const status=deficit-raw>1e-9?'critical':deficit>=threshold||Math.abs(deficit-threshold)<=1e-9?'irrigate':'deferred';
  const net_m3=status==='deferred'?0:deficit*10*field.area_ha,gross_m3=net_m3/efficiency;
  return {status,taw,raw,deficit,unbounded,overflow:Math.max(0,unbounded-taw),rain_excess:Math.max(0,-unbounded),et0,rain,peff,etc,kc:field.kc,zr:field.zr,p:field.p,threshold,tech_threshold,efficiency,net_m3,gross_m3,...economics(gross_m3,deficit,field)};
}
export function fieldKey(payload,field) {
  const lat=number(payload.lat??payload.latitude,'latitude',-90,90),lon=number(payload.lon??payload.longitude,'longitude',-180,180);
  return `${lat.toFixed(5)}:${lon.toFixed(5)}:${field.area_ha.toFixed(6)}:${field.crop}`;
}
