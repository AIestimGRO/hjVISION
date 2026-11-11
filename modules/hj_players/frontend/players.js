'use strict';
(async()=>{
  const root=document.getElementById('playersOverlay');
  const requested=HJ.profileFromQuery();
  await fetch('/api/themes').then(r=>r.json()).then(r=>HJ.setThemes(r.themes)).catch(console.error);
  let state=null;
  function render(snapshot){
    state=snapshot;
    const profile=HJ.currentProfile(state,requested);
    const placements=state.profiles[profile]?.placements||{};
    const active=new Set();
    for(const player of [...state.players,state.dealer]){
      active.add(player.id);
      const p=placements[player.id];
      const old=[...root.children].find(el=>el.dataset.id===player.id);
      if(!p){old?.remove();continue;}
      const badge=HJ.makeBadge(player,p,false,state.settings);
      if(!player.is_dealer)badge.querySelector('.hj-caption')?.remove(); // hide physical BOX number
      if(old){
        // Replace only the changed DOM node; never reload the OBS browser source.
        badge.classList.add('existing');old.replaceWith(badge);
      }else{badge.classList.add('badge-enter');root.appendChild(badge);}
      HJ.fitBadge(badge);
    }
    for(const el of [...root.children])if(!active.has(el.dataset.id))el.remove();
  }
  HJ.socket(message=>{if(message.type==='state')render(message.state);});
  window.addEventListener('resize',()=>{if(state)render(state);});
})();
