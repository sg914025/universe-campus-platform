import * as THREE from './vendor/three.module.js';
import {places,nodes,edges,routeTo} from './campus-layout.js?v=interior3';
import {createInterior} from './map-interior.js?v=checkin1';

const canvas=document.getElementById('campus-map-canvas'),stage=canvas.parentElement;
const t=s=>window.campusI18n?.text(s)||s,data=JSON.parse(document.getElementById('campus-map-data').textContent);
const loading=document.getElementById('map-loading'),list=document.getElementById('map-building-list'),labelLayer=document.getElementById('map-labels');
const interior=createInterior({t,url:data.inventory});
const kinds={study:'学习',life:'生活',sport:'运动',health:'健康'};
let renderer;
try{renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,powerPreference:'low-power'});}catch(error){loading.textContent=t('3D 渲染暂不可用，仍可通过建筑列表访问服务。');}
if(!renderer)labelLayer.hidden=true;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.5,1400);
const sun=new THREE.DirectionalLight(0xfff5df,3.3);sun.position.set(-130,250,100);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-220;sun.shadow.camera.right=220;sun.shadow.camera.top=230;sun.shadow.camera.bottom=-230;sun.shadow.camera.far=650;sun.shadow.normalBias=.4;
const ambient=new THREE.HemisphereLight(0xe4f0ff,0x969d75,2.2);scene.add(ambient,sun);
const world=new THREE.Group();scene.add(world);
const buildingGroups=new Map(),labels=new Map(),windowTransforms=[];
const mat=(color,roughness=.85)=>new THREE.MeshStandardMaterial({color,roughness});
const wallMats={study:mat(0xf0e8d7),life:mat(0xe8d6c3),sport:mat(0xdce5df),health:mat(0xe7e2d7)};
const roof=mat(0x6e8786),stone=mat(0xe5e5d2),roadMat=mat(0x8da5a2),pathMat=mat(0xe5ce9f);
function box(w,h,d,x,y,z,material,parent=world){const mesh=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);mesh.position.set(x,y,z);mesh.castShadow=h>2;mesh.receiveShadow=true;parent.add(mesh);return mesh;}
function roundedShape(w,d,r){const s=new THREE.Shape();s.moveTo(-w/2+r,-d/2);s.lineTo(w/2-r,-d/2);s.quadraticCurveTo(w/2,-d/2,w/2,-d/2+r);s.lineTo(w/2,d/2-r);s.quadraticCurveTo(w/2,d/2,w/2-r,d/2);s.lineTo(-w/2+r,d/2);s.quadraticCurveTo(-w/2,d/2,-w/2,d/2-r);s.lineTo(-w/2,-d/2+r);s.quadraticCurveTo(-w/2,-d/2,-w/2+r,-d/2);return s;}
const baseGeometry=new THREE.ExtrudeGeometry(roundedShape(306,354,16),{depth:7,bevelEnabled:true,bevelSize:1.3,bevelThickness:1.3,bevelSegments:2,steps:1,curveSegments:8});baseGeometry.rotateX(-Math.PI/2);
const base=new THREE.Mesh(baseGeometry,mat(0xc6d3b8));base.position.y=-8.5;base.receiveShadow=true;world.add(base);
function zone(x,z,w,d,color){return box(w,.15,d,x,.12,z,mat(color));}
zone(-62,-102,121,77,0xdce2c7);zone(-40,26,139,135,0xe5e9d4);zone(-73,111,126,53,0xd2ddc2);zone(55,-9,67,58,0xe5e9d7);
// Layered green hills retain the reference's broad green belt between campus groups.
for(const [x,z,sx,sz,h] of [[96,-119,60,60,15],[121,-43,29,65,11],[-128,4,22,64,10],[-118,-145,24,21,7],[70,-151,49,21,8],[100,79,38,53,8]]){
 const hill=new THREE.Mesh(new THREE.SphereGeometry(1,22,12),mat(0xb4c89b));hill.position.set(x,-2,z);hill.scale.set(sx,h,sz);hill.receiveShadow=true;world.add(hill);
}
function stroke(points,width,material,y=.3,parent=world){y+=.7;const smooth=new THREE.CatmullRomCurve3(points.map(([x,z])=>new THREE.Vector3(x,y,z)),false,'catmullrom',.15);const samples=smooth.getPoints(Math.max(12,points.length*12));for(let i=1;i<samples.length;i++){const a=samples[i-1],b=samples[i],mid=a.clone().add(b).multiplyScalar(.5),length=a.distanceTo(b);const mesh=box(width,.12,length+.08,mid.x,y,mid.z,material,parent);mesh.rotation.y=Math.atan2(b.x-a.x,b.z-a.z);}return smooth;}
const arterial=[[-9,-171],[-9,-61],[24,24],[44,78],[77,171]];
stroke(arterial,15,mat(0xf4f4e9),.22);const mainCurve=stroke(arterial,10,roadMat,.34);
stroke([[-151,-49],[-89,-49],[-32,-55],[-9,-61]],13,mat(0xf4f4e9),.2);stroke([[-151,-49],[-89,-49],[-32,-55],[-9,-61]],8,roadMat,.31);
stroke([[-151,148],[-55,146],[21,146],[151,147]],14,mat(0xf4f4e9),.2);stroke([[-151,148],[-55,146],[21,146],[151,147]],9,roadMat,.32);
stroke([[24,24],[73,21],[151,16]],11,mat(0xf4f4e9),.2);stroke([[24,24],[73,21],[151,16]],7,roadMat,.33);
// Dashed centre marks, directional, with a deliberate scale rather than map tiles.
for(let i=1;i<62;i+=2){const p=mainCurve.getPoint(i/62),dir=mainCurve.getTangent(i/62);const mark=box(.28,.1,3,p.x,1.2,p.z,mat(0xf6edbb));mark.rotation.y=Math.atan2(dir.x,dir.z);}
for(const [a,b] of edges)stroke([nodes[a],nodes[b]],3.8,pathMat,.38);
stroke([[-117,-129],[-104,-88],[-58,-62],[-22,-75]],3,pathMat,.38);
stroke([[-95,45],[-94,72],[-68,79],[-41,57]],3,pathMat,.38);
// Main plaza and the south gate.
box(26,.3,19,-7,.4,137,stone);box(3,10,3,-17,5,144,mat(0xe8e5d7));box(3,10,3,3,5,144,mat(0xe8e5d7));box(25,2,4,-7,11,144,roof);
function collectWindows(x,z,w,d,h){const levels=Math.floor((h-3)/3);for(let floor=0;floor<levels;floor++)for(let offset=3;offset<w-2;offset+=3.4)for(const side of [-1,1]){const matrix=new THREE.Matrix4().compose(new THREE.Vector3(x-w/2+offset,3.2+floor*3,z+side*(d/2+.07)),new THREE.Quaternion(),new THREE.Vector3(1.35,1.35,.12));windowTransforms.push(matrix);}for(let floor=0;floor<levels;floor++)for(let offset=3;offset<d-2;offset+=4)for(const side of [-1,1]){const matrix=new THREE.Matrix4().compose(new THREE.Vector3(x+side*(w/2+.07),3.2+floor*3,z-d/2+offset),new THREE.Quaternion(),new THREE.Vector3(.12,1.3,1.35));windowTransforms.push(matrix);}}
function building(p){const group=new THREE.Group();group.userData.place=p;world.add(group);buildingGroups.set(p.id,group);
 if(p.id==='courts'){
  box(p.w,.3,p.d,p.x,.6,p.z,mat(0x8aa996),group);
  const lines=mat(0xe5eee2);for(const x of [-p.w/2+2,p.w/2-2])box(.18,.1,p.d-4,p.x+x,.85,p.z,lines,group);for(const z of [-p.d/2+2,0,p.d/2-2])box(p.w-4,.1,.18,p.x,.85,p.z+z,lines,group);const circle=new THREE.Mesh(new THREE.RingGeometry(4.7,4.9,40),new THREE.MeshBasicMaterial({color:0xe5eee2,side:THREE.DoubleSide}));circle.rotation.x=-Math.PI/2;circle.position.set(p.x,.9,p.z);group.add(circle);for(const sign of [-1,1]){box(8,.15,.18,p.x,.9,p.z+sign*(p.d/2-7),lines,group);for(const dx of [-4,4])box(.18,.15,5,p.x+dx,.9,p.z+sign*(p.d/2-4.5),lines,group);box(5,2,.25,p.x,1.5,p.z+sign*(p.d/2-1),lines,group);}

 }else{
  const parts=p.parts||[[0,0]];
  for(const [dx,dz] of parts){const x=p.x+dx,z=p.z+dz;box(p.w+1,.7,p.d+1,x,.7,z,stone,group);box(p.w,p.h,p.d,x,p.h/2+1,z,wallMats[p.kind],group);box(p.w+1,.7,p.d+1,x,p.h+1.5,z,roof,group);box(p.w-2,.5,p.d-2,x,p.h+2,z,mat(0xb7c2b6),group);collectWindows(x,z,p.w,p.d,p.h);}
  if(p.parts){const xmin=p.x+parts[0][0],xmax=p.x+parts[parts.length-1][0];box(xmax-xmin+p.w,4,5,(xmin+xmax)/2,3,p.z-p.d/2+2.5,wallMats[p.kind],group);}
  if(p.id==='library'){box(14,3,12,p.x,p.h+3,p.z,stone,group);for(let i=0;i<5;i++)box(1.2,7,1.2,p.x-10+i*5,4,p.z+p.d/2+2,mat(0xf5f1df),group);box(27,1,5,p.x,8,p.z+p.d/2+2,stone,group);}
  if(p.id==='gym'){const cap=new THREE.Mesh(new THREE.CylinderGeometry(p.d/2,p.d/2,p.w,24,1,false,0,Math.PI),roof);cap.rotation.z=Math.PI/2;cap.position.set(p.x,p.h+.5,p.z);cap.scale.y=.18;group.add(cap);}
  if(p.kind==='health'){const red=mat(0xc4867e);box(6,1,.35,p.x,p.h-2,p.z+p.d/2+.3,red,group);box(1,6,.35,p.x,p.h-2,p.z+p.d/2+.31,red,group);}
 }
 const marker=document.createElement('button');marker.type='button';marker.className='map-place-label';marker.textContent=t(p.name);marker.addEventListener('click',()=>select(p.id));labelLayer.append(marker);labels.set(p.id,marker);
}
places.forEach(building);
const windows=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),mat(0x8da9ad,.45),windowTransforms.length);windowTransforms.forEach((m,i)=>windows.setMatrixAt(i,m));world.add(windows);
// Deterministic instanced trees: low draw-call vegetation around paths and boundaries.
let seed=721;const random=()=>{seed=(seed*1664580+1013904223)>>>0;return seed/4294967296;};const treePoints=[];
for(let i=0;i<450&&treePoints.length<150;i++){const x=-140+random()*275,z=-159+random()*318;const blocked=places.some(p=>Math.abs(z-p.z)<p.d/2+8&&Math.abs(x-p.x)<p.w/2+(p.parts?35:8));const onMain=Math.abs(x-(-9+(z+60)*.36))<13&&z>-60||Math.abs(x+9)<13&&z<=-60;const crossRoad=Math.abs(z+50)<10||Math.abs(z-147)<10;if(!blocked&&!onMain&&!crossRoad)treePoints.push([x,z,3.8+random()*2.8]);}
const trunks=new THREE.InstancedMesh(new THREE.CylinderGeometry(.36,.5,1,5),mat(0x9d9d78),treePoints.length),crowns=new THREE.InstancedMesh(new THREE.SphereGeometry(1,7,5),mat(0x91ae7b),treePoints.length);
const transform=new THREE.Object3D();treePoints.forEach(([x,z,h],i)=>{transform.position.set(x,h*.35,z);transform.scale.set(1,h*.7,1);transform.updateMatrix();trunks.setMatrixAt(i,transform.matrix);transform.position.y=h;transform.scale.set(h*.48,h*.65,h*.48);transform.updateMatrix();crowns.setMatrixAt(i,transform.matrix);crowns.setColorAt(i,new THREE.Color().setHSL(.23+random()*.04,.2,.48+random()*.13));});crowns.castShadow=true;world.add(trunks,crowns);
let selected=null,filter='all',query='',showLabels=true,routeMesh=null;
const ring=new THREE.Mesh(new THREE.RingGeometry(17,18,64),new THREE.MeshBasicMaterial({color:0xa0a3ca,side:THREE.DoubleSide,transparent:true,opacity:.85}));ring.rotation.x=-Math.PI/2;ring.position.y=.75;ring.visible=false;world.add(ring);
function visible(p){return(filter==='all'||p.kind===filter)&&(!query||[p.name,t(p.name),t(kinds[p.kind])].join(' ').toLowerCase().includes(query));}
function refreshList(){list.replaceChildren();for(const p of places.filter(visible)){const button=document.createElement('button');button.type='button';button.classList.toggle('active',p.id===selected);button.setAttribute('aria-pressed',String(p.id===selected));const title=document.createElement('span');title.textContent=t(p.name);const kind=document.createElement('small');kind.textContent=t(kinds[p.kind]);button.append(title,kind);button.addEventListener('click',()=>select(p.id));list.append(button);}if(!list.childElementCount){const empty=document.createElement('p');empty.textContent=t('没有匹配的建筑');empty.style.fontSize='12px';list.append(empty);}dirty=true;}
function action(label,url){const a=document.createElement('a');a.textContent=t(label)+' ↗';a.href=url;return a;}
function clearRoute(){if(routeMesh){world.remove(routeMesh);routeMesh.geometry.dispose();routeMesh.material.dispose();routeMesh=null;}document.getElementById('map-route-status').hidden=true;}
function showRoute(p){clearRoute();const coords=routeTo(p.node);if(coords.length<2)return;coords.push([p.x,p.z+p.d/2+3]);const curve=new THREE.CatmullRomCurve3(coords.map(([x,z])=>new THREE.Vector3(x,2,z)),false,'catmullrom',.05);routeMesh=new THREE.Mesh(new THREE.TubeGeometry(curve,100,.9,6,false),new THREE.MeshBasicMaterial({color:0x8a82bd}));world.add(routeMesh);const status=document.getElementById('map-route-status');status.textContent=t('南侧入口')+' → '+t(p.name)+' · '+t('示意路线');status.hidden=false;status.onclick=()=>{clearRoute();dirty=true;};dirty=true;}
function select(id){const p=places.find(p=>p.id===id);if(!p)return;if(selected===id&&(p.kind==='study'||p.kind==='sport')){interior.open(p);return;}selected=id;ring.position.set(p.x,.75,p.z);ring.scale.setScalar(Math.max(p.w,p.d)/30);ring.visible=true;labels.forEach((label,key)=>label.classList.toggle('selected',key===id));document.getElementById('map-detail-name').textContent=t(p.name);document.getElementById('map-detail-description').textContent=t(p.description);const count=document.getElementById('map-detail-count');count.textContent=p.kind==='study'?t('本系统已开放自习资源')+' · '+data.counts.study:p.kind==='sport'?t('本系统已开放运动资源')+' · '+Object.entries(data.counts).filter(([kind])=>kind!=='study').reduce((sum,[,count])=>sum+count,0):'';const controls=document.getElementById('map-detail-actions');controls.replaceChildren();if(p.kind==='study'||p.kind==='sport'){const enter=document.createElement('button');enter.type='button';enter.className='map-enter-building';enter.textContent=t(p.kind==='study'?'进入楼层选座':'进入场馆查看');enter.onclick=()=>interior.open(p);controls.append(enter);}const route=document.createElement('button');route.type='button';route.textContent=t('开始导航');route.addEventListener('click',()=>showRoute(p));controls.append(route,action(p.kind==='study'?'预约自习室':p.kind==='sport'?'预约运动场地':p.kind==='health'?'了解导诊服务':'校园跑腿',(data.urls[p.kind==='study'?'study':p.kind]+(p.kind==='study'?'&building='+encodeURIComponent(p.building):''))));if(p.kind==='study'||p.kind==='sport')controls.append(action('找校园伙伴',data.urls.social));aim.x=p.x*.4;aim.z=p.z*.4;desiredRadius=Math.min(desiredRadius,360);refreshList();dirty=true;}
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));refreshList();}));document.getElementById('map-search').addEventListener('input',e=>{query=e.target.value.trim().toLowerCase();refreshList();});
let theta=.56,phi=.79,radius=580,desiredTheta=theta,desiredPhi=phi,desiredRadius=radius,target=new THREE.Vector3(-9,0,0),aim=new THREE.Vector3(-9,0,0),dirty=true;
refreshList();
document.getElementById('map-reset').addEventListener('click',()=>{desiredTheta=.56;desiredPhi=.79;desiredRadius=580;aim.set(-9,0,0);clearRoute();dirty=true;});
document.getElementById('map-top').addEventListener('click',()=>{desiredTheta=0;desiredPhi=.05;desiredRadius=530;aim.set(-9,0,0);dirty=true;});
document.getElementById('map-label-toggle').addEventListener('click',e=>{showLabels=!showLabels;e.currentTarget.setAttribute('aria-pressed',String(showLabels));dirty=true;});
document.getElementById('map-zoom-in').addEventListener('click',()=>{desiredRadius=Math.max(155,desiredRadius*.83);dirty=true;});document.getElementById('map-zoom-out').addEventListener('click',()=>{desiredRadius=Math.min(720,desiredRadius*1.2);dirty=true;});
const pointers=new Map();let gestureMoved=false,startPoint=null,pinchDistance=0;
canvas.addEventListener('contextmenu',e=>e.preventDefault());canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);startPoint=[e.clientX,e.clientY];gestureMoved=false;if(pointers.size===2){const [a,b]=[...pointers.values()];pinchDistance=Math.hypot(a[0]-b[0],a[1]-b[1]);}});
canvas.addEventListener('pointermove',e=>{const previous=pointers.get(e.pointerId);if(!previous)return;const dx=e.clientX-previous[0],dy=e.clientY-previous[1];if(startPoint&&Math.hypot(e.clientX-startPoint[0],e.clientY-startPoint[1])>4)gestureMoved=true;pointers.set(e.pointerId,[e.clientX,e.clientY]);if(pointers.size===2){const [a,b]=[...pointers.values()],distance=Math.hypot(a[0]-b[0],a[1]-b[1]);if(distance>2&&pinchDistance>2)desiredRadius=THREE.MathUtils.clamp(desiredRadius*pinchDistance/distance,155,720);pinchDistance=distance;}else if(e.buttons===2||e.shiftKey){const speed=desiredRadius*.0015;aim.x=THREE.MathUtils.clamp(aim.x-dx*speed*Math.cos(theta)-dy*speed*Math.sin(theta),-130,130);aim.z=THREE.MathUtils.clamp(aim.z+dx*speed*Math.sin(theta)-dy*speed*Math.cos(theta),-150,150);}else{desiredTheta-=dx*.006;desiredPhi=THREE.MathUtils.clamp(desiredPhi+dy*.004,.05,1.25);}dirty=true;});
const raycaster=new THREE.Raycaster();canvas.addEventListener('pointerup',e=>{const hadMultiple=pointers.size>1;pointers.delete(e.pointerId);if(!gestureMoved&&!hadMultiple&&e.button===0&&renderer){const bounds=canvas.getBoundingClientRect();raycaster.setFromCamera(new THREE.Vector2((e.clientX-bounds.left)/bounds.width*2-1,-(e.clientY-bounds.top)/bounds.height*2+1),camera);const hits=raycaster.intersectObjects([...buildingGroups.values()],true);if(hits.length){let n=hits[0].object;while(n&&!n.userData.place)n=n.parent;if(n)select(n.userData.place.id);}}});canvas.addEventListener('pointercancel',e=>pointers.delete(e.pointerId));canvas.addEventListener('wheel',e=>{e.preventDefault();desiredRadius=THREE.MathUtils.clamp(desiredRadius*Math.exp(e.deltaY*.001),155,720);dirty=true;},{passive:false});
function theme(){const dark=document.documentElement.dataset.theme==='dark';scene.background=new THREE.Color(dark?0x193039:0xeaf0e0);scene.fog=new THREE.Fog(scene.background,750,1200);ambient.intensity=dark?1.55:2.2;sun.intensity=dark?1.7:3.3;dirty=true;}
new MutationObserver(theme).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});theme();
if(renderer){renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;const resize=()=>{const {width,height}=stage.getBoundingClientRect();renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();dirty=true;};const observer=new ResizeObserver(resize);observer.observe(stage);resize();loading.hidden=true;
 let last=0,alive=true;const projected=new THREE.Vector3();
 function frame(time){if(!alive)return;requestAnimationFrame(frame);if(time-last<32||document.hidden)return;last=time;const moving=Math.abs(theta-desiredTheta)+Math.abs(phi-desiredPhi)+Math.abs(radius-desiredRadius)+target.distanceTo(aim)>.01;if(!dirty&&!moving)return;theta=THREE.MathUtils.lerp(theta,desiredTheta,.13);phi=THREE.MathUtils.lerp(phi,desiredPhi,.13);radius=THREE.MathUtils.lerp(radius,desiredRadius,.13);target.lerp(aim,.13);const viewRadius=radius*Math.max(1,1.15/camera.aspect);camera.position.set(target.x+viewRadius*Math.sin(phi)*Math.sin(theta),target.y+viewRadius*Math.cos(phi),target.z+viewRadius*Math.sin(phi)*Math.cos(theta));camera.lookAt(target);camera.updateMatrixWorld();const width=canvas.clientWidth,height=canvas.clientHeight,occupied=[];const sorted=[...places].sort((a,b)=>(b.id===selected)-(a.id===selected));for(const p of sorted){const label=labels.get(p.id);projected.set(p.x,p.h+8,p.z).project(camera);const x=(projected.x*.5+.5)*width,y=(-projected.y*.5+.5)*height;const labelWidth=label.offsetWidth||85;const rect={l:x-labelWidth/2,r:x+labelWidth/2,t:y-24,b:y};const blocked=occupied.some(o=>rect.l<o.r+6&&rect.r>o.l-6&&rect.t<o.b+5&&rect.b>o.t-5);const shown=showLabels&&visible(p)&&projected.z<1&&x>30&&x<width-30&&y>45&&y<height-40&&(!blocked||p.id===selected);label.hidden=!shown;if(shown){label.style.left=x+'px';label.style.top=y+'px';occupied.push(rect);}}renderer.render(scene,camera);dirty=false;}
 requestAnimationFrame(frame);window.addEventListener('pagehide',()=>{alive=false;observer.disconnect();renderer.dispose();},{once:true});canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();loading.hidden=false;loading.textContent=t('3D 渲染暂不可用，仍可通过建筑列表访问服务。');});
}

const navigationQuery=new URLSearchParams(location.search),destination=places.find(p=>p.building===navigationQuery.get('area')||(p.id==='gym'&&navigationQuery.get('area')==='gym')||(p.id==='courts'&&navigationQuery.get('area')==='outdoor'));if(destination){select(destination.id);showRoute(destination);if(navigationQuery.has('seat'))interior.open(destination);}

document.getElementById('map-navigate').onclick=()=>{const p=places.find(p=>p.id===selected);if(p)showRoute(p);else{const status=document.getElementById('map-route-status');status.textContent=t('请先选择目的地建筑');status.hidden=false;status.onclick=()=>{status.hidden=true;};}};

// Record opening a rendered route, never claim physical arrival. Author: UniVerse Team.
if(destination&&data.plan_navigation){
 const token=document.querySelector('.plan-resume [name=csrfmiddlewaretoken]')?.value;
 if(token)fetch('/api/assistant/plans/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':token},body:JSON.stringify(data.plan_navigation)}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(result=>{const node=document.querySelector('.plan-resume small');if(node)node.textContent=result.plan.instruction;const heading=document.querySelector('.plan-resume strong');if(heading)heading.textContent=t('我的办事计划')+' · '+result.plan.progress+' / '+result.plan.total;}).catch(()=>{const node=document.querySelector('.plan-resume small');if(node)node.textContent=t('路线已打开，进度同步失败，请回到计划重试。');});
}
