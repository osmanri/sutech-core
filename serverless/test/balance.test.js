import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {calculate,parseField,fieldKey} from '../tgcloud/lib/balance.js';
const fixtures=JSON.parse(fs.readFileSync(new URL('./balance-fixtures.json',import.meta.url)));
for (const [i,fixture] of fixtures.entries()) test(`Python FAO-56 reference scenario ${i}`,()=>{
  const got=calculate(parseField(fixture.payload),fixture.et0,fixture.rain);
  for(const [key,expected] of Object.entries(fixture.result)) {
    if(typeof expected==='number')assert.ok(Math.abs(got[key]-expected)<=1e-8*Math.max(1,Math.abs(expected)),`${key}: ${got[key]} vs ${expected}`);
    else assert.equal(got[key],expected,key);
  }
});
test('rejects malformed inputs, prototype keys and absent GPS',()=>{
  const p=fixtures[0].payload;
  for(const change of [{area:true},{balance_version:'2'},{crop:'constructor'},{soil_type:'__proto__'},{moisture_condition:'constructor'},{day_of_growth:2.4},{area:50000},{area:''}])assert.throws(()=>parseField({...p,...change}));
  assert.throws(()=>fieldKey({...p,lat:undefined,lon:undefined},parseField(p)));
});
test('same method never receives a fabricated water saving',()=>{
 const p={...fixtures[0].payload,irrigation_type:'furrow',moisture_condition:'dry'};
 const r=calculate(parseField(p),9,0);assert.ok(Math.abs(r.gross_m3-r.traditional_m3)<1e-9);
});
