import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {randomBytes} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {db} from 'sdk';
import {VERSION} from '../tgcloud/lib/balance.js';
import {createSnapshot,validateSnapshot,encryptBackup,decryptBackup,restoreDatabase,privatePath} from '../backup-lib.mjs';
import exportSnapshot from '../maintenance/export-snapshot.js';

const raw=()=>({columns:{records:['id','owner','kind','body','updated'],ai_usage_v2:['id','owner','created']},tables:{records:[{id:'field:1',owner:123,kind:'field',body:JSON.stringify({private:'never print this',deficit:12}),updated:1000},{id:'lifecycle:123',owner:0,kind:'lifecycle',body:JSON.stringify({epoch:'synthetic',deleting:false,generation:2}),updated:1000}],ai_usage_v2:[{id:'quota:1',owner:123,created:1000}]}});
function cleanup(dir){
 const target=path.resolve(dir);assert.equal(path.dirname(target),path.resolve(os.tmpdir()));assert.match(path.basename(target),/^sutech-(?:recovery|invalid)-/);
 fs.rmSync(target,{recursive:true,force:true});
}

test('private paths check the real existing parent rather than trusting a lexical directory name',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sutech-recovery-')),original=fs.realpathSync;
 const publishable=fileURLToPath(new URL('../dist',import.meta.url));
 fs.realpathSync=p=>path.resolve(p)===path.resolve(dir)?publishable:original(p);
 try{assert.throws(()=>privatePath(path.join(dir,'key.sutech-key')),/private|publishable/i);}
 finally{fs.realpathSync=original;cleanup(dir);}
});

test('offline CLI creates a private key without printing it and refuses to overwrite it',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sutech-recovery-')),keyPath=path.join(dir,'key.sutech-key');
 const cli=fileURLToPath(new URL('../backup.mjs',import.meta.url));
 try{
  const first=spawnSync(process.execPath,[cli,'keygen','--key-file',keyPath],{encoding:'utf8'});assert.equal(first.status,0,first.stderr);
  const key=fs.readFileSync(keyPath);assert.equal(key.length,32);assert.equal(first.stdout.includes(key.toString('hex')),false);
  const second=spawnSync(process.execPath,[cli,'keygen','--key-file',keyPath],{encoding:'utf8'});assert.equal(second.status,1);assert.deepEqual(fs.readFileSync(keyPath),key);
 }finally{cleanup(dir);}
});

test('a filesystem alias cannot redirect private key creation into the publishable site',t=>{
 const cli=fileURLToPath(new URL('../backup.mjs',import.meta.url)),root=path.dirname(cli),dist=path.join(root,'dist');fs.mkdirSync(dist,{recursive:true});
 const target=fs.mkdtempSync(path.join(dist,'privacy-fixture-')),dir=fs.mkdtempSync(path.join(os.tmpdir(),'sutech-recovery-')),alias=path.join(dir,'alias');
 try{
  try{fs.symlinkSync(target,alias,process.platform==='win32'?'junction':'dir');}catch(e){if(['EPERM','EACCES'].includes(e.code)){t.skip('Host does not allow directory aliases');return;}throw e;}
  const result=spawnSync(process.execPath,[cli,'keygen','--key-file',path.join(alias,'private.sutech-key')],{encoding:'utf8'});
  assert.equal(result.status,1);assert.equal(fs.existsSync(path.join(target,'private.sutech-key')),false);
 }finally{
  // Remove the link itself before recursive cleanup; never traverse its target.
  if(fs.existsSync(alias)){if(process.platform==='win32')fs.rmdirSync(alias);else fs.unlinkSync(alias);}
  cleanup(dir);assert.equal(path.dirname(path.resolve(target)),path.resolve(dist));assert.match(path.basename(target),/^privacy-fixture-/);fs.rmSync(target,{recursive:true,force:true});
 }
});

test('authenticated encrypted backup restores every durable row into a new staging SQLite database',()=>{
 const snapshot=createSnapshot(raw()),key=randomBytes(32),encrypted=encryptBackup(snapshot,key),again=encryptBackup(snapshot,key);
 assert.notDeepEqual(encrypted,again,'each encryption uses a fresh nonce');assert.equal(encrypted.includes(Buffer.from('never print this')),false);
 assert.deepEqual(decryptBackup(encrypted,key),snapshot);
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sutech-recovery-')),dest=path.join(dir,'staging.sqlite');
 try{
  const result=restoreDatabase(encrypted,key,dest);assert.deepEqual(result.counts,snapshot.counts);
  const restored=new DatabaseSync(dest);try{
   assert.deepEqual(restored.prepare('SELECT id,owner,kind,body,updated FROM records ORDER BY id').all().map(r=>({...r})),snapshot.tables.records);
   assert.equal(restored.prepare('SELECT COUNT(*) n FROM leases').get().n,0);assert.equal(restored.prepare('SELECT COUNT(*) n FROM update_receipts').get().n,0);
  }finally{restored.close();}
  const before=fs.readFileSync(dest);assert.throws(()=>restoreDatabase(encrypted,key,dest),/exists/i);assert.deepEqual(fs.readFileSync(dest),before);
 }finally{cleanup(dir);}
});

test('wrong key, changed header/tag/ciphertext and truncation fail before a destination is created',()=>{
 const key=randomBytes(32),encrypted=encryptBackup(createSnapshot(raw()),key);
 const variants=[Buffer.from(encrypted),Buffer.from(encrypted),Buffer.from(encrypted),encrypted.subarray(0,-1)];
 variants[0][0]^=1;variants[1][25]^=1;variants[2][variants[2].length-1]^=1;
 assert.throws(()=>decryptBackup(encrypted,randomBytes(32)),/backup/i);
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sutech-invalid-'));
 try{for(const [i,value] of variants.entries()){const dest=path.join(dir,`${i}.sqlite`);assert.throws(()=>restoreDatabase(value,key,dest),/backup/i);assert.equal(fs.existsSync(dest),false);}}
 finally{cleanup(dir);}
});

test('format, schema, engine, counts, duplicates, unsupported columns and malformed row types are rejected',()=>{
 const snapshot=createSnapshot(raw());assert.equal(snapshot.engine,VERSION);
 const changes=[s=>s.version++,s=>s.schema++,s=>s.engine='fao56.future',s=>s.counts.records++,s=>s.tables.records.push({...s.tables.records[0]}),s=>s.tables.records[0].owner=-1,s=>s.tables.records[0].body='{broken',s=>s.tables.records[0].updated=Infinity,s=>s.tables.ai_usage_v2[0].owner=0,s=>s.tables.extra=[],s=>s.tables.records[0].extra='unexpected'];
 for(const mutate of changes){const value=structuredClone(snapshot);mutate(value);assert.throws(()=>validateSnapshot(value),/backup|version|schema|engine/i);}
 const extra=raw();extra.columns.records.push('unknown_column');assert.throws(()=>createSnapshot(extra),/schema/i);
 assert.throws(()=>encryptBackup(snapshot,Buffer.alloc(16)),/key/i);
});

test('the management export reads a complete consistent snapshot without exposing leases or receipts',async()=>{
 await db.run('INSERT INTO records VALUES(:id,:owner,:kind,:body,:time)',{':id':'synthetic-export',':owner':456,':kind':'field',':body':'{"x":1}',':time':100});
 await db.run("INSERT INTO leases VALUES('active','private-token',9999999999999)");
 const original=db.get;let reads=0;db.get=async(...args)=>{reads++;return original(...args);};
 try{const exported=await exportSnapshot();const snapshot=createSnapshot(exported);assert.equal(reads,1);assert.ok(snapshot.tables.records.some(r=>r.id==='synthetic-export'));assert.equal('leases' in snapshot.tables,false);}
 finally{db.get=original;}
});
