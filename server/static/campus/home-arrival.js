(()=>{
 if(window.self!==window.top)return;
 const screen=document.getElementById('arrival-screen');if(!screen)return;
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const idleMs=5*60*1000;let idleTimer,autoTimer,hideTimer,revealTimer,showing=false,opener=null;
 function arm(){clearTimeout(idleTimer);if(!showing)idleTimer=setTimeout(()=>{if(document.querySelector('dialog[open]')||document.activeElement?.matches('input,textarea,select,[contenteditable=true]')){arm();return;}show(false);},idleMs);}
 function show(auto){clearTimeout(idleTimer);clearTimeout(autoTimer);clearTimeout(hideTimer);clearTimeout(revealTimer);opener=document.activeElement;showing=true;screen.hidden=false;screen.classList.remove('arrival-leaving');document.documentElement.classList.remove('arrival-reveal');document.documentElement.classList.add('arrival-playing');document.querySelector('main')?.setAttribute('inert','');document.querySelector('body>.header')?.setAttribute('inert','');if(!auto)screen.querySelector('button').focus({preventScroll:true});if(auto)autoTimer=setTimeout(enter,1500);}
 function enter(){if(!showing)return;showing=false;clearTimeout(autoTimer);screen.classList.add('arrival-leaving');document.documentElement.classList.remove('arrival-playing');document.querySelector('main')?.removeAttribute('inert');document.querySelector('body>.header')?.removeAttribute('inert');if(!reduced)document.documentElement.classList.add('arrival-reveal');hideTimer=setTimeout(()=>{screen.hidden=true;screen.classList.remove('arrival-leaving');},reduced?0:850);revealTimer=setTimeout(()=>document.documentElement.classList.remove('arrival-reveal'),1800);opener?.focus?.({preventScroll:true});arm();}
 screen.querySelector('button').onclick=enter;
 document.addEventListener('click',e=>{if(e.target.closest('[data-show-arrival]'))show(false)});
 document.addEventListener('keydown',e=>{if(showing&&e.key==='Escape')enter()});
 for(const event of ['pointerdown','pointermove','keydown','scroll','touchstart'])document.addEventListener(event,()=>{if(!showing)arm()},{passive:true});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!showing)arm()});
 if(reduced)arm();else show(true);
})();
