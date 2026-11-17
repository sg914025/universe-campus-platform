/* Service-room navigation is separate from the doctor's clinical specialty. */
(() => {
  const t = value => window.campusI18n.text(value);
  const grid = document.getElementById('departmentGrid');
  const status = document.getElementById('roomHours');
  const search = document.getElementById('deptSearch');
  let data = null, category = '全部', current = null;
  const button = document.getElementById('roomAction');
  const dialog = document.getElementById('roomDialog');
  const recommendation = document.getElementById('roomRecommendation');
  window.openRoomRecommendation = () => {
    if (!recommendation.open) recommendation.showModal();
  };
  document.getElementById('roomStartTriage').addEventListener('click', () => {
    recommendation.close(); switchPage('advanced');
  });
  document.getElementById('roomContinue').addEventListener('click', () => {
    recommendation.close(); switchPage('departments', true);
  });
  document.getElementById('closeRoomRecommendation').addEventListener('click', () => recommendation.close());
  window.appendCareChoices = (host, onlineCallback) => {
    const group = document.createElement('div'); group.className = 'care-choices';
    const online = document.createElement('button'); online.type = 'button'; online.textContent = t('线上咨询');
    online.addEventListener('click', async () => {
      if (!onlineCallback) { switchPage('advanced'); return; }
      online.disabled = true;
      try { await onlineCallback(); } finally { online.disabled = false; }
    });
    const rooms = document.createElement('button'); rooms.type = 'button'; rooms.textContent = t('选择诊室');
    rooms.addEventListener('click', window.openRoomRecommendation);
    group.append(online, rooms); host.append(group);
  };
  function render() {
    if (!data) return;
    status.textContent = t(data.after_hours ? '当前为夜间时段：17:00起仅开放急诊1、急诊2。特殊协助请联系急诊值班人员。' : '普通诊室17:00关闭；17:00起仅开放急诊1、急诊2。');
    grid.replaceChildren();
    const query = search.value.trim().toLowerCase();
    const list = data.rooms.filter(r => (category === '全部' || r.category === category) && [r.name,r.desc,t(r.name),t(r.desc)].join(' ').toLowerCase().includes(query));
    list.forEach(room => {
      const card = document.createElement('button'); card.className = 'dept-card room-card';
      card.dataset.room = room.id;
      card.classList.toggle('room-closed', !room.available);
      const mark = document.createElement('div'); mark.className = 'dept-icon'; mark.append(icon(room.icon));
      const title = document.createElement('strong'); title.textContent = t(room.name);
      const desc = document.createElement('p'); desc.textContent = t(room.desc);
      const hours = document.createElement('small'); hours.textContent = t(room.category === '急诊' ? '全天值班 · 查看指引 ↗' : room.available ? '17:00前开放 · 查看指引 ↗' : '当前已关闭 · 请选择急诊');
      card.append(mark,title,desc,hours);
      card.addEventListener('click', () => open(room.id)); grid.append(card);
    });
    if (!list.length) { const p = document.createElement('p'); p.textContent = t('没有找到相关诊室。'); grid.append(p); }
  }
  async function refresh() {
    const response = await fetch('/api/rooms/', {cache:'no-store'});
    if (!response.ok) throw new Error('room status unavailable');
    data = await response.json(); render();
  }
  function details() {
    const room = data.rooms.find(r => r.id === current);
    document.getElementById('roomTitle').textContent = t(room.name);
    document.getElementById('roomDesc').textContent = t(room.desc);
    document.getElementById('roomInfo').textContent = t(!room.available ? '该入口当前关闭。17:00起请前往急诊1或急诊2；需要特殊协助也请联系急诊值班人员。' : room.category === '特殊通道' ? '请到现场导诊台说明协助需求，由值班人员安排。此入口不自动加号或改变就诊顺序。' : room.category === '急诊' ? '请前往现场急诊值班区域。遇到紧急情况请拨打120，不要等待线上回复。' : '请到现场导诊台确认诊室位置与接诊情况。17:00起停止普通诊室接待。');
    button.disabled = !room.available;
    button.textContent = t(!room.available ? '当前已关闭' : room.category === '特殊通道' ? '知道了，联系现场人员' : '继续描述不适');
  }
  async function open(id) {
    try { await refresh(); current = id; details(); dialog.showModal(); }
    catch { status.textContent = t('暂时无法确认开放状态，请刷新重试或联系现场值班人员。'); }
  }
  search.addEventListener('input', render);
  document.getElementById('deptFilters').addEventListener('click', e => {
    const target = e.target.closest('[data-filter]'); if (!target) return;
    category = target.dataset.filter;
    document.querySelectorAll('#deptFilters button').forEach(b => { b.classList.toggle('selected',b===target); b.setAttribute('aria-pressed',String(b===target)); }); render();
  });
  document.getElementById('closeRoomDialog').addEventListener('click', () => dialog.close());
  button.addEventListener('click', async () => {
    try {
      await refresh(); details();
      const room = data.rooms.find(r => r.id === current); if (!room.available) return;
      dialog.close(); if (room.category !== '特殊通道') { switchPage('chat'); document.getElementById('messageInput').focus(); }
    } catch { status.textContent = t('暂时无法确认开放状态，请刷新重试或联系现场值班人员。'); }
  });
  refresh().catch(() => { status.textContent = t('暂时无法确认开放状态，请刷新重试或联系现场值班人员。'); });
  setInterval(() => refresh().then(() => { if (dialog.open && current) details(); }).catch(() => {}), 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh().catch(() => {}); });
})();
