import json,re,ipaddress
from django.core import signing
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from . import companion_weather as weather
from .ui_language import translate,context


@never_cache
@require_POST
def api(request):
    language=context(request)['ui_language']
    tr=lambda text:translate(text,language)
    try:
        if len(request.body)>4000:raise ValueError()
        data=json.loads(request.body)
        if not isinstance(data,dict):raise ValueError()
        if set(data)=={'locate'} and data['locate'] is True:
            forwarded=request.META.get('HTTP_X_FORWARDED_FOR','').split(',')[0].strip()
            client_ip=request.META.get('HTTP_X_REAL_IP','').strip() or forwarded or request.META.get('REMOTE_ADDR','')
            try:
                address=ipaddress.ip_address(client_ip)
                if not address.is_global:
                    host=request.get_host().split(']')[0].lstrip('[') if request.get_host().startswith('[') else request.get_host().split(':')[0]
                    try:local_host=ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
                    except ValueError:local_host=host=='localhost'
                    if not local_host:return JsonResponse({'error':tr('未获取到访客公网地址，请使用设备定位或手动选城。')},status=503)
                located=weather.ip_place(client_ip)
            except ValueError:
                return JsonResponse({'error':tr('未获取到访客公网地址，请使用设备定位或手动选城。')},status=503)
            except weather.WeatherUnavailable:
                return JsonResponse({'error':tr('网络定位服务暂不可用，可重试或使用设备定位。')},status=503)
            if weather.valid_coordinates(located.get('latitude'),located.get('longitude')):
                place=located
            else:
                choices=weather.city_matches(located['city'],language,located['country'])
                place=next((item for item in choices if weather.valid_coordinates(item.get('latitude'),item.get('longitude'))),None)
            if not place:raise weather.WeatherUnavailable()
            result=located_card({'latitude':place['latitude'],'longitude':place['longitude'],'label':located['label']},language,'ip')
            if result.status_code==200:
                payload=json.loads(result.content)
                payload['local_exit']=bool(located.get('local_exit'))
                return JsonResponse(payload)
            return result
        if set(data)=={'coordinates'}:
            coords=data['coordinates']
            if not isinstance(coords,dict) or set(coords)!={'latitude','longitude'} or not weather.valid_coordinates(coords['latitude'],coords['longitude']):raise ValueError()
            return located_card({'latitude':round(coords['latitude'],2),'longitude':round(coords['longitude'],2),'label':tr('设备位置附近')},language,'device')
        if set(data)=={'place'}:
            if not isinstance(data['place'],str) or len(data['place'])>2000:raise ValueError()
            try:place=signing.loads(data['place'],salt=weather.HOME_SALT,max_age=90*86400)
            except signing.BadSignature:return JsonResponse({'error':tr('已保存的城市已过期，请重新选择。')},status=400)
            if set(place)!={'latitude','longitude','label','source'} or not weather.valid_coordinates(place['latitude'],place['longitude']) or not isinstance(place['label'],str) or len(place['label'])>250 or place['source'] not in ('manual','ip','device'):raise ValueError()
            token=signing.dumps({key:place[key] for key in ('latitude','longitude','label')}|{'offset':0},salt=weather.SALT,compress=True)
            result=weather.chosen(token,language)
            if not result.get('weather_card'):return JsonResponse({'error':result['message']},status=503)
            return JsonResponse({'card':result['weather_card'],'place':data['place'],'source':place['source']})
        if not {'query'}<=set(data)<={'query','country','source'}:raise ValueError()
        query=data['query'];country=data.get('country','');source=data.get('source','manual')
        if not isinstance(query,str) or not 2<=len(query.strip())<=60 or not isinstance(country,str) or country and not re.fullmatch('[A-Z]{2}',country) or source not in ('manual','ip'):raise ValueError()
        city=weather.city_text(query)
        if not city:raise ValueError()
        choices=[];seen=set()
        for item in weather.city_matches(city,language,country):
            if not weather.valid_coordinates(item.get('latitude'),item.get('longitude')):continue
            label=' · '.join(dict.fromkeys(str(item.get(key,''))[:80] for key in ('name','admin1','country') if item.get(key)))
            if not label or label in seen:continue
            seen.add(label)
            choices.append({'label':label,'place':weather.home_place({'latitude':item['latitude'],'longitude':item['longitude'],'label':label},source)})
            if len(choices)==4:break
        if not choices:return JsonResponse({'error':tr('没有找到这个城市，请换用更完整的城市名或英文名。')},status=404)
        return JsonResponse({'choices':choices})
    except (ValueError,TypeError,UnicodeDecodeError):return JsonResponse({'error':tr('请求不正确，请重新选择。')},status=400)
    except (weather.WeatherUnavailable,AttributeError):return JsonResponse({'error':tr('暂时没有取到天气数据，请稍后重试；我不会猜测天气。')},status=503)


def located_card(place, language, source):
    signed=weather.home_place(place,source)
    token=signing.dumps({**place,'offset':0},salt=weather.SALT,compress=True)
    result=weather.chosen(token,language)
    if not result.get('weather_card'):return JsonResponse({'error':result['message']},status=503)
    return JsonResponse({'card':result['weather_card'],'place':signed,'source':source})
