(function(){
 'use strict';
 window.SuTechServerless={request:function(name,options){
  return new Promise(function(resolve,reject){
   var sdk=window.Telegram&&window.Telegram.WebApp&&window.Telegram.WebApp.Serverless;
   if(!sdk||typeof sdk.call!=='function'){reject(new Error('Update Telegram to open this Mini App'));return;}
   var ended=false;
   function cancel(){if(!ended){ended=true;reject(new DOMException('Request cancelled','AbortError'));}}
   if(options.signal){if(options.signal.aborted){cancel();return;}options.signal.addEventListener('abort',cancel,{once:true});}
   var body=JSON.parse(options.body||'{}');delete body.init_data;
   sdk.call(name,body,function(error,result){
    if(ended)return;ended=true;if(options.signal)options.signal.removeEventListener('abort',cancel);
    if(error){reject(new Error(error.parameters&&error.parameters.code||error.message||'Request failed'));return;}
    resolve({ok:true,status:200,json:function(){return Promise.resolve(result);}});
   });
  });
 }};
})();
