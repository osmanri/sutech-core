import {db} from 'sdk';
import {lock} from './store.js';

// Activity-driven maintenance, not a scheduler. Keep this lease for its full
// minute so concurrent updates do not all scan the operational tables.
export async function pruneOperationalData() {
 if(!await lock('maintenance:retention',60))return {ran:false};
 const now=Date.now(),day=86400000;
 await db.run('DELETE FROM update_receipts WHERE created<=:cutoff',{':cutoff':now-7*day});
 await db.run('DELETE FROM ai_usage_v2 WHERE created<=:cutoff',{':cutoff':now-day});
 await db.run('DELETE FROM leases WHERE until<:cutoff',{':cutoff':now-90000});
 await db.run(`DELETE FROM records WHERE
   (kind='ai-context' AND updated<=:context) OR
   (kind='pending' AND updated<=:pending) OR
   (kind='photo-comparison' AND updated<=:photo) OR
   (owner=0 AND kind='weather' AND updated<=:weather)`,{
   ':context':now-1800000,':pending':now-7*day,':photo':now-30*day,':weather':now-day});
 return {ran:true};
}
