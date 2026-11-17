/* Campus clinic appointments. The server owns time, remaining places and identity. */
(() => {
  const t = text => window.campusI18n.text(text);
  const $r = id => document.getElementById(id);
  const grid = $r('departmentGrid'), status = $r('roomHours'), search = $r('deptSearch');
  const dialog = $r('roomDialog'), confirm = $r('roomAction'), recommendation = $r('roomRecommendation');
  let data = null, category = '全部', date = '', current = null, selected = null, requestKey = null, version = 0, submitting = false;
  function element(tag, text, cls) {
    const node = document.createElement(tag); if (text) node.textContent = text; if (cls) node.className = cls; return node;
  }
  function message(text, error = false) {
    $r('roomFeedback').textContent = t(text); $r('roomFeedback').classList.toggle('error', error);
  }
  async function api(url, payload) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 15000);
    try {
      const options = {cache:'no-store', signal:controller.signal};
      if (payload) Object.assign(options, {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken':(document.cookie.match(/(?:^|; )csrftoken=([^;]*)/)||[])[1]||''}, body:JSON.stringify(payload)});
      const response = await fetch(url, options); let result;
      try { result = await response.json(); } catch { throw new Error('暂时无法加载预约信息，请稍后重试。'); }
      if (!response.ok) throw new Error(result.error || '暂时无法加载预约信息，请稍后重试。');
      return result;
    } catch (error) { if (error.name === 'AbortError' || error instanceof TypeError) throw new Error('连接中断，请重试；已提交的预约不会重复创建。'); throw error; }
    finally { clearTimeout(timer); }
  }
  function dateLabel(value) {
    return new Intl.DateTimeFormat(document.documentElement.lang, {month:'short', day:'numeric', weekday:'short', timeZone:'Asia/Shanghai'}).format(new Date(value+'T00:00:00+08:00'));
  }
  window.openRoomRecommendation = () => { if (!recommendation.open) recommendation.showModal(); };
  $r('roomStartTriage').addEventListener('click', () => { recommendation.close(); switchPage('advanced'); });
  $r('roomContinue').addEventListener('click', () => { recommendation.close(); switchPage('departments', true); refresh().catch(e => message(e.message,true)); });
  $r('closeRoomRecommendation').addEventListener('click', () => recommendation.close());
  window.appendCareChoices = (host, onlineCallback) => {
    const group = element('div', '', 'care-choices'), online = element('button',t('线上咨询')), rooms = element('button',t('选择诊室'));
    online.type = rooms.type = 'button';
    online.addEventListener('click', async () => {
      if (!onlineCallback) { switchPage('advanced'); return; }
      online.disabled = true; try { await onlineCallback(); } finally { online.disabled = false; }
    });
    rooms.addEventListener('click', window.openRoomRecommendation); group.append(online,rooms); host.append(group);
  };
  function renderDates() {
    const host = $r('roomDates'); host.replaceChildren();
    data.dates.forEach(value => {
      const button = element('button', (value===data.today?t('今天')+' · ':'')+dateLabel(value));
      button.type='button'; button.dataset.date=value; button.className=value===data.date?'selected':'';
      button.setAttribute('aria-pressed',String(value===data.date));
      button.addEventListener('click', () => { date=value; selected=null; requestKey=null; refresh().catch(e=>message(e.message,true)); });
      host.append(button);
    });
  }
  function render() {
    if (!data) return;
    status.textContent=t('可预约今天及未来3天。普通诊室08:00–12:00、14:00–17:00；17:00后仅急诊。')+' '+t('急诊无需预约。普通门诊每个时段5个号源，以北京时间为准。');
    renderDates(); grid.replaceChildren();
    const query=search.value.trim().toLowerCase();
    const list=data.rooms.filter(room=>(category==='全部'||room.category===category)&&[room.name,room.desc,t(room.name),t(room.desc)].join(' ').toLowerCase().includes(query));
    list.forEach(room => {
      const card=element('button','','dept-card room-card'); card.type='button'; card.dataset.room=room.id;
      card.classList.toggle('room-closed',!room.available&&room.id!=='special');
      const mark=element('div','','dept-icon'); mark.append(icon(room.icon));
      const available=room.slots.filter(s=>s.remaining>0);
      const caption=room.id==='special'?'联系值班人员 ↗':room.category==='急诊'?'无需预约，直接前往 ↗':available.length?'选择预约时段 ↗':'当日暂无可预约时段';
      card.append(mark,element('strong',t(room.name)),element('p',t(room.desc)),element('small',t(caption)));
      if (room.requires_booking) card.append(element('span',t('剩余号源')+' '+available.reduce((sum,s)=>sum+s.remaining,0),'room-count'));
      card.addEventListener('click',()=>open(room.id)); grid.append(card);
    });
    if (!list.length) grid.append(element('p',t('没有找到相关诊室。')));
  }
  async function refresh() {
    const run=++version;
    const result=await api('/api/rooms/'+(date?'?date='+encodeURIComponent(date):''));
    if (run!==version) return;
    data=result; date=data.date; render();
    if (dialog.open&&current) details();
  }
  function details() {
    const room=data.rooms.find(r=>r.id===current); if (!room) return;
    $r('roomTitle').textContent=t(room.name)+(room.requires_booking?' · '+dateLabel(data.date):'');
    $r('roomDesc').textContent=t(room.desc);
    $r('roomDialogFeedback').textContent='';
    const host=$r('roomSlots'); host.replaceChildren();
    if (room.id==='special') {
      $r('roomInfo').textContent=t('特殊通道由现场值班人员安排，不在线占用号源。17:00后需要协助请联系急诊值班人员。');
      confirm.textContent=t('知道了，联系现场人员'); confirm.disabled=false; return;
    }
    if (room.category==='急诊') {
      $r('roomInfo').textContent=t('急诊无需预约，请直接前往诊室等待大厅内等候，听从现场医护安排。如病情紧急，请立即告知医护人员。');
      confirm.textContent=t('知道了，前往急诊');confirm.disabled=false;return;
    }
    $r('roomInfo').textContent=t('请选择时间段，确认后占用1个号源。到场后请出示预约编号，并在诊室等待大厅内等候。');
    if (selected&&!room.slots.some(s=>s.start===selected&&s.remaining>0)) { selected=null; requestKey=null; }
    const periods=[['上午',s=>Number(s.label.slice(0,2))>=8&&Number(s.label.slice(0,2))<12],['下午',s=>Number(s.label.slice(0,2))>=12&&Number(s.label.slice(0,2))<17],['夜间 / 凌晨',s=>Number(s.label.slice(0,2))<8||Number(s.label.slice(0,2))>=17]];
    periods.forEach(([label,filter]) => {
      const slots=room.slots.filter(filter); if (!slots.length) return;
      const row=element('div','','room-slot-grid'); host.append(element('h3',t(label)),row);
      slots.forEach(slot => {
        const button=element('button',slot.label+' · '+(slot.remaining?t('余号')+' '+slot.remaining:t('已约满')));
        button.type='button'; button.disabled=!slot.remaining||submitting;
        button.className=slot.start===selected?'selected':''; button.dataset.start=slot.start;
        button.setAttribute('aria-pressed',String(slot.start===selected));
        button.addEventListener('click',()=>{selected=slot.start;requestKey=crypto.randomUUID();details();}); row.append(button);
      });
    });
    if (!room.slots.length) host.append(element('p',t('当天时段已结束，请选择其他日期或急诊。')));
    confirm.textContent=t(submitting?'正在预约…':'确认预约'); confirm.disabled=!selected||submitting;
  }
  async function open(id) {
    try { await refresh(); current=id; selected=null;requestKey=null;details();dialog.showModal(); }
    catch(e) { message(e.message,true); }
  }
  search.addEventListener('input',render);
  $r('deptFilters').addEventListener('click', e => {
    const target=e.target.closest('[data-filter]');if(!target)return;category=target.dataset.filter;
    document.querySelectorAll('#deptFilters button').forEach(b=>{b.classList.toggle('selected',b===target);b.setAttribute('aria-pressed',String(b===target));});render();
  });
  $r('closeRoomDialog').addEventListener('click',()=>{if(!submitting)dialog.close();});
  dialog.addEventListener('cancel',e=>{if(submitting)e.preventDefault();});
  confirm.addEventListener('click',async()=>{
    if (submitting) return;
    if (current==='special'||current.startsWith('emergency')) {dialog.close();return;}
    if (!selected||!requestKey) return;
    const payload={room:current,start:selected,request_key:requestKey}; submitting=true; details();
    try {
      const result=await api('/api/rooms/reserve/',payload);
      dialog.close(); message(t('预约成功')+' · '+result.appointment.code+' · '+t(result.appointment.name)+' · '+result.appointment.date+' '+result.appointment.time+' · '+t('请按预约时间到场，在诊室等待大厅内等候。'));
      selected=null;requestKey=null; await Promise.all([refresh(),loadMine()]);
    } catch(e) {
      $r('roomDialogFeedback').textContent=t(e.message);
    } finally {submitting=false;if(dialog.open){const text=$r('roomDialogFeedback').textContent;details();$r('roomDialogFeedback').textContent=text;}}
  });
  async function loadMine() {
    const result=await api('/api/rooms/mine/'); const host=$r('roomBookings');host.replaceChildren();
    if (!result.appointments.length) {host.append(element('p',t('暂无诊室预约。'),'lead'));return;}
    result.appointments.forEach(record=>{
      const card=element('article','','room-booking-record');
      card.append(element('strong',t(record.name)+' · '+record.date+' '+record.time),element('p',t('预约编号')+' '+record.code+' · '+t('序号')+' '+record.number+' · '+t(record.status==='confirmed'?'已预约':'已取消')));
      if(record.can_cancel){
        const button=element('button',t('取消预约'));button.type='button';
        button.addEventListener('click',()=>{ $r('cancelRoomInfo').textContent=t(record.name)+' · '+record.date+' '+record.time; $r('cancelRoomConfirm').dataset.id=record.id; $r('cancelRoomDialog').showModal(); });card.append(button);
      }host.append(card);
    });
  }
  $r('cancelRoomBack').addEventListener('click',()=>$r('cancelRoomDialog').close());
  $r('cancelRoomConfirm').addEventListener('click',async e=>{
    const button=e.currentTarget;button.disabled=true;
    try {await api('/api/rooms/'+button.dataset.id+'/cancel/',{});$r('cancelRoomDialog').close();message('预约已取消，号源已释放。');await Promise.all([refresh(),loadMine()]);}
    catch(error){$r('cancelRoomDialog').close();message(error.message,true);}finally{button.disabled=false;}
  });
  $r('refreshRoomBookings').addEventListener('click',()=>Promise.all([refresh(),loadMine()]).catch(e=>message(e.message,true)));
  Promise.all([refresh(),loadMine()]).catch(e=>message(e.message,true));
  setInterval(()=>{if(!submitting&&!document.hidden)refresh().catch(()=>{});},30000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)Promise.all([refresh(),loadMine()]).catch(()=>{});});
})();
