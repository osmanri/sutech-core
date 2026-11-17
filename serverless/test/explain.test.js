import test from 'node:test';
import assert from 'node:assert/strict';
import {calculate,parseField} from '../tgcloud/lib/balance.js';
import {confidence,assumptions,sensitivity,whyCard} from '../tgcloud/lib/explain.js';
import {report} from '../tgcloud/lib/fields.js';

const P=(c={})=>({balance_version:2,crop:'cotton',soil_type:'loam',irrigation_type:'drip',area:2,area_unit:'hectare',day_of_growth:70,moisture_condition:'normal',...c});
const mk=(c={},rowExtra={})=>{const p=P(c),f=parseField(p),r=calculate(f,6,0);return {p,f,r,row:{payload:p,result:r,deficit:r.deficit,last_day:'2026-07-01',weather:{timezone:'Asia/Almaty',et0:6,rain:0},checks:[],gap_days:0,...rowExtra}};};
const NOW=Date.now();

test('confidence: high only with FAO-56 crop data and a fresh soil check; each missing piece lowers it and says what raises it',()=>{
  const fresh=mk({},{checks:[{time:NOW-2*86400000,level:'normal'}]});
  assert.equal(confidence(fresh.row,fresh.f,fresh.r,NOW).level,'high');                       // cotton: every number from the tables
  const none=mk();assert.deepEqual([confidence(none.row,none.f,none.r,NOW).level,confidence(none.row,none.f,none.r,NOW).raise],['medium','check']);
  const old=mk({},{checks:[{time:NOW-20*86400000,level:'dry'}]});assert.ok(confidence(old.row,old.f,old.r,NOW).reasons.includes('old_check'));
  const mixed=mk({crop:'wheat',day_of_growth:30},{checks:[{time:NOW-86400000}]});assert.ok(confidence(mixed.row,mixed.f,mixed.r,NOW).reasons.includes('crop_stages'));
  const saline=mk({is_saline:'yes'},{checks:[{time:NOW-86400000}]});assert.equal(confidence(saline.row,saline.f,saline.r,NOW).raise,'salinity');
  const gap=mk({},{checks:[{time:NOW-86400000}],gap_days:5});assert.equal(confidence(gap.row,gap.f,gap.r,NOW).level,'low');
  const sub=mk({crop:'tomato',field_type:'greenhouse',greenhouse_medium:'substrate'});assert.deepEqual([confidence(sub.row,sub.f,sub.r,NOW).level,confidence(sub.row,sub.f,sub.r,NOW).raise],['low','agronomist']);
});
test('assumptions list what the bot took for granted; sensitivity is plain arithmetic on today\'s numbers',()=>{
  const x=mk({field_type:'greenhouse'});
  const a=assumptions(x.row,x.f,x.r,'en').join('\n');
  assert.match(a,/stage calendar/);assert.match(a,/Salinity is not included/);assert.match(a,/0\.70/);assert.match(a,/no hand check/);
  const [crop,soil]=sensitivity(x.f,x.r,'en');
  const dEtc=.15*x.r.etc;assert.ok(crop.includes(dEtc.toFixed(2).replace(/\.?0+$/,'')));
  assert.ok(soil.includes((x.r.raw*.8).toFixed(2).replace(/\.?0+$/,'')));
});
test('the field report shows the confidence line; the explanation adds assumptions, sources and what-if, in three languages',()=>{
  const x=mk();
  for(const lang of ['ru','kz','en']){
    assert.match(report(x.row,lang),/🟡|🟢|🔴/);
    const text=report(x.row,lang,true);
    assert.match(text,/FAO-56/);assert.ok(text.split('\n').filter(l=>l.startsWith('• ')).length>=7,lang);
  }
  assert.match(whyCard(x.row,x.f,x.r,'ru'),/Мы предположили/);assert.match(whyCard(x.row,x.f,x.r,'kz'),/Біз болжадық/);
  const sub=mk({crop:'tomato',field_type:'greenhouse',greenhouse_medium:'substrate'});
  assert.doesNotMatch(report(sub.row,'en'),/Confidence: high/);
});
