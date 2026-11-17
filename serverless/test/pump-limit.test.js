import test from 'node:test';
import assert from 'node:assert/strict';
import {calculate,parseField,economics,PUMP_MAX_HOURS_PER_DAY} from '../tgcloud/lib/balance.js';
import {demoScreen} from '../tgcloud/lib/demo.js';

const payload=(c={})=>({balance_version:2,crop:'cotton',soil_type:'loam',irrigation_type:'drip',area:10,area_unit:'hectare',day_of_growth:90,moisture_condition:'dry',pump_power_kw:22,pump_productivity_m3h:60,power_price:25,...c});

test('10 ha cotton on drip needs 13 pumping days at 20 h/day (same as the Python engine)',()=>{
  const r=calculate(parseField(payload()),7,0);
  assert.ok(Math.abs(r.gross_m3-15543)<1);
  assert.equal(r.max_daily_m3,60*PUMP_MAX_HOURS_PER_DAY);
  assert.equal(r.irrigation_days,13);
  assert.ok(r.gross_m3/r.irrigation_days<=r.max_daily_m3);
});
test('boundaries: exactly one day is one day, nothing is zero, no pump data is null',()=>{
  const f=parseField(payload());
  assert.equal(economics(1200,100,f).irrigation_days,1);
  assert.equal(economics(1200.5,100,f).irrigation_days,2);
  assert.equal(economics(0,0,f).irrigation_days,0);
  const noPump=parseField(payload({pump_power_kw:null,pump_productivity_m3h:null,power_price:null}));
  assert.equal(economics(5000,100,noPump).irrigation_days,null);
});
test('the bot demo shows the split warning in all languages (1 210 m3 vs 1 200 m3 a day)',()=>{
  for(const lang of ['ru','kz','en'])assert.match(demoScreen(lang).text,/⚠️/);
});
