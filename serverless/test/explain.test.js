import test from 'node:test';
import assert from 'node:assert/strict';
import {calculate,parseField,VERSION} from '../tgcloud/lib/balance.js';
import {confidence,assumptions,sensitivity,whyCard} from '../tgcloud/lib/explain.js';
import {report} from '../tgcloud/lib/fields.js';

const P=(c={})=>({balance_version:2,crop:'cotton',soil_type:'loam',irrigation_type:'drip',area:2,area_unit:'hectare',day_of_growth:70,moisture_condition:'normal',...c});
const mk=(c={},rowExtra={})=>{const p=P(c),f=parseField(p),r=calculate(f,6,0);return {p,f,r,row:{payload:p,result:r,deficit:r.deficit,last_day:'2026-07-01',weather:{timezone:'Asia/Almaty',et0:6,rain:0},checks:[],gap_days:0,...rowExtra}};};
const NOW=Date.now();

test('fresh inputs describe data completeness without claiming measured accuracy',()=>{
 const x=mk({},{checks:[{time:NOW,level:'normal'}]});
 for(const [lang,label,limit] of [['ru',/Данные/,/точность.*не измерена/i],['kz',/Деректер/,/дәлдігі.*өлшенбеген/i],['en',/Inputs/,/accuracy.*not been measured/i]]){
  const summary=report(x.row,lang),details=whyCard(x.row,x.f,x.r,lang);
  assert.match(summary,label);assert.match(details,limit);
  assert.doesNotMatch(summary,/Доверие высокое|Сенімділік жоғары|Confidence: high/);
 }
});

test('checks before a field reset cannot make the new inputs look checked',()=>{
 const x=mk({},{reset_at:NOW,checks:[{time:NOW-1000,level:'normal'}]});
 assert.ok(confidence(x.row,x.f,x.r,NOW).reasons.includes('no_check'));
 assert.match(assumptions(x.row,x.f,x.r,'en').join('\n'),/no hand check/);
});

test('a manual-check reminder does not promise measured accuracy improvement',()=>{
 const x=mk();
 for(const lang of ['ru','kz','en'])assert.doesNotMatch(report(x.row,lang),/так бот точнее|бот дәлірек болады|the bot gets more accurate/i);
});

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

import {fieldCsv,volumeRounded,firstDayNote,detailsBlock} from '../tgcloud/lib/explain.js';
test('polish: rounded volumes, localized units and names, stage and roots, first-day note, agronomist CSV',()=>{
  const x=mk({area:2},{checks:[{time:NOW,day:'2026-07-01',level:'dry',value_mm:118.2,before:65.4,after:118.2}],events:[{time:NOW,applied_m3:700,before:118.2,after:0}]});
  assert.match(volumeRounded(1453.44,'en'),/^1453 m³|1453/);assert.doesNotMatch(volumeRounded(1453.44,'en'),/\./);
  assert.match(volumeRounded(12.345,'en'),/12\.3/);
  const ru=report(x.row,'ru',true);
  assert.match(ru,/га/);assert.doesNotMatch(ru,/ ha\b/);assert.doesNotMatch(ru,/loam|mm\/day/);assert.match(ru,/Суглинок|суглинок/i);assert.match(ru,/мм\/сут/);
  assert.match(ru,/Стадия: развитие|Стадия:/);assert.match(ru,/корни \d/);assert.match(ru,/Open-Meteo/);
  assert.match(report(mk({crop:'wheat'}).row,'en',true),/Stage: (initial|development|mid-season|late season)/);
  const big=mk({moisture_condition:'dry'});
  assert.match(firstDayNote(big.f,big.r,'ru'),/накопленный дефицит/);
  const sprinkler=mk({irrigation_type:'furrow',moisture_condition:'dry'});assert.equal(firstDayNote(sprinkler.f,sprinkler.r,'ru'),'');
  const csv=fieldCsv(x.row);
  assert.ok(csv.startsWith('# Su-Tech field export. Engine '+VERSION+'.'));assert.match(csv,/crop,cotton/);assert.match(csv,/watering: time,applied_m3/);assert.match(csv,/soil_check: time,day,level/);assert.match(csv,/,dry,118\.2,65\.4,118\.2/);
});

import {selfCheck,selfCheckLines} from '../tgcloud/lib/explain.js';
test('self-check: compares model and farmer answers, flags a steady bias, changes nothing, nothing without checks',()=>{
  const none=mk();assert.equal(selfCheck(none.row,none.r),null);assert.deepEqual(selfCheckLines(none.row,none.r,'en'),[]);
  const raw=mk().r.raw;
  const drier=mk({},{checks:[1,2,3,4].map(i=>({time:NOW-i*86400000,before:raw*.2,value_mm:raw*.8}))});
  const c=selfCheck(drier.row,drier.r);assert.equal(c.n,4);assert.equal(c.bias,'model_wetter');assert.ok(Math.abs(c.abs_mm-raw*.6)<1e-9);
  const text=selfCheckLines(drier.row,drier.r,'en').join(' ');assert.match(text,/drier than the bot calculated/);assert.match(text,/changes nothing by itself/);
  assert.match(whyCard(drier.row,drier.f,drier.r,'en'),/Field self-check/);
  const mixed=mk({},{checks:[{time:NOW-3,before:raw*.2,value_mm:raw*.8},{time:NOW-2,before:raw*.8,value_mm:raw*.2},{time:NOW-1,before:raw*.5,value_mm:raw*.5}]});assert.equal(selfCheck(mixed.row,mixed.r).bias,'none');
  const two=mk({},{checks:[{time:NOW-2,before:0,value_mm:raw},{time:NOW-1,before:0,value_mm:raw}]});assert.equal(selfCheck(two.row,two.r).bias,'none');   // fewer than 3: no suggestion
  const wetter=mk({},{checks:[1,2,3].map(i=>({time:NOW-i,before:raw*.9,value_mm:0}))});assert.equal(selfCheck(wetter.row,wetter.r).bias,'model_drier');
});

import {checkAge,needsCheck,checkNudge,CHECK_DUE_DAYS} from '../tgcloud/lib/explain.js';
test('manual reminder: fields not checked for more than 7 days are flagged, with the age; rice and unsupported are not',()=>{
  const never=mk();assert.equal(checkAge(never.row,NOW),null);assert.ok(needsCheck(never.row,NOW));assert.match(checkNudge(never.row,'en',NOW),/not been checked yet/);
  const fresh=mk({},{checks:[{time:NOW-3*86400000,level:'normal'}]});assert.equal(checkAge(fresh.row,NOW),3);assert.ok(!needsCheck(fresh.row,NOW));assert.equal(checkNudge(fresh.row,'en',NOW),'');
  const old=mk({},{checks:[{time:NOW-(CHECK_DUE_DAYS+2)*86400000,level:'dry'}]});assert.match(checkNudge(old.row,'ru',NOW),/9 дн\. назад/);
  const reset=mk({},{checks:[{time:NOW-86400000}],reset_at:NOW});assert.equal(checkAge(reset.row,NOW),null);   // a check from before a restart does not count
  const rice=mk({crop:'rice'});assert.ok(!needsCheck(rice.row,NOW));
  assert.ok(!needsCheck(mk({crop:'tomato',field_type:'greenhouse',greenhouse_medium:'substrate'}).row,NOW));
  const card=report(never.row,'en');assert.match(card,/🔔/);assert.equal((card.match(/Confirm soil moisture/g)??[]).length,0,'no duplicate request');
  assert.doesNotMatch(report(fresh.row,'en'),/🔔/);
});
