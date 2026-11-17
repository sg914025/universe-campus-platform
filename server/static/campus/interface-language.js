/* Translates fixed interface literals only. Never submits user text. */
(() => {
  const node=document.getElementById('campus-ui-catalog');
  const catalog=node ? JSON.parse(node.textContent) : {};
  function text(value) {
    if(typeof value!=='string')return value;
    if(catalog[value])return catalog[value];
    const key=value.trim();
    return catalog[key] ? value.replace(key,catalog[key]) : value;
  }
  function html(value) {
    const fragment=document.createElement('template');fragment.innerHTML=value;
    const walk=document.createTreeWalker(fragment.content,NodeFilter.SHOW_TEXT);
    let n;while((n=walk.nextNode()))n.textContent=text(n.textContent);
    return fragment.innerHTML;
  }
  window.campusI18n={text,html};
})();
