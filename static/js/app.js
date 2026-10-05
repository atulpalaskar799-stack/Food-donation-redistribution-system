async function api(url, method='GET', body=null){
  const opts={method,headers:{'Content-Type':'application/json'}};
  if(body!==null) opts.body=JSON.stringify(body);
  const r=await fetch(url,opts); let data={}; try{data=await r.json()}catch(e){}
  if(!r.ok){toast(data.error||'Request failed',true); throw new Error(data.error||'Request failed')}
  return data;
}
function toast(msg,error=false){const t=document.getElementById('toast');if(!t)return;t.textContent=msg;t.className='toast-msg show '+(error?'error':'');setTimeout(()=>t.className='toast-msg',3000)}
