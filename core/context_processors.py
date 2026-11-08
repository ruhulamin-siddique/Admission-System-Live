from .models import SystemSettings

def system_branding(request):
    """
    Makes system-wide branding settings available to all templates.
    """
    # Use a try/except to handle cases where migrations haven't run or DB isn't ready
    try:
        from .models import SystemSettings, ActivityLog
        settings, _ = SystemSettings.objects.get_or_create(id=1)
        
        # Dynamic Notification Logic: User / Staff Matrix Wise
        if request.user.is_superuser:
            # Superusers see everything
            notifications = ActivityLog.objects.select_related('user').order_by('-timestamp')[:5]
        elif request.user.is_authenticated and hasattr(request.user, 'profile'):
            profile = request.user.profile
            from django.db.models import Q
            
            # Base query: Own activities OR System alerts
            query = Q(user=request.user) | Q(is_system_alert=True)
            
            # Scoped notifications (if profile has department_scope)
            if profile.department_scope:
                query |= Q(scope=profile.department_scope)
            elif profile.role:
                # If no scope, but has a role, maybe show everything in their module?
                # For now, stick to System Alerts + Own Actions if no scope
                pass
                
            notifications = ActivityLog.objects.filter(query).select_related('user').order_by('-timestamp')[:5]
        else:
            notifications = ActivityLog.objects.none()
        
        # Pending User Registrations Count for authorized management staff
        pending_user_count = 0
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            if request.user.is_superuser or request.user.profile.has_access('security', 'manage_users'):
                from django.contrib.auth.models import User
                pending_user_count = User.objects.filter(profile__registration_status='PENDING').count()
        
        total_notification_count = notifications.count() + (1 if pending_user_count > 0 else 0)

        return {
            'sys_settings': settings,
            'recent_notifications': notifications,
            'notification_count': total_notification_count,
            'pending_user_count': pending_user_count
        }
    except Exception:
        return {'sys_settings': None}
