from django import template

register = template.Library()


@register.filter
def dotted_get(obj, path):
    value = obj
    for part in str(path).split('.'):
        value = getattr(value, part, '')
        if value is None:
            return ''
    return value

