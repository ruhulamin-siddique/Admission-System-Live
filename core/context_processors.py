from .models import SystemSettings

def system_branding(request):
    """
    Makes system-wide branding settings available to all templates.
    """
    # Use a try/except to handle cases where migrations haven't run or DB isn't ready
    try:
        from .models import SystemSettings, ActivityLog
        settings, _ = SystemSettings.objects.get_or_create(id=1)
        
        # Fetch latest 5 notifications
        notifications = ActivityLog.objects.select_related('user').order_by('-timestamp')[:5]
        
        return {
            'sys_settings': settings,
            'recent_notifications': notifications,
            'notification_count': notifications.count()
        }
    except Exception:
        return {'sys_settings': None}
