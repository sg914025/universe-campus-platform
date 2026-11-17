const toggle = document.getElementById('friends-toggle');
const panel = document.getElementById('friends-panel');
const close = document.getElementById('friends-close');
function show_friends(open) {
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
}
toggle.addEventListener('click', () => show_friends(panel.hidden));
close.addEventListener('click', () => show_friends(false));
document.addEventListener('keydown', event => {
    if (event.key === 'Escape') show_friends(false);
});
