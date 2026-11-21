import {db} from 'sdk';
export const now=()=>Date.now();
export function ownerId(value) {
  if(!Number.isSafeInteger(value)||value<=0)throw new Error('UNAUTHENTICATED');
  return value;
}
export const decode=row=>row?{...JSON.parse(row.body),_id:row.id,_updated:row.updated}:null;
export async function get(id,owner) {return decode(await db.get('SELECT id,body,updated FROM records WHERE id=:id AND owner=:owner',{':id':id,':owner':owner}));}
export async function put(id,owner,kind,value) {
  const {_id,_updated,...body}=value;
  await db.run('INSERT INTO records(id,owner,kind,body,updated) VALUES(:id,:owner,:kind,:body,:time) ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated WHERE records.owner=excluded.owner AND records.kind=excluded.kind',{
    ':id':id,':owner':owner,':kind':kind,':body':JSON.stringify(body),':time':now()});
}
export async function list(owner,kind,limit=50,offset=0) {
  return (await db.all('SELECT id,body,updated FROM records WHERE owner=:owner AND kind=:kind ORDER BY updated DESC,id DESC LIMIT :limit OFFSET :offset',{':owner':owner,':kind':kind,':limit':Math.min(100,Math.max(1,limit)),':offset':Math.max(0,offset)})).map(decode);
}
// Fence a delayed writer in the same statement as its write. An expired worker
// must not overwrite a retry that has already acquired a new lease token.
export async function putGuarded(id,owner,kind,value,{lease=null,parentLease=null,generation=null,mode=null,epoch=null,existing=false}={}) {
  const {_id,_updated,...body}=value;
  const result=await db.run(`INSERT INTO records(id,owner,kind,body,updated)
    SELECT :id,:owner,:kind,:body,:time WHERE (:guard IS NULL OR EXISTS(
      SELECT 1 FROM leases WHERE id=:guard AND token=:token AND until>:time))
    AND (:parent IS NULL OR EXISTS(
      SELECT 1 FROM leases WHERE id=:parent AND token=:parentToken AND until>:time))
    AND (:epoch IS NULL OR EXISTS(SELECT 1 FROM records WHERE id=:lifecycle AND owner=0 AND kind='lifecycle'
      AND json_extract(body,'$.epoch')=:epoch AND json_extract(body,'$.deleting')=0))
    AND (:existing=0 OR EXISTS(SELECT 1 FROM records WHERE id=:id AND owner=:owner AND kind=:kind))
    AND (:generation IS NULL OR EXISTS(
      SELECT 1 FROM records WHERE id=:user AND owner=:owner
      AND json_extract(body,'$.generation')=:generation AND (:mode IS NULL OR json_extract(body,'$.mode')=:mode)))
    ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated
      WHERE records.owner=excluded.owner AND records.kind=excluded.kind RETURNING id`,{
    ':id':id,':owner':owner,':kind':kind,':body':JSON.stringify(body),':time':now(),':guard':lease?.[0]??null,':token':lease?.[1]??null,
    ':parent':parentLease?.[0]??null,':parentToken':parentLease?.[1]??null,':user':`user:${owner}`,':generation':generation,':mode':mode,
    ':lifecycle':`lifecycle:${owner}`,':epoch':epoch,':existing':existing?1:0});
  if(!result.rows?.length)throw new Error(generation===null?'busy':'stale');
}
export async function remove(id,owner,kind) {await db.run('DELETE FROM records WHERE id=:id AND owner=:owner AND kind=:kind',{':id':id,':owner':owner,':kind':kind});}
export function nonce() {return `${now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;}
export async function lock(id,seconds=60) {
  const token=nonce(),time=now();
  const r=await db.run('INSERT INTO leases(id,token,until) VALUES(:id,:token,:until) ON CONFLICT(id) DO UPDATE SET token=excluded.token,until=excluded.until WHERE leases.until<:time RETURNING token',{
    ':id':id,':token':token,':until':time+seconds*1000,':time':time});
  return r.rows?.[0]?.token===token?token:null;
}
export async function unlock(id,token) {await db.run('DELETE FROM leases WHERE id=:id AND token=:token',{':id':id,':token':token});}
// The minimal marker survives erasure so an old invocation cannot borrow a new
// account's generation. It contains no field, question, answer or location.
export async function ownerState(id,expectedEpoch=null) {
  ownerId(id);const key=`lifecycle:${id}`;
  let state=await get(key,0);
  if(!state){
    if(expectedEpoch!==null)throw new Error('stale');
    await db.run("INSERT OR IGNORE INTO records(id,owner,kind,body,updated) VALUES(:id,0,'lifecycle',:body,:time)",{
      ':id':key,':body':JSON.stringify({epoch:nonce(),deleting:false,generation:0}),':time':now()});
    state=await get(key,0);
  }
  if(state.deleting){await finishErasure(id,state.epoch);state=await get(key,0);}
  if(state.deleting||(expectedEpoch!==null&&state.epoch!==expectedEpoch))throw new Error('stale');return state;
}
export async function user(id,lang,expectedEpoch=null) {
  const state=await ownerState(id,expectedEpoch);let u=await get(`user:${id}`,id);
  if(!u){
    const initial={lang:['ru','kz','en'].includes(lang)?lang:lang==='kk'?'kz':'ru',mode:'home',screen:null,generation:state.generation,epoch:state.epoch};
    await db.run("INSERT OR IGNORE INTO records(id,owner,kind,body,updated) SELECT :id,:owner,'user',:body,:time WHERE EXISTS(SELECT 1 FROM records WHERE id=:marker AND owner=0 AND json_extract(body,'$.epoch')=:epoch AND json_extract(body,'$.deleting')=0)",{
      ':id':`user:${id}`,':owner':id,':body':JSON.stringify(initial),':time':now(),':marker':`lifecycle:${id}`,':epoch':state.epoch});
    u=await get(`user:${id}`,id);
  }
  if(u&&u.epoch===undefined){
    // Adopt pre-epoch profiles once, without resetting language or navigation.
    const result=await db.run("UPDATE records SET body=json_set(body,'$.epoch',:epoch) WHERE id=:id AND owner=:owner AND json_extract(body,'$.epoch') IS NULL AND EXISTS(SELECT 1 FROM records WHERE id=:marker AND owner=0 AND json_extract(body,'$.epoch')=:epoch AND json_extract(body,'$.deleting')=0) RETURNING id,body,updated",{
      ':id':`user:${id}`,':owner':id,':marker':`lifecycle:${id}`,':epoch':state.epoch});
    u=decode(result.rows?.[0])??await get(`user:${id}`,id);
  }
  if(!u||u.epoch!==state.epoch)throw new Error('stale');
  return u;
}
export async function saveUser(id,u) {
  const {_id,_updated,...value}=u;
  // The renderer owns the screen pointer; an older planner/AI snapshot must
  // never overwrite it while saving unrelated conversation settings.
  const result=await db.run('UPDATE records SET body=json_set(:body,\'$.screen\',json_extract(body,\'$.screen\')),updated=:time WHERE id=:id AND owner=:owner AND json_extract(body,\'$.generation\')=:generation AND json_extract(body,\'$.epoch\')=:epoch AND EXISTS(SELECT 1 FROM records WHERE id=:marker AND owner=0 AND json_extract(body,\'$.epoch\')=:epoch AND json_extract(body,\'$.deleting\')=0) RETURNING id',{
    ':id':`user:${id}`,':owner':id,':body':JSON.stringify(value),':time':now(),':generation':u.generation,':epoch':u.epoch,':marker':`lifecycle:${id}`});
  if(!result.rows?.length)throw new Error('stale');
}
export async function setScreen(id,messageId,epoch) {
  await db.run("UPDATE records SET body=json_set(body,'$.screen',:message),updated=:time WHERE id=:id AND owner=:owner AND json_extract(body,'$.epoch')=:epoch",{
    ':id':`user:${id}`,':owner':ownerId(id),':message':messageId,':time':now(),':epoch':epoch});
}
export async function navigateUser(id,mode,expectedEpoch=null) {
  const u=await user(id,null,expectedEpoch);
  const result=await db.run(`UPDATE records SET body=json_remove(json_set(body,'$.mode',:mode,'$.generation',coalesce(json_extract(body,'$.generation'),0)+1),'$.draft','$.water'),updated=:time WHERE id=:id AND owner=:owner AND json_extract(body,'$.epoch')=:epoch AND EXISTS(SELECT 1 FROM records WHERE id=:marker AND owner=0 AND json_extract(body,'$.epoch')=:epoch AND json_extract(body,'$.deleting')=0) RETURNING id,body,updated`,{
    ':id':`user:${id}`,':owner':id,':mode':mode,':time':now(),':epoch':u.epoch,':marker':`lifecycle:${id}`});
  const next=decode(result.rows[0]);if(!next||next.epoch!==u.epoch)throw new Error('stale');return next;
}
export async function setting(name) {return (await get(`config:${name}`,0))?.value;}
export async function reserveAI(id) {
  const time=now(),r=await db.run(`INSERT INTO ai_usage_v2(id,owner,created)
    SELECT :id,:owner,:time WHERE (SELECT COUNT(*) FROM ai_usage_v2 WHERE owner=:owner AND created>:since)<20
    AND (SELECT COUNT(*) FROM ai_usage_v2 WHERE created>:since)<450
    AND NOT EXISTS(SELECT 1 FROM ai_usage_v2 WHERE owner=:owner AND created>:cooldown) RETURNING id`,{
      ':id':nonce(),':owner':ownerId(id),':time':time,':since':time-86400000,':cooldown':time-3000});
  if(r.rows?.length)return true;
  const count=await db.get('SELECT COUNT(*) AS n FROM ai_usage_v2 WHERE owner=:owner AND created>:since',{':owner':id,':since':time-86400000});
  throw new Error(count.n>=20?'daily_limit':'cooldown');
}

// Erase everything stored about one Telegram user: profile, fields, reports, weather snapshots, feedback.
// The last 24 hours of AI-request timestamps (no text, only time and the numeric Telegram id) are kept, because they
// are the daily quota window: deleting them would let anyone reset the limit. They are no longer counted after 24 hours.
async function finishErasure(owner,epoch) {
  const params={':owner':owner,':marker':`lifecycle:${owner}`,':epoch':epoch,':since':now()-86400000};
  const active="EXISTS(SELECT 1 FROM records WHERE id=:marker AND owner=0 AND json_extract(body,'$.epoch')=:epoch AND json_extract(body,'$.deleting')=1)";
  await db.run(`DELETE FROM leases WHERE ${active} AND (id=:ai OR id=:render OR substr(id,1,length(:prefix))=:prefix
    OR id IN (SELECT 'field:'||json_extract(body,'$.id') FROM records WHERE owner=:owner AND kind='field'))`,{
    ':owner':owner,':marker':params[':marker'],':epoch':epoch,':ai':`ai:${owner}`,':render':`ui-render:${owner}`,':prefix':`field-key:${owner}:`});
  await db.run(`DELETE FROM records WHERE owner=0 AND kind LIKE 'legacy:%' AND
    (CAST(json_extract(body,'$.chat_id') AS TEXT)=:ownerText OR CAST(json_extract(body,'$.user_id') AS TEXT)=:ownerText) AND ${active}`,{
    ':ownerText':String(owner),':marker':params[':marker'],':epoch':epoch});
  await db.run(`DELETE FROM records WHERE owner=:owner AND ${active}`,{':owner':owner,':marker':params[':marker'],':epoch':epoch});
  await db.run(`DELETE FROM ai_usage_v2 WHERE owner=:owner AND created<=:since AND ${active}`,params);
  await db.run("UPDATE records SET body=json_set(body,'$.deleting',json('false')),updated=:time WHERE id=:marker AND owner=0 AND json_extract(body,'$.epoch')=:epoch AND json_extract(body,'$.deleting')=1",{
    ':marker':params[':marker'],':epoch':epoch,':time':now()});
}
export async function eraseUserData(id,expectedEpoch=null) {
  const owner=ownerId(id);
  const state=await ownerState(owner,expectedEpoch);
  const before=await db.get('SELECT COUNT(*) AS n FROM records WHERE owner=:owner',{':owner':owner});
  const epoch=nonce();
  const updated=await db.run("UPDATE records SET body=json_object('epoch',:epoch,'deleting',json('true'),'generation',max(coalesce((SELECT json_extract(body,'$.generation') FROM records WHERE id=:user AND owner=:owner),0),coalesce(json_extract(body,'$.generation'),0))+1),updated=:time WHERE id=:marker AND owner=0 AND json_extract(body,'$.epoch')=:previous RETURNING id",{
    ':marker':`lifecycle:${owner}`,':user':`user:${owner}`,':owner':owner,':epoch':epoch,':previous':state.epoch,':time':now()});
  if(!updated.rows?.length)throw new Error('stale');
  await finishErasure(owner,epoch);
  return before?.n??0;
}
