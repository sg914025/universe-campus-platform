import * as THREE from './vendor/three.module.js';

// A small procedural 3D chibi, inspired by the requested pink-haired character.
// No sprite sheet, user input, remote service or account data is used here.
const canvas=document.getElementById('anon-canvas');
if(canvas){
  let renderer;
  try{renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'low-power'});}catch(error){canvas.parentElement.hidden=true;console.warn('3D mascot unavailable:',error.message);}
  if(renderer){
    renderer.setClearColor(0x000000,0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
    renderer.outputColorSpace=THREE.SRGBColorSpace;
    const scene=new THREE.Scene();
    const camera=new THREE.OrthographicCamera(-.95,.95,2.92,-.08,.1,20);
    camera.position.set(0,1.4,7);camera.lookAt(0,1.4,0);
    const ambient=new THREE.HemisphereLight(0xfff8f0,0x9890a7,2.1);scene.add(ambient);
    const key=new THREE.DirectionalLight(0xffffff,2.4);key.position.set(-3,5,6);scene.add(key);
    const rim=new THREE.DirectionalLight(0xffe0ef,.7);rim.position.set(3,2,-3);scene.add(rim);
    const toon=color=>new THREE.MeshToonMaterial({color});
    const mat={skin:toon('#ffe3d2'),hair:toon('#f2a5bf'),hairDark:toon('#d887a3'),coat:toon('#87929f'),skirt:toon('#303952'),sock:toon('#30384d'),shoe:toon('#694e4a'),white:toon('#fff9f0'),blue:toon('#8cb7e1'),black:new THREE.MeshBasicMaterial({color:'#39374a'}),iris:new THREE.MeshBasicMaterial({color:'#628fba'}),shine:new THREE.MeshBasicMaterial({color:'#ffffff'})};
    const model=new THREE.Group();scene.add(model);
    function mesh(geometry,material,parent,x=0,y=0,z=0){const part=new THREE.Mesh(geometry,material);part.position.set(x,y,z);parent.add(part);return part;}
    function oval(parent,material,x,y,z,sx,sy,sz){const part=mesh(new THREE.SphereGeometry(1,28,20),material,parent,x,y,z);part.scale.set(sx,sy,sz);return part;}
    function triangle(parent,material,vertices,z){const shape=new THREE.Shape();shape.moveTo(vertices[0][0],vertices[0][1]);vertices.slice(1).forEach(p=>shape.lineTo(...p));shape.closePath();return mesh(new THREE.ExtrudeGeometry(shape,{depth:.025,bevelEnabled:true,bevelSize:.006,bevelThickness:.006,bevelSegments:2,steps:1}),material,parent,0,0,z);}
    // Torso, pleated skirt, socks and shoes.
    oval(model,mat.coat,0,1.46,0,.29,.35,.19);
    oval(model,mat.white,0,1.51,.173,.12,.28,.045);
    triangle(model,mat.coat,[[-.28,1.76],[-.10,1.53],[-.07,1.10],[-.30,1.20]],.19);
    triangle(model,mat.coat,[[.28,1.76],[.10,1.53],[.07,1.10],[.30,1.20]],.19);
    triangle(model,mat.white,[[-.16,1.82],[-.04,1.72],[-.09,1.56]],.225);
    triangle(model,mat.white,[[.16,1.82],[.04,1.72],[.09,1.56]],.225);
    triangle(model,mat.blue,[[-.14,1.64],[0,1.60],[-.13,1.51]],.27);
    triangle(model,mat.blue,[[.14,1.64],[0,1.60],[.13,1.51]],.27);
    oval(model,mat.blue,0,1.59,.305,.038,.044,.025);
    for(const y of [1.40,1.27])oval(model,mat.white,.025,y,.236,.018,.018,.012);
    mesh(new THREE.CylinderGeometry(.245,.38,.39,12),mat.skirt,model,0,1.02,0);
    for(let i=0;i<12;i++){const a=i*Math.PI/6;const stripe=mesh(new THREE.BoxGeometry(.014,.30,.025),mat.coat,model,Math.sin(a)*.315,.99,Math.cos(a)*.315);stripe.rotation.y=a;}
    for(const x of [-.14,.14]){
      oval(model,mat.skin,x,.72,0,.085,.16,.085);
      mesh(new THREE.CylinderGeometry(.081,.075,.36,16),mat.sock,model,x,.43,0);
      oval(model,mat.shoe,x,.14,.066,.112,.115,.19);
      oval(model,mat.black,x,.071,.064,.113,.024,.19);
    }
    const arms=[];
    for(const side of [-1,1]){
      const arm=new THREE.Group();arm.position.set(side*.30,1.69,0);model.add(arm);
      oval(arm,mat.coat,0,-.17,0,.10,.24,.105);
      oval(arm,mat.white,0,-.365,.008,.089,.035,.088);
      oval(arm,mat.skin,0,-.43,.013,.082,.095,.072);
      oval(arm,mat.skin,-side*.062,-.40,.047,.036,.045,.033);
      arm.rotation.z=side*.17;arms.push(arm);
    }
    mesh(new THREE.CylinderGeometry(.085,.09,.15,16),mat.skin,model,0,1.84,0);
    const head=new THREE.Group();head.position.set(0,2.25,0);model.add(head);
    oval(head,mat.hairDark,0,.02,-.16,.60,.59,.45);
    oval(head,mat.skin,0,-.025,.055,.535,.50,.455);
    for(const x of [-.52,.52])oval(head,mat.skin,x,-.04,.035,.075,.105,.064);
    const cap=mesh(new THREE.SphereGeometry(1,32,24,0,Math.PI*2,0,Math.PI*.53),mat.hair,head,0,.02,-.02);cap.scale.set(.59,.58,.50);
    function lock(parent,x,y,length,width,z,tilt=0){
      const s=new THREE.Shape();s.moveTo(-width*.48,0);s.quadraticCurveTo(-width*.8,-length*.40,-width*.45,-length*.76);s.quadraticCurveTo(-width*.15,-length*.98,width*.16,-length);s.quadraticCurveTo(width*.70,-length*.60,width*.46,-length*.24);s.quadraticCurveTo(width*.34,-length*.02,-width*.48,0);
      const p=mesh(new THREE.ExtrudeGeometry(s,{depth:.07,bevelEnabled:true,bevelSegments:3,steps:1,bevelSize:.025,bevelThickness:.025,curveSegments:16}),mat.hair,parent,x,y,z);p.rotation.z=tilt;return p;
    }
    const hair=[];
    // Layered bangs and softly curved side locks, not a flat character image.
    for(const [x,y,len,w,z,tilt] of [[-.35,.41,.42,.21,.35,-.24],[-.16,.51,.45,.23,.41,-.10],[.04,.52,.44,.24,.43,.13],[.25,.46,.42,.23,.38,.28]])lock(head,x,y,len,w,z,tilt);
    for(const side of [-1,1]){
      hair.push(lock(head,side*.48,.20,1.05,.21,-.12,-side*.11));
      hair.push(lock(head,side*.56,.09,.96,.19,-.22,side*.10));
      lock(head,side*.49,.31,.69,.14,.16,-side*.07);
    }
    const eyes=[];
    for(const x of [-.205,.205]){
      const eye=new THREE.Group();eye.position.set(x,-.085,.461);head.add(eye);
      oval(eye,mat.black,0,.006,0,.137,.164,.018);
      oval(eye,mat.white,0,-.006,.014,.125,.149,.014);
      oval(eye,mat.iris,0,-.012,.028,.084,.124,.012);
      oval(eye,mat.black,0,-.008,.038,.042,.084,.009);
      oval(eye,mat.shine,-.025,.045,.05,.032,.040,.005);
      oval(eye,mat.shine,.032,-.057,.05,.014,.016,.005);
      eyes.push(eye);
      const cheek=new THREE.MeshBasicMaterial({color:'#edacb8',transparent:true,opacity:.45});oval(head,cheek,x*1.50,-.23,.43,.080,.023,.008);
    }
    const smile=new THREE.QuadraticBezierCurve3(new THREE.Vector3(-.055,-.265,.503),new THREE.Vector3(0,-.307,.515),new THREE.Vector3(.055,-.265,.503));
    mesh(new THREE.TubeGeometry(smile,18,.008,6,false),new THREE.MeshBasicMaterial({color:'#b8757b'}),head);
    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
    let frame=0,last=0,visible=true;
    function resize(){const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;renderer.setSize(rect.width,rect.height,false);const halfHeight=1.5;camera.left=-halfHeight*rect.width/rect.height;camera.right=halfHeight*rect.width/rect.height;camera.top=halfHeight;camera.bottom=-halfHeight;camera.updateProjectionMatrix();}
    const observer=new ResizeObserver(resize);observer.observe(canvas);resize();
    function draw(time){frame=requestAnimationFrame(draw);if(!visible||time-last<33)return;last=time;const t=time/1000;
      model.rotation.y=reduced.matches?-.07:Math.sin(t*.65)*.09;
      model.rotation.z=reduced.matches?0:Math.sin(t*1.2)*.018;
      model.position.y=reduced.matches?0:Math.sin(t*1.6)*.012;
      head.rotation.z=reduced.matches?0:Math.sin(t*.8)*.025;
      const blink=t%4.7;eyes.forEach(eye=>eye.scale.y=!reduced.matches&&blink>.08&&blink<.22?.08:1);
      const wave=t%9;arms[0].rotation.z=!reduced.matches&&wave>5&&wave<7?-1.95+Math.sin(t*10)*.15:-.17;
      hair.forEach((strand,i)=>strand.rotation.y=reduced.matches?0:Math.sin(t*1.2+i)*.03);
      renderer.render(scene,camera);
    }
    const visibility=()=>{visible=!document.hidden;};document.addEventListener('visibilitychange',visibility);
    canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();cancelAnimationFrame(frame);});
    canvas.addEventListener('webglcontextrestored',()=>{resize();frame=requestAnimationFrame(draw);});
    window.addEventListener('pagehide',()=>cancelAnimationFrame(frame));
    window.addEventListener('pageshow',()=>{cancelAnimationFrame(frame);resize();frame=requestAnimationFrame(draw);});
    frame=requestAnimationFrame(draw);
  }
}
