import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('.',import.meta.url));
const dist=path.join(root,'dist');fs.mkdirSync(dist,{recursive:true});
for(const item of ['index.html','css','img','js','vendor'])fs.cpSync(path.join(root,'../frontend',item),path.join(dist,item),{recursive:true});
const appFile=path.join(dist,'js/app.js');let app=fs.readFileSync(appFile,'utf8');
if(!app.includes("window.SuTechServerless.request('analyze',")||app.includes('sutech-core.onrender.com'))throw new Error('Review Mini App transport before deployment');
fs.copyFileSync(path.join(root,'web/transport.js'),path.join(dist,'js/serverless-transport.js'));
for(const dir of [path.join(root,'tgcloud'),dist]){
 for(const file of walk(dir)){
  if(!/\.(?:js|html|css|json)$/.test(file))continue;
  const text=fs.readFileSync(file,'utf8');
  if(/AIza[\w-]{25,}|app\d+:[\w-]{20,}|postgres(?:ql)?:\/\/[^\s'"<>]+/i.test(text))throw new Error('Credential pattern in publishable file: '+path.relative(root,file));
 }
}
function* walk(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())yield*walk(p);else yield p;}}
console.log('Built existing Mini App with Telegram Serverless transport; secret scan passed.');
