import test from 'node:test';
import assert from 'node:assert/strict';
import {calculate,parseField} from '../tgcloud/lib/balance.js';
import {currentResult,report} from '../tgcloud/lib/fields.js';

const f=(c={})=>parseField({balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:0.1,area_unit:'hectare',day_of_growth:60,moisture_condition:'dry',field_type:'greenhouse',...c});

test('unheated soil greenhouse gets the estimate; substrate and heated-without-measurement get none',()=>{
  const ok=calculate(f(),6,0);assert.notEqual(ok.status,'unsupported');assert.ok(ok.gross_m3>0);
  const sub=calculate(f({greenhouse_medium:'substrate'}),6,0);
  assert.deepEqual([sub.status,sub.unsupported_reason,sub.gross_m3,sub.net_m3],['unsupported','substrate',0,0]);
  const heated=calculate(f({greenhouse_heated:'yes'}),0.6,0);
  assert.deepEqual([heated.status,heated.unsupported_reason,heated.gross_m3],['unsupported','heated_needs_measurement',0]);
  const measured=calculate(f({greenhouse_heated:'yes',greenhouse_et0:2.5}),0.6,0);assert.notEqual(measured.status,'unsupported');assert.ok(measured.gross_m3>0);
});
test('open field ignores greenhouse settings; invalid values are refused',()=>{
  assert.notEqual(calculate(f({field_type:'open',greenhouse_medium:'substrate',greenhouse_heated:'yes'}),6,0).status,'unsupported');
  for(const bad of [{greenhouse_medium:'peat'},{greenhouse_heated:'maybe'},{greenhouse_heated:true}])assert.throws(()=>f(bad));
});
test('the stored-field view and the report keep "no advice" and explain why in all languages',()=>{
  for(const [change,word] of [[{greenhouse_medium:'substrate'},/rockwool|минвата|минвата/i],[{greenhouse_heated:'yes'},/Heated|Отапливаемая|Жылытылатын/]]){
    const p={balance_version:2,crop:'tomato',soil_type:'loam',irrigation_type:'drip',area:0.1,area_unit:'hectare',day_of_growth:60,moisture_condition:'dry',field_type:'greenhouse',...change};
    const r=calculate(parseField(p),6,0),row={payload:p,result:r,deficit:r.deficit,last_day:'2026-01-15',weather:{timezone:'Asia/Almaty'}};
    assert.equal(currentResult(row).status,'unsupported');
    for(const lang of ['ru','kz','en']){const text=report(row,lang);assert.doesNotMatch(text,/Apply water|Подать воды|Берілетін су/);assert.ok(text.length>40);}
    assert.match(report(row,'en'),word);
  }
});
