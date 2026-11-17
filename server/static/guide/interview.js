'use strict';
(() => {
  function makeRequestKey() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
      const bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
      return Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
    }
    return 'req-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  }
  const panel = document.getElementById('interviewPanel');
  const page = document.getElementById('page-advanced');
  const host = document.getElementById('interviewQuestion');
  const history = document.getElementById('interviewHistory');
  const progress = document.getElementById('interviewProgress');
  const status = document.getElementById('aiEngineStatus');
  const initial = document.getElementById('advancedDescription');
  const startButton = document.getElementById('advancedSubmit');
  let answers = {}, turns = [], current = null, snapshot = null, seed = null, version = 0, pending = null, applying = false, submissionKey = makeRequestKey();

  function el(tag, text, cls='') {
    const node = document.createElement(tag); node.textContent = text;
    if (cls) node.className=cls; return node;
  }
  async function fetchJson(url, data, signal) {
    const csrf = decodeURIComponent((document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] || '');
    const response = await fetch(url,{method:data?'POST':'GET',credentials:'same-origin',cache:'no-store',signal,
      headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:data?JSON.stringify(data):undefined});
    if (response.status===401) {location.href='/login/?next=/'; throw Error(window.campusI18n.text("请重新登录。"));}
    const body = await response.json(); if (!response.ok) throw Error(body.error||window.campusI18n.text("暂时无法继续，请重试。")); return body;
  }
  function reset() {
    version++; pending?.abort(); pending=null;
    answers={}; turns=[]; current=null; snapshot=null; seed=null; submissionKey=makeRequestKey();
    panel.classList.add('hidden'); history.replaceChildren(); host.replaceChildren();
    startButton.disabled=false; startButton.textContent=window.campusI18n.text("分析并继续　→");
  }
  function updateHistory() {
    progress.textContent=window.campusI18n.text("逐步补充 · 已回答 ")+turns.length+window.campusI18n.text(" 条");
    history.replaceChildren();
    turns.forEach(turn => {
      const row=el('div','','interview-turn'); row.append(el('small',window.campusI18n.text(turn.question)),el('p',turn.answer)); history.append(row);
    });
  }
  function sourceLinks(sources) {
    const box=document.getElementById('interviewSources'); box.replaceChildren();
    if (!sources.length) {box.append(el('small',window.campusI18n.text("当前部位暂无匹配摘要，将使用基础问题。"))); return;}
    box.append(el('small',window.campusI18n.text("本轮参考 · MedlinePlus 健康主题摘要")));
    sources.forEach(source => {
      const link=el('a',source.title+' ↗'); link.href=source.url; link.target='_blank'; link.rel='noopener noreferrer'; box.append(link);
    });
    box.append(el('small','Source: MedlinePlus, National Library of Medicine.'));
  }
  function applyLocation(data) {
    applying=true;
    try {window.advancedSelection.apply(data);} finally {applying=false;}
    snapshot.part=data.part; snapshot.detail=data.detail;
  }
  function review(data) {
    current=null;
    host.append(el('h3',window.campusI18n.text("信息已整理，确认一下")),el('p',data.message,'interview-help'));
    const list=el('dl','','interview-summary');
    data.summary.forEach(item=>list.append(el('dt',window.campusI18n.text(item.label)),el('dd',item.value))); host.append(list);
    const button=el('button',window.campusI18n.text("确认并查看导诊结果 →"),'advanced-submit'); button.type='button';
    button.addEventListener('click',async()=>{
      button.disabled=true; button.textContent=window.campusI18n.text("AI 正在整理导诊结果…");
      const payload={...snapshot,answers,request_key:submissionKey};
      payload.duration=answers.duration||snapshot.duration;
      await window.submitAdvancedAssessment(payload);
      button.disabled=false; button.textContent=window.campusI18n.text("确认并查看导诊结果 →");
      document.getElementById('advancedResult').scrollIntoView({behavior:'smooth',block:'nearest'});
    }); host.append(button);
    const back=el('button',window.campusI18n.text("修改上一条回答"),'plain-button'); back.type='button'; back.addEventListener('click',previous); host.append(back);
  }
  function urgent(data) {
    current=null;
    host.append(el('h3',window.campusI18n.text("请先关注紧急情况")),el('p',data.message,'interview-urgent'));
    const phone=el('a',window.campusI18n.text("急救电话 120"),'emergency-link'); phone.href='tel:120'; host.append(phone);
    const button=el('button',window.campusI18n.text("同时提交给后台医生"),'plain-button'); button.type='button';
    button.addEventListener('click',async()=>{button.disabled=true;await window.submitAdvancedAssessment({...snapshot,answers,request_key:submissionKey},true);button.disabled=false;});
    host.append(button,el('p',window.campusI18n.text("后台待答不能替代急诊，提交后也不要等待信箱回复。"),'interview-help'));
  }
  function previous() {
    const last=turns.pop(); if (!last) return;
    delete answers[last.key]; updateHistory(); next();
  }
  async function reply(value) {
    if (!current || pending) return;
    value=value.trim(); if (!value || value.length>200) return;
    if (current.key==='history' && ['有老病症，需要补充','正在长期用药，需要补充'].includes(value)) {
      const input=host.querySelector('input'); input.placeholder=window.campusI18n.text("例如：医生诊断过的病症、长期用药、药物过敏…"); input.focus(); return;
    }
    const q=current; answers[q.key]=value; submissionKey=makeRequestKey(); turns.push({key:q.key,question:q.text,answer:value});
    applying=true;
    try {
      window.advancedSelection.chooseQuestionOption(q.key,value);
      const matches=q.choices.filter(choice=>choice.point && (choice.aliases||[choice.value]).some(alias=>value.includes(alias)));
      const choice=matches.length===1&&!['不是','不确定','说不清','两侧','范围比较大'].some(word=>value.includes(word))?matches[0]:null;
      if (choice) window.advancedSelection.apply({...window.advancedSelection.read(),focus:choice});
    } finally {applying=false;}
    updateHistory(); await next();
  }
  async function next() {
    if (!snapshot) return;
    pending?.abort(); const controller=new AbortController(); pending=controller;
    const mine=++version;
    panel.classList.remove('hidden'); startButton.disabled=true; startButton.textContent=window.campusI18n.text("正在逐步了解…");
    host.replaceChildren(el('p',window.campusI18n.text("正在参考知识库，准备下一问…"),'interview-loading'));
    const timeout=setTimeout(()=>controller.abort(),100000);
    try {
      const data=await fetchJson(page.dataset.followupUrl,{...snapshot,...seed,answers},controller.signal);
      if (mine!==version) return;
      applyLocation(data); sourceLinks(data.sources);
      progress.textContent=window.campusI18n.text("逐步补充 · 已回答 ")+turns.length+window.campusI18n.text(" 条");
      status.textContent=data.engine==='ollama'?window.campusI18n.text("本地 AI · ")+data.model+window.campusI18n.text(" · 知识库 ")+data.knowledge_count+window.campusI18n.text(" 条摘要"):
        data.engine==='fallback'?window.campusI18n.text(data.message):window.campusI18n.text("已整理描述 · 位置需要你确认");
      host.replaceChildren();
      if (data.phase==='urgent') urgent(data);
      else if (data.phase==='review') review(data);
      else {
        current=data.question;
        host.append(el('h3',window.campusI18n.text(current.text)),el('p',window.campusI18n.text(current.help),'interview-help'));
        const choices=el('div','','interview-choices');
        current.choices.forEach(choice=>{
          const button=el('button',window.campusI18n.text(choice.label)); button.type='button'; button.addEventListener('click',()=>reply(choice.value)); choices.append(button);
        }); host.append(choices);
        const form=el('form','','interview-answer-form'); const input=el('input','');
        input.placeholder=window.campusI18n.text("也可以用自己的话回答…"); input.maxLength=200; input.required=true; input.setAttribute('aria-label',window.campusI18n.text("回答当前问题"));
        const send=el('button',window.campusI18n.text("回答并继续 →")); send.type='submit';
        form.append(input,send);form.addEventListener('submit',e=>{e.preventDefault();reply(input.value);});host.append(form);
        if (turns.length) {const back=el('button',window.campusI18n.text("修改上一条回答"),'plain-button');back.type='button';back.addEventListener('click',previous);host.append(back);}
      }
    } catch(error) {
      if (mine!==version) return;
      host.replaceChildren(el('p',error.name==='AbortError'?window.campusI18n.text("本地模型响应超时了，已保留回答。可以重试。"):error.message,'interview-help'));
      const retry=el('button',window.campusI18n.text("重试这一问"),'plain-button'); retry.type='button'; retry.addEventListener('click',next);host.append(retry);
    } finally {
      clearTimeout(timeout);
      if (mine===version) {pending=null;startButton.disabled=false;startButton.textContent=window.campusI18n.text("重新分析并追问　→");}
    }
  }
  async function begin() {
    if (!window.advancedAccepted) {window.openAdvancedNotice(); return;}
    const selected=window.advancedSelection.read();
    if (!selected.part) {status.textContent=window.campusI18n.text("请先选择或描述一个身体部位。"); return;}
    if (!initial.value.trim()) {initial.focus();return;}
    reset();
    snapshot={accepted_notice:true,...selected,description:initial.value.trim(),
      duration:document.getElementById('advancedDuration').value.trim(),feeling:document.getElementById('advancedFeeling').value};
    seed={...selected};
    await next();
    panel.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'nearest'});
  }
  document.getElementById('advancedForm').addEventListener('submit',e=>{e.preventDefault();begin();});
  document.getElementById('restartInterview').addEventListener('click',begin);
  document.addEventListener('advanced-selection-changed',()=>{if (!applying) reset();});
  ['advancedDescription','advancedDuration','advancedFeeling'].forEach(id=>document.getElementById(id).addEventListener('input',reset));
  fetchJson(page.dataset.aiStatusUrl).then(data=>{status.textContent=data.message+window.campusI18n.text(" · 知识库 ")+data.knowledge_count+window.campusI18n.text(" 条摘要");}).catch(()=>{status.textContent=window.campusI18n.text("暂时无法检查本地 AI，开始后会再次尝试。");});
})();
