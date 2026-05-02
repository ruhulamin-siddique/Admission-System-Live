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
@register.filter
def split(value, arg):
    return str(value).split(arg) if value is not None else []


@register.filter
def replace(value, arg):
    if "," not in arg:
        return value
    old, new = arg.split(",", 1)
    return str(value).replace(old, new)
