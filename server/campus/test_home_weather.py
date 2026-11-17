import json
from unittest.mock import patch
from django.core import signing
from django.core.cache import cache
from django.test import TestCase,Client
from . import companion_weather as weather
from .test_companion_weather import DATA,PLACE


class HomeWeatherTests(TestCase):
    def setUp(self):cache.clear()
    def post(self,data):return self.client.post('/api/home/weather/',json.dumps(data),content_type='application/json')

    def test_home_has_public_weather_and_ip_is_opt_in(self):
        result=self.client.get('/')
        self.assertContains(result,'home-weather-report')
        self.assertContains(result,'weather-ip')
        self.assertContains(result,'GeoJS')

    @patch('campus.companion_weather.fetch',return_value={'results':[PLACE]})
    def test_city_search_is_read_only_and_tokens_are_signed(self,fetch):
        result=self.post({'query':'沈阳'}).json()
        self.assertIn('choices',result)
        place=signing.loads(result['choices'][0]['place'],salt=weather.HOME_SALT)
        self.assertEqual(place['label'],'沈阳 · 辽宁 · 中国')
        self.assertEqual(place['source'],'manual')
        self.assertNotIn('ip',place)

    @patch('campus.companion_weather.fetch',return_value={'results':[PLACE]})
    def test_ip_city_uses_country_filter_without_receiving_visitors_ip(self,fetch):
        result=self.post({'query':'Shenyang','country':'CN','source':'ip'}).json()
        self.assertTrue(all(call.args[1]['countryCode']=='CN' for call in fetch.call_args_list))
        self.assertEqual(signing.loads(result['choices'][0]['place'],salt=weather.HOME_SALT)['source'],'ip')
        self.assertEqual(self.post({'query':'Shenyang','ip':'1.2.3.4'}).status_code,400)

    @patch('campus.companion_weather.fetch',return_value=DATA)
    def test_saved_city_refresh_produces_structured_card(self,fetch):
        token=weather.home_place({'latitude':41.8,'longitude':123.4,'label':'沈阳'},'ip')
        result=self.post({'place':token}).json()
        self.assertEqual(result['card']['temperature'],'15')
        self.assertEqual(result['card']['location'],'沈阳')
        self.assertEqual(result['source'],'ip')

    @patch('campus.home_weather.weather.chosen',return_value={'weather_card':{'location':'沈阳','temperature':'15'}})
    @patch('campus.home_weather.weather.city_matches',return_value=[PLACE])
    @patch('campus.home_weather.weather.ip_place',return_value={'label':'沈阳 · 辽宁 · 中国','city':'Shenyang','country':'CN'})
    def test_ip_location_uses_proxy_client_address(self,ip_place,city_matches,chosen):
        result=self.client.post('/api/home/weather/',json.dumps({'locate':True}),content_type='application/json',HTTP_X_REAL_IP='8.8.8.8')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['source'],'ip')
        ip_place.assert_called_once_with('8.8.8.8')
        self.assertNotIn('8.8.8.8',result.content.decode())

    @patch('campus.companion_weather.fetch')
    def test_tampered_or_expired_tokens_and_raw_coordinates_are_rejected(self,fetch):
        self.assertEqual(self.post({'place':'bad'}).status_code,400)
        self.assertEqual(self.post({'latitude':1,'longitude':2}).status_code,400)
        token=weather.home_place({'latitude':41.8,'longitude':123.4,'label':'沈阳'})
        with patch('campus.home_weather.signing.loads',side_effect=signing.SignatureExpired):
            self.assertEqual(self.post({'place':token}).status_code,400)
        fetch.assert_not_called()

    def test_csrf_and_method_checks(self):
        self.assertEqual(self.client.get('/api/home/weather/').status_code,405)
        self.assertEqual(Client(enforce_csrf_checks=True).post('/api/home/weather/',{'query':'沈阳'}).status_code,403)

    @patch('campus.companion_weather.fetch',side_effect=weather.WeatherUnavailable)
    def test_outage_returns_error_instead_of_weather(self,fetch):
        self.assertEqual(self.post({'query':'Example'}).status_code,503)
