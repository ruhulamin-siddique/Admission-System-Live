from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Root Level Authentication
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='core/password_change.html'), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='core/password_change_done.html'), name='password_change_done'),
    
    # Registration & Public Status (Root URLs)
    path('register/', core_views.register, name='register'),
    path('check-status/', core_views.check_status, name='check_status'),

    # Application Modules
    path('', include('students.urls')),
    path('core/', include('core.urls')),
    path('settings/', include('master_data.urls')),
    path('external-api/', include('external_api.urls')),
    path('exam-billing/', include('exam_billing.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
