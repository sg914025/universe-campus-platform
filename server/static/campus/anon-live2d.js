/* Local Live2D display only: no chat, clicks, account or medical data. */
(async function () {
  const canvas = document.getElementById('anon-canvas');
  if (!canvas) return;
  const host = canvas.parentElement;
  let app;
  try {
    app = new PIXI.Application({view: canvas, backgroundAlpha: 0, antialias: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2), autoDensity: true,
      width: host.clientWidth, height: host.clientHeight, autoStart: false});
    app.ticker.maxFPS = 30;
    const model = await PIXI.live2d.Live2DModel.from(canvas.dataset.model, {
      autoInteract: false, autoUpdate: false, idleMotionGroup: 'idle01', motionPreload: 'IDLE'
    });
    model.interactive = false;
    model.anchor.set(0.5, 1);
    app.stage.addChild(model);

    const fit = () => {
      const width = host.clientWidth, height = host.clientHeight;
      app.renderer.resize(width, height);
      model.scale.set(Math.min(width / model.internalModel.width,
        height / model.internalModel.height) * 0.98);
      model.position.set(width / 2, height);
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(host);
    await model.expression('default');
    await model.motion('idle01', 0);
    canvas.dataset.ready = 'true';
    let speaking = false;
    let analyser, context, samples;
    const audio = document.getElementById('mascot-audio');
    host.addEventListener('mascot-gesture', event => {
      if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        model.motion(event.detail.motion, 0, 3);
        model.expression(event.detail.motion === 'thinking01' ? 'thinking01' : 'smile01');
      }
    });
    host.addEventListener('mascot-speaking', async event => {
      speaking = event.detail;
      if (speaking && audio) {
        try {
          if (!context) {
            context = new (window.AudioContext || window.webkitAudioContext)();
            analyser = context.createAnalyser(); analyser.fftSize = 256;
            context.createMediaElementSource(audio).connect(analyser);
            analyser.connect(context.destination); samples = new Uint8Array(analyser.fftSize);
          }
          await context.resume();
        } catch (_) { /* Audio still plays if mouth analysis is unavailable. */ }
      }
      if (!speaking) model.expression('default');
    });
    model.internalModel.on('beforeModelUpdate', () => {
      if (!speaking || !analyser) return;
      analyser.getByteTimeDomainData(samples);
      const level = Math.sqrt(samples.reduce((sum, n) => sum + ((n - 128) / 128) ** 2, 0) / samples.length);
      model.internalModel.coreModel.setParamFloat('PARAM_MOUTH_OPEN_Y', Math.min(1, level * 7));
    });
    if (host.dataset.module) model.motion(host.dataset.module === 'guide' ? 'thinking01' : 'bye01', 0, 3);
    let timer = null;
    let previousTime = performance.now();
    const stop = () => { clearInterval(timer); timer = null; };
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updatePlayback = () => {
      if (document.hidden || reducedMotion.matches) {
        canvas.dataset.playback = reducedMotion.matches ? 'reduced-motion' : 'hidden';
        stop();
        app.renderer.render(app.stage);
      } else { canvas.dataset.playback = 'playing';
        if (timer === null) {
          previousTime = performance.now();
          timer = setInterval(() => {
            const now = performance.now();
            model.update(Math.min(now - previousTime, 100));
            previousTime = now;
            app.renderer.render(app.stage);
          }, 1000 / 30);
        } }
    };
    document.addEventListener('visibilitychange', updatePlayback);
    reducedMotion.addEventListener('change', updatePlayback);
    updatePlayback();
    window.addEventListener('pagehide', stop);
    window.addEventListener('pageshow', updatePlayback);
  } catch (error) {
    host.hidden = true;
    if (app) app.destroy(false);
    console.error('Campus Live2D model could not load:', error);
  }
})();
