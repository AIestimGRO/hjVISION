'use strict';
(async () => {
  const T=window.HJTimer;
  const el=T.$('timerWidget');
  const req=new URLSearchParams(location.search).get('layout')||'top';
  const profile=['top','side','extra'].includes(req)?req:'top';
  async function refresh(){
    try{
      const payload=await T.json(`/api/hj-timer/layout?profile=${encodeURIComponent(profile)}`);
      T.putLayout(el,payload.layout);
    }catch(err){console.warn('Timer layout sync:',err.message)}
  }
  await refresh();
  setInterval(refresh,2000);
  T.startFeed(el);
  T.connectOverlayTracking();
})();
