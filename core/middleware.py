from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings

class AdmissionSecurityMiddleware:
    """
    Middleware that ensures all users are authenticated before accessing any page 
    except the login page and static/media files.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Define URLs that are allowed without authentication
        self.exempt_urls = [
            reverse('login'),
            '/register/',
            '/check-status/',
            settings.STATIC_URL,
            settings.MEDIA_URL,
            '/admin/',
        ]

    def __call__(self, request):
        # 1. Check if the user is authenticated
        if not request.user.is_authenticated:
            # 2. Check if the current URL is in the exempt list
            path = request.path
            is_exempt = any(path.startswith(url) for url in self.exempt_urls)
            
            if not is_exempt:
                # Redirect to login with the 'next' parameter so they return where they wanted
                return redirect(f"{reverse('login')}?next={path}")

        response = self.get_response(request)
        return response
