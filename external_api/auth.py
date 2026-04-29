import time
import uuid
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

from .models import APIClient, APIRequestLog


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def get_api_key(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.lower().startswith('bearer '):
        return auth_header.split(' ', 1)[1].strip()
    return request.META.get('HTTP_X_API_KEY', '').strip()


def api_error(message, status_code, status='DENIED'):
    return JsonResponse({'error': message}, status=status_code), status


def log_api_request(request, client, status_code, status, started_at, error_message=''):
    APIRequestLog.objects.create(
        client=client,
        key_prefix=getattr(client, 'key_prefix', '') or (get_api_key(request)[:12] if get_api_key(request) else ''),
        method=request.method,
        path=request.path,
        query_string=request.META.get('QUERY_STRING', ''),
        status_code=status_code,
        status=status,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
        request_id=getattr(request, 'api_request_id', ''),
        response_ms=max(0, int((time.monotonic() - started_at) * 1000)),
        error_message=error_message[:2000],
    )


def require_api_scope(required_scope):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            started_at = time.monotonic()
            request.api_request_id = request.META.get('HTTP_X_REQUEST_ID', str(uuid.uuid4()))
            client = None
            status = 'SUCCESS'
            error_message = ''
            status_code = 200

            try:
                if settings.EXTERNAL_API_REQUIRE_HTTPS and not request.is_secure():
                    response, status = api_error('HTTPS is required for external API access.', 403)
                    status_code = response.status_code
                    error_message = 'HTTPS required'
                    return response

                raw_key = get_api_key(request)
                if not raw_key:
                    response, status = api_error('Missing API key. Send Authorization: Bearer <key>.', 401)
                    status_code = response.status_code
                    error_message = 'Missing API key'
                    return response

                key_prefix = raw_key[:12]
                client = APIClient.objects.filter(key_prefix=key_prefix).first()
                if not client or client.key_hash != APIClient.hash_key(raw_key):
                    response, status = api_error('Invalid API key.', 401)
                    status_code = response.status_code
                    error_message = 'Invalid API key'
                    return response

                if not client.is_active:
                    response, status = api_error('API client is inactive or revoked.', 403)
                    status_code = response.status_code
                    error_message = 'Inactive client'
                    return response

                ip_address = get_client_ip(request)
                if not client.is_ip_allowed(ip_address):
                    response, status = api_error('This IP address is not allowed for the API client.', 403)
                    status_code = response.status_code
                    error_message = f'IP not allowed: {ip_address}'
                    return response

                if not client.has_scope(required_scope):
                    response, status = api_error(f'Missing required scope: {required_scope}', 403)
                    status_code = response.status_code
                    error_message = f'Missing scope: {required_scope}'
                    return response

                minute_bucket = int(time.time() // 60)
                cache_key = f"external-api-rate:{client.id}:{minute_bucket}"
                request_count = cache.get(cache_key, 0) + 1
                cache.set(cache_key, request_count, 90)
                if request_count > client.rate_limit_per_minute:
                    response, status = api_error('Rate limit exceeded. Try again later.', 429, 'RATE_LIMITED')
                    status_code = response.status_code
                    error_message = 'Rate limit exceeded'
                    return response

                request.api_client = client
                response = view_func(request, *args, **kwargs)
                status_code = response.status_code
                status = 'SUCCESS' if status_code < 400 else 'ERROR'
                return response
            except Exception as exc:
                status = 'ERROR'
                status_code = 500
                error_message = str(exc)
                raise
            finally:
                if client and status == 'SUCCESS':
                    APIClient.objects.filter(id=client.id).update(last_used_at=timezone.now())
                log_api_request(request, client, status_code, status, started_at, error_message)

        return wrapped
    return decorator
