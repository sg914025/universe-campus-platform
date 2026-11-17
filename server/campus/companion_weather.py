"""Explicit city lookup and bounded weather data, independent of LLM guesses."""
import hashlib,ipaddress,json,math,re
from urllib.parse import quote,urlencode
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from django.core import signing
from django.core.cache import cache
from .ui_language import translate

ASK='想查询哪个城市的天气？告诉我城市名就可以，不需要详细地址。'
SOURCE='https://open-meteo.com/'
SALT='universe-weather-v1'
HOME_SALT='universe-home-weather-v1'


def home_place(place,source='manual'):
    return signing.dumps({key:place[key] for key in ('latitude','longitude','label')}|{'source':source},salt=HOME_SALT,compress=True)


class WeatherUnavailable(Exception):pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def ip_place(value):
    """Explicit network lookup. Local development resolves its own network exit.

    Fixed HTTPS providers only; no raw IP is returned or persisted. Author: UniVerse Team.
    """
    try:
        address=ipaddress.ip_address(value)
        local=address.is_loopback or address.is_private and not address.is_link_local
        if not address.is_global and not local:raise ValueError()
    except ValueError as exc:raise WeatherUnavailable() from exc
    encoded='' if local else quote(str(address),safe='')
    providers=(
        ('https://get.geojs.io/v1/ip/geo'+('/'+encoded if encoded else '')+'.json','GeoJS'),
        ('https://ipwho.is/'+encoded,'ipwho.is'),
    )
    for url,provider in providers:
        try:
            request=Request(url,headers={'User-Agent':'UniVerse-Campus/1.0','Accept':'application/json'})
            with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=4) as response:raw=response.read(50001)
            if len(raw)>50000:continue
            data=json.loads(raw)
            if not isinstance(data,dict) or data.get('success') is False:continue
            city=data.get('city');region=data.get('region');country=data.get('country')
            if not isinstance(city,str) or not city.strip():continue
            lat=float(data.get('latitude'));lon=float(data.get('longitude'))
            if not valid_coordinates(lat,lon):continue
            label=' · '.join(dict.fromkeys(item.strip()[:80] for item in (city,region,country) if isinstance(item,str) and item.strip()))
            code=data.get('country_code','')
            return {'label':label,'city':city.strip(),'country':code if isinstance(code,str) and re.fullmatch('[A-Z]{2}',code) else '',
                    'latitude':round(lat,2),'longitude':round(lon,2),'provider':provider,'local_exit':local}
        except (OSError,ValueError,TypeError,KeyError):continue
    raise WeatherUnavailable()


def fetch(endpoint,params):
    urls={'geo':'https://geocoding-api.open-meteo.com/v1/search','forecast':'https://api.open-meteo.com/v1/forecast'}
    request=Request(urls[endpoint]+'?'+urlencode(params),headers={'User-Agent':'UniVerse-Campus/1.0','Accept':'application/json'})
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=7) as response:raw=response.read(300001)
        if len(raw)>300000:raise ValueError()
        data=json.loads(raw)
        if not isinstance(data,dict) or data.get('error'):raise ValueError()
        return data
    except (OSError,ValueError,TypeError) as exc:raise WeatherUnavailable() from exc


def weather_question(text):
    if re.search(r'为什么|原理|解释|翻译|气候|冬天|夏天|why |explain|translate|climate|in winter|in summer|почему|объясн|перевед|климат|зимой|летом|なぜ|翻訳|説明|気候',text.lower()):return False
    return bool(re.search(r'天气|气温|下雨|下雪|weather|temperature|rain|snow|погод|температур|дожд|снег|天気|気温|雨が|雪が',text.lower()))


def city_text(text):
    text=text.strip().strip('？！?!.。')
    aliases={'北京':('北京','beijing','пекин'),'上海':('上海','shanghai','шанха'),'沈阳':('沈阳','shenyang','шэньян'),'大连':('大连','dalian','далян'),'广州':('广州','guangzhou','гуанчжоу'),'深圳':('深圳','shenzhen','шэньчжэнь'),'Moscow':('莫斯科','moscow','москв','モスクワ'),'Saint Petersburg':('圣彼得堡','saint petersburg','санкт-петербург'),'Tokyo':('东京','tokyo','токио','東京')}
    for city,terms in aliases.items():
        if any(term in text.lower() for term in terms):return city
    english=re.search(r'(?:\bin\b|\bfor\b|\bв\b)\s+(.+)',text,re.I)
    if english:text=english[1]
    text=re.sub(r'帮我|请问|查一下|查询|请|今天|明天|后天|现在|目前|天气|气温|怎么样|咋样|怎样|如何|会不会|会|下雨|下雪|吗|呀|的|今日|明日|明後日|天気|気温|どう|ですか|は|の','',text)
    text=re.sub(r'\b(today|tomorrow|day after tomorrow|weather|temperature|please|what|is|the|like|сегодня|завтра|послезавтра|погода|какая)\b','',text,flags=re.I).strip(' ,，:：?？')
    text=re.sub(r'\s+',' ',text)
    return text if re.fullmatch(r'[^\W\d_][\w\s\-\u3000-\u9fff]{1,59}',text,re.UNICODE) else ''


def day_offset(text):
    text=text.lower()
    if any(item in text for item in ('后天','day after tomorrow','послезавтра','明後日')):return 2
    return 1 if any(item in text for item in ('明天','tomorrow','завтра','明日')) else 0


def response(message,language,**extra):
    return {'phase':'chat','mode':'weather','model':'Open-Meteo','message':translate(message,language),**extra}


def city_matches(city,language,country=''):
    params={'count':20,'language':language,'format':'json'}
    if country:params['countryCode']=country
    # Two-character Chinese searches may match village names exactly and omit
    # the actual city named e.g. 大连市. Try the full municipal name first.
    if re.fullmatch(r'[\u4e00-\u9fff]{2,6}',city) and not city.endswith(('市','县','区')):
        try:
            full=fetch('geo',{**params,'name':city+'市'}).get('results',[])
            exact=[place for place in full if place.get('name')==city+'市' and place.get('feature_code') in ('PPL','PPLC','PPLA','PPLA2')]
            if exact:return sorted(exact,key=lambda place:place.get('population') or 0,reverse=True)
        except WeatherUnavailable:pass
    places=fetch('geo',{**params,'name':city}).get('results',[])
    # Sort before truncating, so populous cities do not disappear behind small
    # settlements that happen to share a name.
    return sorted(places,key=lambda place:(place.get('population') or 0,place.get('feature_code') in ('PPLC','PPLA','PPLA2')),reverse=True)


def lookup(message,history,language,token=''):
    """Return None for ordinary chat; never infer a city from account/IP/GPS."""
    previous=next((item['content'] for item in reversed(history) if item['role']=='assistant'),'')
    awaiting=previous in [translate(ASK,code) for code in ('zh','en','ru','ja')]
    explicit=weather_question(message)
    following=bool(token and re.fullmatch(r'(那)?(明天|后天|今天)(呢)?[？?]?|tomorrow[?]?|завтра[?]?|明日[は?？]?',message.strip(),re.I))
    if following:explicit=True
    if not explicit and not awaiting:return None
    # An unrelated follow-up after a city question must still reach normal chat.
    if awaiting and not explicit and (len(message)>60 or re.search(r'解释|翻译|预约|explain|translate|book',message,re.I)):return None
    offset=day_offset(message)
    if awaiting and not explicit:
        original=next((item['content'] for item in reversed(history) if item['role']=='user' and weather_question(item['content'])),'')
        offset=day_offset(original)
    city='' if following else city_text(message)
    # Limit supported dates instead of pretending a requested distant forecast is today.
    if re.search(r'下周|下个月|昨天|去年|今年|明年|\d+月|\d+[-/.]\d+|周[一二三四五六日天]|星期|next week|next month|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|на следующей неделе|вчера|来週|来月|昨日',message,re.I):
        return response('目前支持今天、明天和后天的天气，请指定其中一天。',language)
    if not city:
        return chosen(token,language,offset) if token else response(ASK,language)
    try:
        choices=[];seen=set()
        for place in city_matches(city,language):
            latitude=place.get('latitude');longitude=place.get('longitude')
            if not valid_coordinates(latitude,longitude):continue
            label=' · '.join(dict.fromkeys(str(place.get(key,''))[:80] for key in ('name','admin1','country') if place.get(key)))
            if not label or label in seen:continue
            seen.add(label)
            token=signing.dumps({'latitude':latitude,'longitude':longitude,'label':label,'offset':offset},salt=SALT,compress=True)
            choices.append({'label':label,'token':token})
            if len(choices)==4:break
        if not choices:return response('没有找到这个城市，请换用更完整的城市名或英文名。',language)
        return response('请选择你要查询的城市，避免同名地点混淆。',language,weather_choices=choices)
    except (WeatherUnavailable,TypeError,AttributeError):return response('暂时没有取到天气数据，请稍后重试；我不会猜测天气。',language)


def valid_coordinates(lat,lon):
    return all(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) for value in (lat,lon)) and -90<=lat<=90 and -180<=lon<=180


def conditions(code):
    if code==0:return '晴'
    if code in (1,2):return '晴间多云'
    if code==3:return '阴'
    if code in (45,48):return '雾'
    if code in (51,53,55,56,57):return '毛毛雨'
    if code in (61,63,65,66,67):return '雨'
    if code in (71,73,75,77):return '雪'
    if code in (80,81,82):return '阵雨'
    if code in (85,86):return '阵雪'
    if code in (95,96,99):return '雷暴'
    return '天气状况未知'


def chosen(token,language,offset_override=None):
    try:
        place=signing.loads(token,salt=SALT,max_age=900)
        if set(place)!={'latitude','longitude','label','offset'} or not valid_coordinates(place['latitude'],place['longitude']) or place['offset'] not in (0,1,2):raise ValueError()
    except (signing.BadSignature,ValueError,TypeError):return response('城市选择已过期或无效，请重新询问天气。',language)
    tr=lambda text:translate(text,language)
    try:
        params={'latitude':place['latitude'],'longitude':place['longitude'],'current':'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m','daily':'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max','forecast_days':3,'timezone':'auto','wind_speed_unit':'ms'}
        key='universe-weather:'+hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest()
        data=cache.get(key)
        if data is None:data=fetch('forecast',params);cache.set(key,data,300)
        daily=data['daily'];offset=place['offset'] if offset_override is None else offset_override;day=daily['time'][offset]
        def number(value):
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError()
            return f'{value:g}'
        low=number(daily['temperature_2m_min'][offset]);high=number(daily['temperature_2m_max'][offset])
        lines=[place['label'],tr('预报日期')+'：'+day+' · '+str(data['timezone'])]
        if offset==0:
            current=data['current']
            lines.append(tr('当前天气')+'：'+tr(conditions(current['weather_code']))+'，'+number(current['temperature_2m'])+' °C')
            lines.append(tr('体感温度')+'：'+number(current['apparent_temperature'])+' °C · '+tr('湿度')+'：'+number(current['relative_humidity_2m'])+'% · '+tr('风速')+'：'+number(current['wind_speed_10m'])+' m/s')
            lines.append(tr('数据时间')+'：'+str(current['time']).replace('T',' '))
        lines.append(tr('当日预报')+'：'+tr(conditions(daily['weather_code'][offset]))+' · '+low+'–'+high+' °C')
        probability=daily['precipitation_probability_max'][offset]
        if probability is not None:lines.append(tr('最高降水概率')+'：'+number(probability)+'%')
        lines.append(tr('天气数据为模型估算与预报，供出行参考。'))
        card={'location':place['label'],'temperature':number(data['current']['temperature_2m']),'condition':tr(conditions(data['current']['weather_code'])),'low':low,'high':high,'rain':number(probability) if probability is not None else None,'time':str(data['current']['time']).replace('T',' '),'timezone':str(data['timezone'])}
        return response('\n'.join(lines),language,weather_source=SOURCE,weather_token=token,weather_card=card,home_place=home_place(place))
    except (WeatherUnavailable,KeyError,ValueError,TypeError,IndexError):return response('暂时没有取到天气数据，请稍后重试；我不会猜测天气。',language)
