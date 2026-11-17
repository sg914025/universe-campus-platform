(()=>{'use strict';const panel=document.getElementById('service-plan-panel');if(!panel)return;const content=panel.querySelector('[data-plan-content]'),status=panel.querySelector('[data-plan-status]');const t=s=>window.campusI18n?.text(s)||s;let current=null,busy=false;
function el(tag,text='',cls=''){const n=document.createElement(tag);n.textContent=text;n.className=cls;return n;}
function button(label,action,primary=false){const b=el('button',t(label),primary?'plan-primary':'');b.type='button';b.addEventListener('click',action);return b;}
function link(label,url){const a=el('a',t(label)+' ↗');a.href=url;return a;}
function render(plan){if(!plan)return;current=plan;panel.hidden=false;panel.classList.toggle('plan-complete',plan.state==='completed');document.body.classList.add('has-service-plan');content.replaceChildren();const head=el('div','','plan-top');head.append(el('h2',t('我的办事计划')),el('span',`${plan.progress} / ${plan.total}`,'plan-progress'));content.append(head,el('p',plan.source,'plan-source'));const bar=el('div','','plan-track'),fill=el('span');fill.style.width=100*plan.progress/plan.total+'%';bar.append(fill);bar.setAttribute('role','progressbar');bar.setAttribute('aria-label',t('计划进度'));bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax',String(plan.total));bar.setAttribute('aria-valuenow',String(plan.progress));content.append(bar);const list=el('ol','','plan-list');plan.steps.forEach((step,i)=>{const li=el('li','','plan-step'+(step.done?' done':'')+(plan.state==='active'&&plan.accepted&&plan.current===step.key?' current':''));li.append(el('b',step.skipped?'−':step.done?'✓':String(i+1)),el('span',step.label));if(step.skipped)li.append(el('small',t('已跳过')));else if(step.evidence){const proof=step.evidence.url?link(step.evidence.label,step.evidence.url):el('small',step.evidence.label);proof.className='plan-evidence';li.append(proof);}list.append(li);});content.append(list,el('p',plan.instruction,'plan-instruction'));content.append(button('朗读当前步骤',async()=>{if(document.documentElement.lang.split('-')[0]==='ru'){window.universeSpeech?.stop();status.textContent=t('俄语使用你的语言包，这段文字暂无对应录音。');return;}const host=document.querySelector('.home-mascot');const end=()=>{if(host){host.dataset.nativeSpeech='false';host.classList.remove('is-speaking');host.dispatchEvent(new CustomEvent('mascot-speaking',{detail:false}));}};const ok=await window.universeSpeech?.speak(plan.instruction,{language:document.documentElement.lang.split('-')[0],owner:'plan',onEnd:end,onError:()=>{end();status.textContent=t('系统声线暂不可用，请查看文字步骤。');}});if(ok&&host){host.dataset.nativeSpeech='true';host.classList.add('is-speaking');host.dispatchEvent(new CustomEvent('mascot-gesture',{detail:{motion:'smile01',speaking:true}}));host.dispatchEvent(new CustomEvent('mascot-speaking',{detail:true}));}else if(!ok)status.textContent=t('系统声线暂不可用，请查看文字步骤。');}));const controls=el('div','','plan-controls');content.append(controls);
if(plan.state==='active'){
 if(!plan.accepted)controls.append(button('确认这份计划',()=>act('accept'),true));
 else if(plan.blocked){controls.append(button('重新选择时间预约',()=>act('rebook'),true));}
 else if(['friends','help','health'].includes(plan.current)){const step=plan.steps.find(s=>s.key===plan.current);controls.append(link(plan.current==='friends'?'发交友帖，寻找伙伴':'前往办理',step.url));if(plan.current!=='friends')controls.append(button('我已办妥，继续下一步',()=>act('complete'),true));content.append(el('p',t(plan.current==='friends'?'已预选交友分类，请核对内容后发布；发布成功会自动返回计划。':'打开页面不会算完成；请实际办妥后再确认，伙伴不会代你发帖或联系他人。'),'plan-note'));}
 else if(plan.current==='time'){const day=el('select');day.required=true;day.setAttribute('aria-label',t('预约日期'));day.append(new Option(t('请选择日期'),''));plan.days.forEach(d=>day.append(new Option(d,d)));const slot=el('select');slot.required=true;slot.setAttribute('aria-label',t('预约时段'));slot.append(new Option(t('请选择时段'),''));plan.slots.forEach(s=>slot.append(new Option(s.label,s.value)));const dl=el('label',t('预约日期')),sl=el('label',t('预约时段'));dl.append(day);sl.append(slot);controls.append(dl,sl,button('确认时间，继续',()=>{if(!day.value||!slot.value){status.textContent=t('请先选择日期和时段。');return;}act('time',{day:day.value,slot:slot.value});},true));}
 else if(plan.current==='booking'){controls.append(el('p',`${plan.day} · ${plan.slots.find(s=>s.value===plan.slot)?.label||plan.slot}`),button('查空位并继续预约',()=>act('book'),true),button('重新选择时间',()=>act('retime')));content.append(el('p',t('查空位不会创建预约。核对场地后，仍需点击确认预约。'),'plan-note'));}
 else if(['share','navigate','checkin'].includes(plan.current)){
 const step=plan.steps.find(s=>s.key===plan.current);
 controls.append(link(plan.current==='share'?'选择好友并分享':plan.current==='navigate'?'打开三维路线':'打开签到二维码',step.url));
 if(plan.current==='share'||plan.current==='navigate')controls.append(button(plan.current==='share'?'暂不分享，继续':'已熟悉路线，跳过导航',()=>act('skip')));
 if(plan.receipt)controls.append(link('多语办事卡',plan.receipt.url));
 }
 content.append(button('结束这份计划',()=>{if(window.confirm(t('结束这份计划？已经提交的预约不会被取消。')))act('cancel');}));content.lastElementChild.className='plan-cancel';
}else{controls.append(el('p',t(plan.state==='completed'?'计划已完成':'计划已结束')));if(plan.state==='cancelled')controls.append(button('继续这份计划',()=>act('resume'),true));if(plan.receipt){controls.append(link('多语办事卡',plan.receipt.url));if(!plan.receipt.active)content.append(el('p',t('关联预约已取消，请以办事卡的当前状态为准。'),'plan-note'));}}
window.dispatchEvent(new CustomEvent('campus-journey-step',{detail:{plan:true,step:plan.current==='friends'?'friends':plan.current==='health'?'health':'booking',instruction:plan.instruction,action:t('继续办事计划'),completed:plan.state==='completed'}}));}
async function act(action,extra={}) {
 if(busy||!current)return;
 busy=true;status.textContent=t('正在处理，请稍候…');panel.querySelectorAll('button').forEach(b=>b.disabled=true);
 try {
  const csrf=document.querySelector('#assistant-chat-form input[name=csrfmiddlewaretoken]').value;
  const response=await fetch('/api/assistant/plans/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({id:current.id,revision:current.revision,action,...extra})});
  const data=await response.json();
  if(!response.ok){if(response.status===409)await refreshPlan();throw new Error(data.error);}
  render(data.plan);status.textContent='';
  if(data.next_url){window.location.assign(data.next_url);return;}
  window.dispatchEvent(new CustomEvent('universe-ai-reply',{detail:{text:data.plan.instruction}}));
  if(data.assistant){window.dispatchEvent(new CustomEvent('universe-plan-booking',{detail:data.assistant}));document.getElementById('assistant-venues').scrollIntoView({block:'nearest',behavior:'smooth'});}
 }catch(e){status.textContent=e.message||t('办事请求未完成，请重试。');}
 finally{busy=false;panel.querySelectorAll('button').forEach(b=>b.disabled=false);}
}
async function refreshPlan(){try{const r=await fetch('/api/assistant/plans/',{credentials:'same-origin',cache:'no-store'});if(!r.ok)throw Error();render((await r.json()).plan);}catch(_){status.textContent=t('计划加载失败，请刷新页面重试。');panel.hidden=false;}}
window.addEventListener('universe-service-plan',e=>{render(e.detail);panel.scrollIntoView({block:'start',behavior:'smooth'});});
document.querySelector('[data-plan-example]').addEventListener('click',()=>{const field=document.getElementById('assistant-input');field.value=t('我刚来学校，想认识同学，周末打羽毛球');document.getElementById('assistant-channel').value='auto';field.focus();field.scrollIntoView({block:'center',behavior:'smooth'});});
window.addEventListener('pageshow',e=>{if(e.persisted)refreshPlan();});
window.addEventListener('focus',()=>{if(!busy)refreshPlan();});
refreshPlan();
})();
