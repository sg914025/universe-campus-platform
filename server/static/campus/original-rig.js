/* Original layered illustration rig; not a Cubism .moc/.moc3 model. */
(async () => {
  const canvas = document.getElementById('anon-canvas');
  if (!canvas) return;
  const host = canvas.parentElement;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let app, timer;
  try {
    const response = await fetch(canvas.dataset.rig);
    if (!response.ok) throw new Error('Character rig unavailable');
    const rig = await response.json();
    const texture = PIXI.BaseTexture.from(new URL(rig.atlas, new URL(canvas.dataset.rig, location.href)).href);
    if (!texture.valid) await new Promise((resolve, reject) => {
      texture.once('loaded', resolve); texture.once('error', reject);
    });
    app = new PIXI.Application({view:canvas, backgroundAlpha:0, antialias:true,
      resolution:Math.min(devicePixelRatio || 1,2), autoDensity:true, autoStart:false});
    const actor = new PIXI.Container(); app.stage.addChild(actor);
    const head = new PIXI.Container(); head.position.set(...rig.headPivot);
    const sprites = {};
    for (const part of rig.parts) {
      const [x,y,w,h] = part.frame;
      const sprite = new PIXI.Sprite(new PIXI.Texture(texture, new PIXI.Rectangle(x,y,w,h)));
      sprite.anchor.set(...(part.anchor || [0.5,0]));
      sprite.position.set(part.x,part.y); sprite.width=part.width; sprite.height=part.height;
      sprite.visible=part.visible !== false;
      (part.parent === 'head' ? head : actor).addChild(sprite);
      sprites[part.id]=sprite;
    }
    actor.addChild(head);
    const fit = () => {
      app.renderer.resize(host.clientWidth,host.clientHeight);
      const scale = Math.min(host.clientWidth/600,host.clientHeight/rig.height)*0.88;
      actor.scale.set(scale); actor.pivot.set(300,rig.anchorY || 900);
      actor.position.set(host.clientWidth/2,host.clientHeight);
    };
    new ResizeObserver(fit).observe(host); fit();
    let speaking=false, analyser, context, samples, gesture='bye01', gestureAt=performance.now();
    let lastBlink=performance.now(), nextBlink=2800;
    const audio=document.getElementById('mascot-audio');
    host.addEventListener('mascot-gesture',e=>{gesture=e.detail.motion;gestureAt=performance.now();});
    host.addEventListener('mascot-speaking',async e=>{
      speaking=e.detail;
      if (speaking && audio) {
        try {
          if (!context) {
            context=new (window.AudioContext || window.webkitAudioContext)();
            analyser=context.createAnalyser();analyser.fftSize=256;
            context.createMediaElementSource(audio).connect(analyser);analyser.connect(context.destination);
            samples=new Uint8Array(analyser.fftSize);
          }
          await context.resume();
        } catch (_) { /* Playback remains available when analysis is unsupported. */ }
      }
    });
    function frame() {
      const now=performance.now(),t=now/1000,elapsed=(now-gestureAt)/1000;
      const moving=!reduced.matches && !host.classList.contains('is-collapsed');
      const active=moving && elapsed<3.2;
      const wave=active && ['bye01','kime01'].includes(gesture);
      const thinking=active && gesture==='thinking01';
      head.rotation=moving ? Math.sin(t*1.25)*0.025+(thinking ? 0.06:0) : 0;
      head.y=rig.headPivot[1]+(moving ? Math.sin(t*1.8)*2:0);
      sprites.body.scale.y=rig.parts.find(p=>p.id==='body').height/sprites.body.texture.height*(1+(moving ? Math.sin(t*1.8)*0.004:0));
      sprites.arm_left.rotation=moving ? Math.sin(t*1.25)*0.025:0;
      const raised=wave || host.dataset.module === 'home';
      sprites.arm_right.visible=!raised; sprites.arm_wave.visible=raised;
      sprites.arm_wave.rotation=wave ? Math.sin(elapsed*8)*0.08:0;
      sprites.back_hair.rotation=moving ? Math.sin(t*1.1)*0.008:0;
      for (const id of ['hair_left','hair_right']) {
        sprites[id].rotation=moving ? Math.sin(t*1.4+(id==='hair_left' ? 0:0.6))*0.025:0;
      }
      let blink=false;
      if (moving) {
        if (now-lastBlink>nextBlink+160) {lastBlink=now;nextBlink=2600+Math.random()*2300;}
        blink=now-lastBlink>nextBlink;
      }
      sprites.eye_left.visible=sprites.eye_right.visible=!blink;
      sprites.eye_closed_left.visible=sprites.eye_closed_right.visible=blink;
      let level=0;
      if (speaking && analyser) {
        analyser.getByteTimeDomainData(samples);
        level=Math.sqrt(samples.reduce((s,n)=>s+((n-128)/128)**2,0)/samples.length);
      }
      const opening=speaking ? (analyser ? level : Math.abs(Math.sin(t*10))*0.07) : 0;
      sprites.mouth_closed.visible=opening<0.025;
      sprites.mouth_small.visible=opening>=0.025 && opening<0.09;
      sprites.mouth_open.visible=opening>=0.09;
      app.renderer.render(app.stage);
    }
    function playback() {
      clearInterval(timer);
      canvas.dataset.playback=document.hidden ? 'hidden' : reduced.matches ? 'reduced-motion' : 'playing';
      frame();
      if (!document.hidden) timer=setInterval(frame,reduced.matches ? 100:1000/30);
    }
    document.addEventListener('visibilitychange',playback);
    reduced.addEventListener('change',playback);
    window.addEventListener('pagehide',()=>clearInterval(timer));
    window.addEventListener('pageshow',playback);
    canvas.dataset.ready='true';canvas.dataset.renderer='original-layered-rig'; playback();
  } catch (error) {
    canvas.hidden=true;
    if (app) app.destroy(false);
    console.error('Original campus character failed to load:',error);
  }
})();
