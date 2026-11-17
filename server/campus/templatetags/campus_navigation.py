from django import template
from campus.navigation import page_navigation
register=template.Library()
@register.simple_tag(takes_context=True)
def navigation_for_page(context):
    request=context.get('request')
    return page_navigation(request) if request else None
