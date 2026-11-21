// Operator CLI: private export and offline staging restore, no deployed endpoint.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';
import {createSnapshot,encryptBackup,restoreDatabase,privatePath} from './backup-lib.mjs';

const root=fileURLToPath(new URL('.',import.meta.url));
function createPrivateFile(target){fs.mkdirSync(path.dirname(target),{recursive:true,mode:0o700});return fs.openSync(target,'wx',0o600);}

try{
 const [command,...args]=process.argv.slice(2);
 if(command==='--help'||!command){console.log('keygen --key-file PATH\nexport --key-file PATH --output PATH\nrestore-staging --key-file PATH --input PATH --output PATH');}
 else{
  const options={};for(let i=0;i<args.length;i+=2){if(!['--key-file','--input','--output'].includes(args[i])||!args[i+1]||options[args[i]])throw new Error('Invalid arguments');options[args[i]]=args[i+1];}
  if(!['keygen','export','restore-staging'].includes(command))throw new Error('Unknown command');
  const keyPath=privatePath(options['--key-file']);
  if(command==='keygen'){
   const fd=createPrivateFile(keyPath);try{fs.writeFileSync(fd,randomBytes(32));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
   console.log('Created private recovery key. Keep a separate protected copy.');
  }else{
   const key=fs.readFileSync(keyPath),output=privatePath(options['--output']);
   try{
    if(command==='restore-staging'){
     fs.mkdirSync(path.dirname(output),{recursive:true,mode:0o700});
     const result=restoreDatabase(fs.readFileSync(privatePath(options['--input'])),key,output);console.log(JSON.stringify({staging_only:true,...result}));
    }else{
     if(!process.env.TGCLOUD_TOKEN||key.length!==32)throw new Error('Missing valid credentials/key');
     const fd=createPrivateFile(output);let succeeded=false;
     try{
      delete process.env.TGCLOUD_DEBUG;delete process.env.TG_CLOUD_API_URL;
      const {runFunction}=await import('./node_modules/@tgcloud/cli/src/api/endpoints.js');
      const source=fs.readFileSync(path.join(root,'maintenance/export-snapshot.js'),'utf8');
      const response=await runFunction(process.env.TGCLOUD_TOKEN,'endpoints/private_snapshot',{'endpoints/private_snapshot':source},{},{});
      if(response.error)throw new Error('Export rejected');
      const snapshot=createSnapshot(response.result??response.return_value??response.value??response);
      fs.writeFileSync(fd,encryptBackup(snapshot,key));fs.fsyncSync(fd);succeeded=true;
      console.log(JSON.stringify({encrypted:true,counts:snapshot.counts,engine:snapshot.engine}));
     }finally{fs.closeSync(fd);if(!succeeded)fs.unlinkSync(output);}
    }
   }finally{key.fill(0);}
  }
 }
}catch{console.error('Backup operation failed. Check arguments, private paths, key, credentials and destination; no data printed.');process.exitCode=1;}
