from 主页.views import index as home_index

def index(request):
    return home_index(request, section='daily')
