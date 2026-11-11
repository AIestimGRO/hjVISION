'use strict';
(async () => {
  const T=window.HJTimer,$=T.$;
  const stage=$('stage'),el=$('timerWidget');
  let profile='top',config=null,draft=null,dragging=null,saveTask=Promise.resolve(),saving=0;
  const clone = obj => JSON.parse(JSON.stringify(obj));
  const current = () => config?.drafts?.[profile]||config?.published?.[profile]||T.defaultLayout;
  function message(s,error=false){$('message').textContent=s;$('message').classList.toggle('error',error)}
  function mark(){
    const dirty=!!config?.drafts?.[profile];
    $('publishStatus').textContent=dirty?'ЧЕРНОВИК • НЕ В ЭФИРЕ':'ОПУБЛИКОВАНО';
    $('publishStatus').style.color=dirty?'#f6be85':'#96d8aa';
    $('syncStatus').textContent=saving?'Сохраняется...':dirty?'Публикация требуется':'';
  }
  function show(){
    const p=current();draft=clone(p);
    T.putLayout(el,{...p,visible:true,opacity:p.visible?p.opacity:.6});
    $('visible').checked=p.visible;
    $('variant').value=p.variant;
    $('width').value=Math.round(p.width*100);
    $('widthValue').textContent=Math.round(p.width*100)+'%';
    $('opacity').value=Math.round(p.opacity*100);
    $('opacityValue').textContent=Math.round(p.opacity*100)+'%';
    $('show_ante').checked=p.show_ante;
    $('show_level').checked=p.show_level;
    $('url').textContent=`${location.origin}/overlay/timer?layout=${encodeURIComponent(profile)}`;
    const frame=localStorage.getItem('hj-timer-frame-'+profile);
    $('previewImage').style.backgroundImage=frame?`url(${JSON.stringify(frame)})`:'';
    mark();
  }
  function preview(){
    T.putLayout(el,{...draft,visible:true,opacity:draft.visible?draft.opacity:.6});
    $('widthValue').textContent=Math.round(draft.width*100)+'%';
    $('opacityValue').textContent=Math.round(draft.opacity*100)+'%';
    $('publishStatus').textContent='ИЗМЕНЕНО • НЕ В ЭФИРЕ';
    $('publishStatus').style.color='#f6be85';
    $('syncStatus').textContent='Изменения ещё не опубликованы';
  }
  function save(){
    const profileAtCall=profile, payload=clone(draft);
    saving++;mark();
    const job=saveTask.catch(()=>{}).then(()=>T.json(`/api/hj-timer/draft/${profileAtCall}`,{method:'PUT',body:JSON.stringify(payload)}))
      .then(updated=>{if(profileAtCall===profile){config=updated;draft=clone(updated.drafts[profileAtCall]);}return updated;})
      .catch(err=>{message(`Не удалось сохранить черновик: ${err.message}`,true);throw err;})
      .finally(()=>{saving--;mark()});
    saveTask=job;
    return job;
  }
  async function publish(){
    $('publish').disabled=true;
    try{
      await saveTask;
      // Publish always saves the latest visible edit even if it was changed by a slider.
      await save();
      config=await T.json(`/api/hj-timer/publish/${profile}`,{method:'POST'});
      show();message('Позиция таймера опубликована. В OBS обновится автоматически.');
    }catch(err){message('Ошибка публикации: '+err.message,true)}
    finally{$('publish').disabled=false}
  }
  try{config=await T.json('/api/hj-timer/config');show();}
  catch(err){message('Не удалось загрузить настройки: '+err.message,true);return;}
  T.startFeed(el,{demo:true,onUpdate:connected=>{
    $('remoteStatus').textContent=connected?'● Подключено к timer.hijackpoker.ru — данные реальные':'○ Нет связи с timer.hijackpoker.ru. В РЕДАКТОРЕ показан ДЕМО-пример, в OBS будут прочерки.';
    $('demoCaption').classList.toggle('hidden',connected);
  }});
  $('profile').onchange=async e=>{
    await saveTask.catch(()=>{});
    profile=e.target.value;
    show();
  };
  for(const key of ['visible','show_ante','show_level','variant','width','opacity']){
    const input=$(key);
    const change=()=>{
      const value=key==='width'?Number(input.value)/100:key==='opacity'?Number(input.value)/100:
        input.type==='checkbox'?input.checked:input.value;
      draft[key]=value;
      preview();
    };
    input.addEventListener('input',change);
    input.addEventListener('change',()=>{change();save().catch(()=>{});});
  }
  el.addEventListener('pointerdown',e=>{
    e.preventDefault();
    dragging={pointer:e.pointerId,rect:stage.getBoundingClientRect(),x:e.clientX,y:e.clientY,
      oldX:draft.x,oldY:draft.y};
    el.setPointerCapture(e.pointerId);el.classList.add('dragging');
  });
  el.addEventListener('pointermove',e=>{
    if(!dragging||dragging.pointer!==e.pointerId)return;
    draft.x=T.clamp(dragging.oldX+(e.clientX-dragging.x)/dragging.rect.width,draft.width/2,1-draft.width/2);
    draft.y=T.clamp(dragging.oldY+(e.clientY-dragging.y)/dragging.rect.height,.035,.96);
    preview();
  });
  const finish=()=>{
    if(!dragging)return;
    dragging=null;el.classList.remove('dragging');save().catch(()=>{});
  };
  el.addEventListener('pointerup',finish);el.addEventListener('pointercancel',finish);
  $('publish').onclick=publish;
  $('discard').onclick=async()=>{
    await saveTask.catch(()=>{});
    try{config=await T.json(`/api/hj-timer/discard/${profile}`,{method:'POST'});show();message('Изменения отменены. В OBS остаётся опубликованная позиция.');}
    catch(err){message(err.message,true)}
  };
  $('resetPosition').onclick=()=>{draft.x=.5;draft.y=.09;preview();save().catch(()=>{})};
  $('toggleGrid').onclick=()=>stage.classList.toggle('grid');
  $('copyUrl').onclick=()=>navigator.clipboard.writeText($('url').textContent).then(()=>message('Адрес оверлея скопирован')).catch(()=>message('Скопируйте адрес вручную',true));
  $('chooseImage').onclick=()=>$('frameFile').click();
  $('removeImage').onclick=()=>{localStorage.removeItem('hj-timer-frame-'+profile);$('previewImage').style.backgroundImage=''};
  $('frameFile').onchange=e=>{
    const file=e.target.files?.[0];if(!file)return;
    if(file.size>20*1024*1024){message('Изображение должно быть меньше 20 МБ',true);return;}
    const reader=new FileReader();reader.onload=()=>{
      const img=new Image();img.onload=()=>{
        const canvas=document.createElement('canvas');canvas.width=1920;canvas.height=1080;
        const ctx=canvas.getContext('2d');ctx.fillStyle='#000';ctx.fillRect(0,0,1920,1080);
        const scale=Math.min(1920/img.width,1080/img.height);
        ctx.drawImage(img,(1920-img.width*scale)/2,(1080-img.height*scale)/2,img.width*scale,img.height*scale);
        try{localStorage.setItem('hj-timer-frame-'+profile,canvas.toDataURL('image/jpeg',.65));show();}
        catch(err){message('Недостаточно памяти для этого изображения',true);return;}
        const off=Math.abs(img.width/img.height-16/9)>.015;
        message(off?`Кадр ${img.width}×${img.height} не 16:9. Поставлены поля без обрезки; лучше взять полный кадр OBS.`:'Кадр загружен только в редактор.');
      };img.src=reader.result;
    };reader.readAsDataURL(file);e.target.value='';
  };
})();
