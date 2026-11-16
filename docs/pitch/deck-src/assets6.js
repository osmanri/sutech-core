// Assets for the modern dark deck: white / lime / deep icons, glow blobs, base background.
const {chromium}=require('/opt/node-tools/node_modules/playwright');const fs=require('fs');
const C={white:'#ffffff',lime:'#81ca2a',deep:'#00382a',pale:'#b9e07a'};
const N=['farm','drop-half','grains','drop','handshake','device-mobile','calculator','chart-line-up','cloud-rain','chart-bar','cpu','warning-circle',
 'users-three','wifi-slash','check-circle','check','map-pin','calendar','plant','scales','flask','coins','translate','robot','map-trifold','qr-code',
 'chat-circle-text','waves','warning','thumbs-up','lightbulb','shield-warning','quotes','arrow-right','timer','sun','target','trophy','lightning','globe-hemisphere-east'];
(async()=>{const b=await chromium.launch();const p=await b.newPage({deviceScaleFactor:4});
 for(const n of N) for(const c of Object.keys(C)){
  const f=`../dl/core/package/assets/regular/${n}.svg`; if(!fs.existsSync(f)){console.log('missing',n);break;}
  const svg=fs.readFileSync(f,'utf8').replace('<svg ',`<svg width="128" height="128" style="display:block;color:${C[c]}" `);
  await p.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
  await (await p.$('svg')).screenshot({path:`m/${n}-${c}.png`,omitBackground:true});}
 // glow blobs
 const g=await b.newPage({viewport:{width:1000,height:1000},deviceScaleFactor:1});
 for(const [name,col,a] of [['glow-lime','129,202,42',.55],['glow-green','60,156,36',.6],['glow-white','200,255,190',.28]]){
  await g.setContent(`<html><body style="margin:0;background:transparent"><div id="g" style="width:1000px;height:1000px;background:radial-gradient(circle at 50% 50%, rgba(${col},${a}) 0%, rgba(${col},${a*0.45}) 30%, rgba(${col},0) 68%)"></div></body></html>`);
  await (await g.$('#g')).screenshot({path:`m/${name}.png`,omitBackground:true});}
 // base background: deep emerald gradient + faint dot grid + grain
 const bg=await b.newPage({viewport:{width:1920,height:1080}});
 let dots='';for(let x=40;x<1920;x+=48)for(let y=36;y<1080;y+=48)dots+=`<circle cx="${x}" cy="${y}" r="1.4" fill="#b9e07a" fill-opacity=".09"/>`;
 await bg.setContent(`<html><body style="margin:0"><svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><defs>
  <linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#003527"/><stop offset=".55" stop-color="#002a20"/><stop offset="1" stop-color="#001d17"/></linearGradient>
  <filter id="n" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="linear" slope=".05"/></feComponentTransfer></filter></defs>
  <rect width="1920" height="1080" fill="url(#b)"/>${dots}<rect width="1920" height="1080" filter="url(#n)"/></svg></body></html>`);
 await bg.screenshot({path:'m/base.jpg',type:'jpeg',quality:88});
 await b.close();console.log('ok');})();
