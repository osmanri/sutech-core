import {EndpointError} from 'sdk';
import {caller} from '../lib/auth.js';
import {waterField,card} from '../lib/fields.js';
export default async function(input,ctx){
 const id=caller(ctx,input);
 try{await waterField(id,input.field_id,input.applied_m3,input.expected_deficit,input.revision??null);return {ok:true,field:await card(id,input.field_id)};}
 catch(e){throw new EndpointError('Could not record watering',{code:['balance_changed','not_found','busy'].includes(e.message)?e.message:'INVALID_INPUT'});}
}
