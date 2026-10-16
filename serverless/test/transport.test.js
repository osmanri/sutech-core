import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const transport=fs.readFileSync(new URL('../web/transport.js',import.meta.url),'utf8');
const redirect=fs.readFileSync(new URL('../../frontend/js/serverless-location.js',import.meta.url),'utf8');
test('Mini App sends only payload through official SDK; abort does not create a late result',async()=>{
 let called,reply;const window={Telegram:{WebApp:{Serverless:{call:(name,body,cb)=>{called={name,body};reply=cb;}}}}};
 vm.runInNewContext(transport,{window,DOMException});const controller=new AbortController();
 const result=window.SuTechServerless.request('analyze',{body:JSON.stringify({init_data:'signed-session',payload:{area:1}}),signal:controller.signal});
 assert.equal(called.name,'analyze');assert.equal(called.body.init_data,undefined);assert.equal(called.body.payload.area,1);
 controller.abort();reply(null,{ok:true});await assert.rejects(result,{name:'AbortError'});
});
test('old Mini App links preserve language and signed fragment only to fixed Telegram host',()=>{
 for(const [host,signed,expected] of [['frontend-2-mauve.vercel.app',true,true],['frontend-2-mauve.vercel.app',false,false],['app8796056339.tgcloud.ai',true,false]]){
  let destination=null;const window={location:{hostname:host,search:'?lang=kz',hash:'#tgWebAppData=test-fixture',replace:v=>destination=v},Telegram:{WebApp:{initData:signed?'test-fixture':''}},addEventListener:()=>{}};
  vm.runInNewContext(redirect,{window});assert.equal(!!destination,expected);
  if(expected)assert.equal(destination,'https://app8796056339.tgcloud.ai/?lang=kz#tgWebAppData=test-fixture');
 }
});
