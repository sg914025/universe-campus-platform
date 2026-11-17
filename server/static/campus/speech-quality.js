/* Shared speech ownership: recorded Russian only; device voices for other languages. */
(() => {
 const synth=window.speechSynthesis;let generation=0,owner='',finish=null;
 const codes={zh:'zh-CN',en:'en-US',ru:'ru-RU',ja:'ja-JP'};
 function stop(){generation++;synth?.cancel();const callback=finish;finish=null;owner='';callback?.();}
 function voice(language){const matches=(synth?.getVoices()||[]).filter(v=>v.lang.toLowerCase().replace('_','-').startsWith(language+'-')||v.lang.toLowerCase()===language);return matches.sort((a,b)=>Number(b.localService)-Number(a.localService)||Number(b.default)-Number(a.default))[0];}
 function chunks(text){text=String(text).replace(/```[\s\S]*?```/g,' ').replace(/https?:\/\/\S+/g,' ').replace(/[*#`_]/g,' ').replace(/\s+/g,' ').trim().slice(0,6000);const words=text.split(/\s+/).flatMap(word=>word.length>180&&/[\u3040-\u9fff]/.test(word)&&typeof Intl.Segmenter==='function'?Array.from(new Intl.Segmenter(undefined,{granularity:'word'}).segment(word),s=>s.segment):[word]),result=[];let current='';for(const word of words){if(current.length+word.length>150&&current){result.push(current);current='';}current+=(current?' ':'')+word;}if(current)result.push(current);return result;}
 async function speak(text,options={}){stop();const ticket=generation;const language=options.language||'zh';if(language==='ru')return false; // Russian uses the supplied recording pack only.
  if(!synth)return false;
  if(!voice(language))await new Promise(resolve=>{const timer=setTimeout(resolve,700);synth.addEventListener('voiceschanged',()=>{clearTimeout(timer);resolve();},{once:true});});
  if(ticket!==generation)return false;const selected=voice(language);if(!selected)return false;
  owner=options.owner||'device';const parts=chunks(text);if(!parts.length)return false;
  document.getElementById('mascot-audio')?.pause();window.dispatchEvent(new CustomEvent('universe-audio-owner',{detail:{owner}}));
  finish=options.onEnd||null;let index=0;
  function next(){if(ticket!==generation)return;if(index>=parts.length){const done=finish;finish=null;owner='';done?.();return;}
   const utterance=new SpeechSynthesisUtterance(parts[index++]);utterance.lang=codes[language]||language;utterance.voice=selected;utterance.rate=language==='ru'?.92:1;utterance.pitch=1;utterance.volume=.82;
   utterance.onend=()=>{if(ticket===generation)setTimeout(next,90);};utterance.onerror=e=>{if(ticket!==generation)return;stop();if(!['interrupted','canceled'].includes(e.error))options.onError?.();};synth.speak(utterance);
  }next();return true;
 }
 window.universeSpeech={speak,stop,voice,chunks,get owner(){return owner;}};
 window.addEventListener('pagehide',stop);
})();
