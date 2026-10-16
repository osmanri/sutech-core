import {caller} from '../lib/auth.js';
import {list} from '../lib/store.js';
import {card} from '../lib/fields.js';
export default async function(input,ctx){
 const id=caller(ctx,input),rows=await list(id,'field',100),fields=[];
 for(const row of rows){try{fields.push(await card(id,row.id));}catch(e){fields.push({id:row.id,crop:row.payload.crop,area_ha:Number(row.payload.area)/(row.payload.area_unit==='sotka'?100:1),status:e.message==='season_ended'?'season_ended':'unavailable'});}}
 fields.sort((a,b)=>({critical:0,irrigate:1,deferred:2}[a.status]??3)-({critical:0,irrigate:1,deferred:2}[b.status]??3));
 return {ok:true,fields};
}
