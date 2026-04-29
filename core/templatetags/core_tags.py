from django import template
from core.access_registry import ACCESS_REGISTRY

register = template.Library()

@register.simple_tag(takes_context=True)
def has_access(context, module, task):
    """
    Template tag to check if the current user has access to a specific task.
    Usage: {% has_access 'students' 'add_student' as can_add %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    
    if request.user.is_superuser:
        return True
        
    if not hasattr(request.user, 'profile'):
        return False
        
    return request.user.profile.has_access(module, task)

@register.simple_tag(takes_context=True)
def can_see_student(context, student):
    """
    Checks if the user can see a specific student record based on departmental scoping.
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    
    if request.user.is_superuser:
        return True

    profile = getattr(request.user, 'profile', None)
    if not profile:
        return False
        
    # If no scope is set, user can see all
    if not profile.department_scope:
        return True
        
    # Check if student's program matches the user's scope
    return student.program == profile.department_scope

@register.filter
def replace_underscore(value):
    """Replaces underscores with spaces."""
    if isinstance(value, str):
        return value.replace('_', ' ').capitalize()
    return value

@register.filter
def multiply(value, arg):
    return float(value) * float(arg)

@register.filter
def divide(value, arg):
    return float(value) / float(arg) if float(arg) != 0 else 0

@register.filter
def get_item(dictionary, key):
    """Retrieves a value from a dictionary by key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return ""

@register.filter(name='getattribute')
def getattribute(value, arg):
    """Gets an attribute of an object dynamically from a string name"""
    if hasattr(value, str(arg)):
        return getattr(value, arg)
    return ""
