from django.urls import path
from . import views

urlpatterns = [
    path('academic/', views.academic_settings, name='academic_settings'),
    path('academic/add/<str:model_name>/', views.add_master_data, name='add_master_data'),
    path('academic/delete/<str:model_name>/<int:pk>/', views.delete_master_data, name='delete_master_data'),
    path('academic/edit/<str:model_name>/<int:pk>/', views.edit_master_data, name='edit_master_data'),
]
