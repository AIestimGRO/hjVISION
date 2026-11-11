'use strict';
window.HJTimer = (() => {
  const $ = id => document.getElementById(id);
  const defaultLayout = {x:.50,y:.09,width:.285,visible:true,variant:'horizontal',opacity:.96,show_ante:true,show_level:true};
  const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
  const integer = n => Math.trunc(Number(n)||0).toLocaleString('ru-RU');
  const asClock = seconds => {
    const s = Math.max(0,Math.ceil(seconds));
    return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
  };
  async function json(url, options={}) {
    const init = {...options,cache:'no-store'};
    if (init.body || ['POST','PUT','PATCH','DELETE'].includes(init.method)) {
      init.headers = {...init.headers,'Content-Type':'application/json',
        'X-HJ-Token':sessionStorage.getItem('hj_admin_token')||''};
    } else if (url.endsWith('/config')) {
      init.headers = {...init.headers,'X-HJ-Token':sessionStorage.getItem('hj_admin_token')||''};
    }
    let r=await fetch(url,init);
    if(r.status===401) {
      const token=prompt('Пароль управления HI, JACK LIVE:');
      if(!token) throw Error('Нужен пароль администратора');
      sessionStorage.setItem('hj_admin_token',token);
      return json(url,options);
    }
    const data=await r.json().catch(()=>({}));
    if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:`HTTP ${r.status}`);
    return data;
  }
  function putLayout(el, layout) {
    const p = {...defaultLayout,...layout};
    el.style.left=`${p.x*100}%`;
    el.style.top=`${p.y*100}%`;
    el.style.width=`${p.width*100}%`;
    el.style.opacity=String(p.opacity);
    el.classList.toggle('stacked',p.variant==='stacked');
    el.classList.toggle('minimal',p.variant==='minimal');
    el.classList.toggle('premium',p.variant==='premium');
    el.classList.toggle('hidden',!p.visible);
    el.querySelector('.ante')?.classList.toggle('hidden',!p.show_ante);
    el.querySelector('.timer-level, #timerLevel')?.classList.toggle('hidden',!p.show_level);
  }
  function draw(el, sample, demo=false) {
    // A feed sample is used only until it expires; do not keep running a stale clock.
    const valid = sample?.data?.connected && sample.data.state && performance.now()-sample.received<4500;
    const s= valid?sample.data.state : (demo ? {kind:'level',status:'running',sb:300,bb:600,ante:600,level:4,remaining_sec:754}:null);
    el.classList.toggle('offline',!valid);
    if(!s){
      el.querySelector('.timer-level, #timerLevel').textContent='HI, JACK TIMER';
      el.querySelector('.clock-status, #timerStatus').innerHTML='<i class="live-dot"></i>НЕТ СВЯЗИ';
      el.querySelector('.blinds, #timerBlinds').textContent='— / —';
      el.querySelector('.countdown, #timerCount').textContent='--:--';
      el.querySelector('.ante, #timerAnte').textContent=' ';return;
    }
    const running = s.status==='running';
    const elapsed = valid && running ? (performance.now()-sample.received)/1000 : 0;
    const remaining = Math.max(0, s.remaining_sec-elapsed);
    el.querySelector('.countdown, #timerCount').textContent=asClock(remaining);
    el.classList.toggle('paused',!running);
    el.querySelector('.clock-status, #timerStatus').innerHTML='<i class="live-dot"></i>' + (!valid?'ДЕМО':running?'В ЭФИРЕ':s.status==='paused'?'ПАУЗА':'ОСТАНОВЛЕН');
    if(s.kind==='break'||s.kind==='gap') {
      el.querySelector('.timer-level, #timerLevel').textContent=s.kind==='break'?'ПЕРЕРЫВ':'СМЕНА УРОВНЯ';
      el.querySelector('.blinds, #timerBlinds').textContent='BREAK';
      el.querySelector('.ante, #timerAnte').textContent=s.kind==='break' ? (s.label||'ПЕРЕРЫВ') : 'СЛЕДУЮЩИЙ УРОВЕНЬ';
    } else {
      el.querySelector('.timer-level, #timerLevel').textContent=`УРОВЕНЬ ${String(s.level).padStart(2,'0')}`;
      el.querySelector('.blinds, #timerBlinds').textContent=`${integer(s.sb)} / ${integer(s.bb)}`;
      el.querySelector('.ante, #timerAnte').textContent=`АНТЕ ${integer(s.ante)}`;
    }
  }
  function startFeed(el,{demo=false,onUpdate=()=>{}}={}) {
    let sample=null, busy=false;
    async function poll(){
      if(busy)return;
      busy=true;
      try{
        const data=await json('/api/hj-timer/state');
        sample={data,received:performance.now()};
        onUpdate(data.connected);
      }catch(err){
        sample={data:{connected:false,state:null},received:performance.now()};
        onUpdate(false);
      }finally{busy=false;draw(el,sample,demo)}
    }
    poll();setInterval(poll,1800);setInterval(()=>draw(el,sample,demo),220);
  }
  function connectOverlayTracking(){
    let socket=null;
    function open(){
      try {
        socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws?client=overlay`);
        socket.onmessage=()=>{};
        socket.onclose=()=>setTimeout(open,2000);
        socket.onerror=()=>socket?.close();
      }catch(err){setTimeout(open,3000)}
    }
    open();
  }
  return { $, json, clamp, putLayout, startFeed, connectOverlayTracking, defaultLayout };
})();
