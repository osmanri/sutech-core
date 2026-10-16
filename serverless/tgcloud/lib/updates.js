import {db} from 'sdk';
import {lock,unlock} from './store.js';
export async function once(ctx,handle) {
 const id=ctx?.update?.update_id;
 if(!Number.isSafeInteger(id))throw new Error('UPDATE_CONTEXT_REQUIRED');
 if(await db.get('SELECT id FROM update_receipts WHERE id=:id',{':id':String(id)}))return;
 const token=await lock(`update:${id}`,90);if(!token)throw new Error('UPDATE_IN_PROGRESS');
 try{
  if(await db.get('SELECT id FROM update_receipts WHERE id=:id',{':id':String(id)}))return;
  await handle();
  await db.run('INSERT OR IGNORE INTO update_receipts(id,created) VALUES(:id,:time)',{':id':String(id),':time':Date.now()});
 }finally{await unlock(`update:${id}`,token);}
}
