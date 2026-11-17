import test from 'node:test';
import assert from 'node:assert/strict';
import {calculate,parseField,SALT_TOLERANCE} from '../tgcloud/lib/balance.js';
import {currentResult} from '../tgcloud/lib/fields.js';

const f=(c={})=>parseField({balance_version:2,crop:'corn',soil_type:'loam',irrigation_type:'drip',area:1,area_unit:'hectare',day_of_growth:60,moisture_condition:'dry',...c});
const run=(c)=>calculate(f(c),6,0);

test('salt tolerance table equals FAO-56 Table 23 values',()=>{
  assert.deepEqual(SALT_TOLERANCE.cotton,[7.7,5.2]);assert.deepEqual(SALT_TOLERANCE.corn,[1.7,12.0]);assert.deepEqual(SALT_TOLERANCE.wheat,[6.0,7.1]);
  assert.equal(SALT_TOLERANCE.melon,undefined);
});
test('FAO-29 example 3: maize ECw 1.2 dS/m -> LR 0.164, extra water on drip only',()=>{
  const plain=run(),drip=run({water_ec:1.2});
  assert.ok(Math.abs(drip.leaching_fraction-1.2/(5*1.7-1.2))<1e-12);
  assert.ok(Math.abs(drip.gross_m3/plain.gross_m3-.9/(1-1.2/7.3))<1e-9);
  assert.equal(run({irrigation_type:'furrow',water_ec:1.2}).gross_m3,run({irrigation_type:'furrow'}).gross_m3);
});
test('cotton with good water needs nothing extra; too salty water is flagged',()=>{
  assert.equal(run({crop:'cotton',water_ec:3}).gross_m3,run({crop:'cotton'}).gross_m3);
  assert.equal(run({water_ec:9}).leaching_impossible,true);assert.equal(run({water_ec:9}).leaching_fraction,null);
});
test('salt yield loss from measured ECe, none invented without measurements, none for melon',()=>{
  assert.ok(Math.abs(run({soil_ec:4.7}).salinity_yield_loss_pct-36)<1e-9);
  assert.equal(run({crop:'cotton',soil_ec:7}).salinity_yield_loss_pct,0);
  assert.equal(run({soil_ec:50}).salinity_yield_loss_pct,100);
  const r=run({is_saline:'yes'});assert.equal(r.leaching_fraction,null);assert.equal(r.salinity_yield_loss_pct,null);
  assert.equal(run({crop:'melon',water_ec:2,soil_ec:3}).leaching_fraction,null);
  for(const bad of [{water_ec:-1},{water_ec:26},{soil_ec:51},{water_ec:'abc'}])assert.throws(()=>f(bad));
});
test('stored-field view keeps the leaching volume',()=>{
  const p={balance_version:2,crop:'corn',soil_type:'loam',irrigation_type:'drip',area:1,area_unit:'hectare',day_of_growth:60,moisture_condition:'dry',water_ec:1.2};
  const r=calculate(parseField(p),6,0);
  const row={payload:p,result:r,deficit:r.deficit};
  const shown=currentResult(row);
  assert.ok(Math.abs(shown.gross_m3-r.gross_m3)<1e-9);assert.ok(Math.abs(shown.leaching_fraction-r.leaching_fraction)<1e-12);
});
import {report} from '../tgcloud/lib/fields.js';
test('the field report says what was added for leaching and the salt yield loss, in all languages',()=>{
  const p={balance_version:2,crop:'corn',soil_type:'loam',irrigation_type:'drip',area:1,area_unit:'hectare',day_of_growth:60,moisture_condition:'dry',water_ec:1.2,soil_ec:4.7};
  const r=calculate(parseField(p),6,0),row={payload:p,result:r,deficit:r.deficit,last_day:'2026-11-17',weather:{timezone:'Asia/Almaty'}};
  for(const lang of ['ru','kz','en']){const text=report(row,lang);assert.match(text,/🧂/);assert.match(text,/16[.,]4/);assert.match(text,/36/);}
  const none=report({...row,payload:{...p,water_ec:undefined,soil_ec:undefined},result:calculate(parseField({...p,water_ec:undefined,soil_ec:undefined}),6,0)},'en');
  assert.doesNotMatch(none,/🧂/);
});
