import {message} from '../lib/bot.js';
import {once} from '../lib/updates.js';
export default async function(input,ctx){await once(ctx,()=>message(input,ctx));}
