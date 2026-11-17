(() => {
  const box=document.querySelector('.home-weather');if(!box)return;
  const t=value=>window.campusI18n?.text(value)||value,$=id=>document.getElementById(id),key='universe-weather-city-v1';
  let busy=false,current='';
  const el=(tag,text='',cls='')=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
  function saved(){try{return localStorage.getItem(key)||'';}catch(_){return current;}}
  function setBusy(value){busy=value;box.querySelectorAll('button').forEach(n=>n.disabled=value);}
  async function json(url,options={}){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
    try{const response=await fetch(url,{...options,signal:controller.signal,cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.error||t('天气查询失败，请稍后重试。'));return data;}finally{clearTimeout(timer);}
  }
  const post=data=>json(box.dataset.url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':box.querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify(data)});
  function report(result){
    current=result.place;try{localStorage.setItem(key,result.place);}catch(_){}
    const data=result.card,view=$('home-weather-report');view.replaceChildren();
    view.append(el('p',data.location,'weather-location'));
    const line=el('div','','weather-now');line.append(el('strong',data.temperature+'°'),el('span',data.condition));view.append(line);
    view.append(el('p',data.low+'–'+data.high+' °C'+(data.rain!==null?' · '+t('最高降水概率')+' '+data.rain+'%':''),'weather-range'));
    view.append(el('small',t('数据时间')+' '+data.time+' · '+data.timezone));
    view.append(el('small',t('天气数据为模型估算与预报，供出行参考。')));
    if(result.source==='ip')view.append(el('small',t(result.local_exit?'按本机网络出口估算，VPN 或校园网可能导致偏差。':'按网络位置查询，可手动更正城市。')));if(result.source==='device')view.append(el('small',t('按设备附近位置查询，可手动更正城市。')));
    $('weather-ip-source').hidden=result.source!=='ip';$('home-weather-choices').replaceChildren();$('home-weather-settings').open=false;
  }
  async function refresh(place=saved(),locateIfAutomatic=false){
    if(busy)return;
    if(!place){await locate();return;}
    let source='';
    setBusy(true);$('home-weather-status').textContent=t('正在查询天气…');
    try{const result=await post({place});source=result.source;report(result);$('home-weather-status').textContent='';}catch(error){$('home-weather-status').textContent=error.name==='AbortError'?t('天气查询超时，请稍后重试。'):error.message;$('home-weather-settings').open=true;}finally{setBusy(false);}
    // A manually selected city is a preference. Automatic locations may have
    // changed since the last visit, especially an IP location behind a VPN.
    if(locateIfAutomatic&&source!=='manual')await locate();
  }
  async function search(query,country='',source='manual'){
    const result=await post({query,country,source});
    if(result.choices.length===1){report(await post({place:result.choices[0].place}));return;}
    const choices=$('home-weather-choices');choices.replaceChildren();choices.append(el('p',t('请选择你要查询的城市，避免同名地点混淆。')));
    result.choices.forEach(item=>{const button=el('button',item.label);button.type='button';button.addEventListener('click',()=>refresh(item.place));choices.append(button);});$('home-weather-settings').open=true;
  }
  $('home-weather-form').addEventListener('submit',async event=>{
    event.preventDefault();if(busy)return;setBusy(true);$('home-weather-status').textContent=t('正在查询天气…');
    try{await search($('weather-city').value.trim());$('home-weather-status').textContent='';}catch(error){$('home-weather-status').textContent=error.name==='AbortError'?t('天气查询超时，请稍后重试。'):error.message;}finally{setBusy(false);}
  });
  async function locate(ipOnly=false){
    if(busy)return;
    setBusy(true);let fallback=false;
    try{
      let result;
      if(!ipOnly){
        $('home-weather-status').textContent=t('请允许设备定位，正在获取附近天气…');
        try{
          if(!navigator.geolocation)throw new Error('Geolocation unavailable');
          const position=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:false,timeout:10000,maximumAge:300000}));
          result=await post({coordinates:{latitude:position.coords.latitude,longitude:position.coords.longitude}});
        }catch(error){
          fallback=true;
          $('home-weather-status').textContent=t(error.code===1?'设备定位未获允许，正在尝试 IP 定位…':'设备定位暂不可用，正在尝试 IP 定位…');
        }
      }else $('home-weather-status').textContent=t('正在识别网络所在城市…');
      // Only use the network location after device location fails, or when
      // the visitor explicitly chooses IP. Keep requests same-origin.
      if(!result)result=await post({locate:true});
      report(result);$('home-weather-status').textContent=fallback?t('已使用 IP 定位，可手动更正城市。'):'';
    }catch(error){$('home-weather-status').textContent=t('自动定位未成功，请手动选择城市或重试。');$('home-weather-settings').open=true;}finally{setBusy(false);}
  }
  $('weather-ip').addEventListener('click',()=>locate(true));
  $('weather-device').addEventListener('click',()=>locate());
  $('weather-refresh').addEventListener('click',()=>refresh());
  window.addEventListener('storage',event=>{if(event.key===key&&event.newValue)refresh(event.newValue);});
  window.addEventListener('campus-weather-changed',()=>refresh());
  // Browser permission gates device location. Preserve manual choices across
  // visits; otherwise resolve device first and fall back to the network exit.
  refresh(saved(),true);
})();
