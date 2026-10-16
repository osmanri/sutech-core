import {EndpointError} from 'sdk';
import {caller} from '../lib/auth.js';
import {user,saveUser} from '../lib/store.js';
import {navigate} from '../lib/ui.js';
import {deliverCalculation} from '../lib/bot.js';
export default async function(input,ctx){
 const id=caller(ctx,input),payload=input?.payload;
 if(!payload||typeof payload!=='object'||Array.isArray(payload))throw new EndpointError('Missing field',{code:'INVALID_INPUT'});
 const u=await user(id);if(['ru','kz','en'].includes(payload.lang)){u.lang=payload.lang;await saveUser(id,u);}
 await navigate(id);return deliverCalculation(id,payload);
}
