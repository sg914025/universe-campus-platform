'use strict';

// 高级导诊先阅读说明，再选择部位。这里只做简单的关键词演示。
window.advancedAccepted = false;
(() => {
  const parts = JSON.parse(document.getElementById('advanced-parts').textContent);
  const page = document.getElementById('page-advanced');
  const notice = document.getElementById('advancedNotice');
  const body = document.getElementById('advancedBody');
  const partButtons = document.getElementById('partButtons');
  const input = document.getElementById('advancedDescription');
  const auto = document.getElementById('autoLocate');
  let selectedPart = '', selectedDetail = '', backView = false, locateTimer;
  let requestKey = makeKey();
  let animationFrame = 0, motionVersion = 0, zoomDepth = 0, focusPoint = null, focusLabel = "";
  const stage = document.getElementById('bodyStage');
  const detailLayer = document.getElementById('detailHitLayer');
  // 坐标与人体图对应，只保留常用位置，避免把界面做得过于复杂。
  const detailPoints = {
    head: [[201,24],[210,64],[211,46]], neck: [[202,97],[220,97],[211,104]],
    chest: [[238,151],[180,151],[210,151]], abdomen: [[209,204],[209,264],[209,235]],
    back: [[210,146],[210,205],[210,260]], pelvis: [[210,295],[210,325],[265,305]],
    right_arm: [[142,123],[126,162],[108,210],[91,250]],
    right_hand: [[84,287],[80,314],[77,336]],
    right_leg: [[166,372],[164,421],[160,491],[149,573]]
  };

  function updateBodyImage() {
    const side = backView ? 'back' : 'front';
    const layer = stage.dataset.layer;
    document.getElementById('bodyRender').setAttribute('href', stage.getAttribute('data-' + side + '-' + layer));
  }

  function animateViewBox(target, done) {
    stage.dataset.zoom=zoomDepth===3?'precise':zoomDepth===2?'detail':zoomDepth===1?'part':'whole';
    cancelAnimationFrame(animationFrame);
    const version = ++motionVersion;
    const start = body.getAttribute('viewBox').split(/\s+/).map(Number);
    stage.classList.add('zooming');
    detailLayer.replaceChildren();
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const began = performance.now();
    const duration = reduced ? 0 : 720;
    function frame(now) {
      if (version !== motionVersion) return;
      const progress = duration ? Math.min(1, (now - began) / duration) : 1;
      const ease = progress < .5 ? 4 * progress ** 3 : 1 - (-2 * progress + 2) ** 3 / 2;
      body.setAttribute('viewBox', start.map((n, i) => n + (target[i] - n) * ease).join(' '));
      if (progress < 1) animationFrame = requestAnimationFrame(frame);
      else {stage.classList.remove('zooming'); if (done) done();}
    }
    animationFrame = requestAnimationFrame(frame);
  }

  function partBox() {
    const box = [...parts[selectedPart].box];
    if (backView && /^(left|right)_/.test(selectedPart)) box[0] = 420 - box[0] - box[2];
    return box;
  }

  function pointsForPart() {
    const key = selectedPart.replace('left_', 'right_');
    return (detailPoints[key] || []).map(([x, y]) => {
      if (selectedPart.startsWith('left_')) x = 420 - x;
      if (backView && /^(left|right)_/.test(selectedPart)) x = 420 - x;
      return [x, y];
    });
  }

  function renderDetailHits() {
    detailLayer.replaceChildren();
    if (!selectedPart || !zoomDepth) return;
    if (zoomDepth === 3 && focusPoint) { renderPreciseHit(); return; }
    const points = pointsForPart();
    const box = partBox();
    const scale = Math.max(box[2], box[3]) / 180;
    parts[selectedPart].details.forEach((detail, i) => {
      if (!points[i] || (zoomDepth === 2 && detail !== selectedDetail)) return;
      const [x,y] = points[i];
      const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      group.classList.add('detail-hit');
      group.classList.toggle('selected', detail === selectedDetail);
      group.setAttribute('role', 'button'); group.setAttribute('tabindex', '0');
      group.setAttribute('aria-label', window.campusI18n.text("选择") + window.campusI18n.text(detail));
      group.setAttribute('transform', 'translate(' + x + ' ' + y + ') scale(' + scale + ')');
      const circle = document.createElementNS(group.namespaceURI, 'circle');
      circle.setAttribute('r', '5'); group.append(circle);
      const label = document.createElementNS(group.namespaceURI, 'text');
      label.setAttribute('x', '9'); label.setAttribute('y', '3'); label.textContent = window.campusI18n.text(detail);
      group.append(label);
      group.addEventListener('click', e => {e.stopPropagation(); chooseDetail(detail);});
      group.addEventListener('keydown', e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); chooseDetail(detail);}});
      detailLayer.append(group);
    });
  }

  function chooseDetail(detail, source = "manual") {
    invalidateResult();
    selectedDetail = detail; focusPoint = null; requestKey = makeKey(); detailButtons();
    if (source === 'manual') selectionChanged();
    const i = parts[selectedPart].details.indexOf(detail);
    const point = pointsForPart()[i];
    document.getElementById('bodyZoomCaption').textContent = window.campusI18n.text(parts[selectedPart].name) + ' · ' + window.campusI18n.text(detail);
    if (!point) {renderDetailHits(); return;}
    const broad = partBox();
    const w = Math.max(45, broad[2] * .72), h = Math.max(44, broad[3] * .48);
    zoomDepth = 2;
    document.getElementById('backPart').classList.remove('hidden');
    animateViewBox([Math.max(0, point[0]-w/2), Math.max(0, point[1]-h/2), w, h], renderDetailHits);
  }

  const findOrder = ['left_hand', 'right_hand', 'left_arm', 'right_arm', 'left_leg', 'right_leg', 'neck', 'head', 'chest', 'abdomen', 'back', 'pelvis', 'hands', 'arms', 'legs'];

  document.querySelectorAll('[data-body-layer]').forEach(button => button.addEventListener('click', () => {
    document.getElementById('bodyStage').dataset.layer = button.dataset.bodyLayer;
    updateBodyImage();
    document.querySelectorAll('[data-body-layer]').forEach(item => {
      const active = item === button;
      item.classList.toggle('selected', active);
      item.setAttribute('aria-pressed', String(active));
    });
  }));

  function makeKey() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {const n = Math.floor(Math.random() * 16); return (c === 'x' ? n : (n & 3) | 8).toString(16);});
  }

  window.openAdvancedNotice = () => {
    document.getElementById('noticeCheck').checked = false;
    document.getElementById('acceptAdvanced').disabled = true;
    notice.showModal();
  };
  document.getElementById('noticeCheck').addEventListener('change', e => {document.getElementById('acceptAdvanced').disabled = !e.target.checked;});
  document.getElementById('cancelAdvanced').addEventListener('click', () => notice.close());
  document.getElementById('acceptAdvanced').addEventListener('click', () => {
    if (!document.getElementById('noticeCheck').checked) return;
    window.advancedAccepted = true;
    notice.close();
    switchPage('advanced');
  });
  document.getElementById('reviewNotice').addEventListener('click', window.openAdvancedNotice);

  function updateSide() {
    document.getElementById('bodyStage').dataset.view = backView ? 'back' : 'front';
    updateBodyImage();
    document.getElementById('bodySideLabel').textContent = backView ? window.campusI18n.text("背面示意") : window.campusI18n.text("正面示意");
    document.getElementById('flipBody').textContent = backView ? window.campusI18n.text("查看正面") : window.campusI18n.text("查看背面");
    ['arm', 'hand', 'leg'].forEach(part => {
      const left = document.querySelector('[data-body="left_' + part + '"]');
      const right = document.querySelector('[data-body="right_' + part + '"]');
      if (backView) {left.removeAttribute('transform'); right.setAttribute('transform', 'translate(420 0) scale(-1 1)');}
      else {right.removeAttribute('transform'); left.setAttribute('transform', 'translate(420 0) scale(-1 1)');}
    });
  }

  function updateHighlight() {
    const group = {arms: ['left_arm', 'right_arm'], hands: ['left_hand', 'right_hand'], legs: ['left_leg', 'right_leg']};
    const active = group[selectedPart] || [selectedPart];
    document.querySelectorAll('[data-body]').forEach(g => g.classList.toggle('selected', active.includes(g.dataset.body)));
    partButtons.querySelectorAll('button').forEach(button => {
      const isSelected = button.dataset.part === selectedPart;
      button.classList.toggle('selected', isSelected);
      button.setAttribute('aria-pressed', String(isSelected));
    });
  }

  function zoomSelected() {
    if (!selectedPart) return;
    zoomDepth = 1;
    document.getElementById('backPart').classList.add('hidden');
    document.getElementById('partDetailArea').classList.add('hidden');
    document.getElementById('bodyZoomCaption').textContent = window.campusI18n.text("正在放大 ") + window.campusI18n.text(parts[selectedPart].name) + '…';
    animateViewBox(partBox(), () => {
      document.getElementById('partDetailArea').classList.remove('hidden');
      document.getElementById('bodyZoomCaption').textContent = window.campusI18n.text(parts[selectedPart].name) + window.campusI18n.text(" · 请选择具体位置");
      renderDetailHits();
    });
  }

  function detailButtons() {
    const list = document.getElementById('detailButtons');
    list.replaceChildren();
    if (!selectedPart) return;
    parts[selectedPart].details.forEach(detail => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = window.campusI18n.text(detail);
      button.classList.toggle('selected', selectedDetail === detail);
      button.setAttribute('aria-pressed', String(selectedDetail === detail));
      button.addEventListener('click', () => chooseDetail(detail));
      list.append(button);
    });
  }

  function selectPart(key, source) {
    if (!parts[key]) return;
    if (source === 'manual') { invalidateResult(); selectionChanged(); }
    if (key !== selectedPart) {selectedDetail = ''; focusPoint = null; requestKey = makeKey();}
    selectedPart = key;
    if (key === 'back') backView = true;
    else if (['chest', 'abdomen'].includes(key)) backView = false;
    if (source === 'manual') {
      auto.checked = false;
      document.getElementById('locateHint').textContent = window.campusI18n.text("已手动选择：") + window.campusI18n.text(parts[key].name) + window.campusI18n.text("。自动定位已关闭，可以重新勾选。");
    }
    document.getElementById('partSource').textContent = source === 'auto' ? window.campusI18n.text("已根据描述定位") : window.campusI18n.text("已手动选择");
    document.getElementById('chosenPart').textContent = window.campusI18n.text(parts[key].name);
    document.getElementById('bodySelectedLabel').textContent = window.campusI18n.text(parts[key].name);
    document.getElementById('partDetailArea').classList.remove('hidden');
    document.getElementById('zoomBody').disabled = false;
    updateSide(); updateHighlight(); detailButtons(); zoomSelected();
  }

  function resetPart() {
    invalidateResult();
    selectedPart = ''; selectedDetail = ''; focusPoint = null; requestKey = makeKey();
    selectionChanged();
    document.getElementById('chosenPart').textContent = window.campusI18n.text("还没有选择");
    document.getElementById('bodySelectedLabel').textContent = window.campusI18n.text("未选择");
    document.getElementById('partSource').textContent = window.campusI18n.text("支持手动选择");
    document.getElementById('partDetailArea').classList.add('hidden');
    document.getElementById('zoomBody').disabled = true;
    zoomDepth = 0; document.getElementById('backPart').classList.add('hidden'); animateViewBox([0, 0, 420, 620]);
    document.getElementById('bodyZoomCaption').textContent = window.campusI18n.text("点击部位，或在右侧描述不适");
    updateHighlight();
  }
  Object.entries(parts).filter(([key]) => !['arms', 'hands', 'legs'].includes(key)).forEach(([key, part]) => {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = window.campusI18n.text(part.name); button.dataset.part = key;
    button.setAttribute('aria-pressed', 'false');
    button.addEventListener('click', () => selectPart(key, 'manual'));
    partButtons.append(button);
  });
  document.querySelectorAll('[data-body]').forEach(g => {
    g.addEventListener('click', () => selectPart(g.dataset.body, 'manual'));
    g.addEventListener('keydown', e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); selectPart(g.dataset.body, 'manual');}});
  });
  document.getElementById('resetPart').addEventListener('click', () => {resetPart(); auto.checked = false; document.getElementById('locateHint').textContent = window.campusI18n.text("已清除选择。可以手动选部位，或重新勾选自动定位。");});
  document.getElementById('wholeBody').addEventListener('click', () => {zoomDepth = 0; document.getElementById('backPart').classList.add('hidden'); animateViewBox([0, 0, 420, 620]); document.getElementById('bodyZoomCaption').textContent = window.campusI18n.text("全身视图 · 可以点击其他部位");});
  document.getElementById('zoomBody').addEventListener('click', zoomSelected);
  document.getElementById('backPart').addEventListener('click', () => {if (zoomDepth === 3 && selectedDetail) chooseDetail(selectedDetail, 'flow'); else zoomSelected();});
  document.getElementById('flipBody').addEventListener('click', () => {
    backView = !backView;
    if (backView) selectPart('back', 'manual');
    else if (selectedPart === 'back') resetPart();
    updateSide(); zoomDepth = 0; document.getElementById('backPart').classList.add('hidden'); animateViewBox([0, 0, 420, 620]);
    document.getElementById('bodyZoomCaption').textContent = window.campusI18n.text("全身视图 · ") + (backView ? window.campusI18n.text("背面") : window.campusI18n.text("正面"));
  });

  function locateFromText() {
    if (!auto.checked) return;
    const text = input.value.trim();
    const key = findOrder.find(key => parts[key].keywords.some(word => text.includes(word)));
    if (!key) {
      resetPart();
      document.getElementById('locateHint').textContent = window.campusI18n.text("没有识别到明确部位，请手动选择。");
      return;
    }
    selectPart(key, 'auto');
    const aliases = {'膝盖': ['膝'], '脚踝 / 足部': ['脚', '踝'], '手腕': ['腕'], '手掌': ['掌'], '手指': ['指'], '肩部': ['肩'], '肘部': ['肘'], '腰部': ['腰']};
    selectedDetail = parts[key].details.find(detail => (aliases[detail] || detail.split(' / ')).some(word => text.includes(word))) || '';
    detailButtons();
    document.getElementById('locateHint').textContent = window.campusI18n.text("自动定位：") + window.campusI18n.text(parts[key].name) + (selectedDetail ? ' · ' + selectedDetail : '') + window.campusI18n.text("，已局部放大。你也可以手动改选。");
  }
  input.addEventListener('input', () => {
    invalidateResult();
    requestKey = makeKey();
    document.getElementById('advancedCount').textContent = input.value.length + ' / 2000';
    clearTimeout(locateTimer); locateTimer = setTimeout(locateFromText, 300);
  });
  auto.addEventListener('change', locateFromText);
  ['advancedDuration', 'advancedFeeling'].forEach(id => document.getElementById(id).addEventListener('change', () => {requestKey = makeKey(); invalidateResult();}));

  function invalidateResult() {
    document.getElementById('advancedResult').classList.add('hidden');
  }

  function textElement(tag, text, className = '') {
    const element = document.createElement(tag); element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  function showError(text) {
    const result = document.getElementById('advancedResult');
    result.className = 'advanced-result error'; result.replaceChildren(textElement('strong', window.campusI18n.text("请再确认一下")), textElement('p', text));
  }
  async function api(url, {timeoutMs=15000,...options} = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    const csrf = decodeURIComponent((document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] || '');
    try {
      const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        ...options, headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}});
      if (response.status === 401) {window.location.href = '/login/?next=/guide/'; throw Error(window.campusI18n.text("登录已失效，请重新登录。"));}
      if (!response.headers.get('Content-Type')?.includes('application/json')) throw Error(window.campusI18n.text("暂时无法完成操作，请稍后重试。"));
      const data = await response.json();
      if (!response.ok) throw Error(data.error || window.campusI18n.text("操作失败，请稍后重试。"));
      return data;
    } finally {clearTimeout(timeout);}
  }

  function appendAIReport(host, report, department, reference) {
    window.renderPatientReport(host, report, department, reference);
  }
  window.submitAdvancedAssessment = async (payload, online = false) => {
    const button = document.getElementById('advancedSubmit');
    button.disabled = true; button.textContent = window.campusI18n.text("正在整理描述…");
    try {
      const data = await api(page.dataset.assessUrl, {method: 'POST', body: JSON.stringify({...payload, preview: !online}),timeoutMs:100000});
      const result = document.getElementById('advancedResult');
      result.className = 'advanced-result' + (data.level === 'high' ? ' high' : '');
      result.replaceChildren(textElement('strong', window.campusI18n.text(data.queued ? "信息已提交 · 等待医生核实" : "导诊完成 · 选择就诊方式")), textElement('p', window.campusI18n.text(data.message)));
      appendAIReport(result,data.report,data.department,{request_key:payload.request_key});
      if (data.emergency) result.append(textElement('p', data.urgent_message, 'urgent'));
      if (data.queued) {
        result.append(textElement('p', window.campusI18n.text("咨询编号：") + data.code + ' · ' + data.status));
        const inboxButton = textElement('button', window.campusI18n.text("去信箱查看 →")); inboxButton.type = 'button';
        inboxButton.addEventListener('click', () => switchPage('inbox')); result.append(inboxButton);
      } else {
        window.appendCareChoices(result, () => window.submitAdvancedAssessment(payload, true));
      }
      result.append(textElement('p', window.campusI18n.text("AI 推测与自述程度不能确定真实病情，也不能排除危险情况。"), 'advanced-note'));
    } catch (error) {showError(error.name === 'AbortError' ? '请求超时了，请重试。' : error.message);}
    finally {button.disabled = false; button.textContent = window.campusI18n.text("分析并继续　→");}
  };


  function selectionChanged() {
    document.dispatchEvent(new CustomEvent('advanced-selection-changed'));
  }
  function renderPreciseHit() {
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    group.setAttribute('transform', 'translate(' + focusPoint[0] + ' ' + focusPoint[1] + ')');
    group.classList.add('precise-hit');
    const circle = document.createElementNS(group.namespaceURI, 'circle'); circle.setAttribute('r','3'); group.append(circle);
    const cross = document.createElementNS(group.namespaceURI, 'path'); cross.setAttribute('d','M-8 0h5m6 0h5M0-8v5m0 6v5'); group.append(cross);
    const label = document.createElementNS(group.namespaceURI, 'text'); label.setAttribute('x','5'); label.setAttribute('y','-5'); label.textContent=focusLabel; group.append(label);
    detailLayer.append(group);
  }
  window.advancedSelection = {
    read: () => ({part:selectedPart,detail:selectedDetail}),
    apply: data => {
      const changed = data.part !== selectedPart;
      if (changed) selectPart(data.part, 'flow');
      if (data.detail && (data.detail !== selectedDetail || zoomDepth < 2 || (zoomDepth === 3 && !data.focus))) chooseDetail(data.detail, 'flow');
      if (data.focus) {
        const focus=data.focus;
        const side = focus.back !== undefined ? focus.back : backView;
        backView=side; updateSide();
        let [x,y]=focus.point;
        if (focus.mirror && selectedPart.startsWith('left_')) x=420-x;
        if (backView && focus.mirror) x=420-x;
        if (focusPoint && focusPoint[0]===x && focusPoint[1]===y && focusLabel===focus.label && zoomDepth===3) return;
        focusPoint=[x,y]; focusLabel=focus.label; zoomDepth=3;
        const w=selectedPart==='abdomen'||selectedPart==='chest'?70:48, h=55;
        document.getElementById('backPart').classList.remove('hidden');
        document.getElementById('bodyZoomCaption').textContent=window.campusI18n.text(parts[selectedPart].name)+' · '+window.campusI18n.text(focus.label);
        document.getElementById('chosenPart').textContent=window.campusI18n.text(parts[selectedPart].name)+' · '+window.campusI18n.text(focus.label);
        animateViewBox([Math.max(0,x-w/2),Math.max(0,y-h/2),w,h],renderDetailHits);
      }
    },
    chooseQuestionOption: (key,value) => {
      if (key==='detail' && parts[selectedPart].details.includes(value)) chooseDetail(value,'flow');
    }
  };

  window.loadInbox = async () => {
    const list = document.getElementById('inboxList');
    list.replaceChildren(textElement('p', window.campusI18n.text("正在读取信箱…"), 'advanced-note'));
    try {
      const data = await api(document.getElementById('page-inbox').dataset.inboxUrl);
      document.getElementById('inboxCount').textContent = data.unread ? String(data.unread) : '';
      list.replaceChildren();
      if (!data.messages.length) {list.append(textElement('div', window.campusI18n.text("还没有消息。\n高级导诊中提交给后台的咨询，会显示在这里。"), 'inbox-empty')); return;}
      const dateText = value => new Date(value).toLocaleString(document.documentElement?.lang || 'zh-CN', {hour12:false,timeZone:'Asia/Shanghai'});
      data.messages.forEach(message => {
        const card = document.createElement('article'); card.className = 'inbox-card';
        const top = document.createElement('div'); top.className = 'inbox-top';
        top.append(textElement('strong', message.code + ' · ' + window.campusI18n.text(message.part)), textElement('span', window.campusI18n.text(message.status_label), 'inbox-status ' + message.status));
        card.append(top, textElement('p', dateText(message.created_at) + (message.detail ? ' · ' + window.campusI18n.text(message.detail) : ''), 'inbox-meta'), textElement('p', window.campusI18n.text('病情描述（原文）')+'：'+message.description, 'inbox-desc'));
        if (message.answers && Object.keys(message.answers).length) {
          const extra = textElement('p', window.campusI18n.text('补充回答（原文）')+'：'+Object.values(message.answers).join(' · '), 'inbox-meta'); card.append(extra);
        }
        appendAIReport(card,message.report,message.department||'待分诊',{consultation_id:message.id});
        if (message.reply) {
          const reply = document.createElement('div'); reply.className = 'doctor-reply';
          reply.append(textElement('strong', window.campusI18n.text("医生回复（原文）") + (message.doctor ? ' · ' + message.doctor : '')), textElement('div', message.reply));
          card.append(reply);
          if (!message.reply_read) {
            const actions = document.createElement('div'); actions.className = 'inbox-actions';
            const readButton = textElement('button', window.campusI18n.text("标记已读"), 'plain-button'); readButton.type = 'button';
            readButton.addEventListener('click', async () => {
              readButton.disabled = true;
              try {await api(document.getElementById('page-inbox').dataset.readUrl.replace('/0/', '/' + message.id + '/'), {method: 'POST'}); window.loadInbox();}
              catch (error) {readButton.disabled = false; readButton.textContent = window.campusI18n.text("未完成，请重试");}
            });
            actions.append(readButton); card.append(actions);
          }
        } else card.append(textElement('p', window.campusI18n.text("已提交后台，正在等待医生回答。请留意信箱；紧急情况不要等待回复。"), 'advanced-note'));
        list.append(card);
      });
    } catch (error) {list.replaceChildren(textElement('p', error.message || window.campusI18n.text("信箱暂时不可用，请稍后重试。"), 'inbox-empty'));}
  };
  document.getElementById('refreshInbox').addEventListener('click', window.loadInbox);
})();
