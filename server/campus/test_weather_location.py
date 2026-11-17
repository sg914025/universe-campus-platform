"""Network exit and explicit device location regressions. Author: UniVerse Team."""
import json
from unittest.mock import patch, MagicMock
from django.core import signing
from django.test import TestCase
from . import companion_weather as weather


class WeatherLocationTests(TestCase):
    def post(self, data, **extra):
        return self.client.post('/api/home/weather/', json.dumps(data), content_type='application/json', **extra)

    @patch('campus.home_weather.weather.chosen', return_value={'weather_card': {'location': 'Dalian'}})
    @patch('campus.home_weather.weather.city_matches', side_effect=AssertionError('No redundant geocoding'))
    @patch('campus.home_weather.weather.ip_place', return_value={'label': 'Dalian', 'city': 'Dalian', 'country': 'CN', 'latitude': 38.9, 'longitude': 121.6, 'local_exit': True})
    def test_localhost_uses_exit_coordinates(self, lookup, city, chosen):
        result = self.post({'locate': True}, HTTP_HOST='127.0.0.1:8000', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['local_exit'])
        self.assertNotIn('127.0.0.1', result.content.decode())
        lookup.assert_called_once_with('127.0.0.1')

    @patch('campus.home_weather.weather.ip_place')
    def test_public_deployment_never_uses_server_city_for_missing_visitor(self, lookup):
        result = self.post({'locate': True}, HTTP_HOST='testserver', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(result.status_code, 503)
        lookup.assert_not_called()

    @patch('campus.home_weather.weather.chosen', return_value={'weather_card': {'location': '附近'}})
    def test_device_location_rounded_signed_and_invalid_rejected(self, chosen):
        response = self.post({'coordinates': {'latitude': 38.912345, 'longitude': 121.654321}})
        self.assertEqual(response.status_code, 200)
        token = signing.loads(response.json()['place'], salt=weather.HOME_SALT)
        self.assertEqual((token['latitude'], token['longitude'], token['source']), (38.91, 121.65, 'device'))
        for coords in ({'latitude': 100, 'longitude': 2}, {'latitude': True, 'longitude': 2}, {'latitude': float('nan'), 'longitude': 2}):
            self.assertEqual(self.post({'coordinates': coords}).status_code, 400)

    @patch('campus.companion_weather.build_opener')
    def test_geojs_local_exit_endpoint_and_direct_coordinates(self, opener):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'city': 'Dalian', 'country_code': 'CN', 'country': 'China', 'latitude': '38.91', 'longitude': '121.65'}).encode()
        opener.return_value.open.return_value = response
        result = weather.ip_place('127.0.0.1')
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://get.geojs.io/v1/ip/geo.json')
        self.assertEqual(result['latitude'], 38.91)
        self.assertNotIn('ip', result)

    @patch('campus.companion_weather.build_opener')
    def test_provider_fallback_and_invalid_response(self, opener):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'city': 'Dalian', 'latitude': 38.9, 'longitude': 121.6}).encode()
        opener.return_value.open.side_effect = [OSError('timeout'), response]
        self.assertEqual(weather.ip_place('8.8.8.8')['provider'], 'ipwho.is')
        self.assertEqual(opener.return_value.open.call_count, 2)
