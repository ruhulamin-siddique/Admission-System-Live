import requests
from .models import ActivityLog, SystemSettings

def log_activity(request, action_type, module, description, object_id=None, scope=None, is_system_alert=False):
    """
    Helper to record user activities.
    Captures user, action, module, description, IP address, and timestamp.
    'scope' can be used to filter notifications by department/program.
    """
    user = getattr(request, 'user', None)
    if user and not user.is_authenticated:
        user = None
    
    # Get IP Address
    meta = getattr(request, 'META', {})
    x_forwarded_for = meta.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = meta.get('REMOTE_ADDR', None)
    
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

def get_sms_balance(profile):
    """
    Queries the account balance for a given SMSProfile using its balance_url.
    Returns (success_boolean, balance_string)
    """
    if not profile or not profile.balance_url:
        return False, "Balance URL not configured for this profile."
    
    try:
        response = requests.get(profile.balance_url, timeout=10)
        if response.status_code == 200:
            text = response.text.strip()
            try:
                import json
                data = json.loads(text)
                if isinstance(data, dict):
                    if 'response' in data:
                        return True, f"৳ {data['response']}"
                    elif 'balance' in data:
                        return True, f"৳ {data['balance']}"
                    elif 'AvailableExternalSmsCount' in data:
                        return True, f"{data['AvailableExternalSmsCount']} SMS"
            except Exception:
                pass
            return True, text
        return False, f"HTTP {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return False, str(e)


def send_sms(number, message, module='SYSTEM', use_case_event='general', recipient_name=None, student_id=None):
    """
    Dynamic multi-profile SMS dispatch engine.
    Finds the active SMSProfile, builds dynamic params, dispatches via GET or POST,
    inspects JSON responses for provider errors, and logs full execution details into SMSHistory.
    """
    import json
    from .models import SMSProfile
    from students.models import SMSHistory

    # Clean phone number (strip whitespace and non-digits)
    if number:
        number = str(number).strip()

    profile = SMSProfile.objects.filter(is_active=True).first()
    
    success = False
    response_text = ""
    profile_name = "Legacy Settings"
    
    if profile:
        profile_name = profile.profile_name
        payload = {
            profile.number_param: number,
            profile.message_param: message,
        }
        
        if profile.sender_id and profile.sender_param:
            payload[profile.sender_param] = profile.sender_id
            
        if profile.auth_type == 'api_key':
            if profile.api_key:
                payload['api_key'] = profile.api_key
                payload['apikey'] = profile.api_key
        elif profile.auth_type == 'user_pass':
            if profile.user_id and profile.user_id_param:
                payload[profile.user_id_param] = profile.user_id
            if profile.password and profile.password_param:
                payload[profile.password_param] = profile.password
                
        # Parse extra_params if provided
        if profile.extra_params:
            for line in profile.extra_params.splitlines():
                if '=' in line:
                    k, v = line.split('=', 1)
                    payload[k.strip()] = v.strip()
                    
        try:
            if profile.http_method.upper() == 'POST':
                response = requests.post(profile.api_url, data=payload, timeout=10)
            else:
                response = requests.get(profile.api_url, params=payload, timeout=10)
                
            response_text = response.text
            if response.status_code in [200, 201, 202]:
                success = True
                # Smart JSON error/success detection (BulkSMSBD, Durbar SMS, AUTOMAS, etc.)
                try:
                    data = json.loads(response_text)
                    if isinstance(data, dict):
                        if data.get('isError') is False or str(data.get('isError')).lower() == 'false':
                            success = True
                        elif data.get('insertedSmsIds') or data.get('success_message'):
                            success = True
                        elif data.get('error_message'):
                            success = False
                        elif data.get('isError') is True or str(data.get('isError')).lower() == 'true':
                            success = False
                        elif data.get('response_code') is not None:
                            if str(data.get('response_code')) in ['202', '200', '1000', '1002', '1008', '0']:
                                success = True
                            else:
                                success = False
                    elif isinstance(data, list) and len(data) > 0:
                        item = data[0]
                        if isinstance(item, dict) and 'status' in item and item.get('status') != 0:
                            success = False
                except Exception:
                    pass
            else:
                response_text = f"HTTP {response.status_code}: {response.text}"
                success = False
        except Exception as e:
            response_text = str(e)
            success = False
    else:
        # Fallback to SystemSettings if legacy config exists
        settings = SystemSettings.objects.first()
        if not settings or not settings.sms_is_active or not settings.sms_api_url:
            response_text = "SMS Service is disabled or no active SMS Profile configured."
            success = False
        else:
            params = {
                'api_key': settings.sms_api_key,
                'senderid': settings.sms_sender_id,
                'number': number,
                'message': message,
            }
            try:
                response = requests.get(settings.sms_api_url, params=params, timeout=10)
                response_text = response.text
                success = (response.status_code == 200)
            except Exception as e:
                response_text = str(e)
                success = False

    # Audit log in SMSHistory
    try:
        SMSHistory.objects.create(
            recipient_name=recipient_name,
            student_id=student_id,
            recipient_contact=number or 'Unknown',
            module_name=module,
            use_case_event=use_case_event,
            message_type='SMS',
            message_body=message,
            status='Delivered' if success else 'Failed',
            api_response=response_text,
            api_profile_name=profile_name,
            sms_profile=profile
        )
    except Exception as log_err:
        print(f"SMSHistory log error: {log_err}")

    return success, response_text

