from django.contrib import admin
from .models import Student, ProgramChangeHistory, SMSHistory

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'student_name', 'program', 'batch', 'admission_status')
    list_filter = ('program', 'batch', 'admission_status', 'gender', 'religion')
    search_fields = ('student_id', 'student_name', 'father_name', 'mother_name', 'student_mobile')
    list_per_page = 50

@admin.register(ProgramChangeHistory)
class ProgramChangeHistoryAdmin(admin.ModelAdmin):
    list_display = ('old_student_id', 'new_student_id', 'old_program', 'new_program', 'change_date')
    list_filter = ('old_program', 'new_program')
    search_fields = ('old_student_id', 'new_student_id')

@admin.register(SMSHistory)
class SMSHistoryAdmin(admin.ModelAdmin):
    list_display = ('recipient_name', 'recipient_contact', 'message_type', 'status', 'sent_at')
    list_filter = ('message_type', 'status', 'api_profile_name')
    search_fields = ('recipient_name', 'recipient_contact', 'student_id')
