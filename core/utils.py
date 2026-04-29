import requests
from .models import ActivityLog, SystemSettings

def log_activity(request, action_type, module, description, object_id=None, scope=None, is_system_alert=False):
    """
    Helper to record user activities.
    Captures user, action, module, description, IP address, and timestamp.
    'scope' can be used to filter notifications by department/program.
    """
    user = request.user if request.user.is_authenticated else None
    
    # Get IP Address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    return ActivityLog.objects.create(
        user=user,
        action_type=action_type,
        module=module,
        scope=scope,
        object_id=object_id,
        description=description,
        is_system_alert=is_system_alert,
        ip_address=ip
    )

def send_sms(number, message):
    """
    Generic SMS sending utility using settings-defined API.
    Returns (success_boolean, response_text)
    """
    settings = SystemSettings.objects.first()
    if not settings or not settings.sms_is_active or not settings.sms_api_url:
        return False, "SMS Service is disabled or unconfigured."
    
    # Generic parameter mapping (Works for most BD gateways like BulkSMSBD, GreenWeb)
    params = {
        'api_key': settings.sms_api_key,
        'senderid': settings.sms_sender_id,
        'number': number,
        'message': message,
    }
    
    try:
        response = requests.get(settings.sms_api_url, params=params, timeout=10)
        if response.status_code == 200:
            return True, response.text
        return False, f"API Error: HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)
