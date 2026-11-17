"""项目中的演示科室，与患者端科室导航保持一致。"""
DEPARTMENTS = [
    ('general', '全科医学科'), ('neuro', '神经内科'), ('resp', '呼吸内科'),
    ('digest', '消化内科'), ('skin', '皮肤科'), ('bone', '骨科'),
    ('ent', '耳鼻喉科'), ('eye', '眼科'), ('child', '儿科'), ('urgent', '急诊科'),
]
DEPARTMENT_NAMES = dict(DEPARTMENTS)


def basic_department(part, description, emergency=False, age=None):
    if emergency:
        return 'urgent'
    if age is not None and age < 14:
        return 'child'
    if any(word in description for word in ('眼睛', '视力', '眼痛')):
        return 'eye'
    if any(word in description for word in ('耳鸣', '耳朵', '鼻塞', '咽喉', '嗓子')):
        return 'ent'
    if any(word in description for word in ('红疹', '皮肤', '瘙痒')):
        return 'skin'
    if part == 'head':
        return 'neuro'
    if part == 'chest':
        return 'resp'
    if part == 'abdomen':
        return 'digest'
    if part.endswith(('_leg', '_arm', '_hand')) or part in ('legs', 'arms', 'hands', 'back'):
        return 'bone'
    return 'general'
