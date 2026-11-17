import * as THREE from './vendor/three.module.js';
import {floorLayout,visibleLabels} from './floor-layout.mjs?v=1';

export function createInterior({t,url}){
 const dialog=document.createElement('dialog');dialog.className='interior-dialog';dialog.setAttribute('aria-labelledby','interior-title');
 dialog.innerHTML=`<header class="interior-header"><div><p>UNIVERSE / SPACE EXPLORER</p><h2 id="interior-title"></h2></div><button type="button" data-close>←</button></header><form class="interior-filters"><label data-day-label><input type="date" data-day required></label><label data-slot-label><select data-slot></select></label><button type="button" data-refresh>↻</button><span data-updated></span></form><nav class="interior-floors" aria-label="Floors"></nav><nav class="interior-kinds" aria-label="Resources"></nav><div class="interior-layout"><section class="interior-visual"><canvas aria-label="3D floor plan"></canvas><div class="interior-markers"></div><div class="interior-view-tools"><button type="button" data-fit>↻</button><button type="button" data-top>▤</button><button type="button" data-zoom-in>＋</button><button type="button" data-zoom-out>−</button></div><span class="interior-entry"></span></section><aside class="interior-side"><div class="interior-legend"></div><div class="interior-selected" aria-live="polite"><h3 data-resource-name></h3><p data-resource-meta></p><p data-resource-state></p><button type="button" data-navigate hidden></button><p data-route-instructions role="status"></p><a data-book hidden></a></div><p class="interior-notice"></p><p data-message role="status"></p></aside></div><details class="interior-list"><summary></summary><div data-resource-list></div></details>`;
 document.body.append(dialog);
 const $=s=>dialog.querySelector(s),day=$('[data-day]'),slot=$('[data-slot]'),floorNav=$('.interior-floors'),kindNav=$('.interior-kinds'),canvas=$('canvas'),visual=$('.interior-visual'),markers=$('.interior-markers'),message=$('[data-message]'),booking=$('[data-book]');
 const states={free:'可选',booked:'已预约',held:'候补保留',closed:'暂停开放',past:'时段已开始',conflict:'你已有同时段预约'};
 const colors={free:0x6c9d83,booked:0xc86d73,held:0xd4a357,closed:0x9ca5a2,past:0x9ca5a2,conflict:0x9ca5a2};
 const kindNames={study:'自习座位',table_tennis:'乒乓球台',basketball:'篮球场',badminton:'羽毛球场',football:'足球场'};
 $('[data-fit]').textContent=t('全层');$('[data-zoom-in]').setAttribute('aria-label',t('放大'));$('[data-zoom-out]').setAttribute('aria-label',t('缩小'));
 $('[data-navigate]').textContent=t('从入口导航到这里');
 $('[data-close]').textContent='← '+t('返回校园总览');$('[data-top]').textContent='▤ '+t('俯视');$('[data-refresh]').textContent='↻ '+t('刷新状态');
 for(const [selector,label] of [['[data-day-label]','预约日期'],['[data-slot-label]','预约时段']]){const span=document.createElement('span');span.textContent=t(label);$(selector).prepend(span);}
 $('.interior-entry').textContent=t('拖动旋转 · 右键平移 · 双指缩放');$('.interior-list summary').textContent=t('查看资源列表');
 $('.interior-notice').textContent=t('红色表示所选时段已预约，不代表现场检测。楼层与资源布局为示意，以学校实际安排为准。');
 for(const state of ['free','booked','held','closed']){const span=document.createElement('span');span.className='legend-'+state;span.textContent=t(states[state]);$('.interior-legend').append(span);}
 let place=null,data=null,floor=1,kind='all',selected=null,controller=null,revision=0,timer=null,renderer=null,scene=null,camera=null,group=null,frameId=0,theta=.45,phi=.7,radius=88,dirty=true,drag=null,moved=false,meshTargets=[],labelTargets=[],structureLabels=[],layout=null,target=new THREE.Vector3(),pointers=new Map(),pinch=0,resizeObserver=null,bodyOverflow='',routeGroup=null;
 function button(text,handler,active=false){const b=document.createElement('button');b.type='button';b.textContent=text;b.setAttribute('aria-pressed',String(active));b.onclick=handler;return b;}
 function area(p){return p.building||(p.id==='gym'?'gym':'outdoor');}
 function choose(resource){clearNavigation();selected=resource.id;$('[data-navigate]').hidden=false;meshTargets.forEach(mesh=>mesh.material.color.setHex(mesh.userData.resource.id===selected&&resource.state==='free'?0x8a76b1:mesh.userData.originalColor));$('[data-resource-name]').textContent=resource.name;$('[data-resource-meta]').textContent=data.day+' · '+data.slots.find(s=>s.code===data.slot)?.label+' · '+(place.id==='courts'?t('室外'):floor+' F');$('[data-resource-state]').textContent=t(states[resource.state])+(resource.mine?' · '+t('你的预约'):'');booking.hidden=resource.state!=='free';booking.href=resource.url;booking.textContent=t('核对并预约')+' →';dialog.querySelectorAll('[data-resource-list] button').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.id)===selected)));markers.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.id)===selected)));dirty=true;}
 function clearSelection(){clearNavigation();$('[data-navigate]').hidden=true;selected=null;booking.hidden=true;booking.removeAttribute('href');$('[data-resource-name]').textContent=t('选择座位或场地');$('[data-resource-meta]').textContent=t('点击模型中的座位、球台或球场');$('[data-resource-state]').textContent='';}
 function setLoading(value){day.disabled=value;slot.disabled=value;$('[data-refresh]').disabled=value;dialog.setAttribute('aria-busy',String(value));if(value){booking.hidden=true;message.textContent=t('正在查询预约状态…');}}
 async function load(){
  controller?.abort();controller=new AbortController();const token=++revision;setLoading(true);
  try{const params=new URLSearchParams({area:area(place)});if(day.value)params.set('day',day.value);if(slot.value)params.set('slot',slot.value);
   const response=await fetch(url+'?'+params,{credentials:'same-origin',cache:'no-store',signal:controller.signal});if(!response.ok)throw Error();const result=await response.json();if(token!==revision||!dialog.open)return;
   const hadRoute=!!routeGroup,firstLoad=!data,oldSelected=selected;data=result;day.value=result.day;day.min=result.today;day.max=result.last_day;slot.replaceChildren(...result.slots.map(s=>{const option=document.createElement('option');option.value=s.code;option.textContent=s.label;return option;}));slot.value=result.slot;
   const deepSeat=firstLoad?result.resources.find(r=>r.id===Number(new URLSearchParams(location.search).get('seat'))):null;if(deepSeat)floor=deepSeat.floor;
   if(!result.floors.includes(floor))floor=result.floors[0]||1;
   floorNav.replaceChildren(...result.floors.map(n=>button(place.id==='courts'?t('室外场地'):n+' F',()=>{floor=n;clearSelection();render();},n===floor)));
   $('[data-updated]').textContent=t('状态更新')+' '+result.updated;clearSelection();render();if(firstLoad)fit();
   if(deepSeat){choose(deepSeat);if(new URLSearchParams(location.search).get('navigate')==='1')navigate();}
   if(oldSelected){const current=result.resources.find(r=>r.id===oldSelected&&r.floor===floor&&(kind==='all'||r.kind===kind));if(current){choose(current);if(hadRoute)navigate();}}
   message.textContent=result.resources.length?'':t('该区域尚未登记可预约资源');
  }catch(error){if(error.name!=='AbortError'&&token===revision){clearSelection();data=null;disposeGroup();markers.replaceChildren();$('[data-resource-list]').replaceChildren();message.textContent=t('状态加载失败，请刷新后重试。');}}
  finally{if(token===revision)setLoading(false);}
 }
 function setup(){
  if(renderer)return;try{renderer=new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'low-power'});}catch(_){canvas.hidden=true;message.textContent=t('3D 不可用，请使用下方资源列表');$('.interior-list').open=true;return;}
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.08;
  scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xf3f6ff,0x8e9d8a,3));const light=new THREE.DirectionalLight(0xfff3dc,3);light.position.set(-30,90,50);scene.add(light);camera=new THREE.PerspectiveCamera(43,1,.1,1200);
  resizeObserver=new ResizeObserver(()=>{if(dialog.open)resize();});resizeObserver.observe(visual);
  canvas.addEventListener('contextmenu',event=>event.preventDefault());
  canvas.addEventListener('pointerdown',event=>{canvas.setPointerCapture(event.pointerId);pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});drag={x:event.clientX,y:event.clientY,id:event.pointerId,pan:event.button===2||event.shiftKey};moved=false;if(pointers.size===2){const [a,b]=[...pointers.values()];pinch=Math.hypot(a.x-b.x,a.y-b.y);moved=true;}});
  canvas.addEventListener('pointermove',event=>{if(!pointers.has(event.pointerId))return;const prev=pointers.get(event.pointerId),dx=event.clientX-prev.x,dy=event.clientY-prev.y;pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});if(pointers.size===2){const [a,b]=[...pointers.values()],next=Math.hypot(a.x-b.x,a.y-b.y);if(pinch>0&&next>0)radius=THREE.MathUtils.clamp(radius*pinch/next,35,300);pinch=next;moved=true;dirty=true;return;}if(!drag)return;if(Math.abs(dx)+Math.abs(dy)>2)moved=true;if(drag.pan){const scale=radius/Math.max(visual.clientHeight,1);target.x=THREE.MathUtils.clamp(target.x-dx*scale*Math.cos(theta)-dy*scale*Math.sin(theta),-80,80);target.z=THREE.MathUtils.clamp(target.z+dx*scale*Math.sin(theta)-dy*scale*Math.cos(theta),-80,80);}else{theta-=dx*.007;phi=THREE.MathUtils.clamp(phi+dy*.005,.08,1.15);}dirty=true;});
  canvas.addEventListener('pointerup',event=>{if(!moved&&event.button===0&&data&&camera){const bounds=canvas.getBoundingClientRect(),ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2((event.clientX-bounds.left)/bounds.width*2-1,-(event.clientY-bounds.top)/bounds.height*2+1),camera);const hit=ray.intersectObjects(meshTargets,false)[0];if(hit?.object.userData.resource)choose(hit.object.userData.resource);}pointers.delete(event.pointerId);pinch=0;drag=null;});canvas.addEventListener('pointercancel',event=>{pointers.delete(event.pointerId);drag=null;pinch=0;});
  canvas.addEventListener('wheel',event=>{event.preventDefault();radius=THREE.MathUtils.clamp(radius*Math.exp(event.deltaY*.001),35,300);dirty=true;},{passive:false});
 }
 function resize(){if(!renderer||!camera)return;const bounds=visual.getBoundingClientRect();renderer.setSize(bounds.width,bounds.height,false);camera.aspect=bounds.width/bounds.height;camera.updateProjectionMatrix();dirty=true;}
 function material(color){return new THREE.MeshStandardMaterial({color,roughness:.8});}
 function box(w,h,d,x,y,z,color,resource){const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material(color));m.position.set(x,y,z);group.add(m);if(resource){m.userData.resource=resource;m.userData.originalColor=color;meshTargets.push(m);}return m;}
 function line(points,color=0xfff7da){const geometry=new THREE.BufferGeometry().setFromPoints(points.map(([x,z])=>new THREE.Vector3(x,.3,z)));group.add(new THREE.Line(geometry,new THREE.LineBasicMaterial({color})));}
 function circle(x,z,r){const points=[];for(let i=0;i<=48;i++)points.push([x+Math.cos(i/48*Math.PI*2)*r,z+Math.sin(i/48*Math.PI*2)*r]);line(points);}
 function disposeGroup(){if(!group)return;const geometries=new Set(),materials=new Set();group.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)materials.add(o.material);});geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());scene.remove(group);group=null;meshTargets=[];labelTargets=[];structureLabels=[];dirty=true;}
 function landmark(text,x,z){const element=document.createElement('span');element.className='interior-landmark';element.textContent=t(text);markers.append(element);structureLabels.push({element,point:new THREE.Vector3(x,2,z)});}
 function stairs(x,z){box(13,.15,20,x,.05,z,0xc8d3c1);for(let i=0;i<9;i++){const height=(i+1)*.48;box(5,height,1.5,x-2.7,height/2,z+6-i*1.5,0xc3c5b5);}box(11,.5,4,x,4.4,z-8,0xd9d7c6);for(let i=0;i<9;i++){const height=(9-i)*.48;box(5,height,1.5,x+2.7,height/2,z+6-i*1.5,0xd1cebc);}for(const side of [-1,1])for(let i=0;i<5;i++)box(.18,2,.18,x+side*5.5,2.3+i*.5,z+6-i*3);landmark('楼梯',x,z+11);}
 function buildFloor(){const {width:w,depth:d,study}=layout,outdoor=place.id==='courts';box(w,.9,d,0,-.75,0,0xd8d5c5);box(w,.12,d,0,-.22,0,0xeeeade);
  if(outdoor){landmark('室外场地',0,-d/2+5);box(4,.08,d, -w/2+7,-.12,0,0xc9d4bc);return;}
  // Open cutaway walls keep rooms visible from every zoom level.
  box(w,2,.5,0,.8,-d/2,0xc0cbbf);box(.5,2,d,-w/2,.8,0,0xc0cbbf);box(.5,1,d,w/2,.3,0,0xc0cbbf);
  box(13,.08,d-4,0,-.1,0,0xd3dccb);box(w-4,.08,13,0,-.08,0,0xd3dccb);
  for(const side of [-1,1]){stairs(side*(w/2-8),0);for(const z of [-d/2+9,d/2-9]){box(.5,5,8,side*(w/2-1),2.6,z,0xaec4c2);box(.1,.18,8,side*(w/2-1.3),3.5,z,0xf5f4e7);}}
  if(study){for(let room=0;room<4;room++){const side=room%2?1:-1,back=room<2?-1:1,x=side*28,z=back*23;box(40,.06,29,x,-.08,z,room%2?0xe4e9da:0xe8e3d5);box(40,1.4,.35,x,.5,z+back*15,0xc3cebf);box(.35,1.4,30,x+side*20,.5,z,0xc3cebf);box(14,1.4,.35,x-side*13,.5,back*8,0xc3cebf);box(14,1.4,.35,x+side*13,.5,back*8,0xc3cebf);landmark(String(floor*100+room+1)+' · '+t('自习区'),x,back*37);box(8,3,1,x,1.4,z+back*13,0xa5b6a0);}}
  box(8,3,7,0,1.3,-d/2+6,0xbaccc9);box(3.3,2.6,.2,-1.8,1.3,-d/2+9.6,0x839d9b);box(3.3,2.6,.2,1.8,1.3,-d/2+9.6,0x839d9b);landmark('电梯',0,-d/2+13);
  box(9,.1,4,0,-.02,d/2-3,0x8ea994);landmark('楼层入口',0,d/2-8);landmark('主走廊',0,14);
  for(const side of [-1,1]){box(8,2,6,side*17,1,d/2-5,0xcbd5c5);landmark(side<0?'卫生间':'服务区',side*20,d/2-5);}
 }
 function render(){
  if(!data)return;disposeGroup();markers.replaceChildren();const resources=data.resources.filter(r=>r.floor===floor),kinds=[...new Set(resources.map(r=>r.kind))];if(kind!=='all'&&!kinds.includes(kind))kind='all';
  floorNav.querySelectorAll('button').forEach((b,index)=>b.setAttribute('aria-pressed',String(data.floors[index]===floor)));
  kindNav.replaceChildren(button(t('全部资源'),()=>{kind='all';clearSelection();render();},kind==='all'),...kinds.map(k=>button(t(kindNames[k]),()=>{kind=k;clearSelection();render();},kind===k)));
  const filtered=resources.filter(r=>kind==='all'||r.kind===kind),list=$('[data-resource-list]');list.replaceChildren();
  layout=floorLayout(resources,place.id==='courts');
  if(renderer){group=new THREE.Group();scene.add(group);scene.background=new THREE.Color(document.documentElement.dataset.theme==='dark'?0x243c40:0xe9eee3);buildFloor();}
  filtered.forEach((r,index)=>{
   const state=t(states[r.state]),b=button(r.name+' · '+state,()=>choose(r),r.id===selected);b.className='interior-resource '+r.state;b.dataset.id=r.id;list.append(b);
   if(!renderer)return;const {x,z}=layout.positions.get(r.id),color=colors[r.state];
   if(r.kind==='study'){box(6,.55,3.5,x,2.5,z,0xeee8d4,r);box(.4,2.3,.4,x-2,1.1,z,0x9aa896);box(.4,2.3,.4,x+2,1.1,z,0x9aa896);box(3,.55,2.8,x,1.3,z+3.8,color,r);box(3,2,.5,x,2.3,z+5,color,r);}
   else if(r.kind==='table_tennis'){box(12,.55,6.6,x,2.7,z,color,r);box(12,.12,.12,x,3.02,z,0xffffff);box(.15,1.2,6.8,x,3.5,z,0xced9d4,r);box(.6,2.5,5,x-4,1,z,0x84968a);box(.6,2.5,5,x+4,1,z,0x84968a);}
   else {const football=r.kind==='football',w=football?25:14,d=football?38:12;box(w,.3,d,x,-.02,z,color,r);line([[x-w/2,z-d/2],[x+w/2,z-d/2],[x+w/2,z+d/2],[x-w/2,z+d/2],[x-w/2,z-d/2]]);line([[x-w/2,z],[x+w/2,z]]);circle(x,z,football?4:2);
    if(r.kind==='basketball')for(const sign of [-1,1]){box(.3,4,.3,x,2,z+sign*(d/2+.8),0x63796b);box(3,1.7,.2,x,4,z+sign*d/2,0xeef2e7);const hoop=new THREE.Mesh(new THREE.TorusGeometry(.8,.12,6,20),material(0xd59c6b));hoop.rotation.x=Math.PI/2;hoop.position.set(x,3.5,z+sign*(d/2-.7));group.add(hoop);}
    if(football)for(const sign of [-1,1]){box(7,2.5,.2,x,1.1,z+sign*d/2,0xdce7d8);}
    if(r.kind==='badminton')box(w,1.8,.15,x,.9,z,0xf3eee0);
   }
   const label=button((r.kind==='study'?String(Number(r.name.match(/(\d+)\s*号/)?.[1]||index+1)).padStart(2,'0'):t(kindNames[r.kind])+' '+(r.name.match(/(\d+)\s*号/)?.[1]||index+1)),()=>choose(r),r.id===selected);label.dataset.id=r.id;label.className='interior-marker '+r.state;label.setAttribute('aria-label',r.name+' · '+state);markers.append(label);labelTargets.push({element:label,point:new THREE.Vector3(x,r.kind==='study'?5:4,z)});
  });
  if(!filtered.length)list.textContent=t('当前楼层没有该类型的资源');dirty=true;
 }
 function clearNavigation(){if(routeGroup){routeGroup.traverse(o=>{o.geometry?.dispose();if(o.material)o.material.dispose();});routeGroup.parent?.remove(routeGroup);routeGroup=null;}$('[data-route-instructions]').textContent='';dirty=true;}
 function navigate(){if(!layout||!selected)return;clearNavigation();const pos=layout.positions.get(selected);if(!pos)return;const start=layout.depth/2-8,points=[[0,start],[0,pos.z+7],[pos.x,pos.z+7],[pos.x,pos.z+3]];if(renderer&&group){routeGroup=new THREE.Group();group.add(routeGroup);const geometry=new THREE.BufferGeometry().setFromPoints(points.map(([x,z])=>new THREE.Vector3(x,.6,z)));routeGroup.add(new THREE.Line(geometry,new THREE.LineBasicMaterial({color:0x8c59c3})));for(let i=1;i<points.length;i++){const [ax,az]=points[i-1],[bx,bz]=points[i],length=Math.hypot(bx-ax,bz-az);for(let step=4;step<length;step+=6){const arrow=new THREE.Mesh(new THREE.ConeGeometry(.65,1.8,3),material(0x8956b8));arrow.rotation.x=Math.PI/2;arrow.rotation.z=-Math.atan2(bz-az,bx-ax)+Math.PI/2;arrow.position.set(ax+(bx-ax)*step/length,.8,az+(bz-az)*step/length);routeGroup.add(arrow);}}}const resource=data.resources.find(r=>r.id===selected);$('[data-route-instructions]').textContent=t('楼层入口')+' → '+t('主走廊')+' → '+resource.name+' · '+floor+' F · '+t('示意路线，请以现场标识为准');dirty=true;}
 $('[data-navigate]').onclick=navigate;
 function fit(){target.set(0,0,0);theta=.28;phi=.65;radius=layout?Math.max(layout.width,layout.depth)*1.62:145;dirty=true;}
 function frame(){cancelAnimationFrame(frameId);if(!dialog.open)return;frameId=requestAnimationFrame(frame);if(!renderer||!dirty||!camera)return;const adjusted=radius*Math.max(1,.95/camera.aspect);camera.position.set(target.x+adjusted*Math.sin(phi)*Math.sin(theta),adjusted*Math.cos(phi),target.z+adjusted*Math.sin(phi)*Math.cos(theta));camera.lookAt(target);camera.updateMatrixWorld();
 const point=new THREE.Vector3(),candidates=labelTargets.map(({element,point:position},order)=>{point.copy(position).project(camera);const x=(point.x*.5+.5)*visual.clientWidth,y=(-point.y*.5+.5)*visual.clientHeight;element.style.left=x+'px';element.style.top=y+'px';return {x,y,z:point.z,w:element.offsetWidth||40,h:element.offsetHeight||28,order,selected:Number(element.dataset.id)===selected,focused:document.activeElement===element};});
 structureLabels.forEach(({element,point:position},index)=>{point.copy(position).project(camera);const x=(point.x*.5+.5)*visual.clientWidth,y=(-point.y*.5+.5)*visual.clientHeight;element.style.left=x+'px';element.style.top=y+'px';candidates.push({x,y,z:radius<65?2:point.z,w:element.offsetWidth||60,h:element.offsetHeight||24,order:labelTargets.length+index,selected:false,focused:false});});
 const shown=new Set(visibleLabels(candidates,visual.clientWidth,visual.clientHeight));labelTargets.forEach(({element},i)=>{element.style.visibility=shown.has(i)?'visible':'hidden';});structureLabels.forEach(({element},i)=>{element.style.visibility=shown.has(labelTargets.length+i)?'visible':'hidden';});renderer.render(scene,camera);dirty=false;}

 function close(){dialog.close();}
 $('[data-close]').onclick=close;dialog.addEventListener('close',()=>{document.body.style.overflow=bodyOverflow;controller?.abort();revision++;clearInterval(timer);cancelAnimationFrame(frameId);});
 day.onchange=slot.onchange=()=>{clearSelection();load();};$('[data-refresh]').onclick=load;$('[data-fit]').onclick=fit;$('[data-top]').onclick=()=>{phi=.08;theta=0;dirty=true;};$('[data-zoom-in]').onclick=()=>{radius=Math.max(35,radius*.8);dirty=true;};$('[data-zoom-out]').onclick=()=>{radius=Math.min(300,radius*1.2);dirty=true;};
 window.addEventListener('pagehide',()=>{controller?.abort();clearInterval(timer);cancelAnimationFrame(frameId);disposeGroup();resizeObserver?.disconnect();renderer?.dispose();});
 return {open(p){place=p;data=null;disposeGroup();floor=1;kind='all';selected=null;day.value=new URLSearchParams(location.search).get('day')||'';slot.replaceChildren();const initialSlot=new URLSearchParams(location.search).get('slot');if(initialSlot){const option=document.createElement('option');option.value=initialSlot;slot.append(option);slot.value=initialSlot;}floorNav.replaceChildren();kindNav.replaceChildren();markers.replaceChildren();$('[data-resource-list]').replaceChildren();$('#interior-title').textContent=t(p.name)+' / '+t(p.kind==='study'?'楼层选座':'场馆资源');if(!dialog.open){bodyOverflow=document.body.style.overflow;document.body.style.overflow='hidden';dialog.showModal();}clearSelection();setup();resize();fit();dirty=true;frame();clearInterval(timer);timer=setInterval(()=>{if(dialog.open&&!document.hidden&&!document.activeElement?.matches('input,select'))load();},30000);load();}};
}
