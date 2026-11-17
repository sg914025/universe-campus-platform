/* Translated AI display is separate from immutable source and patient text. */
(() => {
  const t = value => window.campusI18n.text(value);
  const language = document.documentElement.lang.split('-')[0];
  const cache = new Map(), queue = [];
  let running = false;
  const jobs = new WeakMap();
  const observer = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => {
    entries.forEach(entry => {if(entry.isIntersecting){observer.unobserve(entry.target);jobs.get(entry.target)?.();}});
  },{rootMargin:'120px'}) : null;
  function el(tag,text='',cls='') {
    const node=document.createElement(tag);node.textContent=text;if(cls)node.className=cls;return node;
  }
  function content(host,report,department,original=false) {
    const label=original ? value=>value : t;
    host.replaceChildren(el('h3',label('AI 初步推测 · 待医生核实')),el('p',report.summary||''),el('strong',label('建议科室：')+' '+label(department)));
    if(report.routing_reason)host.append(el('p',report.routing_reason));
    (report.possible_causes||[]).forEach(cause=>host.append(el('strong',label('可能原因：')+' '+cause.name),el('p',cause.reason)));
    if(!(report.possible_causes||[]).length)host.append(el('p',label('资料不足或 AI 未完成分析，暂不列出病因。'),'advanced-note'));
    if(report.message)host.append(el('p',report.message,'advanced-note'));
    host.append(el('p',report.notice||label('AI 推测不是确诊，需由医生核实。'),'advanced-note'));
  }
  async function runQueue() {
    if(running)return;running=true;
    try{while(queue.length){const job=queue.shift();if(job.host.isConnected)await job.run();}}finally{running=false;}
  }
  window.renderPatientReport = (host,report,department,reference) => {
    if(!report)return;
    const box=el('div','','patient-ai-report'),body=el('div','','report-translated');box.append(body);host.append(box);
    if(language==='zh'||!['en','ru','ja'].includes(language)){content(body,report,department);}
    else {
      const details=el('details','','report-original'),summary=el('summary',t('查看原文')),source=el('div');
      content(source,report,department,true);details.append(summary,source);box.append(details);
      const key=JSON.stringify([language,reference,report]);
      let queued=false;
      async function translate() {
        if(queued)return;queued=true;
        body.replaceChildren(el('h3',t('AI 初步推测 · 待医生核实')),el('p',t('正在翻译 AI 分析…'),'advanced-note'));
        queue.push({host:box,run:async()=>{
          const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),110000);
          try {
            if(!reference)throw new Error('导诊预览已过期，请重新生成结果。');
            let translated=cache.get(key);
            if(!translated){
              const csrf=decodeURIComponent((document.cookie.match(/(?:^|; )csrftoken=([^;]*)/)||[])[1]||'');
              const response=await fetch('/api/report-translation/',{method:'POST',credentials:'same-origin',cache:'no-store',signal:controller.signal,
                headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({...reference,language})});
              const data=await response.json();
              if(!response.ok)throw new Error(data.error||'AI分析暂时无法翻译，请查看原文或稍后重试。');
              if(!data.report||data.language!==language||!data.translated)throw new Error('AI分析暂时无法翻译，请查看原文或稍后重试。');
              translated=data.report;cache.set(key,translated);
            }
            content(body,translated,department);
            body.append(el('p',t('AI 自动译文 · 请结合原文核对'),'advanced-note report-translation-note'));
          }catch(error){
            body.replaceChildren(el('h3',t('AI 初步推测 · 待医生核实')),el('p',t(error.name==='AbortError'?'AI分析暂时无法翻译，请查看原文或稍后重试。':error.message),'advanced-note'));
            const retry=el('button',t('重试翻译'),'plain-button');retry.type='button';retry.addEventListener('click',translate);body.append(retry);
          }finally{clearTimeout(timer);queued=false;}
        }});runQueue();
      }
      body.append(el('h3',t('AI 初步推测 · 待医生核实')),el('p',t('正在翻译 AI 分析…'),'advanced-note'));
      if(observer){jobs.set(box,translate);observer.observe(box);}else{translate();}
    }
    const sources=el('div','','interview-sources');
    (report.sources||[]).forEach(source=>{const link=el('a',source.title+' ↗');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';sources.append(link);});
    if((report.sources||[]).length)sources.append(el('small','Source: MedlinePlus, National Library of Medicine.'));
    box.append(sources);
  };
})();
