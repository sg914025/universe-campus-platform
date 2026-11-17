/* Fixed greetings only. No user/profile/medical text is sent to speech services. */
(async () => {
  const script = document.querySelector('script[data-lines]');
  const host = document.querySelector('.home-mascot[data-module]');
  if (!host || !script) return;
  const line = document.getElementById('mascot-line');
  const audio = document.getElementById('mascot-audio');
  const status = document.getElementById('mascot-voice-status');
  const speakButton = document.getElementById('mascot-speak');
  const language = document.getElementById('mascot-language');
  const auto = document.getElementById('mascot-auto');
  auto.checked = localStorage.getItem('campus-mascot-auto') === 'yes';
  const module = host.dataset.module;
  let lines, key, index = 0, generation = 0, journey = null;
  const journeySteps={
    chat:{key:'home_plan',motion:'thinking01',url:'#assistant-work'},
    language:{key:'home_plan',motion:'bye01',url:'#journey-language'},
    friends:{key:'forum_hello',motion:'smile01',url:'/forum/friends/'},
    help:{key:'errands_hello',motion:'kime01',url:'/errands/new/'},
    booking:{key:'booking_hello',motion:'smile02',url:'/booking/'},
    health:{key:'guide_hello',motion:'thinking01',url:'/guide/'}
  };
  window.addEventListener('campus-journey-step',event=>{
    if(!document.getElementById('mascot-guide-link')||!journeySteps[event.detail?.step])return;
    journey={...journeySteps[event.detail.step],instruction:event.detail.instruction,action:event.detail.action};index=0;
    if(host.dataset.assistant==='true')journey.url=event.detail.plan?'#service-plan-panel':event.detail.completed?'/my-services/':'#assistant-work';
    if(lines)show();
  });
  const hour = new Date().getHours();
  const period = hour < 5 || hour >= 23 ? 'night' : hour < 11 ? 'morning' : hour < 14 ? 'noon' : hour < 18 ? 'afternoon' : 'evening';
  let keys = module === 'home' ? ['home_' + period, 'home_plan'] : [module + '_hello', module + '_extra'];
  const gestures = {home:'bye01', forum:'smile01', errands:'kime01', guide:'thinking01', booking:'smile02'};
  function gesture(speaking = false) {
    const variants={home:['bye01','smile02'],forum:['smile01','smile02'],errands:['kime01','smile01'],guide:['thinking01'],booking:['smile02','smile01']};
    const motions=variants[module]||[gestures[module]||'smile01'];
    host.dispatchEvent(new CustomEvent('mascot-gesture', {detail:{motion:journey?.motion || motions[index%motions.length],speaking}}));
  }
  function stop() {host.dataset.nativeSpeech='false';if(window.universeSpeech?.owner==='mascot')window.universeSpeech.stop();
    generation++; audio.pause(); audio.currentTime = 0;
    speakButton.textContent = window.campusI18n.text("听她说"); host.classList.remove('is-speaking');
    host.dispatchEvent(new CustomEvent('mascot-speaking', {detail:false}));
  }
  function show() {
    stop(); key = journey && index===0 ? journey.key : keys[index % keys.length];
    line.textContent = lines[key]?.[language.value] || lines[key]?.zh || window.campusI18n.text("今天也一起加油吧！");
    status.textContent = ''; gesture();
    if(journey){
      const instruction=document.getElementById('mascot-guide-instruction');
      instruction.textContent=journey.instruction;instruction.hidden=false;
      const link=document.getElementById('mascot-guide-link');link.textContent=journey.action+' ↗';link.href=journey.url;link.hidden=false;
    }
  }
  try {
    const response = await fetch(script.dataset.lines);
    if (!response.ok) throw new Error('lines unavailable');
    lines = await response.json();
    keys=(module==='home'?['home_'+period,'home_'+period+'_extra','home_plan','home_plan_extra']:Object.keys(lines).filter(name=>name.startsWith(module+'_'))).filter(name=>lines[name]);
    if(!keys.length)throw new Error('no greetings for this module');
    // Only time-appropriate greetings enter the home pool. Other modules vary on entry.
    index=module==='home'?Math.floor(Math.random()*Math.min(2,keys.length)):Math.floor(Math.random()*keys.length);
    const saved = localStorage.getItem('campus-mascot-language');
    const pageLanguage=document.documentElement.lang.split('-')[0];
    const lastInterface=localStorage.getItem('campus-mascot-ui-language');
    if (['zh','en','ja','ru'].includes(pageLanguage) && lastInterface!==pageLanguage) {
      language.value=pageLanguage;localStorage.setItem('campus-mascot-language',pageLanguage);
    } else if (['zh','en','ja','ru'].includes(saved)) language.value=saved;
    localStorage.setItem('campus-mascot-ui-language',pageLanguage);
    show();
  } catch (_) {status.textContent = window.campusI18n.text("问候暂时加载不了，稍后再试。"); return;}
  document.getElementById('mascot-next').addEventListener('click', () => {index++; show();});
  language.addEventListener('change', () => {localStorage.setItem('campus-mascot-language', language.value); show();});
  async function play() {
    if (!audio.paused || window.universeSpeech?.owner==='mascot') {stop(); return;}
    const current = ++generation;
    status.textContent = window.campusI18n.text("正在准备语音…");
    try {
      window.universeSpeech?.stop();window.dispatchEvent(new CustomEvent('universe-audio-owner',{detail:{owner:'recording'}}));audio.volume=language.value==='ru'?.78:.9;audio.playbackRate=1;
      const url = script.dataset.voice + language.value + '/' + key + '.wav';
      const response = await fetch(url);
      if (!response.ok) throw new Error('voice unavailable');
      const blob = await response.blob();
      if (current !== generation) return;
      if (audio.dataset.objectUrl) URL.revokeObjectURL(audio.dataset.objectUrl);
      audio.src = URL.createObjectURL(blob); audio.dataset.objectUrl = audio.src;
      await audio.play();
      if (current !== generation) return;
      speakButton.textContent = window.campusI18n.text("停止"); status.textContent = window.campusI18n.text("AI 合成语音");
      host.classList.add('is-speaking'); gesture(true);
      host.dispatchEvent(new CustomEvent('mascot-speaking', {detail:true}));
    } catch (error) {if (current === generation) status.textContent = error.name === 'NotAllowedError' ? window.campusI18n.text("点一下“听她说”，就能播放语音啦。") : window.campusI18n.text("语音暂时没能播放，请再试一次。");}
  }
  window.addEventListener('universe-audio-owner',event=>{if(event.detail?.owner!=='mascot'&&event.detail?.owner!=='recording'){generation++;audio.pause();speakButton.textContent=window.campusI18n.text('听她说');host.classList.remove('is-speaking');host.dispatchEvent(new CustomEvent('mascot-speaking',{detail:false}));}});
  speakButton.addEventListener('click', play);
  auto.addEventListener('change', () => {localStorage.setItem('campus-mascot-auto',auto.checked ? 'yes' : 'no'); if (auto.checked) play(); else stop();});
  if (document.querySelector('.journey-card')){host.classList.add('is-collapsed');host.querySelector('.mascot-restore').hidden=false;}else if (auto.checked) play();
  audio.addEventListener('ended', stop);
  audio.addEventListener('error', () => {stop(); status.textContent = window.campusI18n.text("语音播放失败，请再试一次。");});
  document.getElementById('mascot-hide').addEventListener('click', () => {stop();host.classList.add('is-collapsed');host.querySelector('.mascot-restore').hidden=false;});
  host.querySelector('.mascot-restore').addEventListener('click', () => {host.classList.remove('is-collapsed');host.querySelector('.mascot-restore').hidden=true;gesture();});
  document.addEventListener('visibilitychange', () => {if (document.hidden) stop();});
  window.addEventListener('pagehide', stop);
})();
