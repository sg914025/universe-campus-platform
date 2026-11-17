(() => {
  const host=document.querySelector('.journey-details');if(!host)return;
  const panels=[...host.querySelectorAll('.journey-panel')],buttons=[...document.querySelectorAll('.journey-step')];
  const storageKey='universe-newcomer-v1:'+host.dataset.user;
  let saved={done:[],current:'language'};
  try{const value=JSON.parse(localStorage.getItem(storageKey));if(value&&Array.isArray(value.done))saved={done:value.done.filter(key=>panels.some(panel=>panel.dataset.key===key)),current:value.current};}catch(_){}
  const completed=new Set(saved.done);
  function persist(key){try{localStorage.setItem(storageKey,JSON.stringify({done:[...completed],current:key}));}catch(_){}}
  function show(key){
    const panel=panels.find(item=>item.dataset.key===key)||panels[0];key=panel.dataset.key;
    panels.forEach(item=>item.hidden=item!==panel);
    buttons.forEach(button=>{button.setAttribute('aria-pressed',String(button.dataset.step===key));button.classList.toggle('is-done',completed.has(button.dataset.step));});
    document.getElementById('journey-done').textContent=completed.size;
    document.getElementById('journey-progress').value=completed.size;
    document.getElementById('journey-finish').hidden=completed.size!==panels.length;
    persist(key);
    window.dispatchEvent(new CustomEvent('campus-journey-step',{detail:{step:key,instruction:panel.dataset.instruction,action:panel.dataset.action}}));
  }
  buttons.forEach(button=>button.addEventListener('click',()=>show(button.dataset.step)));
  panels.forEach((panel,index)=>panel.querySelector('.journey-complete').addEventListener('click',()=>{completed.add(panel.dataset.key);show(panels[Math.min(index+1,panels.length-1)].dataset.key);}));
  document.getElementById('journey-reset').addEventListener('click',()=>{completed.clear();show('language');});
  document.querySelector('[data-language-focus]').addEventListener('click',event=>{event.preventDefault();document.querySelector('#journey-language select')?.focus();});
  show(saved.current);
})();
