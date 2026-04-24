from .models import SystemSettings

def system_branding(request):
    """
    Makes system-wide branding settings available to all templates.
    """
    # Use a try/except to handle cases where migrations haven't run or DB isn't ready
    try:
        settings, _ = SystemSettings.objects.get_or_create(id=1)
        return {'sys_settings': settings}
    except Exception:
        return {'sys_settings': None}
