const message_link = document.getElementById('message-link');
const message_count = document.getElementById('message-count');
let checking_messages = false;
async function check_messages() {
    if (!message_link || document.hidden || checking_messages) return;
    checking_messages = true;
    try {
        const response = await fetch(message_link.dataset.unreadUrl, {headers: {'Accept': 'application/json'}});
        if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
        const data = await response.json();
        message_link.classList.toggle('unread', data.count > 0);
        message_count.hidden = data.count === 0;
        message_count.textContent = data.count;
    } catch (error) {
        // 网络暂时断开时，下一次再检查。
    } finally {
        checking_messages = false;
    }
}
setInterval(check_messages, 10000);
window.addEventListener('focus', check_messages);
