"""
public_relations/admin.py
=========================
Django admin registrations for the PR Office module.
Inline admins allow managing coverage rows and asset rows
directly from the archive entry admin page.
"""

from django.contrib import admin
from .models import MediaHouse, PublicRelationsArchive, MediaCoverage, MediaAsset


# ---------------------------------------------------------------------------
# Inline admins
# ---------------------------------------------------------------------------

class MediaCoverageInline(admin.TabularInline):
    model       = MediaCoverage
    extra       = 1
    fields      = ['media_house', 'published_date', 'newspaper_pdf', 'screenshot', 'online_link']
    autocomplete_fields = []


class MediaAssetInline(admin.TabularInline):
    model  = MediaAsset
    extra  = 1
    fields = ['asset_type', 'file', 'link', 'year', 'caption']


# ---------------------------------------------------------------------------
# MediaHouse admin
# ---------------------------------------------------------------------------

@admin.register(MediaHouse)
class MediaHouseAdmin(admin.ModelAdmin):
    list_display   = ['name', 'media_type', 'editor', 'mobile', 'email', 'created_at']
    list_filter    = ['media_type']
    search_fields  = ['name', 'editor', 'email', 'mobile']
    ordering       = ['media_type', 'name']


# ---------------------------------------------------------------------------
# PublicRelationsArchive admin
# ---------------------------------------------------------------------------

@admin.register(PublicRelationsArchive)
class PublicRelationsArchiveAdmin(admin.ModelAdmin):
    list_display   = [
        'press_release_no', 'press_release_date', 'event_name',
        'department', 'coverage_count', 'created_by', 'created_at'
    ]
    list_filter    = ['press_release_date', 'department']
    search_fields  = ['press_release_no', 'event_name', 'full_text', 'department']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    inlines        = [MediaCoverageInline, MediaAssetInline]
    ordering       = ['-press_release_date']
    date_hierarchy = 'press_release_date'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def coverage_count(self, obj):
        return obj.coverage_count
    coverage_count.short_description = 'কভারেজ সংখ্যা'
