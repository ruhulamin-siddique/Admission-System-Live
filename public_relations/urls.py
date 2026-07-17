"""
public_relations/urls.py
========================
URL configuration for the PR Office module.
All paths are prefixed with `pr/` in the root urls.py.
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Dashboard ────────────────────────────────────────────────────────
    path('',                          views.dashboard,           name='pr_dashboard'),

    # ── Archive (CRUD) ───────────────────────────────────────────────────
    path('archive/',                  views.archive_list,        name='pr_archive_list'),
    path('portal/',                   views.pr_portal,           name='pr_portal'),
    path('archive/create/',           views.archive_create,      name='pr_archive_create'),
    path('archive/<int:pk>/',         views.archive_detail,      name='pr_archive_detail'),
    path('archive/<int:pk>/edit/',    views.archive_edit,        name='pr_archive_edit'),
    path('archive/<int:pk>/delete/',  views.archive_delete,      name='pr_archive_delete'),

    # ── Media Houses ─────────────────────────────────────────────────────
    path('media-houses/',             views.media_house_list,    name='pr_media_houses'),
    path('media-houses/create/',      views.media_house_create,  name='pr_media_house_create'),
    path('media-houses/<int:pk>/edit/',   views.media_house_edit,   name='pr_media_house_edit'),
    path('media-houses/<int:pk>/delete/', views.media_house_delete, name='pr_media_house_delete'),

    # ── Exports ──────────────────────────────────────────────────────────
    path('export/excel/',             views.export_excel,        name='pr_export_excel'),
    path('export/pdf/<int:pk>/',      views.export_pdf,          name='pr_export_pdf'),
]
