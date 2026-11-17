from django.utils import translation
from django.utils.cache import patch_vary_headers
from .ui_language import context


class InterfaceLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code = context(request)['ui_language']
        request.LANGUAGE_CODE = 'zh-hans' if code == 'zh' else code
        with translation.override(request.LANGUAGE_CODE):
            response = self.get_response(request)
        response.headers['Content-Language'] = request.LANGUAGE_CODE
        patch_vary_headers(response, ['Cookie'])
        return response
