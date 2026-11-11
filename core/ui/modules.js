'use strict';
(() => {
  const $=id=>document.getElementById(id);
  let checked=null,checkedBytes=null;
  async function api(url,method='GET',body=null){
    const headers={'X-HJ-Token':sessionStorage.getItem('hj_admin_token')||''};
    if(body instanceof Uint8Array)headers['Content-Type']='application/zip';
    let response=await fetch(url,{method,body,headers});
    if(response.status===401){const token=prompt('Пароль администратора:');if(!token)throw Error('Необходим пароль');sessionStorage.setItem('hj_admin_token',token);return api(url,method,body);}
    const result=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(result.detail||`HTTP ${response.status}`);
    return result;
  }
  const escape=s=>HJ.esc(String(s??''));
  function message(s,error=false){$('result').textContent=s;$('result').className=error?'error':'ok';}
  async function refresh(){
    const result=await api('/api/modules');
    $('connection').textContent=`API ядра: ${result.host_api} · Подключено OBS-оверлеев: ${result.overlay_connections}`;
    $('modules').replaceChildren();
    for(const item of result.modules){
      const line=document.createElement('div');line.className='module';
      const left=document.createElement('div');left.innerHTML=`<strong>${escape(item.name)}</strong><span class="badge">${escape(item.version)}</span><div class="muted">${escape(item.id)} · <span class="${item.status==='loaded'?'ok':'warn'}">${escape(item.status)}</span>${item.error?' · '+escape(item.error):''}</div>`;
      const buttons=document.createElement('div');buttons.className='row';
      const rollback=document.createElement('button');rollback.className='subtle';rollback.textContent='Откатить';
      rollback.onclick=async()=>{if(!confirm(`Откатить ${item.id} на предыдущую сохранённую версию?`))return;try{message(JSON.stringify(await api(`/api/modules/${encodeURIComponent(item.id)}/rollback`,'POST')))}catch(err){message(err.message,true)}};
      const toggle=document.createElement('button');toggle.className='subtle';toggle.textContent=item.status==='disabled'?'Включить':'Выключить';
      toggle.onclick=async()=>{try{message(JSON.stringify(await api(`/api/modules/${encodeURIComponent(item.id)}/disable?disabled=${item.status!=='disabled'}`,'POST')));toggle.disabled=true}catch(err){message(err.message,true)}};
      buttons.append(rollback,toggle);line.append(left,buttons);$('modules').append(line);
    }
  }
  $('zip').onchange=()=>{checked=null;checkedBytes=null;$('install').disabled=true;$('packageInfo').replaceChildren();message('')};
  $('validate').onclick=async()=>{
    const file=$('zip').files?.[0];if(!file)return message('Выберите ZIP-файл.',true);
    try{
      const bytes=new Uint8Array(await file.arrayBuffer());
      const data=await api('/api/modules/validate','POST',bytes);
      checked=data;checkedBytes=bytes;$('packageInfo').replaceChildren();
      const p=document.createElement('pre');p.textContent=`Модуль: ${data.name} (${data.id})\nВерсия: ${data.version}\nAPI: ${data.host_api}\nЗависимости: ${data.requires.join(', ')}\n\n${data.changelog}`;
      $('packageInfo').append(p);
      $('install').disabled=false;message('Целостность и совместимость пакета проверены. Ознакомьтесь с изменениями.');
    }catch(err){checked=null;checkedBytes=null;$('install').disabled=true;message(err.message,true)}
  };
  $('install').onclick=async()=>{
    if(!checked || !checkedBytes)return;
    if(!$('trust').checked)return message('Подтвердите, что доверяете источнику ZIP.',true);
    if(!confirm(`Установить ${checked.id} ${checked.version}? После операции потребуется перезапуск.`))return;
    try{const result=await api('/api/modules/install','POST',checkedBytes);message(`Модуль ${result.id} установлен. Перезапустите приложение.`,false);$('install').disabled=true;await refresh();}
    catch(err){message(err.message,true)}
  };
  refresh().catch(err=>message(err.message,true));
})();
