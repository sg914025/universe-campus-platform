(() => {
    const form = document.getElementById('ai-chat-form');
    if (!form) return;
    const question = document.getElementById('ai-question');
    const thinking = document.getElementById('ai-thinking');
    const stage = document.getElementById('thinking-stage');
    const log = document.getElementById('ai-chat-log');
    const button = form.querySelector('button[type="submit"]');
    const stages = ['正在读取你的近期统计', '正在归纳浏览和跑腿记录', '正在组织数据回答'];

    if (log) log.scrollTop = log.scrollHeight;
    form.addEventListener('submit', event => {
        event.preventDefault();
        if (!question.value.trim() || form.dataset.waiting === 'true') return;
        form.dataset.waiting = 'true';
        question.readOnly = true;
        button.disabled = true;
        if (thinking) thinking.hidden = false;
        if (log) log.scrollTop = log.scrollHeight;
        let stageIndex = 0;
        const timer = window.setInterval(() => {
            stageIndex = Math.min(stageIndex + 1, stages.length - 1);
            if (stage) stage.textContent = stages[stageIndex];
            if (log) log.scrollTop = log.scrollHeight;
        }, 1650);
        window.setTimeout(() => {
            window.clearInterval(timer);
            HTMLFormElement.prototype.submit.call(form);
        }, 5000);
    });
    question.addEventListener('keydown', event => {
        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            form.requestSubmit();
        }
    });
})();
