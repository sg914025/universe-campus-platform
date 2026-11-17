(() => {
  const t=s=>window.campusI18n?.text(s)||s;
  const shell=document.querySelector('.security-shell');
  if(shell?.dataset.needsScan==='1'){
    const token=document.querySelector('#security-csrf [name=csrfmiddlewaretoken]').value;
    const feedback=document.getElementById('security-feedback');feedback.textContent=t('正在生成今日安全快照…');
    fetch(shell.dataset.dailyUrl,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':token,'X-Requested-With':'XMLHttpRequest','Content-Type':'application/x-www-form-urlencoded'},body:'daily=1'})
      .then(r=>{if(!r.ok)throw Error();return r.json();}).then(()=>location.reload()).catch(()=>{feedback.textContent=t('安全检查未完成，请稍后重试。');});
  }
  document.querySelectorAll('[data-busy-form]').forEach(form=>form.addEventListener('submit',()=>{const button=form.querySelector('button');button.disabled=true;button.textContent=t('正在处理，请稍候…');}));
  const canvas=document.getElementById('security-twin');if(!canvas)return;
  const data=JSON.parse(document.getElementById('security-twin-data').textContent),ctx=canvas.getContext('2d');
  if(!ctx)return;
  let width=1,height=1,yaw=-.55,drag=false,moved=false,lastX=0,selected='app',paused=matchMedia('(prefers-reduced-motion: reduce)').matches,lastTime=0,clock=0,frame=0;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const colors={pass:'#a2d4b6',warn:'#d6be82',unknown:'#7e9dac',linked:'#8eb8c2'};
  function size(){const r=canvas.getBoundingClientRect();width=r.width;height=r.height;const ratio=Math.min(devicePixelRatio||1,2);canvas.width=width*ratio;canvas.height=height*ratio;ctx.setTransform(ratio,0,0,ratio,0,0);draw();}
  function project([x,y,z]){const rx=x*Math.cos(yaw)-z*Math.sin(yaw),rz=x*Math.sin(yaw)+z*Math.cos(yaw),zoom=Math.min(width/660,height/510),perspective=650/(760-rz);return {x:width/2+rx*zoom*perspective*1.5,y:height*.50+(rz*.38-y)*zoom*perspective*1.5,z:rz,scale:zoom*perspective};}
  function line(a,b,color='#28515a',weight=1){ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.strokeStyle=color;ctx.lineWidth=weight;ctx.stroke();}
  function cuboid(node){const [x,y,z]=node.position,half=node.id==='app'?23:17,h=node.id==='db'?51:node.id==='app'?65:32;const vertices=[[-half,0,-half],[half,0,-half],[half,0,half],[-half,0,half],[-half,h,-half],[half,h,-half],[half,h,half],[-half,h,half]].map(([a,b,c])=>project([x+a,y+b,z+c]));const c=colors[node.state]||colors.unknown;
    ctx.fillStyle='#2a5d6260';for(const ids of [[0,1,5,4],[1,2,6,5],[4,5,6,7]]){ctx.beginPath();ids.forEach((i,j)=>j?ctx.lineTo(vertices[i].x,vertices[i].y):ctx.moveTo(vertices[i].x,vertices[i].y));ctx.closePath();ctx.fill();}
    const active=node.id===selected;for(const [a,b] of [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]])line(vertices[a],vertices[b],active?'#e1d6a7':c,active?1.8:1);
    const top=project([x,y+h+10,z]),base=project([x,y,z]);node.screen=base;
    ctx.shadowBlur=active?16:6;ctx.shadowColor=c;ctx.fillStyle=c;ctx.beginPath();ctx.ellipse(base.x,base.y+4,35*base.scale,12*base.scale,0,0,Math.PI*2);ctx.strokeStyle=c+'55';ctx.stroke();ctx.shadowBlur=0;
    ctx.textAlign='center';ctx.font=(active?'600 ':'')+'11px "Segoe UI","Microsoft YaHei",sans-serif';ctx.fillStyle=active?'#e5ead1':'#a3c3ba';ctx.fillText(node.label,top.x,top.y-5,145);
    ctx.font='8px ui-monospace,monospace';ctx.fillStyle='#6e9a98';ctx.fillText(node.id.toUpperCase(),base.x,base.y+26*Math.max(.75,base.scale));
  }
  function draw(){ctx.clearRect(0,0,width,height);
    for(let n=-300;n<=300;n+=50){line(project([n,-18,-300]),project([n,-18,300]),'#24474c65');line(project([-300,-18,n]),project([300,-18,n]),'#24474c65');}
    const byId=Object.fromEntries(data.nodes.map(n=>[n.id,n]));
    for(const [a,b] of data.links){const A=project(byId[a].position),B=project(byId[b].position);line(A,B,'#609a8b55',1.1);const p=(clock/4000+b.length*.11)%1;const x=A.x+(B.x-A.x)*p,y=A.y+(B.y-A.y)*p;ctx.fillStyle='#bdce8b';ctx.shadowBlur=9;ctx.shadowColor='#bad89c';ctx.beginPath();ctx.arc(x,y,2,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;}
    [...data.nodes].sort((a,b)=>project(a.position).z-project(b.position).z).forEach(cuboid);
  }
  function choose(id){const node=data.nodes.find(n=>n.id===id);if(!node)return;selected=id;document.getElementById('twin-node-name').textContent=node.label;document.getElementById('twin-node-evidence').textContent=node.metric;document.getElementById('twin-node-state').textContent=t(node.state==='pass'?'已核验':node.state==='warn'?'需关注':node.state==='linked'?'逻辑关联':'未核验');document.querySelectorAll('[data-node]').forEach(n=>n.classList.toggle('selected',n.dataset.node===id));draw();}
  document.querySelectorAll('[data-node]').forEach(button=>button.addEventListener('click',()=>choose(button.dataset.node)));
  canvas.addEventListener('pointerdown',e=>{drag=true;moved=false;lastX=e.clientX;canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(drag){const dx=e.clientX-lastX;if(Math.abs(dx)>1)moved=true;yaw+=dx*.008;lastX=e.clientX;draw();}});
  canvas.addEventListener('pointerup',e=>{drag=false;if(!moved){const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;const node=[...data.nodes].reverse().find(n=>n.screen&&Math.hypot(n.screen.x-x,n.screen.y-y)<48);if(node)choose(node.id);}});
  canvas.addEventListener('pointercancel',()=>drag=false);
  function animate(now){frame=requestAnimationFrame(animate);if(document.hidden||paused){lastTime=now;return;}clock+=Math.min(now-lastTime,60);lastTime=now;draw();}
  const pause=document.getElementById('twin-pause');function pauseLabel(){pause.textContent=t(paused?'继续动画':'暂停动画');pause.setAttribute('aria-pressed',String(paused));}pause.addEventListener('click',()=>{paused=!paused;if(!paused&&!frame)frame=requestAnimationFrame(animate);pauseLabel();});pauseLabel();
  new ResizeObserver(size).observe(canvas);size();choose('app');if(!reduced)frame=requestAnimationFrame(animate);
  window.addEventListener('pagehide',()=>cancelAnimationFrame(frame));
})();
