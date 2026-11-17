import re
from .models import risk_alert

# 免费的本地规则筛查，只把可疑内容送入人工复核，不自动判断用户违规。
signals = {
    '刷单': 5, '刷信誉': 5, '返利': 4, '博彩': 5, '赌博': 5, '代考': 5,
    '加微信': 4, '加微': 4, '加v': 4, 'vx联系': 4, '扫码': 3, '私聊领': 3,
    '稳赚': 4, '日入': 3, '高薪兼职': 4, '贷款秒批': 4, '裸聊': 5,
}

def flag_content(source_type, source_id, author, content):
    text = (content or '').strip()
    folded = text.casefold()
    matched = [(word, score) for word, score in signals.items() if word.casefold() in folded]
    links = re.findall(r'https?://|www\.', folded)
    if links:
        matched.append(('外部链接', 2))
    score = sum(value for _, value in matched)
    if score < 4:
        return None
    reason = '疑似广告或引流：' + '、'.join(word for word, _ in matched[:6])
    alert, created = risk_alert.objects.update_or_create(
        source_type=source_type,
        source_id=source_id,
        defaults={
            'author_id': getattr(author, 'pk', None),
            'author_name': getattr(author, 'username', ''),
            'content': text[:5000],
            'reason': reason,
            'score': min(score, 99),
            'status': 'pending',
            'reviewer': None,
            'reviewed_at': None,
        },
    )
    return alert

def clear_moderated_content(alert):
    if alert.source_type == 'post':
        from .models import post
        post.objects.filter(pk=alert.source_id).update(is_hidden=True)
    elif alert.source_type == 'comment':
        from .models import comment
        comment.objects.filter(pk=alert.source_id).update(is_hidden=True)
    elif alert.source_type == 'chat':
        from .models import chat_message
        chat_message.objects.filter(pk=alert.source_id).update(is_hidden=True)
