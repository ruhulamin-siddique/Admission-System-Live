from django.contrib import admin

from .models import (
    BillingExam,
    BillingRateTemplate,
    CECCAssignment,
    ECMember,
    ExamBillingSetting,
    ExamCourse,
    ExamFaculty,
    ExamProgram,
    FacultyProfile,
    QMSCAssignment,
    QPSCMember,
    QuestionSetterAssignment,
    RPSCAssignment,
    ScriptExaminerAssignment,
    ScriptScrutinizerAssignment,
)


@admin.register(BillingExam)
class BillingExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam_type', 'semester_label', 'status', 'created_at')
    list_filter = ('status', 'exam_type')
    search_fields = ('name', 'semester_label')


@admin.register(ExamProgram)
class ExamProgramAdmin(admin.ModelAdmin):
    list_display = ('exam', 'program', 'status', 'submitted_at', 'approved_at')
    list_filter = ('status', 'program')
    search_fields = ('exam__name', 'program__name', 'program__short_name')


@admin.register(FacultyProfile)
class FacultyProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'employee_id', 'program', 'is_active', 'is_deleted')
    list_filter = ('program', 'is_active', 'is_deleted')
    search_fields = ('first_name', 'last_name', 'employee_id', 'designation')


@admin.register(ExamCourse)
class ExamCourseAdmin(admin.ModelAdmin):
    list_display = ('course_code', 'course_title', 'exam_program', 'level', 'term', 'no_of_scripts')
    list_filter = ('exam_program__exam', 'exam_program__program')
    search_fields = ('course_code', 'course_title')


for model in [
    BillingRateTemplate,
    ExamBillingSetting,
    ExamFaculty,
    CECCAssignment,
    ECMember,
    RPSCAssignment,
    QMSCAssignment,
    QPSCMember,
    QuestionSetterAssignment,
    ScriptExaminerAssignment,
    ScriptScrutinizerAssignment,
]:
    admin.site.register(model)
