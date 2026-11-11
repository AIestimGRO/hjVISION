'use strict';
const HJ = (() => {
  const esc = str => String(str ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const styles={compact:'COMPACT',classic:'CLASSIC',premium:'PREMIUM'};
  const statusLabels={active:'ACTIVE','all-in':'ALL-IN',fold:'FOLD',out:'OUT',winner:'WINNER'};
  let themeCatalog=[];
  const setThemes=items=>{themeCatalog=Array.isArray(items)?items:[];};
  const getThemes=()=>themeCatalog;
  const themeById=id=>themeCatalog.find(x=>x.id===id) || themeCatalog.find(x=>x.id==='bronze-premium');
  const profileFromQuery=()=>new URLSearchParams(location.search).get('layout') || 'auto';
  const currentProfile=(state,requested)=>requested==='auto'?state.active_profile:(state.profiles[requested]?requested:state.active_profile);
  function makeBadge(player, placement, selected=false, settings={}){
    const el=document.createElement('div');
    const style=placement.style||player.style||settings.default_style||'classic';
    const theme=player.theme || settings.theme || 'bronze-premium';
    const colors=themeById(theme)||{color:'#ffe4b7',glow:'#ec9543',accent:'#d39a52'};
    el.className=`hj-badge ${style} status-${player.status||'active'}${selected?' selected':''}`;
    el.dataset.id=player.id;el.dataset.theme=theme;
    // Art and text are independent layers: no name is baked into frame.svg.
    // Themes are loaded from local asset packs without changing the rendering code.
    if (/^[a-z][a-z0-9-]*$/.test(theme)) el.style.setProperty('--frame-url',`url('${colors.frame_url||'/themes/bronze-premium/frame.svg'}')`);
    el.style.setProperty('--metal-text',colors.color);el.style.setProperty('--metal-glow',colors.glow);
    const caption=player.is_dealer?'DEALER':player.seat?`BOX ${String(player.seat).padStart(2,'0')}`:'NO BOX';
    el.innerHTML=`<span class="hj-metal" aria-hidden="true"></span><span class="hj-inner"><span class="hj-gem" aria-hidden="true">♠</span><span class="hj-name">${esc(player.nickname)}</span><span class="hj-caption">${caption}</span></span><span class="hj-resize-handle" title="Изменить ширину и высоту"></span>`;
    el._placement=placement;
    positionBadge(el,placement);
    if(!player.visible || !placement.visible || player.status==='out')el.classList.add('hidden-badge');
    return el;
  }
  function positionBadge(el,p){
    el._placement=p;
    el.style.left=`${p.x*100}%`;el.style.top=`${p.y*100}%`;
    el.style.width=`${p.width*100}%`;el.style.height=`${(p.height??.065)*100}%`;
    el.style.opacity=`${p.opacity??1}`;
    el.style.setProperty('--rotation',`${p.rotation||0}deg`);
    el.style.setProperty('--badge-scale',p.scale??1);
    el.style.setProperty('--badge-pad',`${p.padding??8}px`);
    el.style.setProperty('--badge-glow',p.glow??.6);
    fitBadge(el);
  }
  function fitBadge(el){
    const root=el.parentElement;
    if(!root)return;
    const p=el._placement||{};
    const canvasScale=Math.max(.1,root.clientWidth/1920);
    const fontPx=(p.font_size??24)*canvasScale;
    el.style.setProperty('--canvas-scale',canvasScale);
    el.style.setProperty('--font-px',`${fontPx}px`);
    const text=el.querySelector('.hj-name');
    if(!text)return;
    text.style.fontSize=`${fontPx}px`;
    for(let i=0;i<12 && text.scrollWidth>text.clientWidth+1;i++){
      const next=Math.max(4*canvasScale,parseFloat(text.style.fontSize)*.9);
      text.style.fontSize=`${next}px`;
      if(next<=4*canvasScale)break;
    }
  }
  function socket(onMessage,onStatus){
    let ws,retry=600,stopped=false;
    const connect=()=>{
      if(stopped)return;
      const protocol=location.protocol==='https:'?'wss:':'ws:';
      ws=new WebSocket(`${protocol}//${location.host}/ws?client=${location.pathname.startsWith('/overlay/')?'overlay':'admin'}`);
      ws.onopen=()=>{retry=600;onStatus?.(true);};
      ws.onmessage=e=>{try{onMessage(JSON.parse(e.data));}catch(err){console.error('HJ websocket payload',err);}};
      ws.onclose=()=>{onStatus?.(false);if(!stopped){setTimeout(connect,retry);retry=Math.min(retry*1.7,8000);}};
      ws.onerror=()=>ws.close();
    };connect();return()=>{stopped=true;ws?.close();};
  }
  const getToken=()=>sessionStorage.getItem('hj_admin_token')||'';
  async function api(url,options={}){
    const headers={'X-HJ-Token':getToken(),...(options.headers||{})};
    if(options.body && !(options.body instanceof FormData))headers['Content-Type']='application/json';
    // Do not leave the operator waiting forever for a stalled mutation.
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),10000);
    let response;
    try{
      response=await fetch(url,{...options,headers,signal:options.signal||controller.signal});
    } catch(err) {
      if(controller.signal.aborted)throw Error('Сервер не ответил за 10 секунд. Проверьте соединение; не повторяйте действие, пока состояние не обновится.');
      throw err;
    } finally { clearTimeout(timeout); }
    if(response.status===401){
      const token=prompt('Пароль администратора HJ CONTROL:');
      if(!token)throw Error('Нужен пароль администратора');
      sessionStorage.setItem('hj_admin_token',token);return api(url,options);
    }
    const result=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(result.detail||`HTTP ${response.status}`);
    return result;
  }
  // Diagnostics run only in operator panels (never in OBS overlays).
  if(['/admin','/modules','/ai'].includes(location.pathname)){
    const report=(kind,message)=>{
      const body=JSON.stringify({kind,message:String(message||'').slice(0,260)});
      fetch('/api/desktop/client-error',{method:'POST',headers:{'Content-Type':'application/json'},body,keepalive:true}).catch(()=>{});
    };
    window.addEventListener('error',e=>report('error',e.message));
    window.addEventListener('unhandledrejection',e=>report('promise',e.reason?.message||'Unhandled promise'));
    const pulse=()=>fetch('/api/desktop/heartbeat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({page:location.pathname}),cache:'no-store'}).catch(()=>{});
    pulse();setInterval(pulse,3000);
  }
  return {esc,styles,statusLabels,setThemes,getThemes,themeById,profileFromQuery,currentProfile,makeBadge,positionBadge,fitBadge,socket,api};
})();
