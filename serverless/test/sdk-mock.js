import {DatabaseSync} from 'node:sqlite';
const connection=new DatabaseSync(':memory:');
connection.exec(`CREATE TABLE records(id TEXT PRIMARY KEY,owner INTEGER NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,updated INTEGER NOT NULL);
 CREATE TABLE leases(id TEXT PRIMARY KEY,token TEXT NOT NULL,until INTEGER NOT NULL);
 CREATE TABLE ai_usage_v2(id TEXT PRIMARY KEY,owner INTEGER NOT NULL,created INTEGER NOT NULL);
 CREATE TABLE update_receipts(id TEXT PRIMARY KEY,created INTEGER NOT NULL);`);
export const db={
 async get(q,p={}){return connection.prepare(q).get(p)??null;},
 async all(q,p={}){return connection.prepare(q).all(p);},
 async run(q,p={}){const s=connection.prepare(q);if(/RETURNING\s+/i.test(q)){const rows=s.all(p);return {rows,rowsAffected:rows.length};}const r=s.run(p);return {rows:[],rowsAffected:Number(r.changes),lastInsertRowid:Number(r.lastInsertRowid)};}
};
export const messages=[];let nextId=100;
let apiHandler=null;
export function setApiHandler(handler){apiHandler=handler;}
export const liveMessages=new Map();
export const api=new Proxy({}, {get:(_,method)=>async(params={})=>{
 messages.push({method,params});
 const intercepted=apiHandler?await apiHandler(method,params):undefined;
 if(intercepted!==undefined)return intercepted;
 if(method==='sendMessage'||method==='sendDocument'){
  const message={...params,message_id:nextId++};liveMessages.set(`${params.chat_id}:${message.message_id}`,message);return message;
 }
 if(method==='editMessageText')liveMessages.set(`${params.chat_id}:${params.message_id}`,{...params});
 if(method==='deleteMessage')liveMessages.delete(`${params.chat_id}:${params.message_id}`);
 if(method==='getFileContent')return new Uint8Array([255,216,255,0]);
 return true;
}});
export let fetchHandler=async()=>{throw new Error('Network not mocked');};
export function setFetch(fn){fetchHandler=fn;}
export const fetch=(...args)=>fetchHandler(...args);
export class InputFile {constructor(data,name,options){Object.assign(this,{data,name,options});}}
export class EndpointError extends Error {constructor(message,parameters){super(message);this.parameters=parameters;}}
