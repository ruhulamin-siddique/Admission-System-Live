from django.contrib import admin
from .models import APIClient, APIRequestLog


@admin.register(APIClient)
class APIClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'key_prefix', 'is_active', 'rate_limit_per_minute', 'last_used_at', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'contact_name', 'contact_email', 'key_prefix')
    readonly_fields = ('key_prefix', 'key_hash', 'created_at', 'updated_at', 'last_used_at', 'revoked_at')


@admin.register(APIRequestLog)
class APIRequestLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'client', 'method', 'path', 'status_code', 'status', 'ip_address', 'response_ms')
    list_filter = ('status', 'status_code', 'method', 'created_at')
    search_fields = ('path', 'query_string', 'ip_address', 'user_agent', 'request_id', 'key_prefix')
    readonly_fields = [field.name for field in APIRequestLog._meta.fields]
