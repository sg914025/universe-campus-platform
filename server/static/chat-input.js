document.addEventListener('click', event => {
    const button = event.target.closest('[data-emoji]');
    if (!button) return;
    const panel = button.closest('.chat-panel');
    const field = panel?.querySelector('textarea[name="content"]');
    if (!field) return;
    const emoji = button.dataset.emoji;
    // 点击表情时输入框会失去焦点；此时把表情追加到文字末尾，避免插到开头。
    const focused = document.activeElement === field;
    const start = focused ? field.selectionStart : field.value.length;
    const end = focused ? field.selectionEnd : start;
    field.setRangeText(emoji, start, end, 'end');
    field.dispatchEvent(new Event('input', { bubbles: true }));
    field.focus();
});
