"""人体部位及简单关键词，用于课程演示，不是医学分诊规则。"""
import re
PARTS = {
    'head': {'name': '头部', 'details': ['头顶 / 太阳穴', '面部', '眼耳鼻口'], 'keywords': ['头痛', '头疼', '头晕', '太阳穴', '眼睛', '耳朵', '牙', '鼻子', '脸', '头部'], 'box': [166, 0, 88, 98]},
    'neck': {'name': '颈部', 'details': ['前颈', '后颈', '咽喉'], 'keywords': ['脖子', '颈', '嗓子', '咽喉'], 'box': [170, 76, 80, 54]},
    'chest': {'name': '胸部', 'details': ['左胸', '右胸', '胸部中间'], 'keywords': ['胸', '咳嗽', '呼吸', '喘', '肺', '心脏', '肋骨'], 'box': [137, 102, 146, 90]},
    'abdomen': {'name': '腹部', 'details': ['上腹', '下腹', '肚脐周围'], 'keywords': ['肚子', '腹', '胃', '肠', '腹泻', '拉肚', '恶心', '肝'], 'box': [137, 176, 146, 117]},
    'back': {'name': '腰背部', 'details': ['上背', '下背', '腰部'], 'keywords': ['腰', '背', '脊柱', '脊椎', '肾'], 'box': [137, 102, 146, 191]},
    'pelvis': {'name': '骨盆 / 臀部', 'details': ['骨盆', '臀部', '髋部'], 'keywords': ['骨盆', '臀', '胯', '髋'], 'box': [128, 274, 164, 81]},
    'left_arm': {'name': '左上肢', 'details': ['肩部', '上臂', '肘部', '前臂'], 'keywords': ['左肩', '左胳膊', '左臂', '左肘'], 'box': [258, 99, 101, 195]},
    'right_arm': {'name': '右上肢', 'details': ['肩部', '上臂', '肘部', '前臂'], 'keywords': ['右肩', '右胳膊', '右臂', '右肘'], 'box': [61, 99, 101, 195]},
    'left_hand': {'name': '左手', 'details': ['手腕', '手掌', '手指'], 'keywords': ['左手'], 'box': [317, 274, 56, 82]},
    'right_hand': {'name': '右手', 'details': ['手腕', '手掌', '手指'], 'keywords': ['右手'], 'box': [47, 274, 56, 82]},
    'left_leg': {'name': '左下肢', 'details': ['大腿', '膝盖', '小腿', '脚踝 / 足部'], 'keywords': ['左腿', '左膝', '左脚', '左踝'], 'box': [214, 321, 85, 286]},
    'right_leg': {'name': '右下肢', 'details': ['大腿', '膝盖', '小腿', '脚踝 / 足部'], 'keywords': ['右腿', '右膝', '右脚', '右踝'], 'box': [121, 321, 85, 286]},
    'arms': {'name': '上肢（左右待确认）', 'details': ['肩部', '上臂', '肘部', '前臂'], 'keywords': ['肩', '胳膊', '臂', '肘'], 'box': [61, 99, 298, 195]},
    'hands': {'name': '手部（左右待确认）', 'details': ['手腕', '手掌', '手指'], 'keywords': ['手'], 'box': [47, 274, 326, 82]},
    'legs': {'name': '下肢（左右待确认）', 'details': ['大腿', '膝盖', '小腿', '脚踝 / 足部'], 'keywords': ['腿', '膝', '脚', '踝'], 'box': [121, 321, 178, 286]},
}


def find_part(description):
    # 先匹配带左右的词，避免“左手腕”被匹配成笼统的“手部”。
    order = ['left_hand', 'right_hand', 'left_arm', 'right_arm', 'left_leg', 'right_leg',
             'neck', 'head', 'chest', 'abdomen', 'back', 'pelvis', 'hands', 'arms', 'legs']
    for key in order:
        if any(word in description for word in PARTS[key]['keywords']):
            return key
    return None


def assess_description(description, feeling):
    urgent_words = ['胸痛', '胸口痛', '胸口疼', '呼吸困难', '喘不过气', '意识不清', '昏迷', '说话不清', '口角歪', '肢体无力', '出血不止', '吐血', '便血', '突然剧烈头痛']
    def reported(word):
        for match in re.finditer(re.escape(word),description):
            prefix=description[max(0,match.start()-10):match.start()]
            if not re.search(r'(没有|无|否认|未出现|不伴|不存在|是否|有没有)(明显的?|出现)?$',prefix):
                return True
        return False
    emergency = any(reported(word) for word in urgent_words)
    high = emergency or feeling == 'severe' or any(reported(word) for word in ['剧烈', '严重', '疼得受不了', '痛得受不了', '越来越重', '持续加重'])
    moderate = feeling == 'moderate' or any(word in description for word in ['反复', '一直', '一周', '影响睡眠'])
    return ('high' if high else 'moderate' if moderate else 'low'), emergency
