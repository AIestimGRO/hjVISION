/* HJ TIMER 0.2.0 — single-window integrated editing. No dependency on HJ Players data model. */
'use strict';
(() => {
  const T=window.HJTimer, $=id=>document.getElementById(id);
  const panel=$('hjTimerPanel'), widget=$('hjTimerWidget'), stage=$('stage');
  if(!T || !panel || !widget || !stage)return;
  const copy=obj=>JSON.parse(JSON.stringify(obj));
  let config=null,profile='top',mode='live',draft=null,dirty=false,saveTail=Promise.resolve();
  let busy=false,drag=null,changeSerial=0,loadSerial=0;
  const note=(msg,err=false)=>{$('hjtFeedback').textContent=msg;$('hjtFeedback').classList.toggle('error',err);};
  function layoutFromConfig(){return copy(config?.drafts?.[profile]||config?.published?.[profile]||T.defaultLayout);}
  function applyControls(){
    if(!draft)return;
    $('hjtVisible').checked=draft.visible;
    $('hjtVariant').value=draft.variant;
    $('hjtWidth').value=Math.round(draft.width*100);
    $('hjtWidthLabel').textContent=Math.round(draft.width*100)+'%';
    $('hjtOpacity').value=Math.round(draft.opacity*100);
    $('hjtOpacityLabel').textContent=Math.round(draft.opacity*100)+'%';
    $('hjtLevel').checked=draft.show_level;
    $('hjtAnte').checked=draft.show_ante;
    $('hjtUrl').textContent=`${location.origin}/overlay/timer?layout=${encodeURIComponent(profile)}`;
  }
  function renderWidget(){
    if(!config)return;
    const published=config?.published?.[profile]||T.defaultLayout;
    const current=mode==='editor'?(draft||published):published;
    T.putLayout(widget,{...current,visible:mode==='editor'?true:current.visible,
      opacity:mode==='editor'&&!current.visible?Math.max(.4,current.opacity*.65):current.opacity});
    widget.classList.toggle('editable',mode==='editor');
  }
  function sync(){
    if(!config)return;
    draft=layoutFromConfig();dirty=false;
    applyControls();renderWidget();
    const pending=Boolean(config.drafts?.[profile]);
    note(pending?'Черновик сохранён. Нажми «Опубликовать таймер», чтобы увидеть изменения в OBS.':'Таймер опубликован. Для перемещения включи режим РЕДАКТОР.');
  }
  function preview(){
    if(!draft)return;
    dirty=true;changeSerial++;
    renderWidget();
    $('hjtWidthLabel').textContent=Math.round(draft.width*100)+'%';
    $('hjtOpacityLabel').textContent=Math.round(draft.opacity*100)+'%';
    note('Изменения пока только в редакторе. Нажми «Опубликовать таймер».');
  }
  async function saveDraft(){
    if(!dirty||!config)return;
    const snapshot=copy(draft), at=profile, serial=changeSerial;
    dirty=false;
    const job=saveTail.catch(()=>{}).then(()=>T.json(`/api/hj-timer/draft/${encodeURIComponent(at)}`,{
      method:'PUT',body:JSON.stringify(snapshot)}));
    saveTail=job;
    try{
      const next=await job;
      if(profile===at){
        config=next;
        if(changeSerial===serial)draft=copy(next.drafts[at]);
      }
      note('Черновик сохранён. Для OBS нажми «Опубликовать таймер».');
    }catch(err){
      if(profile===at){dirty=true;note('Не удалось сохранить изменения: '+err.message,true)}
      throw err;
    }
  }
  async function reload(nextProfile=profile,nextMode=mode){
    const serial=++loadSerial;
    try{
      config=await T.json('/api/hj-timer/config');
      if(serial!==loadSerial)return;
      profile=nextProfile;mode=nextMode;
      sync();
    }catch(err){
      if(serial!==loadSerial)return;
      note('Модуль таймера недоступен: '+err.message,true);
      panel.querySelector('.hjt-panel-body').style.opacity='.55';
    }
  }
  async function selectContext(nextProfile,nextMode){
    if(nextProfile===profile){
      if(nextMode!==mode){mode=nextMode;renderWidget()}
      return;
    }
    if(!config)return;
    try{await saveDraft();await saveTail}catch(err){return}
    await reload(nextProfile,nextMode);
  }
  widget.addEventListener('pointerdown',e=>{
    if(mode!=='editor'||!draft||busy)return;
    e.preventDefault();e.stopPropagation();
    const rect=stage.getBoundingClientRect();
    drag={x:e.clientX,y:e.clientY,base:copy(draft),rect,id:e.pointerId};
    widget.setPointerCapture(e.pointerId);
    widget.classList.add('dragging');
  });
  widget.addEventListener('pointermove',e=>{
    if(!drag||drag.id!==e.pointerId)return;
    const x=drag.base.x+(e.clientX-drag.x)/drag.rect.width;
    const y=drag.base.y+(e.clientY-drag.y)/drag.rect.height;
    draft.x=Math.round(T.clamp(x,.03,.97)*10000)/10000;
    draft.y=Math.round(T.clamp(y,.03,.97)*10000)/10000;
    preview();
  });
  const finish=e=>{
    if(!drag||drag.id!==e.pointerId)return;
    drag=null;widget.classList.remove('dragging');
    saveDraft().catch(()=>{});
  };
  widget.addEventListener('pointerup',finish);
  widget.addEventListener('pointercancel',finish);
  for(const [id,key,transform] of [
    ['hjtVisible','visible',el=>el.checked],
    ['hjtVariant','variant',el=>el.value],
    ['hjtWidth','width',el=>Number(el.value)/100],
    ['hjtOpacity','opacity',el=>Number(el.value)/100],
    ['hjtLevel','show_level',el=>el.checked],
    ['hjtAnte','show_ante',el=>el.checked]
  ]){
    const el=$(id);
    el.addEventListener('input',()=>{if(!draft)return;draft[key]=transform(el);preview()});
    el.addEventListener('change',()=>saveDraft().catch(()=>{}));
  }
  $('hjtPublish').addEventListener('click',async()=>{
    if(busy||!config)return;
    busy=true;$('hjtPublish').disabled=true;
    try{
      await saveDraft();await saveTail;
      const result=await T.json(`/api/hj-timer/publish/${encodeURIComponent(profile)}`,{method:'POST'});
      const expected=config.drafts?.[profile];
      if(expected && JSON.stringify(result.published?.[profile])!==JSON.stringify(expected)){
        throw Error('Сервер не подтвердил изменение позиции');
      }
      if(result.drafts?.[profile])throw Error('Черновик не был опубликован');
      config=result;sync();note('✓ Таймер опубликован в OBS.');
    }catch(err){note('Ошибка публикации: '+err.message,true)}
    finally{busy=false;$('hjtPublish').disabled=false}
  });
  $('hjtDiscard').addEventListener('click',async()=>{
    if(busy||!config)return;
    busy=true;
    try{
      await saveTail;
      config=await T.json(`/api/hj-timer/discard/${encodeURIComponent(profile)}`,{method:'POST'});
      sync();note('Изменения таймера отменены; в OBS сохранена опубликованная позиция.');
    }catch(err){note('Ошибка отмены: '+err.message,true)}
    finally{busy=false}
  });
  $('hjtCopy').addEventListener('click',()=>{
    navigator.clipboard.writeText($('hjtUrl').textContent).then(()=>note('Адрес OBS скопирован.')).catch(err=>note('Не удалось скопировать: '+err.message,true));
  });
  window.addEventListener('hj:editor-context',e=>{
    const ctx=e.detail||{};const p=ctx.profile,m=ctx.mode;
    if(!p||!['editor','live'].includes(m))return;
    selectContext(p,m).catch(err=>note('Ошибка ракурса: '+err.message,true));
  });
  T.startFeed(widget,{demo:true,onUpdate:ok=>{
    $('hjtConnection').textContent=ok?'ТАЙМЕР НА СВЯЗИ':'НЕТ СВЯЗИ';
    $('hjtConnection').classList.toggle('ok',ok);
  }});
  profile=$('profile')?.value||'top';
  mode=$('editMode')?.classList.contains('active')?'editor':'live';
  reload(profile,mode);
})();
