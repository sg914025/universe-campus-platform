(() => {
    const modal = document.getElementById('chat-modal');
    const content = document.getElementById('chat-modal-content');
    const friends = document.getElementById('friends-panel');
    if (!modal || !content) return;

    async function load_chat(url, focus = false) {
        content.innerHTML = window.campusI18n.html("<div class=\"chat-loading\">正在打开聊天…</div>");
        modal.hidden = false;
        try {
            const response = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
            if (!response.ok) throw new Error(window.campusI18n.text("聊天暂时无法打开"));
            const html = await response.text();
            const document_page = new DOMParser().parseFromString(html, 'text/html');
            const panel = document_page.querySelector('.chat-panel');
            if (!panel) throw new Error(window.campusI18n.text("没有找到聊天内容"));
            // 保留聊天面板外壳；表情插入和发送拦截都依赖这个容器。
            content.innerHTML = `<section class="chat-panel">${panel.innerHTML}</section>`;
            const form = content.querySelector('.chat-panel form');
            if (form) form.action = response.url;
            const log = content.querySelector('.chat-log');
            if (log) log.scrollTop = log.scrollHeight;
            if (focus) content.querySelector('#chat-content')?.focus();
        } catch (error) {
            content.innerHTML = `<div class="notice">${error.message}</div>`;
        }
    }

    document.addEventListener('click', event => {
        const friend = event.target.closest('[data-chat-url]');
        if (friend) {
            event.preventDefault();
            if (friends) friends.hidden = true;
            load_chat(friend.dataset.chatUrl, true);
            return;
        }
        if (event.target.closest('[data-chat-close]')) modal.hidden = true;
        const refresh = event.target.closest('#chat-modal-content .chat-panel a[href*="/forum/profile/chat/"]');
        if (refresh) {
            event.preventDefault();
            load_chat(refresh.href);
        }
    });

    document.addEventListener('submit', async event => {
        const form = event.target.closest('#chat-modal-content .chat-panel form');
        if (!form) return;
        event.preventDefault();
        const button = form.querySelector('button[type="submit"], button:not([type])');
        if (button) button.disabled = true;
        try {
            const response = await fetch(form.action || window.location.href, {
                method: 'POST',
                body: new FormData(form),
                headers: {'X-Requested-With': 'XMLHttpRequest'},
                credentials: 'same-origin'
            });
            if (!response.ok) throw new Error(window.campusI18n.text("发送失败，请稍后重试"));
            await load_chat(response.url);
        } catch (error) {
            if (button) button.disabled = false;
            const log = content.querySelector('.chat-log');
            if (log) log.insertAdjacentHTML('beforeend', `<div class="notice">${error.message}</div>`);
        }
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !modal.hidden) modal.hidden = true;
    });
})();
