from unittest.mock import patch
from django.test import SimpleTestCase,TestCase
from django.core import signing
from django.core.cache import cache
from . import companion_weather as weather
from . import test_task_assistant as task_tests

PLACE={'name':'沈阳','admin1':'辽宁','country':'中国','latitude':41.8,'longitude':123.4}
DATA={'timezone':'Asia/Shanghai','current':{'temperature_2m':15,'apparent_temperature':14,'relative_humidity_2m':54,'weather_code':2,'wind_speed_10m':2,'time':'2026-10-17T09:00'},'daily':{'time':['2026-10-17','2026-10-18','2026-10-19'],'weather_code':[3,61,0],'temperature_2m_max':[20,21,22],'temperature_2m_min':[10,11,12],'precipitation_probability_max':[20,80,0]}}


class WeatherTests(SimpleTestCase):
    def setUp(self):cache.clear()
    def token(self):return signing.dumps({'latitude':41.8,'longitude':123.4,'label':'沈阳 · 辽宁 · 中国','offset':0},salt=weather.SALT)

    @patch('campus.companion_weather.fetch')
    def test_dalian_full_city_name_is_searched_before_same_name_villages(self,fetch):
        fetch.return_value={'results':[{'name':'大连市','admin1':'辽宁','country':'中国','latitude':38.91,'longitude':121.60,'population':7450785,'feature_code':'PPL'}]}
        result=weather.lookup('大连今天天气',[],'zh')
        self.assertEqual(fetch.call_args.args[1]['name'],'大连市')
        self.assertEqual(len(result['weather_choices']),1)
        self.assertIn('大连市 · 辽宁',result['weather_choices'][0]['label'])
        self.assertAlmostEqual(signing.loads(result['weather_choices'][0]['token'],salt=weather.SALT)['latitude'],38.91)

    @patch('campus.companion_weather.fetch')
    def test_population_ranking_happens_before_four_choice_limit(self,fetch):
        villages=[{**PLACE,'name':'Village '+str(i),'population':50} for i in range(6)]
        fetch.return_value={'results':villages+[{**PLACE,'name':'Major city','population':1000000}]}
        result=weather.lookup('weather in Example',[],'en')
        self.assertEqual(len(result['weather_choices']),4)
        self.assertTrue(result['weather_choices'][0]['label'].startswith('Major city'))

    @patch('campus.companion_weather.fetch')
    def test_missing_city_asks_without_network_or_inferred_location(self,fetch):
        for message in ('今天天气咋样呀','今天会下雨吗','What is the weather like today?','Какая погода сегодня?','今日の天気はどうですか？'):
            with self.subTest(message=message):self.assertEqual(weather.lookup(message,[],'zh')['message'],weather.ASK)
        fetch.assert_not_called()

    @patch('campus.companion_weather.fetch',return_value={'results':[PLACE,{**PLACE,'admin1':'江苏'}]})
    def test_city_followup_and_ambiguity_require_selection(self,fetch):
        result=weather.lookup('沈阳',[{'role':'user','content':'明天天气怎样'},{'role':'assistant','content':weather.ASK}],'zh')
        self.assertEqual(len(result['weather_choices']),2)
        token=result['weather_choices'][0]['token']
        self.assertEqual(signing.loads(token,salt=weather.SALT)['offset'],1)
        self.assertEqual(fetch.call_args.args[1]['name'],'沈阳')

    @patch('campus.companion_weather.fetch',return_value=DATA)
    def test_real_data_format_units_source_and_tomorrow(self,fetch):
        result=weather.chosen(self.token(),'zh')
        self.assertIn('15 °C',result['message']);self.assertIn('2 m/s',result['message'])
        self.assertEqual(result['weather_source'],'https://open-meteo.com/')
        tomorrow=weather.lookup('那明天呢',[],'zh',self.token())
        self.assertIn('2026-10-18',tomorrow['message']);self.assertIn('80%',tomorrow['message'])
        self.assertNotIn('当前天气',tomorrow['message'])
        self.assertEqual(fetch.call_count,1)

    @patch('campus.companion_weather.fetch',side_effect=weather.WeatherUnavailable)
    def test_outage_does_not_fall_back_to_fake_weather(self,fetch):
        result=weather.chosen(self.token(),'zh')
        self.assertIn('暂时没有取到天气数据',result['message'])
        self.assertNotIn('weather_source',result)

    @patch('campus.companion_weather.fetch')
    def test_tampered_or_expired_city_token_never_calls_network(self,fetch):
        result=weather.chosen(self.token()+'tampered','zh')
        self.assertIn('无效',result['message'])
        with patch('campus.companion_weather.signing.loads',side_effect=signing.SignatureExpired):weather.chosen(self.token(),'zh')
        fetch.assert_not_called()

    def test_weather_explanations_and_unrelated_followups_remain_general_chat(self):
        for message in ('为什么会下雨','Explain the weather cycle','翻译天气预报','沈阳冬天天气怎么样'):
            self.assertIsNone(weather.lookup(message,[],'zh'))
        self.assertIsNone(weather.lookup('解释一下递归',[{'role':'assistant','content':weather.ASK}],'zh'))

    @patch('campus.companion_weather.fetch',return_value={'results':[]})
    def test_unknown_city_and_unsupported_date_are_explicit(self,fetch):
        self.assertIn('没有找到',weather.lookup('天气 in Neverland',[],'zh')['message'])
        for query in ('上海下周天气','上海10月20日天气','Weather in London next Monday'):
            self.assertIn('目前支持',weather.lookup(query,[],'zh')['message'])

    @patch('campus.companion_weather.fetch',return_value=DATA)
    def test_weather_labels_are_localized(self,fetch):
        for language,label in [('en','Current conditions'),('ru','Текущая погода'),('ja','現在の天気')]:
            self.assertIn(label,weather.chosen(self.token(),language)['message'])


class WeatherEndpointTests(TestCase):
    setUp=task_tests.TaskAssistantTests.setUp
    post=task_tests.TaskAssistantTests.post
    draft=task_tests.TaskAssistantTests.draft

    @patch('campus.task_assistant.answer')
    def test_weather_missing_city_bypasses_llm_and_keeps_booking(self,model):
        draft=self.draft()
        result=self.post('chat',{'message':'今天天气咋样呀'}).json()
        self.assertEqual(result['mode'],'weather');self.assertEqual(result['message'],weather.ASK)
        self.assertEqual(self.client.get('/api/assistant/state/').json()['draft_key'],draft['draft_key'])
        model.assert_not_called()

    @patch('campus.companion_weather.fetch',return_value=DATA)
    def test_signed_city_selection_returns_weather_without_booking(self,fetch):
        cache.clear()
        token=signing.dumps({'latitude':41.8,'longitude':123.4,'label':'沈阳','offset':0},salt=weather.SALT)
        result=self.post('chat',{'selection':{'weather':token}}).json()
        self.assertEqual(result['mode'],'weather');self.assertIn('15 °C',result['message'])
        from .models import VenueBooking
        self.assertFalse(VenueBooking.objects.exists())
