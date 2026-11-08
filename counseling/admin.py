from django.contrib import admin
from .models import (
    CounselingSettings,
    CounselorProfile,
    CounselingCase,
    CaseStatusLog,
    CounselingAppointment,
    SessionRecord,
    MentalHealthAssessment,
    EmergencyIntervention,
    WellbeingWorkshop,
    WellbeingWorkshopParticipant,
)

@admin.register(CounselingSettings)
class CounselingSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'enable_sms_notifications', 'session_lock_hours', 'crisis_sla_hours', 'updated_at')

@admin.register(CounselorProfile)
class CounselorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'designation', 'room_number', 'contact_number', 'is_active_counselor')
    list_filter = ('is_active_counselor', 'designation')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'license_number')

class CaseStatusLogInline(admin.TabularInline):
    model = CaseStatusLog
    extra = 0
    readonly_fields = ('changed_at', 'changed_by', 'old_status', 'new_status', 'note')
    can_delete = False

@admin.register(CounselingCase)
class CounselingCaseAdmin(admin.ModelAdmin):
    list_display = ('case_number', 'student', 'alias_code', 'category', 'risk_level', 'status', 'assigned_counselor', 'intake_date', 'is_deleted')
    list_filter = ('risk_level', 'status', 'category', 'is_deleted', 'intake_date')
    search_fields = ('case_number', 'alias_code', 'student__student_id', 'student__student_name')
    inlines = [CaseStatusLogInline]

@admin.register(CounselingAppointment)
class CounselingAppointmentAdmin(admin.ModelAdmin):
    list_display = ('case', 'counselor', 'appointment_date', 'time_slot', 'session_mode', 'status', 'sms_reminder_sent')
    list_filter = ('status', 'session_mode', 'appointment_date')
    search_fields = ('case__case_number', 'case__student__student_name', 'time_slot')

@admin.register(SessionRecord)
class SessionRecordAdmin(admin.ModelAdmin):
    list_display = ('case', 'session_number', 'session_date', 'is_locked', 'recorded_by')
    list_filter = ('is_locked', 'session_date')
    search_fields = ('case__case_number', 'case__student__student_name')

@admin.register(MentalHealthAssessment)
class MentalHealthAssessmentAdmin(admin.ModelAdmin):
    list_display = ('case', 'assessment_type', 'total_score', 'severity_tier', 'assessed_date', 'administered_by')
    list_filter = ('assessment_type', 'severity_tier', 'assessed_date')
    search_fields = ('case__case_number', 'case__student__student_name')

@admin.register(EmergencyIntervention)
class EmergencyInterventionAdmin(admin.ModelAdmin):
    list_display = ('case', 'incident_type', 'incident_date', 'medical_referral_made', 'hospital_name', 'resolved')
    list_filter = ('medical_referral_made', 'resolved', 'incident_date')
    search_fields = ('case__case_number', 'incident_type', 'hospital_name')

@admin.register(WellbeingWorkshop)
class WellbeingWorkshopAdmin(admin.ModelAdmin):
    list_display = ('title', 'speaker', 'venue', 'event_date', 'capacity', 'is_cancelled')
    list_filter = ('event_date', 'is_cancelled')
    search_fields = ('title', 'speaker', 'venue')

@admin.register(WellbeingWorkshopParticipant)
class WellbeingWorkshopParticipantAdmin(admin.ModelAdmin):
    list_display = ('workshop', 'student', 'registered_at', 'attended')
    list_filter = ('attended', 'registered_at')
    search_fields = ('workshop__title', 'student__student_name', 'student__student_id')
