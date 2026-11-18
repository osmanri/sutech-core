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
export async function putGuarded(id,owner,kind,value,{lease=null,parentLease=null,generation=null,mode=null}={}) {
  const {_id,_updated,...body}=value;
  const result=await db.run(`INSERT INTO records(id,owner,kind,body,updated)
    SELECT :id,:owner,:kind,:body,:time WHERE (:guard IS NULL OR EXISTS(
      SELECT 1 FROM leases WHERE id=:guard AND token=:token AND until>:time))
    AND (:parent IS NULL OR EXISTS(
      SELECT 1 FROM leases WHERE id=:parent AND token=:parentToken AND until>:time))
    AND (:generation IS NULL OR EXISTS(
      SELECT 1 FROM records WHERE id=:user AND owner=:owner
      AND json_extract(body,'$.generation')=:generation AND (:mode IS NULL OR json_extract(body,'$.mode')=:mode)))
    ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated
      WHERE records.owner=excluded.owner AND records.kind=excluded.kind RETURNING id`,{
    ':id':id,':owner':owner,':kind':kind,':body':JSON.stringify(body),':time':now(),':guard':lease?.[0]??null,':token':lease?.[1]??null,
    ':parent':parentLease?.[0]??null,':parentToken':parentLease?.[1]??null,':user':`user:${owner}`,':generation':generation,':mode':mode});
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
export async function user(id,lang) {
  ownerId(id);let u=await get(`user:${id}`,id);
  if(!u){
    const initial={lang:['ru','kz','en'].includes(lang)?lang:lang==='kk'?'kz':'ru',mode:'home',screen:null,generation:0};
    await db.run('INSERT OR IGNORE INTO records(id,owner,kind,body,updated) VALUES(:id,:owner,\'user\',:body,:time)',{':id':`user:${id}`,':owner':id,':body':JSON.stringify(initial),':time':now()});
    u=await get(`user:${id}`,id);
  }
  return u;
}
export async function saveUser(id,u) {
  const {_id,_updated,...value}=u;
  // The renderer owns the screen pointer; an older planner/AI snapshot must
  // never overwrite it while saving unrelated conversation settings.
  const result=await db.run('UPDATE records SET body=json_set(:body,\'$.screen\',json_extract(body,\'$.screen\')),updated=:time WHERE id=:id AND owner=:owner AND json_extract(body,\'$.generation\')=:generation RETURNING id',{
    ':id':`user:${id}`,':owner':id,':body':JSON.stringify(value),':time':now(),':generation':u.generation});
  if(!result.rows?.length)throw new Error('stale');
}
export async function setScreen(id,messageId) {
  await db.run("UPDATE records SET body=json_set(body,'$.screen',:message),updated=:time WHERE id=:id AND owner=:owner",{
    ':id':`user:${id}`,':owner':ownerId(id),':message':messageId,':time':now()});
}
export async function navigateUser(id,mode) {
  await user(id);
  const result=await db.run(`UPDATE records SET body=json_remove(json_set(body,'$.mode',:mode,'$.generation',coalesce(json_extract(body,'$.generation'),0)+1),'$.draft','$.water'),updated=:time WHERE id=:id AND owner=:owner RETURNING id,body,updated`,{
    ':id':`user:${id}`,':owner':id,':mode':mode,':time':now()});
  return decode(result.rows[0]);
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
export async function eraseUserData(id) {
  const owner=ownerId(id);
  const before=await db.get('SELECT COUNT(*) AS n FROM records WHERE owner=:owner',{':owner':owner});
  await db.run('DELETE FROM records WHERE owner=:owner',{':owner':owner});
  await db.run('DELETE FROM ai_usage_v2 WHERE owner=:owner AND created<=:since',{':owner':owner,':since':now()-86400000});
  return before?.n??0;
}
