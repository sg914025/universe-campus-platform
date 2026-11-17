/* Uses the supplied Stretch project meshes. This is not a Cubism moc3 loader. */
(async () => {
  const canvas = document.getElementById('anon-canvas');
  if (!canvas || !canvas.dataset.meshRig) return;
  const host = canvas.parentElement;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let app, timer, disposed = false;
  try {
    const response = await fetch(canvas.dataset.meshRig);
    if (!response.ok) throw new Error('Supplied mesh rig unavailable');
    const rig = await response.json();
    const texture = PIXI.Texture.from(new URL(rig.atlas, new URL(canvas.dataset.meshRig, location.href)).href);
    if (!texture.baseTexture.valid) await new Promise((resolve, reject) => {
      texture.baseTexture.once('loaded', resolve); texture.baseTexture.once('error', reject);
    });
    app = new PIXI.Application({view:canvas,backgroundAlpha:0,antialias:true,
      resolution:Math.min(devicePixelRatio || 1,2),autoDensity:true,autoStart:false});
    const actor = new PIXI.Container(); app.stage.addChild(actor);
    const groups = rig.nodes.filter(n => n.type === 'group');
    const bones = Object.fromEntries(groups.map(n => [n.boneRole,n]));
    const parts = rig.nodes.filter(n => n.type === 'part').sort((a,b) => a.draw_order-b.draw_order).map(n => {
      const vertices = new Float32Array(n.mesh.vertices.flatMap(p => [p.x,p.y]));
      const mesh = new PIXI.SimpleMesh(texture,vertices,new Float32Array(n.mesh.uvs),new Uint16Array(n.mesh.triangles.flat()));
      mesh.autoUpdate = true; mesh.interactive = false; actor.addChild(mesh);
      return {node:n,mesh,rest:vertices.slice()};
    });
    // Keep the supplied shoulder pivots and soft elbow weights: sleeves must
    // remain attached while the forearms move.
    const identity = () => [1,0,0,1,0,0];
    const multiply = (a,b) => [a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]];
    function local(t) {
      const angle=(t.rotation || 0)*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle);
      const a=c*(t.scaleX ?? 1),b=s*(t.scaleX ?? 1),d=c*(t.scaleY ?? 1),e=-s*(t.scaleY ?? 1);
      const px=t.pivotX || 0,py=t.pivotY || 0;
      return [a,b,e,d,(t.x || 0)+px-a*px-e*py,(t.y || 0)+py-b*px-d*py];
    }
    const fit = () => {
      // Embedded task panel includes dialogue below the canvas. Measure only
      // the canvas to avoid ResizeObserver growing it by the dialogue height.
      const width=host.clientWidth,height=host.dataset.assistant==='true'?canvas.clientHeight:host.clientHeight;
      app.renderer.resize(width,height);
      // The supplied artwork ends at the knees. Fit its actual painted area,
      // not the surrounding 1024px transparent document.
      actor.scale.set(Math.min(width/620,height/940)*0.96);
      actor.pivot.set(512,1024);actor.position.set(width/2,height);
    };
    const resize = new ResizeObserver(fit);resize.observe(host);fit();
    const moduleMotion={home:'bye01',forum:'smile01',errands:'kime01',guide:'thinking01',booking:'smile02'};
    let motion=moduleMotion[host.dataset.module] || 'bye01',motionAt=performance.now();
    let speaking=false,context,analyser,samples,mouth=0;
    let blinkAt=performance.now()+2600+Math.random()*1800;
    const audio=document.getElementById('mascot-audio');
    const actionNames={bye01:'greeting',smile01:'friendly',kime01:'encouraging',thinking01:'listening',smile02:'inviting'};
    function gesture(event) {
      motion=event.detail?.motion || moduleMotion[host.dataset.module] || 'bye01';
      motionAt=performance.now();canvas.dataset.action=actionNames[motion] || 'greeting';
    }
    host.addEventListener('mascot-gesture',gesture);
    document.getElementById('mascot-motion')?.addEventListener('change',event=>{
      if(event.target.value)gesture({detail:{motion:event.target.value}});
      event.target.value='';
    });
    host.addEventListener('mascot-speaking',async event => {
      speaking=Boolean(event.detail);
      if (!speaking) {mouth=0;return;}
      try {
        if (!context && audio) {
          context=new (window.AudioContext || window.webkitAudioContext)();
          analyser=context.createAnalyser();analyser.fftSize=256;
          context.createMediaElementSource(audio).connect(analyser);analyser.connect(context.destination);
          samples=new Uint8Array(analyser.fftSize);
        }
        if (context) await context.resume();
      } catch (_) { /* Fixed speech playback remains independent of the rig. */ }
    });
    const interpolate = (keys,time) => {
      let i=1;while(i<keys.length && keys[i].time<time)i++;
      if(i>=keys.length)return keys[keys.length-1].value;
      const a=keys[i-1],b=keys[i];let f=Math.max(0,(time-a.time)/(b.time-a.time || 1));
      if(a.easing!=='linear')f=f*f*(3-2*f);
      return a.value+(b.value-a.value)*f;
    };
    function frame() {
      if(disposed)return;
      const now=performance.now(),t=now/1000,elapsed=(now-motionAt)/1000;
      const moving=!reduced.matches && !host.classList.contains('is-collapsed');
      const envelope=moving && elapsed<3.8 ? Math.sin(Math.PI*Math.min(1,elapsed/3.8))**2 : 0;
      const pose=Object.fromEntries(groups.map(n => [n.id,{...n.transform}]));
      function add(role,property,value) {if(bones[role])pose[bones[role].id][property]=(pose[bones[role].id][property] || 0)+value;}
      if(moving) {
        const idle=rig.animations[0];
        for(const track of idle.tracks)if(pose[track.nodeId])pose[track.nodeId][track.property]=interpolate(track.keyframes,now%idle.duration);
        add('torso','scaleY',Math.sin(t*1.7)*0.0018);
        add('head','y',Math.sin(t*1.7)*0.7);
        if(motion==='bye01') {add('rightArm','rotation',5*envelope);add('rightElbow','rotation',(8+Math.sin(elapsed*8)*4)*envelope);add('head','rotation',-1.8*envelope);}
        if(motion==='smile01') {add('head','rotation',-2.5*envelope);add('leftArm','rotation',-4*envelope);add('rightArm','rotation',4*envelope);}
        if(motion==='kime01') {add('leftArm','rotation',-5*envelope);add('leftElbow','rotation',-6*envelope);add('head','y',Math.sin(elapsed*5)*1.8*envelope);}
        if(motion==='thinking01') {add('head','rotation',3.5*envelope);add('eyes','y',1.6*envelope);add('rightArm','rotation',3*envelope);}
        if(motion==='smile02') {add('leftArm','rotation',-5*envelope);add('leftElbow','rotation',-5*envelope);add('head','y',Math.sin(elapsed*4)*1.5*envelope);}
        if(speaking)add('head','rotation',Math.sin(t*3.1)*0.6);
      }
      const world=new Map();
      function resolve(node) {
        if(world.has(node.id))return world.get(node.id);
        const parent=groups.find(n => n.id===node.parent);
        const value=multiply(parent ? resolve(parent):identity(),local(pose[node.id]));world.set(node.id,value);return value;
      }
      groups.forEach(resolve);
      let openness=1;
      if(moving && now>=blinkAt) {
        const phase=(now-blinkAt)/180;
        if(phase>=1)blinkAt=now+2800+Math.random()*2600;
        else openness=Math.max(0.05,Math.abs(phase*2-1));
      }
      let volume=0;
      if(speaking && analyser) {
        analyser.getByteTimeDomainData(samples);
        volume=Math.sqrt(samples.reduce((sum,x)=>sum+((x-128)/128)**2,0)/samples.length);
      }
      const target=speaking ? Math.min(1,analyser && host.dataset.nativeSpeech!=='true' ? Math.max(0,(volume-0.012)*10):Math.abs(Math.sin(t*12))*0.65):0;
      mouth=mouth*0.45+target*0.55;
      for(const part of parts) {
        const n=part.node,name=n.name,vertices=part.mesh.vertices;
        const mat=world.get(n.parent) || identity();
        const joint=groups.find(g=>g.id===n.mesh.jointBoneId);
        const jointMatrix=joint ? local(pose[joint.id]):null;
        const eye=/eyewhite|irides|eyelash/.test(name);
        for(let i=0;i<vertices.length;i+=2) {
          let x=part.rest[i],y=part.rest[i+1];
          if(eye) {const cy=292;y=cy+(y-cy)*openness;}
          if(name==='mouth Old_Open')y=349+(y-349)*(0.3+mouth*0.7);
          if(moving && /hair/.test(name)) {
            const weight=Math.max(0,Math.min(1,(y-260)/600));
            x+=Math.sin(t*1.35+(name==='back hair'?0:0.7))*3.8*weight*weight;
          }
          if(jointMatrix) {
            const weight=n.mesh.boneWeights[i/2] || 0;
            const jx=jointMatrix[0]*x+jointMatrix[2]*y+jointMatrix[4],jy=jointMatrix[1]*x+jointMatrix[3]*y+jointMatrix[5];
            x+=(jx-x)*weight;y+=(jy-y)*weight;
          }
          vertices[i]=mat[0]*x+mat[2]*y+mat[4];vertices[i+1]=mat[1]*x+mat[3]*y+mat[5];
        }
        part.mesh.visible=n.visible!==false;
        part.mesh.alpha=n.opacity ?? 1;
        if(name==='mouth Old_Open')part.mesh.visible=mouth>0.07;
        if(name==='mouth Old_Closed')part.mesh.visible=mouth<=0.07;
        if(/irides|eyewhite/.test(name))part.mesh.alpha*=Math.min(1,openness*2);
      }
      canvas.dataset.action=envelope>0.03 ? actionNames[motion] || 'greeting' : speaking ? 'speaking':'idle';
      canvas.dataset.speaking=String(speaking);canvas.dataset.mouth=mouth.toFixed(2);
      canvas.dataset.motionPhase=envelope>0.8?'peak':envelope>0.03?'transition':'idle';
      app.renderer.render(app.stage);
    }
    function playback() {
      clearInterval(timer);
      const paused=document.hidden || host.classList.contains('is-collapsed');
      canvas.dataset.playback=paused?'paused':reduced.matches?'reduced-motion':'playing';
      if(!paused) {frame();timer=setInterval(frame,reduced.matches?100:1000/30);}
    }
    document.addEventListener('visibilitychange',playback);
    reduced.addEventListener('change',playback);
    new MutationObserver(playback).observe(host,{attributes:true,attributeFilter:['class']});
    window.addEventListener('pagehide',()=>clearInterval(timer));window.addEventListener('pageshow',playback);
    canvas.dataset.ready='true';canvas.dataset.renderer='supplied-stretch-mesh';playback();
  } catch(error) {
    disposed=true;clearInterval(timer);canvas.hidden=true;
    if(app)app.destroy(false);
    console.error('Supplied campus model failed to load:',error);
  }
})();
