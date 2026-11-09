from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
import threading

_thread_locals = threading.local()

def get_current_request():
    """Utility to get the active HTTP request in the current thread."""
    return getattr(_thread_locals, 'request', None)

class ThreadLocalMiddleware:
    """Middleware that stores the request in thread-local storage for audit logging."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        try:
            response = self.get_response(request)
        finally:
            if hasattr(_thread_locals, 'request'):
                del _thread_locals.request
        return response


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
            '/api/manual-verify-student/',
            '/api/batch-verify-queue/',
            '/api/toggle-login-admission/',
            '/bookmarklet-installer/',
            '/extension-guide/',
            '/verification-center/',
            '/extension/download-zip/',
            '/external-api/v1/',
            '/coe/submit/',
            '/coe/track/',
            '/coe/verify/',
            '/coe/reupload/',
            '/counseling/book/',
            '/counseling/api/verify-student/',
            '/counseling/api/check-status/',
            '/counseling/api/cancel-appointment/',
            '/apply/',
            '/apply/track/',
            '/apply/blank-pdf/',
            '/apply/blank-docx/',
            '/apply/api/autofill/',
            '/apply/api/check-sibling/',
            '/apply/api/validate-id/',
            '/admission-portal/',
            settings.STATIC_URL,
            settings.MEDIA_URL,
            '/admin/',
            '/portfolio/',
            '/ict/',
        ]

    def __call__(self, request):
        # 1. Check if the user is authenticated
        if not request.user.is_authenticated:
            # 2. Check if the current URL is in the exempt list
            path = request.path
            is_exempt = any(path.startswith(url) for url in self.exempt_urls)
            
            if not is_exempt:
                login_url = f"{reverse('login')}?next={path}"
                # If it's an HTMX request, force a full page reload to the login page
                if request.headers.get('HX-Request') == 'true':
                    from django.http import HttpResponse
                    response = HttpResponse()
                    response['HX-Redirect'] = login_url
                    return response
                
                # Redirect to login with the 'next' parameter so they return where they wanted
                return redirect(login_url)

        response = self.get_response(request)
        return response


from django.utils import translation

class UserLanguageMiddleware:
    """
    Middleware that activates the user's preferred language saved in their UserProfile.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            user_language = request.user.profile.language
            if user_language:
                translation.activate(user_language)
                request.LANGUAGE_CODE = user_language
        response = self.get_response(request)
        return response


import os
import mimetypes
from urllib.parse import unquote
from django.http import FileResponse, HttpResponseNotFound, HttpResponseNotModified, HttpResponseForbidden
from django.utils.http import http_date, parse_http_date_safe
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.exceptions import SessionInterrupted
import logging

logger = logging.getLogger('django.sessions')


class FastMediaMiddleware:
    """
    High-performance, lock-free media serving middleware.
    Runs BEFORE SessionMiddleware and AuthenticationMiddleware to serve uploaded
    media files (student photos, vouchers, documents) directly from disk.
    
    Why this is critical:
    1. Zero Session/DB overhead: Bypasses SessionMiddleware entirely for /media/ requests.
       Completely eliminates concurrent SQLite write collisions (disk I/O errors and
       SessionInterrupted exceptions) when browsers load multiple student avatars in parallel.
    2. Zero-overhead 404s: Missing avatars return immediate lightweight 404 responses
       without invoking session writes or DB lookups.
    3. Browser Caching: Sends HTTP 304 Not Modified and Cache-Control headers for instant caching.
    4. Path traversal protection: Ensures requested files reside inside settings.MEDIA_ROOT.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.media_url = getattr(settings, 'MEDIA_URL', '/media/') or '/media/'
        self.media_root = os.path.abspath(str(getattr(settings, 'MEDIA_ROOT', '')))

    def __call__(self, request):
        if request.path.startswith(self.media_url):
            return self.serve_media(request)
        return self.get_response(request)

    def serve_media(self, request):
        rel_path = request.path[len(self.media_url):]
        # Decode and normalize path to prevent directory traversal
        safe_rel_path = os.path.normpath(unquote(rel_path)).lstrip('/\\')
        full_path = os.path.abspath(os.path.join(self.media_root, safe_rel_path))

        # Security check: must reside inside MEDIA_ROOT
        if not full_path.startswith(self.media_root):
            return HttpResponseForbidden("Access denied")

        if not os.path.isfile(full_path):
            response = HttpResponseNotFound("Media file not found")
            response['Cache-Control'] = 'no-cache'
            return response

        # Check HTTP conditional caching (If-Modified-Since)
        stat = os.stat(full_path)
        last_modified = int(stat.st_mtime)
        header_mtime = request.META.get('HTTP_IF_MODIFIED_SINCE')
        if header_mtime:
            parsed_mtime = parse_http_date_safe(header_mtime)
            if parsed_mtime is not None and parsed_mtime >= last_modified:
                response = HttpResponseNotModified()
                response['Cache-Control'] = 'public, max-age=86400'
                return response

        # Guess MIME type
        content_type, encoding = mimetypes.guess_type(full_path)
        content_type = content_type or 'application/octet-stream'

        response = FileResponse(open(full_path, 'rb'), content_type=content_type)
        response['Last-Modified'] = http_date(last_modified)
        response['Cache-Control'] = 'public, max-age=86400'
        if encoding:
            response['Content-Encoding'] = encoding
        return response


class ResilientSessionMiddleware(SessionMiddleware):
    """
    Concurrency-hardened SessionMiddleware that catches SessionInterrupted / UpdateError
    from concurrent worker threads updating the same session row.
    Prevents 500 errors when multiple tabs or rapid requests complete simultaneously.
    """
    def process_response(self, request, response):
        try:
            return super().process_response(request, response)
        except SessionInterrupted:
            # Another concurrent request for the same session completed first and saved the session.
            # Returning response normally prevents unhandled 500 crashes for the user.
            logger.debug(
                "Concurrent session update collision absorbed gracefully for session %s",
                getattr(getattr(request, 'session', None), 'session_key', 'unknown')
            )
            return response

