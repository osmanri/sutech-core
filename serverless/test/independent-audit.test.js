// Independent re-derivation of every bot calculation straight from FAO-56 definitions,
// written without reusing balance.js internals, then compared on random inputs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {calculate,parseField,SOILS,CROPS,METHODS} from '../tgcloud/lib/balance.js';
import {currentResult} from '../tgcloud/lib/fields.js';
import {volume} from '../tgcloud/lib/i18n.js';

// --- reference implementation (FAO-56 chapter 8 + project rules stated in the docs) ---
function refKc([ini,mid,end],[a,b,c,d],day){
  if(day<=a)return ini;                                   // initial stage: constant
  if(day<=a+b)return ini+(day-a)/b*(mid-ini);             // FAO-56 eq. 66, linear development
  if(day<=a+b+c)return mid;
  return mid+Math.min(1,(day-a-b-c)/d)*(end-mid);         // eq. 66, linear late season
}
function ref(field,et0,rain){
  const [fc,wp]=SOILS[field.soil];
  const taw=1000*(fc-wp)*field.zr;                        // eq. 82, mm
  const raw=field.p*taw;                                  // eq. 83
  const dr0=field.yesterday;
  const ks=dr0>raw?Math.max(0,(taw-dr0)/((1-field.p)*taw)):1; // eq. 84
  const peff=rain>=5?0.75*rain:0;                         // project rule (not FAO)
  const etc=ks*field.kc*et0;
  const dr=Math.min(taw,Math.max(0,dr0+etc-peff));        // eq. 85 without RO, CR, DP terms
  const [tech,eff]=METHODS[field.method];
  const trigger=Math.min(tech,raw);
  const status=dr>raw+1e-9?'critical':dr>=trigger-1e-9?'irrigate':'deferred';
  const netM3=status==='deferred'?0:dr*10*field.area_ha;  // 1 mm over 1 ha = 10 m3
  const grossM3=netM3/eff;
  let cost=null;
  if(field.power_price!==null&&field.pump_power_kw!==null&&field.pump_productivity_m3h!==null)
    cost=grossM3/field.pump_productivity_m3h*field.pump_power_kw*field.power_price; // h * kW * tg/kWh
  return {taw,raw,ks,etc,peff,deficit:dr,status,net_m3:netM3,gross_m3:grossM3,cost};
}
let seed=20261115;const rnd=()=>((seed=(seed*1103515245+12345)%2147483648)/2147483648);
const pick=a=>a[Math.floor(rnd()*a.length)];
function randomPayload(){
  const crop=pick(Object.keys(CROPS)),season=CROPS[crop][4].reduce((x,y)=>x+y,0);
  return {balance_version:2,crop,soil_type:pick(Object.keys(SOILS)),irrigation_type:pick(Object.keys(METHODS)),
    area:+(rnd()*200+0.01).toFixed(3),area_unit:pick(['hectare','sotka']),day_of_growth:Math.floor(rnd()*(season+1)),
    moisture_condition:pick(['recent','normal','dry']),field_type:'open',is_saline:'no',
    ...(rnd()<.7?{power_price:+(rnd()*60).toFixed(2),pump_power_kw:+(rnd()*90+.5).toFixed(2),pump_productivity_m3h:+(rnd()*200+1).toFixed(2)}:{})};
}
const close=(a,b,msg)=>assert.ok(Math.abs(a-b)<=1e-9*Math.max(1,Math.abs(b)),`${msg}: bot ${a} vs reference ${b}`);

test('5000 random fields: bot equals an independent FAO-56 re-derivation',()=>{
  for(let i=0;i<5000;i++){
    const p=randomPayload(),f=parseField(p);
    if(rnd()<.5)f.yesterday=rnd()*1.1*1000*(SOILS[f.soil][0]-SOILS[f.soil][1])*f.zr; // include stressed starts
    const et0=+(rnd()*12).toFixed(2),rain=rnd()<.3?+(rnd()*40).toFixed(1):0;
    const bot=calculate(f,et0,rain),r=ref(f,et0,rain),ctx=JSON.stringify({p,yesterday:f.yesterday,et0,rain});
    for(const k of ['taw','raw','ks','etc','peff','deficit','net_m3','gross_m3'])close(bot[k],r[k],`${k} ${ctx}`);
    assert.equal(bot.status,r.status,ctx);
    if(r.cost===null)assert.equal(bot.cost,null);else close(bot.cost,r.cost,`cost ${ctx}`);
    close(f.kc,refKc(CROPS[f.crop][3],CROPS[f.crop][4],f.day),'Kc');
    assert.equal(f.area_ha,p.area_unit==='hectare'?p.area:p.area/100,'1 sotka = 0.01 ha');
  }
});
test('hand-computed reference cases',()=>{
  // Wheat day 60, loam, drip, 1 ha, dry start: TAW 187.5, RAW 103.125, ETc 1.15*5, deficit 108.875 (CALCULATION_AUDIT.md)
  const f=parseField({balance_version:2,crop:'wheat',soil_type:'loam',irrigation_type:'drip',area:1,area_unit:'hectare',day_of_growth:60,moisture_condition:'dry',power_price:25,pump_power_kw:22,pump_productivity_m3h:60});
  const r=calculate(f,5,0);
  close(r.taw,187.5,'TAW');close(r.raw,103.125,'RAW');close(r.etc,5.75,'ETc');close(r.deficit,108.875,'Dr');
  assert.equal(r.status,'critical');close(r.gross_m3,1088.75/0.9,'gross m3');
  close(r.cost,1088.75/0.9/60*22*25,'cost tg');
  // 30 m3 of rain-free demand is not booked twice: rain 4.9 mm is ignored, 5 mm counts 3.75 mm
  close(calculate(f,0,4.9).peff,0,'rain < 5 mm');close(calculate(f,0,5).peff,3.75,'rain 5 mm');
  // 20 sotka = 0.2 ha
  assert.equal(parseField({...f.payload,balance_version:2,crop:'wheat',soil_type:'loam',irrigation_type:'drip',area:20,area_unit:'sotka',day_of_growth:60,moisture_condition:'dry'}).area_ha,0.2);
});
test('display: volumes below 1 m3 are shown in litres, never rounded to zero',()=>{
  assert.equal(volume(0.25,'ru'),'250 л');assert.equal(volume(0.0004,'en'),'0.4 L');assert.equal(volume(12.345,'en'),'12.35 m³');
});
test('stored-field view recomputes status and volume from the current deficit only',()=>{
  const p={balance_version:2,crop:'tomato',soil_type:'sand',irrigation_type:'furrow',area:.5,area_unit:'hectare',day_of_growth:40,moisture_condition:'normal'};
  const f=parseField(p),base=calculate(f,6,0);
  for(const d of [0,base.threshold-1e-6,base.threshold,base.raw,base.raw+1]){
    const cur=currentResult({payload:p,result:base,deficit:d}),g={...f,yesterday:0};
    const want=d-base.raw>1e-9?'critical':d>=base.threshold-1e-9?'irrigate':'deferred';
    assert.equal(cur.status,want,`deficit ${d}`);
    close(cur.gross_m3,want==='deferred'?0:d*10*f.area_ha/METHODS.furrow[1],'gross');
    void g;
  }
});
