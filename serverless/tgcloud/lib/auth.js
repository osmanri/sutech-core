import {EndpointError} from 'sdk';
import {ownerId} from './store.js';
export function caller(ctx,input) {
 try{
  const id=ownerId(ctx?.initData?.user?.id),stamp=Number(ctx.initData.auth_date);
  if(!Number.isFinite(stamp)||Date.now()/1000-stamp>86400||stamp>Date.now()/1000+300)throw new Error();
  if(JSON.stringify(input).length>8192)throw new Error();
  return id;
 }catch{throw new EndpointError('Invalid or expired session',{code:'UNAUTHENTICATED'});}
}
