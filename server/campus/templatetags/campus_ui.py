from django import template
from campus.ui_language import translate

register = template.Library()


@register.simple_tag(takes_context=True)
def tr(context, text):
    return translate(text, context.get('ui_language', 'zh'))


@register.simple_tag(takes_context=True)
def ui(context, key):
    from campus.ui_language import UI_KEYS
    return translate(UI_KEYS.get(key, ''), context.get('ui_language', 'zh'))


@register.filter
def ui_text(text, language):
    return translate(text, language)


@register.simple_tag(takes_context=True)
def localize_forms(context):
    from django.forms import BaseForm, ModelChoiceField
    from django.utils.html import conditional_escape
    from django.utils.safestring import mark_safe
    code = context.get('ui_language', 'zh')
    if code == 'zh':
        return ''
    def choices(items):
        for value, label in items:
            yield value, list(choices(label)) if isinstance(label, (tuple, list)) else translate(label, code)
    for value in context.flatten().values():
        if not isinstance(value, BaseForm) or getattr(value, '_campus_language', None) == code:
            continue
        value._campus_language = code
        for field in value.fields.values():
            field.label = translate(field.label, code)
            # Custom help can contain lists from Django password validators.
            if field.help_text:
                from campus.ui_language import translate_html
                field.help_text = mark_safe(translate_html(str(conditional_escape(field.help_text)), code))
            for name in ('placeholder', 'title', 'aria-label'):
                if name in field.widget.attrs:
                    field.widget.attrs[name] = translate(field.widget.attrs[name], code)
            if isinstance(field, ModelChoiceField):
                if field.empty_label:
                    field.empty_label = translate(field.empty_label, code)
                if field.queryset.model._meta.label == 'triage.Department':
                    original = field.label_from_instance
                    field.label_from_instance = lambda obj, fn=original: translate(fn(obj), code)
            elif hasattr(field, 'choices'):
                field.choices = list(choices(field.choices))
        # Error messages are display text; input values stay unchanged.
        if value.is_bound:
            from django.forms.utils import ErrorList
            for key, errors in value.errors.items():
                value._errors[key] = ErrorList([translate(error, code) for error in errors])
    return ''
