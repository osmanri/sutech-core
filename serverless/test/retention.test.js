import test from 'node:test';
import assert from 'node:assert/strict';
import {db} from 'sdk';
import {get,put,ownerState,lock,eraseUserData} from '../tgcloud/lib/store.js';
import {pruneOperationalData} from '../tgcloud/lib/retention.js';

test('cleanup expires operational data, preserves active guards and durable user history, and is throttled',async()=>{
 const now=Date.now(),day=86400000,id=82001;const state=await ownerState(id);
 const record=async(key,kind,age,owner=id)=>{await put(key,owner,kind,{value:'synthetic'});await db.run('UPDATE records SET updated=:time WHERE id=:id',{':id':key,':time':now-age});};
 await record('context-old','ai-context',1800001);await record('context-new','ai-context',1000);
 await record('pending-old','pending',8*day);await record('pending-new','pending',day);
 await record('weather-old','weather',2*day,0);await record('weather-new','weather',1000,0);
 await record('photo-old','photo-comparison',31*day);await record('photo-new','photo-comparison',day);
 await record('answer-keep','ai-answer',400*day);await record('field-keep','field',400*day);await record('report-keep','report',400*day);
 for(const [key,age] of [['old',8*day],['recent',day]])await db.run('INSERT INTO update_receipts VALUES(:id,:time)',{':id':key,':time':now-age});
 for(const [key,age] of [['old',2*day],['recent',1000]])await db.run('INSERT INTO ai_usage_v2 VALUES(:id,:owner,:time)',{':id':key,':owner':id,':time':now-age});
 await db.run('INSERT INTO leases VALUES(:id,:token,:until)',{':id':'expired',':token':'old',':until':now-day});const active=await lock('active',90);
 assert.equal((await pruneOperationalData()).ran,true);
 for(const key of ['context-old','pending-old','photo-old'])assert.equal(await get(key,id),null,key);
 assert.equal(await get('weather-old',0),null);
 for(const key of ['context-new','pending-new','photo-new','answer-keep','field-keep','report-keep'])assert.ok(await get(key,id),key);
 assert.ok(await get('weather-new',0));assert.equal((await get(`lifecycle:${id}`,0)).epoch,state.epoch);
 assert.equal(await db.get("SELECT id FROM update_receipts WHERE id='old'"),null);assert.ok(await db.get("SELECT id FROM update_receipts WHERE id='recent'"));
 assert.equal(await db.get("SELECT id FROM ai_usage_v2 WHERE id='old'"),null);assert.ok(await db.get("SELECT id FROM ai_usage_v2 WHERE id='recent'"));
 assert.equal(await db.get("SELECT id FROM leases WHERE id='expired'"),null);assert.equal((await db.get("SELECT token FROM leases WHERE id='active'")).token,active);
 assert.equal((await pruneOperationalData()).ran,false);
});

test('erasure revokes only this owner locks so a fresh request need not wait for the old lease',async()=>{
 const id=82002,other=82003;await ownerState(id);await ownerState(other);
 await lock(`ai:${id}`,75);await lock(`field-key:${id}:synthetic`,45);const keep=await lock(`ai:${other}`,75);
 await eraseUserData(id);assert.ok(await lock(`ai:${id}`,75));assert.ok(await lock(`field-key:${id}:synthetic`,45));
 assert.equal((await db.get('SELECT token FROM leases WHERE id=:id',{':id':`ai:${other}`})).token,keep);
});
