from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_device, name='register_device'),
    path('success/<int:pk>/', views.registration_success, name='registration_success'),
    path('status/', views.check_device_status, name='check_device_status'),
    
    # ICT Wing Management Dashboard (Staff only)
    path('manage/', views.manage_devices, name='manage_devices'),
    path('manage/approve/<int:pk>/', views.approve_device, name='approve_device'),
    path('manage/reject/<int:pk>/', views.reject_device, name='reject_device'),
]
