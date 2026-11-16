// Day logic: missed days are closed in order, forecasts never become history, actions replay,
// legacy rows migrate, and re-submitted fields are not silently ignored.
import test from 'node:test';
import assert from 'node:assert/strict';
import {setFetch} from 'sdk';
import {put,get} from '../tgcloud/lib/store.js';
import {calculateField,refresh,waterField,checkMoisture,ownedField,currentResult} from '../tgcloud/lib/fields.js';
import {calculate,parseField} from '../tgcloud/lib/balance.js';
import {validateWeather} from '../tgcloud/lib/weather.js';

const REAL=Date.now.bind(Date),OFF=18000;let shift=0;
const iso=(n=0)=>new Date(REAL()+shift+OFF*1000+n*86400000).toISOString().slice(0,10);
// days: {offset: [et0, rain]} relative to "today"; offset 0 is today's forecast.
function serve(days){setFetch(async()=>{const keys=Object.keys(days).map(Number).sort((a,b)=>a-b);
  return {ok:true,json:async()=>({timezone:'Asia/Almaty',utc_offset_seconds:OFF,daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},
    daily:{time:keys.map(k=>iso(k)),et0_fao_evapotranspiration:keys.map(k=>days[k]?.[0]??null),precipitation_sum:keys.map(k=>days[k]?.[1]??null)}})};});}
function travel(n){shift=n*86400000;Date.now=()=>REAL()+shift;}
function home(){shift=0;Date.now=REAL;}
let lat=40;const base=()=>({balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:1,area_unit:'hectare',day_of_growth:50,moisture_condition:'normal',latitude:lat+=0.01,longitude:68.3,field_type:'open'});
const etcOf=(p,day,start,et0)=>{const f=parseField({...p,day_of_growth:day});f.yesterday=start;return calculate(f,et0,0);};

test('weather keeps completed past days and today separately',()=>{
  shift=0;const d={timezone:'X',utc_offset_seconds:OFF,daily_units:{et0_fao_evapotranspiration:'mm',precipitation_sum:'mm'},daily:{time:[iso(-2),iso(-1),iso(0)],et0_fao_evapotranspiration:[4,null,6],precipitation_sum:[0,1,2]}};
  const w=validateWeather(d);assert.equal(w.day,iso(0));assert.equal(w.et0,6);
  assert.deepEqual(w.history,[{day:iso(-2),et0:4,rain:0}],'a day with missing data is left out, not zeroed');
});

test('missed days are closed one by one with that day\'s weather',async()=>{
  const p=base();serve({0:[6,0]});const a=await calculateField(801,p);
  travel(4);try{
    serve({'-4':[6,0],'-3':[6,0],'-2':[6,0],'-1':[6,0],0:[6,0]});
    const r=await refresh(801,a.id);
    let d=a.closed_deficit;for(let k=0;k<=4;k++)d=etcOf(p,50+k,d,6).deficit;
    assert.ok(Math.abs(r.deficit-d)<1e-9,`expected ${d}, got ${r.deficit}`);
    assert.ok(r.deficit-a.deficit>4*5,'four more days of water use are counted, not one');
    assert.equal(r.gap_days,0);assert.equal(r.closed_day,iso(-1));
  }finally{home();}
});

test('a forecast rain that did not fall is not kept as soil water',async()=>{
  const p=base();serve({0:[6,20]});const a=await calculateField(802,p);
  assert.ok(a.result.peff>0,'today the forecast rain is used for advice');
  travel(1);try{
    serve({'-1':[6,0],0:[6,0]});const r=await refresh(802,a.id);
    const day0=etcOf(p,50,a.closed_deficit,6).deficit,expect=etcOf(p,51,day0,6).deficit;
    assert.ok(Math.abs(r.deficit-expect)<1e-9,'yesterday is re-closed with the rain that actually fell (none)');
  }finally{home();}
});

test('an updated forecast during the same day replaces, never adds',async()=>{
  const p=base();serve({0:[4,0]});const a=await calculateField(803,p);
  serve({0:[7,0]});await put(`weather:v2:${p.latitude.toFixed(4)}:${p.longitude.toFixed(4)}`,0,'weather',{day:'2000-01-01'}); // expire the 15-min cache
  const r=await refresh(803,a.id);
  assert.ok(Math.abs(r.deficit-etcOf(p,50,a.closed_deficit,7).deficit)<1e-9);
  const again=await refresh(803,a.id);assert.equal(again.deficit,r.deficit);
});

test('watering and soil checks of a day survive when that day is closed',async()=>{
  const p=base();serve({0:[6,0]});const a=await calculateField(804,p);
  const w=await waterField(804,a.id,0.2,a.deficit,a.revision);           // 0.2 m3 gross on 1 ha drip = 0.018 mm net
  assert.ok(Math.abs(w.deficit-(a.deficit-0.2*0.9/10))<1e-9);
  const c=await checkMoisture(804,a.id,'wet');assert.equal(c.deficit,0);
  travel(1);try{
    serve({'-1':[6,0],0:[5,0]});const r=await refresh(804,a.id);
    assert.equal(r.closed_deficit,0,'the wet check closed yesterday at 0');
    assert.ok(Math.abs(r.deficit-etcOf(p,51,0,5).deficit)<1e-9);
  }finally{home();}
});

test('a day without provider data is reported as a gap and only its logged actions apply',async()=>{
  const p=base();serve({0:[6,0]});const a=await calculateField(805,p);
  travel(2);try{
    serve({'-2':[6,0],'-1':[null,null],0:[6,0]});const r=await refresh(805,a.id);
    assert.equal(r.gap_days,1);
  }finally{home();}
});

test('legacy rows migrate: past last_day is accepted as closed, today is rebuilt from its start state',async()=>{
  const p={...base(),planting:undefined};delete p.planting;
  const f=parseField(p),res=calculate(f,5,0);
  await put('field:880',806,'field',{id:880,payload:p,result:res,deficit:res.deficit,planting:iso(-50),last_day:iso(-1),revision:3,events:[]});
  serve({'-1':[5,0],0:[5,0]});
  const r=await refresh(806,880);
  assert.equal(r.migrated_from,'legacy');assert.ok(Math.abs(r.deficit-etcOf(p,50,res.deficit,5).deficit)<1e-9);
  await put('field:881',806,'field',{id:881,payload:p,result:res,deficit:res.deficit,planting:iso(-50),last_day:iso(0),revision:3,events:[]});
  const t=await refresh(806,881);
  assert.ok(Math.abs(t.closed_deficit-f.yesterday)<1e-9,'start of today recovered from the stored calculation');
  assert.ok(Math.abs(t.deficit-res.deficit)<1e-9,'same day, same weather: unchanged deficit');
});

test('re-submitted field: changed soil restarts, changed pump keeps the balance, unchanged says so',async()=>{
  const p=base();serve({0:[6,0]});const a=await calculateField(807,p);
  await waterField(807,a.id,5,a.deficit,a.revision);
  const same=await calculateField(807,{...p,moisture_condition:'dry'});
  assert.equal(same.submit,'existing');assert.equal(same.id,a.id);
  const pump=await calculateField(807,{...p,power_price:25,pump_power_kw:10,pump_productivity_m3h:30});
  assert.equal(pump.submit,'costs');assert.equal(pump.deficit,same.deficit);assert.ok(currentResult(pump).cost!==null||pump.deficit===0);
  const reset=await calculateField(807,{...p,soil_type:'sand',irrigation_type:'furrow'});
  assert.equal(reset.submit,'reset');assert.equal(reset.id,a.id);
  assert.equal((await ownedField(807,a.id)).payload.soil_type,'sand');
  assert.ok(Math.abs(reset.deficit-etcOf({...p,soil_type:'sand',irrigation_type:'furrow'},50,parseField({...p,soil_type:'sand',irrigation_type:'furrow'}).yesterday,6).deficit)<1e-9,
    'the earlier watering is not replayed into the restarted balance');
  void get;
});

test('re-sending the same field with a stale day count does not wipe the balance',async()=>{
  const p=base();serve({0:[6,0]});const a=await calculateField(808,p);
  travel(7);try{
    serve({'-7':[6,0],'-6':[6,0],'-5':[6,0],'-4':[6,0],'-3':[6,0],'-2':[6,0],'-1':[6,0],0:[6,0]});
    const r=await calculateField(808,p);            // day_of_growth still 50 from the old draft
    assert.equal(r.submit,'existing');assert.equal(r.payload.day_of_growth,57);assert.ok(r.deficit>a.deficit);
  }finally{home();}
});
