/* Device appearance, local-clock illustration and opt-in browser voice tools. */
(() => {
  const language=(document.documentElement.lang||'zh').slice(0,2);
  const lang=['zh','en','ru','ja'].includes(language)?language:'zh';
  const words={
    dark:['深色模式','Dark mode','Тёмная тема','ダークモード'],light:['浅色模式','Light mode','Светлая тема','ライトモード'],
    moon:['愿你今晚也有好梦','Wishing you a peaceful night','Спокойной ночи и добрых снов','今夜もいい夢を'],
    sun:['愿你今天也有好心情','Have a lovely day','Хорошего настроения сегодня','今日も素敵な一日を'],
    start:['语音输入','Voice input','Голосовой ввод','音声入力'],stop:['结束录音','Stop listening','Завершить запись','録音を終了'],
    listen:['正在聆听，结束后可修改文字再发送。','Listening. Review the transcript before sending.','Слушаю. Проверьте текст перед отправкой.','聞き取り中です。送信前に内容を確認できます。'],
    denied:['无法使用麦克风，请检查浏览器权限。','Microphone unavailable. Check browser permissions.','Микрофон недоступен. Проверьте разрешения браузера.','マイクを利用できません。ブラウザーの権限を確認してください。'],
    fail:['未识别到语音或识别服务不可用，请重试或输入文字。','No speech detected or recognition unavailable. Retry or type.','Речь не распознана или служба недоступна. Повторите или введите текст.','音声を認識できませんでした。再試行するか文字で入力してください。'],
    unsupported:['当前浏览器不支持语音识别，可使用 Edge 或 Chrome，文字输入仍可用。','Speech recognition is unavailable. Try Edge or Chrome, or type.','Распознавание недоступно. Используйте Edge или Chrome либо вводите текст.','音声認識は利用できません。Edge、Chrome、または文字入力をご利用ください。'],
    auto:['自动朗读 AI 回复','Read AI replies aloud','Озвучивать ответы ИИ','AIの返信を読み上げる'],
    read:['朗读最新回复','Read latest reply','Озвучить последний ответ','最新の返信を読む'],
    quiet:['停止朗读','Stop speaking','Остановить озвучивание','読み上げを停止'],
    privacy:['调用设备麦克风与系统语音；识别可能使用浏览器厂商的在线服务。录音不上传本项目，识别文字由你确认后发送。','Uses your microphone and system voices. Recognition may use the browser vendor’s online service. This app receives text only after you send it.','Использует микрофон и системные голоса. Распознавание может обращаться к онлайн-службе браузера. Проект получает только отправленный вами текст.','マイクとシステム音声を使用します。認識にブラウザー提供元のオンラインサービスを使う場合があります。本アプリには送信した文字だけが渡されます。'],
    noVoice:['设备暂未提供该语言的朗读语音。','No system voice is available for this language.','На устройстве нет голоса для этого языка.','この言語のシステム音声がありません。'],
    empty:['暂时没有可朗读的回复。','No reply to read yet.','Пока нет ответа для озвучивания.','読み上げる返信がありません。'],
    ready:['识别结束，请检查文字后发送。','Finished. Review the text before sending.','Готово. Проверьте текст перед отправкой.','認識が完了しました。内容を確認して送信してください。']
  };
  const t=k=>words[k][['zh','en','ru','ja'].indexOf(lang)];
  const make=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text||'';if(cls)n.className=cls;return n;};
  const themeButton=make('button','','uv-theme-toggle');themeButton.type='button';
  const themeTarget=document.querySelector('.account,.header-tools,.manage-tools,.auth-language,.top-tools,.manage-header nav,.run-header nav,.resource-nav')||document.querySelector('.manage-header,header nav');
  if(themeTarget)themeTarget.append(themeButton);else{themeButton.classList.add('uv-theme-floating');document.body.append(themeButton);}
  function themeLabel(){const dark=document.documentElement.dataset.theme==='dark';themeButton.textContent=(dark?'☀ ':'☾ ')+t(dark?'light':'dark');themeButton.setAttribute('aria-pressed',String(dark));document.querySelector('meta[name="theme-color"]')?.setAttribute('content',dark?'#101e28':'#153641');}
  themeButton.addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=next;try{localStorage.setItem('universe-theme',next);}catch(_){}themeLabel();});
  const systemTheme=matchMedia('(prefers-color-scheme: dark)');systemTheme.addEventListener('change',e=>{try{if(localStorage.getItem('universe-theme'))return;}catch(_){}document.documentElement.dataset.theme=e.matches?'dark':'light';themeLabel();});
  window.addEventListener('storage',e=>{if(e.key==='universe-theme'){document.documentElement.dataset.theme=e.newValue==='dark'?'dark':e.newValue==='light'?'light':systemTheme.matches?'dark':'light';themeLabel();}});themeLabel();
  const corner=document.querySelector('.sun-corner');
  if(corner){
    const ns='http://www.w3.org/2000/svg',moon=document.createElementNS(ns,'svg');moon.setAttribute('viewBox','0 0 180 180');moon.classList.add('uv-moon');
    const shapes=[['path',{d:'M113 29A61 61 0 1 0 151 119A52 52 0 0 1 113 29Z',fill:'#d7e2f1',stroke:'#91a9c8','stroke-width':2.4}],['path',{d:'m133 24 2 7 7 2-7 2-2 7-2-7-7-2 7-2Zm22 39 2 5 5 2-5 2-2 5-2-5-5-2 5-2Z',fill:'#e7d5a5'}],['circle',{cx:54,cy:100,r:6,fill:'#bdcde2',opacity:.55}],['circle',{cx:70,cy:125,r:4,fill:'#bdcde2',opacity:.5}]];
    for(const [tag,attrs] of shapes){const n=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));moon.append(n);}corner.prepend(moon);
    const update=()=>{const hour=new Date().getHours(),night=hour<6||hour>=18;corner.classList.toggle('celestial-night',night);const caption=corner.querySelector('span');if(caption)caption.textContent=t(night?'moon':'sun');};update();setInterval(update,60000);
  }
  const input=document.getElementById('assistant-input')||document.getElementById('messageInput');if(!input)return;
  const form=input.closest('form'),bar=make('div','','uv-voice-tools'),status=make('p','','uv-voice-status');status.setAttribute('role','status');
  const mic=make('button','● '+t('start'),'uv-voice-mic'),read=make('button','▷ '+t('read')),stop=make('button','□ '+t('quiet'));
  [mic,read,stop].forEach(b=>{b.type='button';bar.append(b);});
  const label=make('label','','uv-voice-auto'),auto=make('input');auto.type='checkbox';label.append(auto,document.createTextNode(t('auto')));bar.append(label);
  const note=make('p',t('privacy'),'uv-voice-note'),tools=make('div','','uv-voice');tools.append(bar,status,note);form.insertAdjacentElement('afterend',tools);
  const synth=window.speechSynthesis;let latest='',recognizer=null,listening=false,base='',recognized='';
  async function speech(text){if(lang==='ru'){window.universeSpeech?.stop();status.textContent=window.campusI18n.text('俄语使用你的语言包，这段文字暂无对应录音。');return;}if(!synth||!text){status.textContent=t('empty');return;}const ok=await window.universeSpeech?.speak(text,{language:lang,owner:'assistant',onError:()=>status.textContent=t('noVoice')});if(!ok)status.textContent=t('noVoice');}
  window.addEventListener('universe-audio-owner',event=>{if(event.detail?.owner!=='assistant'&&window.universeSpeech?.owner==='assistant')window.universeSpeech.stop();});
  read.disabled=!synth;stop.disabled=!synth;auto.disabled=!synth;
  read.addEventListener('click',()=>speech(latest));stop.addEventListener('click',()=>{window.universeSpeech?.stop();status.textContent='';});
  auto.addEventListener('change',()=>{if(!auto.checked)window.universeSpeech?.stop();});
  window.addEventListener('universe-ai-reply',e=>{if(typeof e.detail?.text!=='string')return;latest=e.detail.text;if(auto.checked)speech(latest);});
  const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Recognition){mic.disabled=true;status.textContent=t('unsupported');}
  else{
    recognizer=new Recognition();recognizer.lang={zh:'zh-CN',en:'en-US',ru:'ru-RU',ja:'ja-JP'}[lang];recognizer.continuous=false;recognizer.interimResults=true;
    function end(){listening=false;mic.textContent='● '+t('start');mic.setAttribute('aria-pressed','false');bar.classList.remove('is-listening');}
    recognizer.onstart=()=>{listening=true;mic.textContent='■ '+t('stop');mic.setAttribute('aria-pressed','true');bar.classList.add('is-listening');status.textContent=t('listen');};
    recognizer.onresult=e=>{recognized=Array.from(e.results).map(r=>r[0].transcript).join('');input.value=(base+(base?' ':'')+recognized).slice(0,input.maxLength>0?input.maxLength:2000);input.dispatchEvent(new Event('input',{bubbles:true}));};
    recognizer.onerror=e=>{if(e.error!=='aborted')status.textContent=t(['not-allowed','service-not-allowed','audio-capture'].includes(e.error)?'denied':'fail');end();};
    recognizer.onend=()=>{end();if(recognized)status.textContent=t('ready');};
    mic.addEventListener('click',()=>{if(listening){recognizer.stop();return;}if(input.disabled)return;window.universeSpeech?.stop();document.getElementById('mascot-audio')?.pause();window.dispatchEvent(new CustomEvent('universe-audio-owner',{detail:{owner:'microphone'}}));base=input.value.trim();recognized='';try{recognizer.start();}catch(_){status.textContent=t('fail');end();}});
    form.addEventListener('submit',()=>{if(listening)recognizer.abort();});
  }
  window.addEventListener('pagehide',()=>{recognizer?.abort();synth?.cancel();});
})();
