"""逐步收集位置和症状；AI 只选择问题，不诊断。"""
from .parts import PARTS, assess_description
from .knowledge import retrieve, load_knowledge
from .ollama_client import choose_question, ModelUnavailable, MODEL

ANSWER_LABELS = {'side': '左右', 'detail': '具体部位', 'location': '更具体的位置', 'sensation': '感受',
                 'duration': '持续时间', 'severity': '自述程度', 'associated': '其他表现', 'trigger': '变化或诱因', 'history': '既往病史'}
LOCATION_ALIASES={'膝盖内侧':['内侧','里侧','内边','里面'],'膝盖外侧':['外侧','外边'],
                  '膝盖前侧':['前侧','前面'],'膝盖后侧':['后侧','后面'],
                  '右上腹':['右上腹','右上边'],'左上腹':['左上腹','左上边'],
                  '右下腹':['右下腹','右下边'],'左下腹':['左下腹','左下边']}


def locate_answer(text, choices):
    # 多个位置、否定或不确定时，保留原话并等待手动确认。
    if not text or any(word in text for word in ['不是','不确定','说不清','两侧','范围比较大']):
        return None
    matches=[choice for choice in choices if any(alias in text for alias in LOCATION_ALIASES.get(choice['value'],[choice['value']]))]
    return matches[0] if len(matches)==1 else None


def options(values):
    return [{'value': value, 'label': value} for value in values]


def question(key, text, choices, help_text='不确定可以选择“说不清”，也可以用自己的话回答。', **kwargs):
    return {'id': key, 'key': key.split(':')[0], 'text': text, 'choices': options(choices), 'help': help_text, **kwargs}


def fine_locations(part, detail):
    # 坐标按人体右侧正面给出；前端按左右和前后镜像。
    if part == 'abdomen':
        y = {'上腹': 204, '下腹': 264, '肚脐周围': 235}.get(detail, 235)
        return [{'value': label, 'label': label, 'point': [x, y], 'mirror': False}
                for label, x in zip({'上腹': ['右上腹', '上腹正中', '左上腹'],
                                    '下腹': ['右下腹', '下腹正中', '左下腹']}.get(detail, ['肚脐右侧', '肚脐周围', '肚脐左侧']), [181, 210, 239])]
    if part == 'chest':
        x = {'左胸': 238, '右胸': 180, '胸部中间': 210}.get(detail, 210)
        return [{'value': label, 'label': label, 'point': [x,y], 'mirror': False}
                for label,y in [('靠近锁骨',122),('胸部中段',151),('靠近下缘',178)]]
    if part.endswith('_leg'):
        if detail == '膝盖':
            return [{'value': label, 'label': label, 'point': point, 'mirror': True, 'back': back}
                    for label,point,back in [('膝盖前侧',[164,421],False),('膝盖内侧',[180,421],False),
                                             ('膝盖外侧',[147,421],False),('膝盖后侧',[164,421],True)]]
        y = {'大腿':372,'小腿':491,'脚踝 / 足部':573}.get(detail,421)
        return [{'value': label,'label':label,'point':[x,y],'mirror':True}
                for label,x in [('内侧',177),('中间',163),('外侧',147)]]
    if part.endswith('_arm'):
        x,y = {'肩部':(142,123),'上臂':(126,162),'肘部':(108,210),'前臂':(91,250)}.get(detail,(126,162))
        return [{'value':label,'label':label,'point':[x+dx,y+dy],'mirror':True}
                for label,dx,dy in [('靠上侧',0,-10),('靠中间',0,0),('靠下侧',-4,10)]]
    if part.endswith('_hand'):
        x,y = {'手腕':(84,287),'手掌':(80,314),'手指':(77,336)}.get(detail,(80,314))
        return [{'value':label,'label':label,'point':[x+dx,y],'mirror':True}
                for label,dx in [('靠拇指一侧',7),('中间',0),('靠小指一侧',-7)]]
    points = {'head': [('左侧',[230,41]),('中间',[210,48]),('右侧',[190,41])],
              'neck': [('左侧',[228,97]),('中间',[210,97]),('右侧',[192,97])],
              'back': [('左侧',[189,230]),('正中',[210,230]),('右侧',[231,230])],
              'pelvis': [('左侧',[241,310]),('中间',[210,310]),('右侧',[179,310])]}
    return [{'value':label,'label':label,'point':point,'mirror':False,'back':part=='back'} for label,point in points.get(part,[])]


def validate_answers(answers):
    if not isinstance(answers, dict) or len(answers) > len(ANSWER_LABELS):
        raise ValueError('追问记录格式不正确。')
    if any(key not in ANSWER_LABELS or not isinstance(value,str) or not 1 <= len(value.strip()) <= 200 for key,value in answers.items()):
        raise ValueError('每条回答请控制在 200 字以内。')
    return {key:value.strip() for key,value in answers.items()}


def candidates_for(part, detail, answers, duration):
    if part in ('arms','hands','legs') and 'side' not in answers:
        return [question('side','先确认一下，是身体左侧还是右侧？',['左侧','右侧','两侧都有','说不清'])]
    if not detail and 'detail' not in answers:
        return [question('detail','在'+PARTS[part]['name']+'中，具体哪里不舒服？',PARTS[part]['details']+['说不清'])]
    if 'location' not in answers:
        choices = fine_locations(part,detail)
        for choice in choices:
            choice['aliases']=LOCATION_ALIASES.get(choice['value'],[choice['value']])
        q=question('location','我们再靠近一点：不舒服的位置更接近哪里？',[])
        q['choices']=choices+options(['范围比较大','说不清'])
        return [q]
    if 'sensation' not in answers:
        choices=['隐痛 / 酸痛','刺痛','胀痛','麻木','肿胀','其他 / 说不清']
        if part in ('chest','abdomen'):
            choices=['隐痛','刺痛','胀 / 堵的感觉','灼热感','其他 / 说不清']
        return [question('sensation','这个位置主要是什么感觉？',choices)]
    if not duration and 'duration' not in answers:
        return [question('duration','这种不适大概持续多久了？',['刚出现','不到一天','两三天','一周左右','更久 / 反复出现','说不清'])]
    if 'severity' not in answers:
        return [question('severity','现在不适对活动或休息的影响怎样？',['还能正常活动','活动或睡眠受到影响','很明显，想请医生确认','说不清'],help_text='感受轻重不能单独判断病情是否危险。')]
    if 'associated' not in answers:
        if part in ('abdomen','pelvis'):
            return [question('associated:stomach','除了这个位置不舒服，还有恶心、呕吐或排便变化吗？',['没有明显其他表现','恶心 / 呕吐','腹泻 / 排便变化','有其他表现','说不清'])]
        if part in ('chest','neck','head'):
            return [question('associated:general','同时还有发热、咳嗽、头晕或其他不适吗？',['没有明显其他表现','发热 / 咳嗽','头晕','有其他表现','说不清'])]
        return [question('associated:swelling','附近有没有肿胀、发红、麻木或活动困难？',['没有明显其他表现','肿胀 / 发红','麻木','活动困难','有其他表现','说不清']),
                question('associated:injury','开始不舒服之前，有没有摔倒、碰撞或扭伤？',['没有明显外伤','摔倒 / 碰撞','扭伤','说不清'])]
    if 'trigger' not in answers:
        return [question('trigger:movement','什么情况下会更明显，比如活动、按压或休息时？',['活动时更明显','按压时更明显','休息时也不舒服','没有明显规律','说不清']),
                question('trigger:change','这段时间不适有没有变化？',['差不多','时好时坏','越来越明显','有所减轻','说不清'])]
    if 'history' not in answers:
        return [question('history','以前有过什么老病症，或者正在长期吃药吗？',['没有已知既往病史','有老病症，需要补充','正在长期用药，需要补充','不清楚'],help_text='请用自己的话说明医生诊断过的病症、长期用药或药物过敏；不要填写姓名或证件号码。')]
    return []


def interview_step(part, detail, description, duration, feeling, answers):
    # “说不清”继续追问症状，但不编造定位；不按否定描述强行选左右。
    side=answers.get('side','')
    if part in ('arms','hands','legs') and (('左' in side) != ('右' in side)) and not any(word in side for word in ['不确定','说不清','不是','两侧']):
        part = ('left_' if '左' in side else 'right_')+{'arms':'arm','hands':'hand','legs':'leg'}[part]
    raw_detail=answers.get('detail','')
    matched=[value for value in PARTS[part]['details'] if value in raw_detail]
    if len(matched)==1 and not any(word in raw_detail for word in ['不是','说不清','不确定']):
        detail=matched[0]
    combined=description+' '+ ' '.join(answers.values())
    level, emergency=assess_description(combined,feeling)
    sources=retrieve(part,combined+' '+detail)
    source_links=[{key:source[key] for key in ('title','url','attribution')} for source in sources]
    focus=locate_answer(answers.get('location',''),fine_locations(part,detail))
    base={'part':part,'detail':detail,'focus':focus,'sources':source_links,'knowledge_count':len(load_knowledge()['records']),
          'answered':len(answers),'total':8,'level':level,'emergency':emergency}
    if emergency:
        return {**base,'phase':'urgent','engine':'safety','message':'描述涉及紧急表现。若正在发生，请立即寻求急诊或拨打 120，不要等待追问或医生信箱。'}
    candidates=candidates_for(part,detail,answers,duration)
    if not candidates:
        rows=[{'label':'主要描述','value':description},{'label':'部位','value':PARTS[part]['name']+((' · '+detail) if detail else '')}]
        rows += [{'label':ANSWER_LABELS[key],'value':value} for key,value in answers.items()]
        if duration: rows.append({'label':'持续时间','value':duration})
        return {**base,'phase':'review','engine':'local','summary':rows,'message':'信息已整理，请确认后继续。定位是你描述的位置，不代表病灶或诊断。'}
    engine='ollama'
    message='本地 AI 正在参考资料整理下一问。'
    try:
        chosen=choose_question(candidates,{'part':PARTS[part]['name'],'detail':detail,'description':description,'duration':duration,'answers':answers},sources)
        selected=next(q for q in candidates if q['id']==chosen)
    except ModelUnavailable as error:
        engine='fallback'; message=str(error); selected=candidates[0]
    return {**base,'phase':'question','engine':engine,'model':MODEL,'question':selected,'message':message}
