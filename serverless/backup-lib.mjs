// Node-only recovery tooling. Never import into deployed modules/static assets.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createCipheriv,createDecipheriv,randomBytes} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {VERSION} from './tgcloud/lib/balance.js';

const MAGIC=Buffer.from('SUTECHBK1'),MAX_BYTES=16*1024*1024,MAX_ROWS=100000;
const COLUMNS={records:['id','owner','kind','body','updated'],ai_usage_v2:['id','owner','created']};
export function privatePath(value){
 if(!value)throw new Error('Missing path');const root=fileURLToPath(new URL('.',import.meta.url)),project=path.resolve(root,'..');
 const check=target=>{const relative=path.relative(project,target);
  if(!relative.startsWith('..'+path.sep)&&relative!=='..'&&!path.isAbsolute(relative)&&!target.startsWith(path.join(root,'.tgcloud')+path.sep))throw new Error('Choose a private destination outside publishable source');};
 const target=path.resolve(value);check(target);
 let parent=target;const suffix=[];
 while(!fs.existsSync(parent)){suffix.unshift(path.basename(parent));const next=path.dirname(parent);if(next===parent)throw new Error('Missing private parent');parent=next;}
 const resolved=path.join(fs.realpathSync(parent),...suffix);check(resolved);return resolved;
}
const invalid=()=>{throw new Error('Invalid backup format');};
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const keys=(v,wanted)=>object(v)&&Object.keys(v).sort().join(',')===[...wanted].sort().join(',');
const integer=v=>Number.isSafeInteger(v)&&v>=0;
const identifier=v=>typeof v==='string'&&v.length>0&&v.length<=200;

export function validateSnapshot(value) {
 if(!keys(value,['format','version','schema','engine','created_at','counts','tables']))invalid();
 if(value.format!=='sutech-private-db'||value.version!==1||value.schema!==1)throw new Error('Unsupported backup version/schema');
 if(value.engine!==VERSION)throw new Error('Unsupported backup engine');
 if(typeof value.created_at!=='string'||!Number.isFinite(Date.parse(value.created_at))||new Date(value.created_at).toISOString()!==value.created_at)invalid();
 if(!keys(value.tables,Object.keys(COLUMNS))||!keys(value.counts,Object.keys(COLUMNS)))invalid();
 let total=0;const tables={};
 for(const [name,columns] of Object.entries(COLUMNS)){
  const rows=value.tables[name];if(!Array.isArray(rows)||rows.length!==value.counts[name]||(total+=rows.length)>MAX_ROWS)invalid();
  const ids=new Set();tables[name]=rows.map(row=>{
   if(!keys(row,columns)||!identifier(row.id)||ids.has(row.id)||!integer(row.owner))invalid();ids.add(row.id);
   if(name==='records'){
    if(typeof row.kind!=='string'||!/^[a-z][a-z0-9:_-]{0,79}$/.test(row.kind)||typeof row.body!=='string'||row.body.length>1024*1024||!integer(row.updated))invalid();
    try{if(!object(JSON.parse(row.body)))invalid();}catch{invalid();}
   }else if(row.owner===0||!integer(row.created))invalid();
   return Object.fromEntries(columns.map(c=>[c,row[c]]));
  }).sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);
 }
 const normalized={format:value.format,version:1,schema:1,engine:VERSION,created_at:value.created_at,counts:{records:tables.records.length,ai_usage_v2:tables.ai_usage_v2.length},tables};
 if(Buffer.byteLength(JSON.stringify(normalized))>MAX_BYTES)invalid();return normalized;
}

export function createSnapshot(raw) {
 if(!keys(raw,['columns','tables'])||JSON.stringify(raw.columns)!==JSON.stringify(COLUMNS))throw new Error('Unsupported backup source schema');
 if(!keys(raw.tables,Object.keys(COLUMNS))||!Array.isArray(raw.tables.records)||!Array.isArray(raw.tables.ai_usage_v2))invalid();
 return validateSnapshot({format:'sutech-private-db',version:1,schema:1,engine:VERSION,created_at:new Date().toISOString(),counts:{records:raw.tables.records.length,ai_usage_v2:raw.tables.ai_usage_v2.length},tables:raw.tables});
}

function checkKey(key){if(!Buffer.isBuffer(key)||key.length!==32)throw new Error('Backup key must contain exactly 32 random bytes');}
export function encryptBackup(snapshot,key) {
 checkKey(key);const plain=Buffer.from(JSON.stringify(validateSnapshot(snapshot))),iv=randomBytes(12);
 const cipher=createCipheriv('aes-256-gcm',key,iv,{authTagLength:16});cipher.setAAD(MAGIC);
 const encrypted=Buffer.concat([cipher.update(plain),cipher.final()]);plain.fill(0);
 return Buffer.concat([MAGIC,iv,cipher.getAuthTag(),encrypted]);
}
export function decryptBackup(bytes,key) {
 checkKey(key);
 if(!Buffer.isBuffer(bytes)||bytes.length<MAGIC.length+29||bytes.length>MAX_BYTES+MAGIC.length+28||!bytes.subarray(0,MAGIC.length).equals(MAGIC))invalid();
 let plain;
 try{
  const at=MAGIC.length,decipher=createDecipheriv('aes-256-gcm',key,bytes.subarray(at,at+12),{authTagLength:16});
  decipher.setAAD(MAGIC);decipher.setAuthTag(bytes.subarray(at+12,at+28));
  plain=Buffer.concat([decipher.update(bytes.subarray(at+28)),decipher.final()]);
  return validateSnapshot(JSON.parse(plain.toString('utf8')));
 }catch{throw new Error('Backup authentication or validation failed');}
 finally{plain?.fill(0);}
}

export function restoreDatabase(bytes,key,destination) {
 const snapshot=decryptBackup(bytes,key);
 // Exclusive creation also refuses symlinks; validation happens before any file.
 const fd=fs.openSync(destination,'wx',0o600);fs.closeSync(fd);let connection;
 try{
  connection=new DatabaseSync(destination);connection.exec(`BEGIN IMMEDIATE;
   CREATE TABLE records(id TEXT PRIMARY KEY,owner INTEGER NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,updated INTEGER NOT NULL);
   CREATE INDEX records_owner_kind ON records(owner,kind);
   CREATE TABLE ai_usage_v2(id TEXT PRIMARY KEY,owner INTEGER NOT NULL,created INTEGER NOT NULL);
   CREATE INDEX usage_owner_time ON ai_usage_v2(owner,created);
   CREATE TABLE leases(id TEXT PRIMARY KEY,token TEXT NOT NULL,until INTEGER NOT NULL);
   CREATE TABLE update_receipts(id TEXT PRIMARY KEY,created INTEGER NOT NULL);`);
  for(const [name,columns] of Object.entries(COLUMNS)){
   const insert=connection.prepare(`INSERT INTO ${name}(${columns.join(',')}) VALUES(${columns.map(()=>'?').join(',')})`);
   for(const row of snapshot.tables[name])insert.run(...columns.map(c=>row[c]));
   const restored=connection.prepare(`SELECT ${columns.join(',')} FROM ${name} ORDER BY id`).all();
   if(JSON.stringify(restored)!==JSON.stringify(snapshot.tables[name]))throw new Error('Backup restore verification failed');
  }
  if(connection.prepare('PRAGMA integrity_check').get().integrity_check!=='ok')throw new Error('Backup restore integrity failed');
  connection.exec('COMMIT');connection.close();connection=null;
  return {counts:snapshot.counts,engine:snapshot.engine};
 }catch(error){connection?.close();fs.unlinkSync(destination);throw error;}
}
