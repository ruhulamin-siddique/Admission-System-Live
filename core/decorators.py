from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse

def require_access(module, task):
    """
    Decorator for views that checks if the logged-in user has access 
    to a specific module and task in the ACCESS_REGISTRY.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            is_api = (
                request.path.startswith('/api/') or 
                request.headers.get('Accept') == 'application/json' or
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                request.content_type == 'application/json'
            )

            if not request.user.is_authenticated:
                if is_api:
                    return JsonResponse({'success': False, 'error': 'Authentication required. Please log in.'}, status=401)
                if request.headers.get('HX-Request') == 'true':
                    response = HttpResponse()
                    response['HX-Redirect'] = '/login/'
                    return response
                return redirect('login')
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Use the has_access helper on the profile
            if hasattr(request.user, 'profile') and request.user.profile.has_access(module, task):
                return view_func(request, *args, **kwargs)
            
            if is_api:
                return JsonResponse({
                    'success': False, 
                    'error': f"Access Denied: You do not have permission for '{module}.{task}'"
                }, status=403)

            messages.error(request, f"Access Denied: You do not have permission for '{module}.{task}'")
            # Redirect to profile page so they don't loop on the dashboard
            if request.headers.get('HX-Request') == 'true':
                from django.urls import reverse
                response = HttpResponse()
                response['HX-Redirect'] = reverse('user_profile')
                return response
            return redirect('user_profile')
            
        return _wrapped_view
    return decorator

