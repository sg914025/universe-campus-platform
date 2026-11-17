// 卡片进入视野时，淡入并向上浮动一次。
if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const cards = document.querySelectorAll('.postcard');
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.remove('card-waiting');
                observer.unobserve(entry.target);
            }
        });
    }, {threshold: 0, rootMargin: '0px 0px -30px 0px'});

    cards.forEach(card => {
        card.classList.add('card-reveal', 'card-waiting');
        observer.observe(card);
    });
    // 键盘跳转到卡片中的链接时，直接显示卡片。
    cards.forEach(card => card.addEventListener('focusin', () => {
        card.classList.remove('card-waiting');
        observer.unobserve(card);
    }));
}
