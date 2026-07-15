from django.contrib import admin
from .models import DeviceRegistration

@admin.register(DeviceRegistration)
class DeviceRegistrationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user_type', 'device_name_brand', 'mac_address', 'status', 'assigned_ip', 'created_at')
    list_filter = ('status', 'user_type', 'device_type', 'department')
    search_fields = ('full_name', 'email', 'phone', 'mac_address', 'designation_or_roll')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('full_name', 'email', 'phone', 'user_type', 'department', 'designation_or_roll')
        }),
        ('Device Details', {
            'fields': ('device_type', 'device_name_brand', 'mac_address', 'reason')
        }),
        ('ICT Administration', {
            'fields': ('status', 'assigned_ip', 'admin_notes', 'created_at', 'updated_at')
        }),
    )

    actions = ['approve_devices', 'reject_devices']

    def approve_devices(self, request, queryset):
        rows_updated = queryset.update(status='approved')
        self.message_user(request, f"{rows_updated} device registration(s) successfully approved.")
    approve_devices.short_description = "Approve selected device registrations"

    def reject_devices(self, request, queryset):
        rows_updated = queryset.update(status='rejected')
        self.message_user(request, f"{rows_updated} device registration(s) successfully marked as rejected.")
    reject_devices.short_description = "Reject selected device registrations"
