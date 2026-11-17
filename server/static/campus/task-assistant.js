(() => {
  const t=value=>window.campusI18n.text(value),$=id=>document.getElementById(id);
  const log=$('assistant-conversation'),choices=$('assistant-choices'),venues=$('assistant-venues'),links=$('assistant-links');
  let state=null,selected=null,busy=false,history=[],weatherToken='';
  function el(tag,text='',cls=''){const node=document.createElement(tag);node.textContent=text;if(cls)node.className=cls;return node;}
  function message(text,user=false){const node=el('div','','assistant-message'+(user?' user':''));node.append(el('small',t(user?'我的需求':'校园办事向导')),el('span',text));log.append(node);log.scrollTop=log.scrollHeight;if(!user)window.dispatchEvent(new CustomEvent('universe-ai-reply',{detail:{text}}));}
  function button(label,action,enabled=true){const node=el('button',label);node.type='button';node.disabled=!enabled;node.addEventListener('click',action);return node;}
  function row(dl,label,value){dl.append(el('dt',t(label)),el('dd',String(value)));}
  function setBusy(value){busy=value;document.querySelectorAll('.assistant-work button,#assistant-reset').forEach(node=>{if(!node.closest('.uv-voice'))node.disabled=value||node.dataset.unavailable==='yes';});$('assistant-input').disabled=value;$('assistant-channel').disabled=value;}
  function select(field,value,label){message(label,true);send({selection:{[field]:value}});}
  function receipt(result){const box=el('div','','assistant-receipt');box.append(el('h3',t('预约成功')));const dl=el('dl');row(dl,'预约编号','#'+result.id);row(dl,'场地',result.venue);row(dl,'预约日期',result.day);row(dl,'预约时段',result.slot);row(dl,'状态',result.status);box.append(dl);venues.append(box);}
  function render(result,addMessage=true){
    if(result.plan)window.dispatchEvent(new CustomEvent('universe-service-plan',{detail:result.plan}));
    if(result.phase==='plan'){$('assistant-status').textContent='';state=null;selected=null;$('assistant-confirm').hidden=true;$('assistant-date-form').hidden=true;choices.replaceChildren();venues.replaceChildren();links.replaceChildren();$('assistant-summary').replaceChildren();message(result.message);return;}
    if(result.phase==='chat'){
      message(result.message);
      const bubble=log.lastElementChild;
      bubble.querySelector('small').textContent=t(result.mode==='weather'?'天气查询':result.mode==='external_ai'?'DeepSeek 官方 AI':'本地 AI')+' · '+result.model;
      if(result.route_note)bubble.append(el('small',result.route_note,'assistant-route-note'));
      (result.weather_choices||[]).forEach(choice=>bubble.append(button(choice.label,()=>send({selection:{weather:choice.token}}))));
      if(result.weather_source){const source=el('a',t('天气数据来源')+' · Open-Meteo ↗');source.href=result.weather_source;source.target='_blank';source.rel='noopener noreferrer';bubble.append(source);}
      if(result.mode==='weather'&&(result.weather_source||result.weather_choices?.length)){const geo=el('a','GeoNames ↗');geo.href='https://www.geonames.org/';geo.target='_blank';geo.rel='noopener noreferrer';bubble.append(geo);}
      if(result.weather_token)weatherToken=result.weather_token;
      if(result.home_place){try{localStorage.setItem('universe-weather-city-v1',result.home_place);}catch(_){}window.dispatchEvent(new Event('campus-weather-changed'));}
      $('assistant-status').textContent='';
      window.dispatchEvent(new CustomEvent('campus-journey-step',{detail:{step:'chat',instruction:t('回答在左侧，可以继续追问我。'),action:t('继续聊天')}}));
      return;
    }
    state=result;selected=null;$('assistant-confirm').hidden=true;$('assistant-status').textContent='';
    choices.replaceChildren();venues.replaceChildren();links.replaceChildren();$('assistant-summary').replaceChildren();
    if(addMessage)message(result.message);
    const phases={ask_kind:'ask',ask_building:'ask',ask_day:'ask',ask_slot:'choose',choose_venue:'choose',done:'done',navigate:'ask'};
    document.querySelectorAll('.assistant-steps span').forEach(node=>node.classList.toggle('active',node.dataset.phase===phases[result.phase]));
    $('assistant-date-form').hidden=Boolean(result.plan_linked)||!['ask_day','ask_slot','choose_venue'].includes(result.phase);
    $('assistant-day').min=result.today||'';$('assistant-day').max=result.last_day||'';$('assistant-day').value=result.draft?.day||'';
    if(result.phase==='ask_building')(result.buildings||[]).forEach(item=>choices.append(button(item.label,()=>select('building',item.value,item.label))));
    if(result.phase==='ask_kind'){
      (result.kinds||[]).forEach(kind=>choices.append(button(kind.label,()=>select('kind',kind.value,kind.label))));
      [['我想认识同学','认识校园同学'],['我需要跑腿帮助','请求或提供帮助'],['我想了解导诊','了解导诊服务'],['我的服务','我的服务']].forEach(([query,label])=>choices.append(button(t(label),()=>{message(t(label),true);send({message:query,channel:'task'});})));
    }
    if(!result.plan_linked&&['ask_slot','choose_venue'].includes(result.phase)){
      (result.slots||[]).forEach(slot=>{const node=button(slot.label+' · '+slot.count,()=>select('slot',slot.value,slot.label),slot.count>0);if(!slot.count)node.dataset.unavailable='yes';choices.append(node);});
    }
    if(result.phase!=='done'&&result.draft&&Object.keys(result.draft).length){
      const kind=(result.kinds||[]).find(item=>item.value===result.draft.kind);
      [kind?.label,result.draft.day,(result.slots||[]).find(item=>item.value===result.draft.slot)?.label].filter(Boolean).forEach(text=>$('assistant-summary').append(el('span',text)));
      $('assistant-summary').hidden=false;
    }else $('assistant-summary').hidden=true;
    (result.venues||[]).forEach(venue=>{
      const card=el('article','','assistant-venue');card.append(el('h3',venue.label),el('p',venue.day+' · '+venue.slot),el('small',t('场地原名')+'：'+venue.name));
      card.append(button(t('选择这个场地'),async()=>{
        if(busy)return;setBusy(true);try{const preview=await request('/api/assistant/preview/',{draft_key:state.draft_key,venue_id:venue.id});if(!preview.available){$('assistant-status').textContent=t('空位已变化或正在处理候补，请重新查询。');selected=null;return;}message(t('办事预演')+' · '+preview.message);
        selected=venue;const dl=el('dl');row(dl,'场地',venue.name);row(dl,'预约日期',venue.day);row(dl,'预约时段',venue.slot);
        $('assistant-confirm-details').replaceChildren(dl);$('assistant-confirm').hidden=false;
        document.querySelectorAll('.assistant-steps span').forEach(node=>node.classList.toggle('active',node.dataset.phase==='confirm'));
        $('assistant-confirm').scrollIntoView({block:'nearest'});
        }catch(error){$('assistant-status').textContent=error.message;}finally{setBusy(false);}
      }));venues.append(card);
    });
    if(result.receipt)receipt(result.receipt);
    (result.actions||[]).forEach(action=>{const link=el('a',action.label+' ↗');link.href=action.url;links.append(link);});
    const step=result.phase==='ask_kind'?'chat':result.intent==='friends'?'friends':result.intent==='health'?'health':result.intent==='help'?'help':result.phase==='done'?'language':'booking';
    if(result.plan?.state!=='active')window.dispatchEvent(new CustomEvent('campus-journey-step',{detail:{step,instruction:result.message,action:t(result.phase==='done'?'我的服务':'查看办事卡片'),completed:result.phase==='done'}}));
  }
  async function request(url,data){
    const csrf=document.querySelector('#assistant-chat-form input[name=csrfmiddlewaretoken]').value;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),120000);
    try{const response=await fetch(url,{method:data?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:data?{'Content-Type':'application/json','X-CSRFToken':csrf}:{},body:data?JSON.stringify(data):undefined,signal:controller.signal});const value=await response.json();if(!response.ok)throw new Error(value.error||t('办事请求未完成，请重试。'));return value;}finally{clearTimeout(timer);}
  }
  async function send(data){
    if(busy)return;
    if(data.message){data.channel=data.channel||$('assistant-channel').value;data.history=history.slice(-6);data.weather_context=weatherToken;data.external_allowed=$('assistant-external').checked;}
    setBusy(true);$('assistant-status').textContent=t('正在处理，请稍候…');
    document.querySelector('.home-mascot')?.dispatchEvent(new CustomEvent('mascot-gesture',{detail:{motion:'thinking01'}}));
    try{const result=await request('/api/assistant/chat/',data);if(result.phase==='chat'){if(data.message)history.push({role:'user',content:data.message.slice(0,2000)});history.push({role:'assistant',content:result.message.slice(0,2000)});history=history.slice(-6);}render(result);}catch(error){$('assistant-status').textContent=error.name==='AbortError'?t('请求超时，请重试或直接选择下方选项。'):error.message;}finally{setBusy(false);}
  }
  $('assistant-chat-form').addEventListener('submit',event=>{event.preventDefault();const text=$('assistant-input').value.trim();if(!text||busy)return;message(text,true);$('assistant-input').value='';send({message:text});});
  $('assistant-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();$('assistant-chat-form').requestSubmit();}});
  $('assistant-date-form').addEventListener('submit',event=>{event.preventDefault();if(!busy)select('day',$('assistant-day').value,$('assistant-day').value);});
  $('assistant-reset').addEventListener('click',()=>{if(!busy){history=[];weatherToken='';log.replaceChildren();send({reset:true});}});
  $('assistant-confirm-back').addEventListener('click',()=>{$('assistant-confirm').hidden=true;selected=null;});
  $('assistant-confirm-button').addEventListener('click',async()=>{
    if(busy||!selected||!state?.draft_key)return;
    const key=state.draft_key,venue=selected.id;setBusy(true);$('assistant-status').textContent=t('正在提交预约，请勿重复点击。');
    try{render(await request('/api/assistant/confirm/',{draft_key:key,venue_id:venue}));}
    catch(error){$('assistant-status').textContent=error.name==='AbortError'?t('暂未收到提交结果，可重试或到“我的预约”核对。'):error.message;}
    finally{setBusy(false);}
  });
  window.addEventListener('universe-plan-booking',event=>render(event.detail));
  setBusy(true);request('/api/assistant/state/').then(result=>render(result)).catch(error=>{$('assistant-status').textContent=error.message;}).finally(()=>setBusy(false));
})();
