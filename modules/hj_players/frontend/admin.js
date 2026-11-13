'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const api=HJ.api;
  let pendingGlobalTheme=null, pendingGlobalStyle=null;
  let state=null, mode='live', selected=null, drag=null, showGrid=false, modalAction='add';
  let draftChanges={}, saving=false, saveInFlight=null, publishing=false, toastTimer=null;
  const effectIcons={'ALL-IN':'♠','PLAYER OUT':'✕','DOUBLE UP':'×2',WINNER:'★','FINAL TABLE':'♛',BREAK:'◷',BOUNTY:'◎',JACKPOT:'◆'};
  const effectDescriptions={'ALL-IN':'All chips in','PLAYER OUT':'Elimination','DOUBLE UP':'Big comeback',WINNER:'Champion','FINAL TABLE':'Showtime',BREAK:'Time-out',BOUNTY:'Knockout',JACKPOT:'Big moment'};
  const statuses=[['active','ACTIVE'],['all-in','ALL-IN'],['fold','FOLD'],['out','OUT'],['winner','WINNER']];
  let profileId= 'top';
  let widePreview = localStorage.getItem('hj-editor-wide') === 'true';
  let badgeSettingsMode = localStorage.getItem('hj-badge-settings-mode') === 'advanced' ? 'advanced' : 'basic';
  const setToast=(text,bad=false)=>{
    const t=$('toast');t.textContent=text;t.classList.toggle('error',bad);t.classList.add('show');
    clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('show'),3100);
  };
  const post=(path,obj={})=>api(path,{method:'POST',body:JSON.stringify(obj)});
  const patch=(path,obj)=>api(path,{method:'PATCH',body:JSON.stringify(obj)});
  const put=(path,obj)=>api(path,{method:'PUT',body:JSON.stringify(obj)});
  const del=path=>api(path,{method:'DELETE'});
  const act=async op=>{try{await op();}catch(err){setToast(err.message,true);}};
  function placementFor(id) {
    if(!state) return null;
    return draftChanges[id] || (mode==='editor' ? state.drafts?.[profileId]?.[id] : null) || state.profiles?.[profileId]?.placements?.[id] || null;
  }
  function render(){
    if(!state)return;
    if(!state.profiles[profileId])profileId=state.active_profile;
    $('count').textContent=`${state.players.length} / 10`;
    $('addPlayer').disabled=state.players.length>=10;
    $('profile').innerHTML=Object.entries(state.profiles).map(([k,v])=>`<option value="${HJ.esc(k)}">${HJ.esc(v.name)}</option>`).join('');
    $('profile').value=profileId;
    $('profileTag').textContent=state.profiles[profileId].name;
    const url=`${location.origin}/overlay/players?layout=${encodeURIComponent(profileId)}`;
    $('playersUrl').textContent=url.replace(/^https?:\/\//,'');
    $('effectsUrl').textContent=`${location.host}/overlay/effects`;
    $('saveState').textContent=`SQLite · версия #${state.revision} · сохранено`;
    const chosenTarget=$('effectTarget').value;
    $('effectTarget').innerHTML=`<option value="">Без привязки</option>`+state.players.map(p=>`<option value="${HJ.esc(p.id)}">${HJ.esc(p.nickname)}</option>`).join('');
    $('effectTarget').value=state.players.some(p=>p.id===chosenTarget)?chosenTarget:'';
    $('volume').value=Math.round(state.settings.volume*100);
    $('volumeValue').textContent=`${Math.round(state.settings.volume*100)}%`;
    if(pendingGlobalTheme===null)pendingGlobalTheme=state.settings.theme||'bronze-premium';
    if(pendingGlobalStyle===null)pendingGlobalStyle=state.settings.default_style||'classic';
    renderThemes();renderPlayers();renderStage();renderProperties();renderEditorStatus();
    // Notify optional modules without requiring HJ PLAYERS to know their internals.
    window.dispatchEvent(new CustomEvent('hj:editor-context',{detail:{profile:profileId,mode}}));
  }
  function renderEditorStatus(){
    const editor=mode==='editor';
    $('liveMode').classList.toggle('active',!editor);
    $('editMode').classList.toggle('active',editor);
    $('editorBar').hidden=!editor;
    $('publishTop').hidden=!editor;
    $('publish').disabled=publishing;
    $('publishTop').disabled=publishing;
    $('autoPlace').disabled=publishing;
    $('properties').hidden=!editor || !selected;
    $('dashboard').classList.toggle('editor-wide',editor && widePreview);
    $('widePreview').setAttribute('aria-pressed',String(editor && widePreview));
    $('widePreview').textContent=editor && widePreview?'⛶ Обычный размер':'⛶ Широкий кадр';
    $('widePreview').title=editor && widePreview?'Вернуть компактное расположение панели':'Расширить кадр 16:9 на ширину приложения';
    $('stage').classList.toggle('editable',editor);
    $('stageGrid').classList.toggle('show',showGrid&&editor);
    $('stageHint').textContent=editor?'Перетащите или поверните плашку, затем нажмите «Опубликовать в OBS».':'Изменения никнеймов сразу попадают в эфир';
    const unsaved=Boolean(Object.keys(draftChanges).length || saveInFlight);
    const hasDraft=Boolean(state?.drafts?.[profileId] || unsaved);
    $('draftLabel').textContent=publishing?'Публикация и проверка координат в OBS...':unsaved?'Сохраняем черновик... Не закрывайте приложение.':hasDraft?'Черновик сохранён, но НЕ опубликован в OBS. Нажмите «Опубликовать в OBS».':'Переместите или поверните плашки, затем опубликуйте раскладку.';
  }
  function selectInput(values,chosen,attrs){
    return `<select ${attrs}>${values.map(([value,label])=>`<option value="${HJ.esc(value)}" ${String(value)===String(chosen)?'selected':''}>${HJ.esc(label)}</option>`).join('')}</select>`;
  }
  function renderThemes(){
    const items=HJ.getThemes();const container=$('themeCards');
    container.replaceChildren();
    for(const item of items){
      const button=document.createElement('button');button.className='theme-card';
      if(item.id===pendingGlobalTheme)button.classList.add('selected');
      button.innerHTML=`<img src="${HJ.esc(item.frame_url)}" alt=""><span>${HJ.esc(item.name)}</span>`;
      button.onclick=()=>{pendingGlobalTheme=item.id;renderThemes();renderStage();};
      container.appendChild(button);
    }
    $('globalStyle').value=pendingGlobalStyle;
    $('applyTheme').disabled=!items.length;
  }
  function renderPlayers(){
    const list=$('playerList'); list.replaceChildren();
    if(!state.players.length){
      const empty=document.createElement('div');empty.className='empty-players';empty.innerHTML='<span>♠</span><b>Стол пока пуст</b><p>Добавьте игрока или загрузите демонстрационную рассадку.</p>';list.appendChild(empty);
    }
    for(const p of state.players)list.appendChild(buildRow(p));
    $('dealerRow').replaceChildren(buildRow(state.dealer));
  }
  function buildRow(p){
    const row=document.createElement('div');row.className=`player-row ${!p.visible?'is-hidden':''}`;row.dataset.player=p.id;
    if(p.is_dealer)row.classList.add('dealer-row');
    const seatOptions=[['','—'],...Array.from({length:10},(_,i)=>[i+1,String(i+1).padStart(2,'0')])];
    row.innerHTML=`<div class="player-seat">${p.is_dealer?'D':p.seat?String(p.seat).padStart(2,'0'):'—'}</div><div class="player-main"><button class="player-name" title="Изменить имя">${HJ.esc(p.nickname)}</button><span>${p.is_dealer?'Дилер':'Игрок'} · ${(p.style||state.settings.default_style||'classic').toUpperCase()}</span></div><div class="player-controls"><button class="icon-button avatar-upload" title="Загрузить фото лица">📷</button>${selectInput([['nickname','НИК'],['avatar','ФОТО'],['both','ФОТО+НИК']],p.display_mode||'nickname','aria-label="Вид плашки" class="avatar-mode"')}${!p.is_dealer?selectInput(seatOptions,p.seat??'','aria-label="Бокс" class="mini-seat"'):''}${selectInput(statuses,p.status,'aria-label="Статус игрока" class="mini-status"')}<button class="icon-button visibility" title="${p.visible?'Скрыть':'Показать'}">${p.visible?'◉':'◎'}</button>${!p.is_dealer?'<button class="icon-button more" title="Действия">···</button>':''}</div>`;
    row.querySelector('.player-name').addEventListener('click',()=>openModal('edit',p));
    row.querySelector('.avatar-upload').addEventListener('click',()=>uploadPlayerAvatar(p));
    row.querySelector('.avatar-mode').addEventListener('change',e=>act(async()=>{
      await patch('/api/players/'+encodeURIComponent(p.id),{display_mode:e.target.value});
      setToast('Режим плашки обновлён');
    }));

    row.querySelector('.visibility').addEventListener('click',()=>act(()=>patch(`/api/players/${p.id}`,{visible:!p.visible})));
    row.querySelector('.mini-status').addEventListener('change',e=>act(()=>patch(`/api/players/${p.id}`,{status:e.target.value})));
    row.querySelector('.mini-seat')?.addEventListener('change',e=>act(()=>patch(`/api/players/${p.id}`,{seat:e.target.value?Number(e.target.value):null})));
    row.querySelector('.more')?.addEventListener('click',()=>{
      document.querySelectorAll('.player-menu').forEach(el=>el.remove());
      const menu=document.createElement('div'); menu.className='player-menu';
      menu.innerHTML='<button data-action="replace">⇆ Заменить игрока</button><button data-action="style">◈ Сменить стиль</button><button class="menu-danger" data-action="delete">✕ Удалить игрока</button>';
      menu.addEventListener('click',e=>{
        const target=e.target.closest('button');if(!target)return;
        const action=target.dataset.action;menu.remove();
        if(action==='replace')openModal('replace',p);
        if(action==='style')openModal('edit',p);
        if(action==='delete')act(()=>del(`/api/players/${p.id}`));
      });row.appendChild(menu);
    });
    return row;
  }
  async function uploadPlayerAvatar(player){
    const picker = document.createElement('input');
    picker.type = 'file'; picker.accept = 'image/*';
    picker.onchange = async () => {
      const file = picker.files?.[0];
      if (!file) return;
      try {
        if (file.size > 15*1024*1024) throw Error('Фото должно быть меньше 15 МБ');
        const image = await createImageBitmap(file);
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 512;
        const context = canvas.getContext('2d');
        const crop = Math.min(image.width, image.height);
        context.drawImage(image,(image.width-crop)/2,(image.height-crop)/2,crop,crop,0,0,512,512);
        image.close?.();
        let blob = await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.80));
        if(!blob || blob.size>400000) blob = await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.62));
        if(!blob || blob.size>400000) throw Error('Не удалось сжать фото');
        const response = await fetch('/api/players/'+encodeURIComponent(player.id)+'/avatar',{
          method:'POST',headers:{'Content-Type':'image/jpeg'},body:blob
        });
        if (!response.ok) {
          const data = await response.json().catch(()=>null);
          throw Error(data?.detail || 'HTTP '+response.status);
        }
        state = await response.json();
        render();
        setToast('Фото сохранено. Режим «ФОТО» включён.');
      } catch(err) {setToast('Не удалось загрузить фото: '+err.message,true);}
    };
    picker.click();
  }
  function renderStage(){
    const root=$('stageLabels');root.replaceChildren();
    const profile=state.profiles[profileId];if(!profile)return;
    for(const p of [...state.players,state.dealer]){
      const placement=placementFor(p.id); if(!placement)continue;
      const tempStyle={...state.settings,theme:pendingGlobalTheme||state.settings.theme,default_style:pendingGlobalStyle||state.settings.default_style};
      const el=HJ.makeBadge(p,placement,p.id===selected && mode==='editor',tempStyle);
      if(!p.is_dealer)el.querySelector('.hj-caption')?.remove(); // BOX is operator-only
      if(mode==='editor'){
        // Preserve visibility in editor so hidden players can still be placed.
        if(!p.visible || !placement.visible || p.status==='out'){el.classList.remove('hidden-badge');el.classList.add('ghost-badge');}
        el.title='Перетащите, чтобы переместить';
        el.addEventListener('pointerdown',ev=>beginDrag(ev,p.id,el));
        el.addEventListener('click',()=>{selected=p.id;renderStage();renderProperties();});
      }
      root.appendChild(el);HJ.fitBadge(el);
    }
    const data=localStorage.getItem(`hj-preview-${profileId}`);
    $('stageBackground').style.backgroundImage=data?`url(${JSON.stringify(data)})`:'';
    $('stageBackground').style.display=data?'block':'none';
    $('frameGuide').textContent=data?'Кадр OBS загружен. Плашки размещаются относительно всего холста 1920×1080. Изображение не обрезается и не отправляется в OBS.':'Для точного совмещения с камерой загрузите полный кадр сцены OBS 16:9 (не обрезанный фрагмент). Фон используется только для расстановки плашек.';
  }
  function beginDrag(e,id,el){
    if(mode!=='editor')return;
    e.preventDefault();selected=id;
    const rect=$('stage').getBoundingClientRect();
    const current=placementFor(id);if(!current)return;
    drag={id,startX:e.clientX,startY:e.clientY,placement:{...current},rect,el,
      resize:!!e.target.closest('.hj-resize-handle')};
    el.setPointerCapture(e.pointerId);
    el.classList.add('dragging','selected');renderProperties();
    el.addEventListener('pointermove',onDrag);
    el.addEventListener('pointerup',finishDrag,{once:true});
    el.addEventListener('pointercancel',finishDrag,{once:true});
  }
  function onDrag(e){
    if(!drag)return;
    const {rect,placement,el,id}=drag;
    const x=Math.max(0,Math.min(1,placement.x+(e.clientX-drag.startX)/rect.width));
    const y=Math.max(0,Math.min(1,placement.y+(e.clientY-drag.startY)/rect.height));
    let next={...placement};
    if(drag.resize){
      if (badgeSettingsMode === 'basic') {
        // Resize from the rotated bottom-right corner, preserving badge proportions.
        // This also grows/shrinks the entire nickname automatically in the OBS overlay.
        const rotation = (placement.rotation || 0) * Math.PI / 180;
        const cosine = Math.cos(rotation), sine = Math.sin(rotation);
        const multiplier = placement.scale ?? 1;
        const halfW = placement.width * rect.width * multiplier / 2;
        const halfH = (placement.height ?? .065) * rect.height * multiplier / 2;
        const cornerX = halfW * cosine - halfH * sine;
        const cornerY = halfW * sine + halfH * cosine;
        const distanceSq = Math.max(1, cornerX * cornerX + cornerY * cornerY);
        const dx = e.clientX - drag.startX, dy = e.clientY - drag.startY;
        const ratio = Math.max(
          .04 / placement.width, .02 / (placement.height ?? .065),
          Math.min(.75 / placement.width, .4 / (placement.height ?? .065),
                   1 + (dx * cornerX + dy * cornerY) / distanceSq)
        );
        next.width = Math.round(placement.width * ratio * 10000) / 10000;
        next.height = Math.round((placement.height ?? .065) * ratio * 10000) / 10000;
      } else {
        next.width = Math.max(.04,Math.min(.75,(placement.width+(e.clientX-drag.startX)/rect.width)));
        next.height = Math.max(.02,Math.min(.4,((placement.height??.065)+(e.clientY-drag.startY)/rect.height)));
        next.width = Math.round(next.width*10000)/10000;
        next.height = Math.round(next.height*10000)/10000;
      }
    }else{
      next.x=Math.round(x*10000)/10000;next.y=Math.round(y*10000)/10000;
      if(showGrid){next.x=Math.round(next.x*40)/40;next.y=Math.round(next.y*40)/40;}
    }
    draftChanges[id]=next;HJ.positionBadge(el,next);renderProperties();renderEditorStatus();
  }
  function finishDrag(e){
    if(!drag)return;
    const el=drag.el;el.classList.remove('dragging');
    el.removeEventListener('pointermove',onDrag);drag=null;
    saveDraft().catch(()=>{});
  }
  // Always finish saving every in-flight edit before publishing or switching camera.
  // Previous fire-and-forget writes could silently fail or race a publish.
  function saveDraft(){
    if(saveInFlight) return saveInFlight.then(()=>saveDraft());
    if(!Object.keys(draftChanges).length || !state) return Promise.resolve();
    const profile=profileId;
    const changes={...draftChanges};draftChanges={};
    saving=true;renderEditorStatus();
    const operation=put(`/api/profiles/${encodeURIComponent(profile)}/draft`,{placements:changes})
      .then(snapshot=>{state=snapshot;return snapshot;})
      .catch(err=>{
        // Keep unsaved values available for retry; newer edits take precedence.
        if(profile===profileId) draftChanges={...changes,...draftChanges};
        setToast('Не удалось сохранить раскладку: '+err.message,true);
        throw err;
      }).finally(()=>{saving=false;saveInFlight=null;renderEditorStatus();});
    saveInFlight=operation;
    return operation.then(()=>saveDraft());
  }
  async function publishCurrentLayout(){
    if(publishing)return false;
    publishing=true;renderEditorStatus();
    try{
      await saveDraft();
      const profile=profileId;
      const snapshot=await api('/api/state');
      const expected=snapshot.drafts?.[profile];
      if(!expected){setToast('Изменений для публикации нет');state=snapshot;render();return true;}
      const published=await post(`/api/profiles/${encodeURIComponent(profile)}/publish`);
      const actual=published.profiles?.[profile]?.placements;
      if(!actual || Object.keys(expected).some(id=>JSON.stringify(actual[id])!==JSON.stringify(expected[id])) || published.drafts?.[profile]){
        throw Error('Сервер не подтвердил применение координат. Проверьте состояние и повторите публикацию.');
      }
      state=published;
      render();
      setToast(`Раскладка «${published.profiles[profile].name}» опубликована в OBS (версия #${published.revision})`);
      return true;
    }finally{publishing=false;renderEditorStatus();}
  }
  function renderProperties(){
    $('properties').hidden=mode!=='editor'||!selected;
    if(!selected)return;
    const player=state.players.find(p=>p.id===selected)||state.dealer;
    const p=placementFor(selected);if(!p)return;
    $('selectedName').textContent=player.nickname;
    $('badgeAdvancedOptions').hidden = badgeSettingsMode !== 'advanced';
    for (const [id, active] of [['badgeModeBasic',badgeSettingsMode==='basic'],['badgeModeAdvanced',badgeSettingsMode==='advanced']]) {
      $(id).classList.toggle('active', active);
      $(id).setAttribute('aria-pressed', String(active));
    }
    for (const [id, angle] of [['rotateLeft',-90],['rotateStraight',0],['rotateRight',90]]) {
      $(id).classList.toggle('active', (p.rotation||0) === angle);
    }
    const items=[
      ['propSize',Math.round(p.width*100),'%'],
      ['propHeight',Math.round((p.height??.065)*1000)/10,'%'],
      ['propScale',Math.round((p.scale??1)*100),'%'],
      ['propFont',p.font_size??24,' px'],
      ['propPadding',p.padding??8,' px'],
      ['propGlow',Math.round((p.glow??.6)*100),'%'],
      ['propRotation',p.rotation??0,'°'],
      ['propOpacity',Math.round((p.opacity??1)*100),'%']
    ];
    for(const [id,value,suffix] of items){$(id).value=value;$(id+'Value').textContent=value+suffix;}
    $('propScaleNumber').value=Math.round((p.scale??1)*100);
    $('propStyle').value=p.style||'';
    $('propVisible').checked=p.visible;
  }
  for (const [id, setting] of [['badgeModeBasic','basic'],['badgeModeAdvanced','advanced']]) {
    $(id).onclick = () => {
      badgeSettingsMode = setting;
      localStorage.setItem('hj-badge-settings-mode', setting);
      renderProperties();
    };
  }
  function updateProp(prop,value){
    if(!selected)return;
    draftChanges[selected]={...placementFor(selected),[prop]:value};
    renderStage();renderProperties();renderEditorStatus();
  }
  for(const [id,prop,convert] of [
    ['propSize','width',v=>Number(v)/100],['propHeight','height',v=>Number(v)/100],
    ['propScale','scale',v=>Number(v)/100],['propFont','font_size',Number],
    ['propPadding','padding',Number],['propGlow','glow',v=>Number(v)/100],
    ['propRotation','rotation',Number],['propOpacity','opacity',v=>Number(v)/100],
    ['propVisible','visible',v=>v],['propStyle','style',v=>v||null],
    ['propScaleNumber','scale',v=>Math.max(.25,Math.min(3,Number(v)/100))]
  ]){
    $(id).addEventListener('input',e=>updateProp(prop,prop==='visible'?e.target.checked:convert(e.target.value)));
    $(id).addEventListener('change',()=>saveDraft().catch(()=>{}));
  }
  for(const [control,angle] of [['rotateLeft',-90],['rotateStraight',0],['rotateRight',90]]){
    $(control).onclick=()=>{
      if(!selected)return;
      updateProp('rotation',angle);
      saveDraft().catch(()=>{});
    };
  }
  $('resetBadgeSize').onclick=()=>{
    if(!selected)return;
    // Prefer the operator's persisted preset; fall back to original defaults.
    const defaults = state?.settings?.badge_default || {
      width:.15,height:.065,scale:1,font_size:24,padding:8,glow:.6,rotation:0,opacity:1,style:null
    };
    const appearanceKeys = ['width','height','scale','font_size','padding','glow','rotation','opacity','style'];
    const appearance = Object.fromEntries(appearanceKeys.map(k => [k, defaults[k]]));
    draftChanges[selected]={...placementFor(selected),...appearance};
    renderStage();renderProperties();saveDraft().catch(()=>{});
  };
  $('saveBadgeDefault').onclick=()=>act(async()=>{
    if(!selected)return;
    await saveDraft();
    const current=placementFor(selected);
    if(!current)throw Error('Не выбрана плашка');
    state=await post('/api/players/default-badge',{placement:current});
    render();
    setToast('Стандарт сохранён! Новые игроки получат эти размеры и оформление.');
  });
  $('applyBadgeDefault').onclick=()=>act(async()=>{
    if(!state?.settings?.badge_default){setToast('Сначала нажми «Сохранить как стандарт».',true);return;}
    await saveDraft();
    state=await post(`/api/profiles/${encodeURIComponent(profileId)}/apply-badge-default`);
    draftChanges={};render();
    setToast('Оформление всех игроков изменено в черновике. Нажми «Опубликовать в OBS».');
  });
  $('globalStyle').onchange=e=>{pendingGlobalStyle=e.target.value;renderStage();};
  $('applyTheme').onclick=()=>act(async()=>{
    await post('/api/settings',{theme:pendingGlobalTheme,default_style:pendingGlobalStyle});
    setToast('Общая тема и шаблон применены в эфир');
  });
  function openModal(action,p){
    modalAction=action;const title=action==='add'?'Новый игрок':action==='replace'?'Замена участника':'Редактирование игрока';
    $('modalHeading').textContent=title;$('submitModal').textContent=action==='add'?'Добавить игрока':action==='replace'?'Заменить':'Сохранить';
    $('formName').value=action==='replace'?'':p?.nickname||'';
    $('formSeat').innerHTML=`<option value="">Без бокса</option>`+Array.from({length:10},(_,i)=>{
      const n=i+1;const occupied=state.players.some(q=>q.seat===n&&q.id!==p?.id);
      return `<option value="${n}" ${occupied?'disabled':''}>Бокс ${n}${occupied?' · занят':''}</option>`;
    }).join('');
    $('formSeat').value=p?.seat??'';$('formSeat').disabled=!!p?.is_dealer;
    $('formStyle').value=p?.style||'';
    $('formTheme').innerHTML='<option value="">Использовать общую тему</option>' + HJ.getThemes().map(t=>`<option value="${HJ.esc(t.id)}">${HJ.esc(t.name)}</option>`).join('');
    $('formTheme').value=p?.theme||'';
    $('modal').hidden=false;$('modal').dataset.pid=p?.id||'';
    $('modal').dataset.dealer=p?.is_dealer?'1':'0';
    // Avoid programmatic focus during native WebView2 modal creation on Windows 11.
    // The input remains keyboard accessible via Tab or an explicit click.
  }
  const closeModal=()=>{$('modal').hidden=true;};
  $('closeModal').onclick=closeModal;$('cancelModal').onclick=closeModal;$('modalBackdrop').onclick=closeModal;
  $('playerForm').addEventListener('submit',e=>{
    e.preventDefault();const pid=$('modal').dataset.pid;
    const obj={nickname:$('formName').value.trim(),seat:$('formSeat').value?Number($('formSeat').value):null,style:$('formStyle').value||null,theme:$('formTheme').value||null};
    const submit=$('submitModal');
    if(submit.disabled)return;
    submit.disabled=true;
    act(async()=>{
      if(modalAction==='add')await post('/api/players',obj);
      else if(modalAction==='replace')await post(`/api/players/${pid}/replace`,obj);
      else await patch(`/api/players/${pid}`,$('modal').dataset.dealer==='1'?{nickname:obj.nickname,style:obj.style,theme:obj.theme}:obj);
      closeModal();
    }).finally(()=>{submit.disabled=false;});
  });
  $('addPlayer').onclick=()=>openModal('add');
  $('liveMode').onclick=()=>act(async()=>{
    if(publishing)return;
    if(mode==='editor'){
      await saveDraft();
      const snapshot=await api('/api/state');
      state=snapshot;
      if(snapshot.drafts?.[profileId]){
        if(!confirm('В раскладке есть изменения, которые OBS ещё не показывает. Опубликовать их сейчас?\n\nНажмите «Отмена», чтобы остаться в редакторе.'))return;
        if(!await publishCurrentLayout())return;
      }
    }
    mode='live';selected=null;render();
  });
  $('editMode').onclick=()=>{if(publishing)return;mode='editor';render();};
  $('undo').onclick=()=>act(()=>post('/api/undo'));
  $('profile').onchange=e=>act(async()=>{
    const next=e.target.value;
    if(publishing){render();return;}
    await saveDraft();
    profileId=next;selected=null;
    state=await post(`/api/profiles/${encodeURIComponent(profileId)}/activate`);
    render();
  });
  $('addProfile').onclick=()=>{
    const name=prompt('Название профиля камеры (например, CAMERA 3):');
    if(name?.trim())act(()=>post('/api/profiles',{name:name.trim()}));
  };
  const requestPublish=()=>act(publishCurrentLayout);
  $('publish').onclick=requestPublish;
  $('publishTop').onclick=requestPublish;
  $('autoPlace').onclick=()=>act(async()=>{
    if(publishing)return;
    await saveDraft();
    const result=await post(`/api/profiles/${encodeURIComponent(profileId)}/auto-place`);
    state=result;draftChanges={};render();
    setToast('Плашки расставлены по боксам в РЕДАКТОРЕ. Нажмите «Опубликовать в OBS».');
  });
  $('discard').onclick=()=>act(async()=>{
    if(publishing)return;
    await saveDraft();
    draftChanges={};state=await post(`/api/profiles/${encodeURIComponent(profileId)}/discard`);
    render();setToast('Черновик отменён, опубликованная раскладка сохранена');
  });
  $('widePreview').onclick=()=>{
    if(mode!=='editor'){
      mode='editor';
      widePreview=true;
    }else widePreview=!widePreview;
    localStorage.setItem('hj-editor-wide',String(widePreview));
    render(); // also attach drag controls if expanded directly from LIVE mode
    setToast(widePreview?'Кадр 16:9 расширен. Для точной расстановки разверните окно приложения.':'Восстановлена компактная панель.');
  };
  $('toggleGrid').onclick=()=>{showGrid=!showGrid;renderEditorStatus();};
  $('clearPlayers').onclick=()=>{if(confirm('Убрать всех игроков со стола? Действие можно отменить.'))act(()=>post('/api/players/clear'));};
  $('resetStatuses').onclick=()=>act(()=>post('/api/players/reset-statuses'));
  $('demo').onclick=()=>act(async()=>{
    if(state.players.length && !confirm('Заменить текущую рассадку демо-игроками?'))return;
    if(state.players.length)await post('/api/players/clear');
    for(let i=1;i<=10;i++)await post('/api/players',{nickname:`Игрок ${String(i).padStart(2,'0')}`,seat:i});
    await patch('/api/players/dealer',{visible:true});
  });
  $('effects').innerHTML=Object.entries(effectIcons).map(([name,icon])=>`<button class="effect-button" data-effect="${HJ.esc(name)}"><span class="effect-symbol">${icon}</span><span class="effect-copy"><strong>${HJ.esc(name)}</strong><small>${HJ.esc(effectDescriptions[name])}</small></span><span class="effect-go">↗</span></button>`).join('');
  $('effects').onclick=e=>{
    const btn=e.target.closest('[data-effect]');if(!btn)return;
    const name=btn.dataset.effect;
    act(async()=>{await post('/api/effects',{name,player_id:$('effectTarget').value||null});
      setToast(`${name} · эффект отправлен в OBS`);btn.classList.add('triggered');setTimeout(()=>btn.classList.remove('triggered'),450);});
  };
  $('stopEffects').onclick=()=>act(async()=>{await post('/api/effects/stop');setToast('Эффекты остановлены');});
  $('volume').onchange=e=>act(()=>post('/api/settings',{volume:Number(e.target.value)/100}));
  $('volume').oninput=e=>$('volumeValue').textContent=`${e.target.value}%`;
  $('openPlayers').onclick=()=>window.open(`/overlay/players?layout=${profileId}`,'_blank');
  $('copyPlayers').onclick=()=>navigator.clipboard.writeText(`${location.origin}/overlay/players?layout=${profileId}`).then(()=>setToast('Ссылка на игроков скопирована'));
  $('copyEffects').onclick=()=>navigator.clipboard.writeText(`${location.origin}/overlay/effects`).then(()=>setToast('Ссылка на эффекты скопирована'));
  $('export').onclick=()=>act(async()=>{
    const data=await api('/api/config/export');
    const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='hi-jack-live-config.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
  });
  $('import').onclick=()=>$('importFile').click();
  $('importFile').onchange=e=>{
    const file=e.target.files[0]; if(!file)return;
    act(async()=>{
      if(!confirm('Импорт заменит текущую рассадку и раскладки. Сервер автоматически сделает резервную копию. Продолжить?'))return;
      if(file.size>500000)throw Error('JSON должен быть меньше 500 КБ');
      const body=await file.text();
      await api('/api/config/import',{method:'POST',body});
      selected=null;draftChanges={};setToast('Конфигурация импортирована');
    });e.target.value='';
  };
  $('backup').onclick=()=>act(async()=>{const result=await post('/api/config/backup');setToast(`Резервная копия: ${result.filename}`);});
  $('screenshot').onclick=()=>$('screenshotFile').click();
  $('screenshotFile').onchange=e=>{
    const file=e.target.files[0];if(!file)return;
    if(file.size>20*1024*1024){setToast('Максимум 20 МБ',true);return;}
    const reader=new FileReader();reader.onload=()=>{
      const img=new Image();img.onload=()=>{
        const canvas=document.createElement('canvas');canvas.width=1920;canvas.height=1080;
        // FIT, not COVER: avoid crop/shift of seat positions when reference image is not 16:9.
        // Black side/top bars are intentional and match OBS "Fit to screen" behaviour.
        const ctx=canvas.getContext('2d');const scale=Math.min(1920/img.width,1080/img.height);
        const w=img.width*scale,h=img.height*scale;
        ctx.fillStyle='#000';ctx.fillRect(0,0,1920,1080);
        ctx.drawImage(img,(1920-w)/2,(1080-h)/2,w,h);
        const aspectOff=Math.abs(img.width/img.height-16/9)>.015;
        try{localStorage.setItem(`hj-preview-${profileId}`,canvas.toDataURL('image/jpeg',.7));renderStage();setToast(aspectOff?`Исходный кадр ${img.width}×${img.height} не 16:9: добавлены чёрные поля БЕЗ обрезки. Лучше загрузить полный кадр OBS 1920×1080.`:'Кадр 16:9 загружен только в редактор (не попадает в OBS)');}
        catch(err){setToast('Недостаточно памяти браузера для изображения',true);}
      };img.src=reader.result;
    };reader.readAsDataURL(file);e.target.value='';
  };
  $('removeScreenshot').onclick=()=>{localStorage.removeItem(`hj-preview-${profileId}`);renderStage();};
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape')closeModal();
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){e.preventDefault();act(()=>post('/api/undo'));}
  });
  fetch('/api/themes').then(r=>r.json()).then(r=>{HJ.setThemes(r.themes);if(state)render();}).catch(err=>setToast('Не удалось загрузить темы: '+err.message,true));
  HJ.socket(message=>{
    if(message.type==='state'){
      const prev=state;state=message.state;
      if(prev && prev.settings.theme!==state.settings.theme)pendingGlobalTheme=state.settings.theme;
      if(prev && prev.settings.default_style!==state.settings.default_style)pendingGlobalStyle=state.settings.default_style;
      // Honor profile activated elsewhere, but keep local editing context if present.
      if(!prev || (prev.active_profile!==state.active_profile && !saving)) profileId=state.active_profile;
      render();
    }
  },online=>{
    $('connection').classList.toggle('offline',!online);
    $('connection').classList.toggle('online',online);
    $('connection').innerHTML=online?'<i></i> LIVE CONNECTION':'<i></i> НЕТ СОЕДИНЕНИЯ';
  });
  api('/api/state').then(s=>{if(!state){state=s;profileId=s.active_profile;render();}}).catch(err=>setToast(err.message,true));
})();
