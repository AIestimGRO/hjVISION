'use strict';
(() => {
  const root=document.getElementById('effectVisual');
  let queue=[], active=null, timer=null, audioContext=null, currentOscillators=[];
  const names={'ALL-IN':'ALL IN','PLAYER OUT':'PLAYER OUT','DOUBLE UP':'DOUBLE UP',WINNER:'WINNER','FINAL TABLE':'FINAL TABLE',BREAK:'BREAK',BOUNTY:'BOUNTY',JACKPOT:'JACKPOT'};
  const icons={'ALL-IN':'♠','PLAYER OUT':'✖','DOUBLE UP':'×2',WINNER:'★','FINAL TABLE':'♛',BREAK:'◷',BOUNTY:'◎',JACKPOT:'◆'};
  function stop(){queue=[];active=null;clearTimeout(timer);root.replaceChildren();for(const osc of currentOscillators){try{osc.stop();}catch(_){}}currentOscillators=[];}
  function sound(evt){
    if(!evt.sound || evt.volume<=0) return;
    try {
      audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
      if(audioContext.state==='suspended')audioContext.resume();
      const notes=evt.name==='PLAYER OUT'?[440,349,261]:evt.name==='WINNER'?[392,523,659,784]:[330,440,554];
      const start=audioContext.currentTime+.03;
      notes.forEach((freq,index)=>{
        const osc=audioContext.createOscillator(),gain=audioContext.createGain();
        const t=start+index*.11;osc.type='sine';osc.frequency.setValueAtTime(freq,t);
        gain.gain.setValueAtTime(.001,t);gain.gain.exponentialRampToValueAtTime(Math.max(.001,evt.volume*.095),t+.04);
        gain.gain.exponentialRampToValueAtTime(.001,t+.32);
        osc.connect(gain);gain.connect(audioContext.destination);
        osc.start(t);osc.stop(t+.34);currentOscillators.push(osc);
      });
    } catch(err){console.warn('Audio could not start',err);}
  }
  function playNext(){
    if(active || !queue.length) return;
    active=queue.shift();
    const e=active;
    root.innerHTML=`<div class="fx-screen fx-${e.name.toLowerCase().replace(/\s+/g,'-')}" style="--fx-exit-start:${Math.max(250,e.duration-350)}ms"><div class="fx-rings"><i></i><i></i><i></i></div><div class="fx-sparks"></div><div class="fx-medallion">${icons[e.name]||'♠'}</div><div class="fx-kicker">HI, JACK CLUB · LIVE MOMENT</div><div class="fx-title">${HJ.esc(names[e.name]||e.name)}</div>${e.nickname?`<div class="fx-player">${HJ.esc(e.nickname)}</div>`:''}<div class="fx-line"></div></div>`;
    sound(e);
    timer=setTimeout(()=>{root.replaceChildren();active=null;playNext();},e.duration);
  }
  const seen = new Set();
  HJ.socket(message=>{
    if(message.type==='effect-stop'){stop();return;}
    if(message.type==='effect' && !seen.has(message.event_id)){
      seen.add(message.event_id);
      if(seen.size>150)seen.clear();
      if(queue.length>=8) queue.shift();
      queue.push(message);playNext();
    }
  });
})();
