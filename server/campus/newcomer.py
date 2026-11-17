from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

STEPS=(
 ('language','选择你的语言','用熟悉的语言，开始校园生活。','在右上角选择中文、English、Русский或日本語，界面和伙伴提示会随之切换。','先选好语言，我们就可以一起出发啦！','选择页面语言',None),
 ('friends','认识校园同学','先打个招呼，找到聊得来的伙伴。','进入交友广场看看同学的分享；双方互相关注后，可以私信交流。','想认识新同学吗？我带你去交友广场看看。','去认识同学','campus:friends'),
 ('help','请求或提供帮助','校园里的小事，可以一起解决。','发布取快递、代买或送物需求，也可以到接单广场帮助别人。订单进度在“我的服务”查看。','需要帮忙，还是想帮助别人？从这里开始吧。','去发布需求','campus:errand_create'),
 ('booking','安排学习与运动','给今天的计划，留一个位置。','选择自习室或球场，确认日期和时段；预约成功后，在“我的服务”查看安排。','今天想安静学习，还是去运动？一起看看空位吧。','去选择场地','campus:booking'),
 ('health','了解就医方向','需要照顾身体时，也知道下一步。','不清楚就医方向时，可以先描述不适进行导诊，再选择线上咨询或门诊预约；急诊不需要预约。','如果身体不舒服，就先看看就医方向吧。希望你每天都健健康康的。','了解导诊服务','guide'),
)


@never_cache
@require_GET
def welcome(request):
    steps=[dict(key=key,title=title,subtitle=subtitle,description=description,instruction=instruction,action=action,url=reverse(route) if route else '#journey-language') for key,title,subtitle,description,instruction,action,route in STEPS]
    return render(request,'campus/welcome.html',{'steps':steps})
