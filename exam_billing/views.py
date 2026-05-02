from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
import csv
import io
import pandas as pd
from django.db.models import Q

from core.decorators import require_access
from core.utils import log_activity
from master_data.models import Program

from .billing_calculator import calculate_exam_program_summary, calculate_faculty_bill, full_or_half
from .forms import (
    BillingExamForm,
    BillingRateTemplateForm,
    CECCAssignmentForm,
    ECMemberForm,
    ExamBillingSettingForm,
    ExamCourseForm,
    ExamFacultyForm,
    ExamLevelTermSummaryForm,
    FacultyProfileForm,
    QMSCChairmanForm,
    QMSCMemberForm,
    QPSCMemberForm,
    QuestionSetterAssignmentForm,
    RPSCAssignmentForm,
    ScriptExaminerAssignmentForm,
    ScriptScrutinizerAssignmentForm,
)
from .models import (
    BillingExam,
    BillingRateTemplate,
    CECCAssignment,
    ECMember,
    ExamBillingSetting,
    ExamCourse,
    ExamFaculty,
    ExamLevelTermSummary,
    ExamProgram,
    FacultyProfile,
    QMSCAssignment,
    QPSCMember,
    QuestionSetterAssignment,
    RPSCAssignment,
    ScriptExaminerAssignment,
    ScriptScrutinizerAssignment,
)
from .scope import filter_by_user_scope, get_allowed_programs, require_exam_program_access, user_can_view_all_departments


@login_required
@require_access('exam_billing', 'view_dashboard')
def dashboard(request):
    programs = get_allowed_programs(request.user)
    exam_programs = ExamProgram.objects.select_related('exam', 'program').filter(program__in=programs)
    exams = BillingExam.objects.filter(programs__program__in=programs).distinct()
    active_exam_programs = exam_programs.exclude(exam__status='finalized')
    total_payable = sum((ep.cached_total for ep in active_exam_programs), 0)
    context = {
        'exam_count': exams.count(),
        'open_count': exams.filter(status='open').count(),
        'pending_count': exam_programs.filter(status='submitted').count(),
        'total_payable': total_payable,
        'recent_exam_programs': active_exam_programs[:10],
    }
    return render(request, 'exam_billing/dashboard.html', context)


@login_required
@require_access('exam_billing', 'manage_global_settings')
def rate_templates(request):
    instance = BillingRateTemplate.objects.filter(is_default=True).first()
    if request.method == 'POST':
        form = BillingRateTemplateForm(request.POST, instance=instance)
        if form.is_valid():
            template = form.save()
            messages.success(request, 'Global billing defaults saved.')
            log_activity(request, 'UPDATE', 'exam_billing', f'Updated billing rate template: {template.name}', object_id=str(template.id), is_system_alert=True)
            return redirect('billing_rate_templates')
    else:
        form = BillingRateTemplateForm(instance=instance or BillingRateTemplate(name='Default', is_default=True))
    return render(request, 'exam_billing/rate_templates.html', {'form': form})


@login_required
@require_access('exam_billing', 'manage_exams')
def exam_list(request):
    exams = BillingExam.objects.prefetch_related('programs__program').all()
    if not user_can_view_all_departments(request.user):
        exams = exams.filter(programs__program__in=get_allowed_programs(request.user)).distinct()
    form = BillingExamForm(user=request.user)
    return render(request, 'exam_billing/exam_list.html', {'exams': exams, 'form': form})


@login_required
@require_access('exam_billing', 'manage_exams')
def exam_create(request):
    return _save_exam(request)


@login_required
@require_access('exam_billing', 'manage_exams')
def exam_edit(request, pk):
    exam = get_object_or_404(BillingExam, pk=pk)
    if not user_can_view_all_departments(request.user) and not exam.programs.filter(program__in=get_allowed_programs(request.user)).exists():
        raise PermissionDenied
    return _save_exam(request, exam)


def _save_exam(request, exam=None):
    if request.method == 'POST':
        form = BillingExamForm(request.POST, instance=exam, user=request.user)
        if form.is_valid():
            created = exam is None
            exam = form.save(commit=False)
            if created:
                exam.created_by = request.user
            exam.save()
            if created and not hasattr(exam, 'settings'):
                ExamBillingSetting.create_from_template(exam)
            selected_programs = form.cleaned_data['programs']
            for program in selected_programs:
                ExamProgram.objects.get_or_create(exam=exam, program=program)
            exam.programs.exclude(program__in=selected_programs).delete()
            log_activity(request, 'CREATE' if created else 'UPDATE', 'exam_billing', f'{"Created" if created else "Updated"} billing exam: {exam}', object_id=str(exam.id), is_system_alert=True)
            messages.success(request, 'Exam saved successfully.')
            return redirect('billing_exam_detail', pk=exam.pk)
    else:
        form = BillingExamForm(instance=exam, user=request.user)
    return render(request, 'exam_billing/exam_form.html', {'form': form, 'exam': exam})


@login_required
@require_access('exam_billing', 'delete_exam')
def exam_delete(request, pk):
    exam = get_object_or_404(BillingExam, pk=pk)
    if not user_can_view_all_departments(request.user) and not exam.programs.filter(program__in=get_allowed_programs(request.user)).exists():
        raise PermissionDenied
    
    if request.method == 'POST':
        exam_name = exam.name
        exam.delete()
        log_activity(request, 'DELETE', 'exam_billing', f'Permanently deleted billing exam: {exam_name}', object_id=str(pk), is_system_alert=True)
        messages.success(request, f'Exam "{exam_name}" and all associated data have been removed.')
        return redirect('billing_exam_list')
    
    return render(request, 'exam_billing/exam_confirm_delete.html', {'exam': exam})


@login_required
@require_access('exam_billing', 'view_dashboard')
def exam_detail(request, pk):
    exam = get_object_or_404(BillingExam, pk=pk)
    exam_programs = exam.programs.select_related('program')
    if not user_can_view_all_departments(request.user):
        exam_programs = exam_programs.filter(program__in=get_allowed_programs(request.user))
        if not exam_programs.exists():
            raise PermissionDenied
    rows = []
    for ep in exam_programs:
        summary = calculate_exam_program_summary(ep)
        rows.append({'exam_program': ep, 'summary': summary})
    return render(request, 'exam_billing/exam_detail.html', {'exam': exam, 'rows': rows})


@login_required
@require_access('exam_billing', 'manage_exams')
def exam_settings(request, pk):
    exam = get_object_or_404(BillingExam, pk=pk)
    if exam.status in {'locked', 'finalized'}:
        messages.error(request, 'Locked or finalized exam settings cannot be edited.')
        return redirect('billing_exam_detail', pk=pk)
    settings, _ = ExamBillingSetting.objects.get_or_create(
        exam=exam,
        defaults=_settings_defaults(),
    )
    if request.method == 'POST':
        form = ExamBillingSettingForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            log_activity(request, 'UPDATE', 'exam_billing', f'Updated exam bill settings: {exam}', object_id=str(exam.id), is_system_alert=True)
            messages.success(request, 'Per-exam billing settings saved.')
            return redirect('billing_exam_detail', pk=pk)
    else:
        form = ExamBillingSettingForm(instance=settings)
    return render(request, 'exam_billing/exam_settings.html', {'exam': exam, 'form': form})


@login_required
@require_access('exam_billing', 'approve_finalize')
def exam_status(request, pk, action):
    exam = get_object_or_404(BillingExam, pk=pk)
    if action == 'open':
        exam.status = 'open'
    elif action == 'lock':
        exam.status = 'locked'
        for ep in exam.programs.exclude(status='locked'):
            ep.mark_locked()
    elif action == 'finalize':
        exam.status = 'finalized'
        for ep in exam.programs.select_related('program'):
            summary = calculate_exam_program_summary(ep)
            ep.mark_finalized(summary['grand_total'], _summary_payload(summary))
    elif action == 'reopen':
        exam.status = 'open'
        for ep in exam.programs.all():
            ep.mark_open()
    else:
        raise PermissionDenied
    exam.save(update_fields=['status', 'updated_at'])
    log_activity(request, 'UPDATE', 'exam_billing', f'{action.title()} billing exam: {exam}', object_id=str(exam.id), is_system_alert=True)
    messages.success(request, f'Exam {action} complete.')
    return redirect('billing_exam_detail', pk=pk)


@login_required
@require_access('exam_billing', 'manage_department_data')
def faculty_directory(request):
    """Professional faculty directory with search, filtering, and summary analytics."""
    queryset = filter_by_user_scope(FacultyProfile.objects.select_related('program'), request.user)
    
    # Search and Filter Logic
    query = request.GET.get('search', '').strip()
    program_id = request.GET.get('program', '')
    designation = request.GET.get('designation', '')
    status = request.GET.get('status', '')
    
    if query:
        queryset = queryset.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(employee_id__icontains=query) |
            Q(email__icontains=query)
        )
    
    if program_id:
        queryset = queryset.filter(program_id=program_id)
        
    if designation:
        queryset = queryset.filter(designation__icontains=designation)
        
    if status == 'active':
        queryset = queryset.filter(is_active=True)
    elif status == 'inactive':
        queryset = queryset.filter(is_active=False)

    form = FacultyProfileForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        faculty = form.save()
        log_activity(request, 'CREATE', 'exam_billing', f'Added faculty profile: {faculty.name}', object_id=str(faculty.id), scope=faculty.program.short_name)
        messages.success(request, 'Faculty profile saved successfully.')
        return redirect('billing_faculty_directory')
    
    # Summary Analytics for KPI Cards
    stats = {
        'total': queryset.count(),
        'active': queryset.filter(is_active=True).count(),
        'inactive': queryset.filter(is_active=False).count(),
        'departments': queryset.values('program').distinct().count()
    }
    
    # Filter Metadata
    programs = get_allowed_programs(request.user)
    designations = FacultyProfile.objects.values_list('designation', flat=True).distinct().order_by('designation')
    designations = [d for d in designations if d]

    context = {
        'faculty_list': queryset,
        'form': form,
        'stats': stats,
        'can_manage': request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.has_access('exam_billing', 'manage_department_data')),
        'programs': programs,
        'designations': designations,
        'query': query,
        'selected_program': program_id,
        'selected_designation': designation,
        'selected_status': status,
    }
    
    template = 'exam_billing/partials/faculty_results.html' if request.headers.get('HX-Request') else 'exam_billing/faculty_directory.html'
    return render(request, template, context)


@login_required
@require_access('exam_billing', 'manage_department_data')
def faculty_edit(request, pk):
    faculty = get_object_or_404(filter_by_user_scope(FacultyProfile.objects.all(), request.user), pk=pk)
    form = FacultyProfileForm(request.POST or None, instance=faculty, user=request.user)
    
    if request.method == 'POST' and form.is_valid():
        faculty = form.save()
        log_activity(request, 'UPDATE', 'exam_billing', f'Updated faculty profile: {faculty.name}', object_id=str(faculty.id), scope=faculty.program.short_name)
        messages.success(request, 'Faculty profile updated.')
        return redirect('billing_faculty_directory')

    # Fetch existing designations for suggestions
    designations = FacultyProfile.objects.values_list('designation', flat=True).distinct().order_by('designation')
    designations = [d for d in designations if d]
    
    return render(request, 'exam_billing/faculty_edit.html', {
        'form': form, 
        'faculty': faculty, 
        'designations': designations
    })


@login_required
@require_access('exam_billing', 'manage_department_data')
def faculty_delete(request, pk):
    faculty = get_object_or_404(filter_by_user_scope(FacultyProfile.objects.all(), request.user), pk=pk)
    if request.method == 'POST':
        faculty.is_deleted = True
        faculty.is_active = False
        faculty.save(update_fields=['is_deleted', 'is_active'])
        log_activity(request, 'DELETE', 'exam_billing', f'Deactivated faculty profile: {faculty.name}', object_id=str(faculty.id), scope=faculty.program.short_name)
        messages.success(request, 'Faculty profile deactivated.')
    return redirect('billing_faculty_directory')


@login_required
@require_access('exam_billing', 'bulk_import_faculty')
def faculty_export_template(request):
    """Generates an Excel template for faculty bulk import."""
    # Main template data
    df = pd.DataFrame(columns=['First Name', 'Last Name', 'Employee ID', 'Designation', 'Department', 'Email', 'Mobile'])
    
    # Department reference sheet
    programs = Program.objects.all().order_by('name')
    dept_df = pd.DataFrame({
        'Valid Department Names': [p.name for p in programs],
        'Short Names': [p.short_name for p in programs]
    })
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Faculty Data', index=False)
        dept_df.to_excel(writer, sheet_name='Department Reference', index=False)
    
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="faculty_import_template.xlsx"'
    return response


@login_required
@require_access('exam_billing', 'bulk_import_faculty')
def faculty_import(request):
    """Handles bulk faculty import from Excel."""
    if request.method != 'POST' or 'file' not in request.FILES:
        return redirect('billing_faculty_directory')
    
    file = request.FILES['file']
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file, sheet_name=0)
            
        required_cols = {'First Name', 'Department'}
        if not required_cols.issubset(df.columns):
            messages.error(request, f"Invalid template. Missing required columns: {required_cols - set(df.columns)}")
            return redirect('billing_faculty_directory')
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        allowed_programs = get_allowed_programs(request.user)
        program_map = {p.name.lower(): p for p in Program.objects.all()}
        program_map.update({p.short_name.lower(): p for p in Program.objects.all() if p.short_name})
        
        for _, row in df.iterrows():
            first_name = str(row.get('First Name', '')).strip()
            last_name = str(row.get('Last Name', '')).strip()
            if last_name == 'nan': last_name = ''

            if not first_name or first_name == 'nan':
                skipped_count += 1
                continue
                
            dept_name = str(row.get('Department', '')).strip().lower()
            program = program_map.get(dept_name)
            
            if not program:
                error_count += 1
                continue
            
            # Check user scope
            if not user_can_view_all_departments(request.user) and program not in allowed_programs:
                error_count += 1
                continue
            
            emp_id = str(row.get('Employee ID', '')).strip()
            if emp_id == 'nan': emp_id = ''
            
            email = str(row.get('Email', '')).strip()
            if email == 'nan': email = ''
            
            mobile = str(row.get('Mobile', '')).strip()
            if mobile == 'nan': mobile = ''
            
            designation = str(row.get('Designation', '')).strip()
            if designation == 'nan': designation = ''
            
            # Update or Create
            defaults = {
                'first_name': first_name,
                'last_name': last_name,
                'program': program,
                'designation': designation,
                'email': email,
                'mobile': mobile,
                'is_active': True,
                'is_deleted': False
            }
            
            if emp_id:
                FacultyProfile.objects.update_or_create(employee_id=emp_id, defaults=defaults)
            else:
                FacultyProfile.objects.update_or_create(first_name=first_name, last_name=last_name, program=program, defaults=defaults)
            
            success_count += 1
            
        log_activity(request, 'CREATE', 'exam_billing', f'Bulk imported {success_count} faculty profiles', is_system_alert=True)
        messages.success(request, f"Successfully processed {success_count} faculty records. Errors: {error_count}, Skipped: {skipped_count}")
        
    except Exception as e:
        messages.error(request, f"Error processing file: {str(e)}")
        
    return redirect('billing_faculty_directory')


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_fundamentals(request, pk):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    
    course_form = ExamCourseForm(request.POST or None, exam_program=exam_program)
    summary_form = ExamLevelTermSummaryForm(request.POST or None)
    
    if request.method == 'POST' and exam_program.is_editable:
        action = request.POST.get('action')
        if action == 'add_course' and course_form.is_valid():
            course = course_form.save(commit=False)
            course.exam_program = exam_program
            if not course.offering_department:
                course.offering_department = exam_program.program.short_name
            course.save()
            messages.success(request, 'Course added.')
            return redirect('billing_program_fundamentals', pk=pk)
        elif action == 'add_summary' and summary_form.is_valid():
            summary = summary_form.save(commit=False)
            summary.exam_program = exam_program
            summary.save()
            messages.success(request, 'Level/Term student count saved.')
            return redirect('billing_program_fundamentals', pk=pk)
        elif action == 'delete_summary':
            summary_id = request.POST.get('summary_id')
            ExamLevelTermSummary.objects.filter(exam_program=exam_program, id=summary_id).delete()
            messages.success(request, 'Summary removed.')
            return redirect('billing_program_fundamentals', pk=pk)
            
    context = {
        'exam_program': exam_program,
        'course_form': course_form,
        'summary_form': summary_form,
        'courses': ExamCourse.objects.filter(exam_program=exam_program),
        'summaries': ExamLevelTermSummary.objects.filter(exam_program=exam_program),
        'summary': calculate_exam_program_summary(exam_program),
    }
    return render(request, 'exam_billing/fundamentals.html', context)


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_course_edit(request, pk, course_id):
    exam_program = get_object_or_404(ExamProgram, pk=pk)
    require_exam_program_access(request.user, exam_program)
    course = get_object_or_404(ExamCourse, pk=course_id, exam_program=exam_program)
    
    form = ExamCourseForm(request.POST or None, instance=course, exam_program=exam_program)
    if request.method == 'POST' and form.is_valid() and exam_program.is_editable:
        form.save()
        messages.success(request, 'Course updated.')
        return redirect('billing_program_fundamentals', pk=pk)
        
    return render(request, 'exam_billing/fundamentals_edit.html', {
        'exam_program': exam_program,
        'form': form,
        'title': f'Edit Course: {course.course_code}',
    })


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_summary_edit(request, pk, summary_id):
    exam_program = get_object_or_404(ExamProgram, pk=pk)
    require_exam_program_access(request.user, exam_program)
    summary = get_object_or_404(ExamLevelTermSummary, pk=summary_id, exam_program=exam_program)
    
    form = ExamLevelTermSummaryForm(request.POST or None, instance=summary)
    if request.method == 'POST' and form.is_valid() and exam_program.is_editable:
        form.save()
        messages.success(request, 'Student count updated.')
        return redirect('billing_program_fundamentals', pk=pk)
        
    return render(request, 'exam_billing/fundamentals_edit.html', {
        'exam_program': exam_program,
        'form': form,
        'title': f'Edit Student Count: L-{summary.level} T-{summary.term}',
    })


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_summary_delete(request, pk, summary_id):
    exam_program = get_object_or_404(ExamProgram, pk=pk)
    require_exam_program_access(request.user, exam_program)
    if exam_program.is_editable:
        ExamLevelTermSummary.objects.filter(exam_program=exam_program, id=summary_id).delete()
        messages.success(request, 'Student count removed.')
    return redirect('billing_program_fundamentals', pk=pk)


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_workspace(request, pk):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    
    faculty_form = ExamFacultyForm(request.POST or None, exam_program=exam_program)
    if request.method == 'POST' and 'add_faculty' in request.POST and exam_program.is_editable:
        if faculty_form.is_valid():
            obj = faculty_form.save(commit=False)
            obj.exam_program = exam_program
            obj.save()
            messages.success(request, f'Faculty {obj.faculty.name} added to bill.')
            return redirect('billing_program_workspace', pk=pk)

    summary = calculate_exam_program_summary(exam_program)
    context = {
        'exam_program': exam_program,
        'summary': summary,
        'faculty_count': ExamFaculty.objects.filter(exam_program=exam_program).count(),
        'course_count': ExamCourse.objects.filter(exam_program=exam_program).count(),
        'faculty_form': faculty_form,
    }
    return render(request, 'exam_billing/program_workspace.html', context)


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_faculty_remove(request, pk, faculty_id):
    exam_program = get_object_or_404(ExamProgram, pk=pk)
    require_exam_program_access(request.user, exam_program)
    if exam_program.is_editable:
        ExamFaculty.objects.filter(exam_program=exam_program, faculty_id=faculty_id).delete()
        messages.success(request, 'Faculty removed from bill.')
    return redirect('billing_program_workspace', pk=pk)


@login_required
def fundamentals_hub(request):
    exams = BillingExam.objects.all().prefetch_related('programs__program')
    return render(request, 'exam_billing/fundamentals_hub.html', {'exams': exams})


@login_required
def individual_bills_directory(request):
    query = request.GET.get('q', '')
    faculties = filter_by_user_scope(FacultyProfile.objects.filter(is_active=True).select_related('program'), request.user)
    if query:
        faculties = faculties.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(employee_id__icontains=query))
    
    # Optionally filter by active exam
    active_exam = BillingExam.objects.filter(status__in=['draft', 'open']).order_by('-created_at').first()
    
    return render(request, 'exam_billing/individual_bills_directory.html', {
        'faculties': faculties[:50], 
        'query': query,
        'active_exam': active_exam
    })


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_sheet(request, pk, sheet):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    config = _sheet_config(sheet)

    # ---- QMSC: two-form special handling ------------------------------------
    if sheet == 'qmsc':
        chairman_form = QMSCChairmanForm(exam_program=exam_program)
        member_form   = QMSCMemberForm(exam_program=exam_program)
        if request.method == 'POST' and exam_program.is_editable:
            if 'add_chairman' in request.POST:
                chairman_form = QMSCChairmanForm(request.POST, exam_program=exam_program)
                if chairman_form.is_valid():
                    obj = chairman_form.save(commit=False)
                    obj.exam_program = exam_program
                    obj.role = 'Chairman'
                    obj.save()
                    messages.success(request, 'QMSC Chairman saved.')
                    log_activity(request, 'CREATE', 'exam_billing', f'Added QMSC Chairman for {exam_program}', object_id=str(obj.id), scope=exam_program.program.short_name)
                    return redirect('billing_program_sheet', pk=pk, sheet=sheet)
            elif 'add_member' in request.POST:
                confirm_replace = 'confirm_replace' in request.POST
                member_form = QMSCMemberForm(request.POST, exam_program=exam_program)
                if confirm_replace:
                    course_id = request.POST.get('course')
                    if course_id:
                        existing = QMSCAssignment.objects.filter(
                            exam_program=exam_program, course_id=course_id, role='Member', is_deleted=False
                        ).first()
                        if existing:
                            existing.faculty_id = request.POST.get('faculty') or None
                            existing.external_member_name = request.POST.get('external_member_name', '')
                            existing.external_member_designation = request.POST.get('external_member_designation', '')
                            existing.save()
                            messages.success(request, 'QMSC member assignment replaced.')
                            log_activity(request, 'UPDATE', 'exam_billing', f'Replaced QMSC member for {exam_program}', object_id=str(existing.id), scope=exam_program.program.short_name)
                            return redirect('billing_program_sheet', pk=pk, sheet=sheet)
                if member_form.is_valid():
                    obj = member_form.save(commit=False)
                    obj.exam_program = exam_program
                    obj.role = 'Member'
                    obj.save()
                    messages.success(request, 'QMSC member row saved.')
                    log_activity(request, 'CREATE', 'exam_billing', f'Added QMSC member for {exam_program}', object_id=str(obj.id), scope=exam_program.program.short_name)
                    return redirect('billing_program_sheet', pk=pk, sheet=sheet)
        qs = config['queryset'](exam_program)
        chairman   = qs.filter(role='Chairman').select_related('faculty').first()
        member_rows = qs.filter(role='Member').select_related('course', 'faculty').order_by('course__level', 'course__term', 'course__course_code')
        return render(request, 'exam_billing/sheet_form.html', {
            'exam_program': exam_program, 'sheet': sheet, 'title': config['title'],
            'rows': {'chairman': chairman, 'member_rows': member_rows},
            'form': member_form, 'chairman_form': chairman_form, 'member_form': member_form,
        })

    # ---- Standard POST handling for all other sheets -------------------------
    if request.method == 'POST':
        confirm_replace = 'confirm_replace' in request.POST
        # Handle replace for course-based sheets (qsetter, examiner, scrutinizer)
        if confirm_replace and sheet in ('qsetter', 'examiner', 'scrutinizer') and exam_program.is_editable:
            course_id = request.POST.get('course')
            part = request.POST.get('part')
            faculty_id = request.POST.get('faculty')
            if course_id and part and faculty_id:
                existing = config['model'].objects.filter(
                    exam_program=exam_program, course_id=course_id, part=part, is_deleted=False
                ).first()
                if existing:
                    existing.faculty_id = faculty_id
                    existing.save(update_fields=['faculty_id'])
                    messages.success(request, f'{config["title"]} assignment replaced.')
                    log_activity(request, 'UPDATE', 'exam_billing', f'Replaced {config["title"]} row for {exam_program}', object_id=str(existing.id), scope=exam_program.program.short_name)
                    return redirect('billing_program_sheet', pk=pk, sheet=sheet)

        form = config['form'](request.POST, exam_program=exam_program) if config['needs_ep'] else config['form'](request.POST)
        if form.is_valid() and exam_program.is_editable:
            obj = form.save(commit=False)
            if 'exam_program' in [f.name for f in obj._meta.fields]:
                obj.exam_program = exam_program
            obj.save()
            messages.success(request, f'{config["title"]} row saved.')
            log_activity(request, 'CREATE', 'exam_billing', f'Added {config["title"]} row for {exam_program}', object_id=str(obj.id), scope=exam_program.program.short_name)
            return redirect('billing_program_sheet', pk=pk, sheet=sheet)
        if not exam_program.is_editable:
            messages.error(request, 'This department bill is locked or submitted.')
    else:
        form = config['form'](exam_program=exam_program) if config['needs_ep'] else config['form']()

    queryset = config['queryset'](exam_program)

    # ---- RPSC: group into chairman row + tabulator rows per level/term -------
    if sheet == 'rpsc':
        chairman = queryset.filter(level='All').select_related('faculty').first()
        tab_groups = {}
        for item in queryset.exclude(level='All').select_related('faculty'):
            key = (item.level, item.term)
            if key not in tab_groups:
                tab_groups[key] = {'level': item.level, 'term': item.term, 'tabulators': []}
            tab_groups[key]['tabulators'].append(item)

        filtered_tabulators = [g for g in tab_groups.values() if g['tabulators']]
        rows = {
            'chairman': chairman,
            'tabulators': sorted(filtered_tabulators, key=lambda x: (x['level'], x['term']))
        }
    # ---- qsetter / examiner / scrutinizer grouped by course -----------------
    elif sheet in ['qsetter', 'examiner', 'scrutinizer']:
        grouped_rows = {}
        for item in queryset:
            c_id = item.course_id
            if c_id not in grouped_rows:
                grouped_rows[c_id] = {'course': item.course, 'part_a': None, 'part_b': None, 'full': None}
            if item.part == 'A':   grouped_rows[c_id]['part_a'] = item
            elif item.part == 'B': grouped_rows[c_id]['part_b'] = item
            elif item.part == 'A+B': grouped_rows[c_id]['full'] = item
        rows = sorted(grouped_rows.values(), key=lambda x: (x['course'].level, x['course'].term, x['course'].course_code))
    else:
        rows = queryset

    return render(request, 'exam_billing/sheet_form.html', {
        'exam_program': exam_program,
        'sheet': sheet,
        'title': config['title'],
        'columns': config.get('columns', []),
        'rows': rows,
        'form': form,
    })


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_sheet_delete(request, pk, sheet, row_id):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    if not exam_program.is_editable:
        messages.error(request, 'This department bill is locked or submitted.')
        return redirect('billing_program_sheet', pk=pk, sheet=sheet)
    config = _sheet_config(sheet)
    obj = get_object_or_404(config['model'].all_objects.filter(exam_program=exam_program), pk=row_id)
    
    column = request.GET.get('column')
    action_performed = 'DELETE'
    
    # Handle independent Part A/B deletion for merged sheets
    if hasattr(obj, 'part') and obj.part == 'A+B' and column in ['A', 'B']:
        obj.part = 'B' if column == 'A' else 'A'
        obj.save(update_fields=['part'])
        action_performed = 'UPDATE'
        msg = f'Removed Part {column} from assignment. Record persisted for Part {obj.part}.'
    else:
        if hasattr(obj, 'is_deleted'):
            obj.is_deleted = True
            obj.save(update_fields=['is_deleted'])
        else:
            obj.delete()
        msg = 'Row removed.'

    messages.success(request, msg)
    log_activity(request, action_performed, 'exam_billing', f'{msg} for {exam_program}', object_id=str(row_id), scope=exam_program.program.short_name)
    
    if sheet == 'courses':
        return redirect('billing_program_fundamentals', pk=pk)
    return redirect('billing_program_sheet', pk=pk, sheet=sheet)


@login_required
@require_access('exam_billing', 'manage_department_data')
def billing_row_delete_confirm(request, pk, sheet, row_id):
    """Returns a confirmation modal for row deletion."""
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    
    config = _sheet_config(sheet)
    obj = get_object_or_404(config['model'].all_objects.filter(exam_program=exam_program), pk=row_id)
    column = request.GET.get('column', '') # A or B for merged sheets
    
    delete_url = reverse('billing_program_sheet_delete', kwargs={'pk': pk, 'sheet': sheet, 'row_id': row_id})
    
    return render(request, 'exam_billing/partials/delete_confirm.html', {
        'title': config['title'],
        'delete_url': delete_url,
        'obj': obj,
        'column': column,
    })


@login_required
def get_course_info(request):
    """Returns course details (title, scripts) for dynamic form updates."""
    course_id = request.GET.get('course_id')
    if not course_id:
        return HttpResponse("")

    course = get_object_or_404(ExamCourse, pk=course_id)
    return HttpResponse(f'<div class="alert alert-info py-2 px-3 small mb-0 mt-2 border-0 shadow-sm" style="border-left: 4px solid #17a2b8 !important;"><i class="fas fa-info-circle mr-2"></i> <strong>Course Info:</strong> {course.course_title} ({course.no_of_scripts} scripts)</div>')


@login_required
def check_course_assignments(request):
    """Returns existing assignments for a course_code across the entire exam."""
    course_id = request.GET.get('course_id')
    exam_program_id = request.GET.get('exam_program_id')
    current_sheet = request.GET.get('sheet', '')

    if not course_id:
        return HttpResponse("")

    try:
        course = ExamCourse.objects.select_related('exam_program__exam', 'exam_program__program').get(pk=course_id)
    except ExamCourse.DoesNotExist:
        return HttpResponse("")

    exam = course.exam_program.exam
    course_code = course.course_code

    related_courses = ExamCourse.objects.filter(
        exam_program__exam=exam,
        course_code=course_code,
        is_deleted=False,
    ).select_related('exam_program__program')

    assignments = []
    for c in related_courses:
        program_name = c.exam_program.program.short_name or c.exam_program.program.name
        is_self = str(c.exam_program_id) == str(exam_program_id)

        for qs in c.question_setters.filter(is_deleted=False).select_related('faculty'):
            assignments.append({
                'program': program_name, 'sheet': 'Q Setter', 'sheet_key': 'qsetter',
                'faculty_name': qs.faculty.name, 'faculty_id': qs.faculty_id,
                'part': qs.part, 'is_self': is_self, 'id': qs.id,
            })
        for se in c.script_examiners.filter(is_deleted=False).select_related('faculty'):
            assignments.append({
                'program': program_name, 'sheet': 'Examiner', 'sheet_key': 'examiner',
                'faculty_name': se.faculty.name, 'faculty_id': se.faculty_id,
                'part': se.part, 'is_self': is_self, 'id': se.id,
            })
        for ss in c.script_scrutinizers.filter(is_deleted=False).select_related('faculty'):
            assignments.append({
                'program': program_name, 'sheet': 'Scrutinizer', 'sheet_key': 'scrutinizer',
                'faculty_name': ss.faculty.name, 'faculty_id': ss.faculty_id,
                'part': ss.part, 'is_self': is_self, 'id': ss.id,
            })
        for qm in c.qmsc_assignments.filter(is_deleted=False, role='Member').select_related('faculty'):
            faculty_name = qm.faculty.name if qm.faculty else qm.external_member_name or 'External'
            assignments.append({
                'program': program_name, 'sheet': 'QMSC', 'sheet_key': 'qmsc',
                'faculty_name': faculty_name, 'faculty_id': qm.faculty_id or 0,
                'part': '', 'is_self': is_self, 'id': qm.id,
            })

    return render(request, 'exam_billing/partials/course_assignment_info.html', {
        'assignments': assignments,
        'course_code': course_code,
        'current_sheet': current_sheet,
    })


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_row_edit(request, pk, sheet, row_id):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    if not exam_program.is_editable:
        messages.error(request, 'This department bill is locked or submitted.')
        return redirect('billing_program_sheet', pk=pk, sheet=sheet)
        
    config = _sheet_config(sheet)
    obj = get_object_or_404(config['model'].all_objects.filter(exam_program=exam_program), pk=row_id)
    
    # Special handling for QMSC forms (Chairman vs Member)
    if sheet == 'qmsc':
        from .forms import QMSCChairmanForm, QMSCMemberForm
        form_class = QMSCChairmanForm if obj.role == 'Chairman' else QMSCMemberForm
    else:
        form_class = config['form']
    
    if request.method == 'POST':
        form = form_class(request.POST, instance=obj, exam_program=exam_program) if config['needs_ep'] else form_class(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'{config["title"]} row updated.')
            log_activity(request, 'UPDATE', 'exam_billing', f'Updated {sheet} row for {exam_program}', object_id=str(obj.id), scope=exam_program.program.short_name)
            
            if request.headers.get('HX-Request') == 'true':
                response = HttpResponse("")
                response['HX-Refresh'] = 'true'
                return response
                
            if sheet == 'courses':
                return redirect('billing_program_fundamentals', pk=pk)
            return redirect('billing_program_sheet', pk=pk, sheet=sheet)
    else:
        form = form_class(instance=obj, exam_program=exam_program) if config['needs_ep'] else form_class(instance=obj)
        
    is_htmx = request.headers.get('HX-Request') == 'true'
    template = 'exam_billing/partials/row_edit_modal.html' if is_htmx else 'exam_billing/row_edit.html'
    
    return render(request, template, {
        'exam_program': exam_program,
        'form': form,
        'title': f"Edit {config['title']} Entry",
        'sheet': sheet,
        'obj': obj,
    })


@login_required
@require_access('exam_billing', 'manage_department_data')
def copy_faculty_to_exam(request, pk):
    if request.method != 'POST':
        raise PermissionDenied
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    copied = 0
    for faculty in FacultyProfile.objects.filter(program=exam_program.program, is_active=True):
        _, created = ExamFaculty.objects.get_or_create(exam_program=exam_program, faculty=faculty)
        copied += int(created)
    messages.success(request, f'Copied {copied} faculty profiles into this exam.')
    return redirect('billing_program_sheet', pk=pk, sheet='faculty')


@login_required
@require_access('exam_billing', 'manage_department_data')
def copy_previous_program_data(request, pk):
    if request.method != 'POST':
        raise PermissionDenied
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    if not exam_program.is_editable:
        messages.error(request, 'This department bill is locked or submitted.')
        return redirect('billing_program_workspace', pk=pk)
    previous = (
        ExamProgram.objects
        .filter(program=exam_program.program)
        .exclude(pk=exam_program.pk)
        .order_by('-exam__created_at')
        .first()
    )
    if not previous:
        messages.info(request, 'No previous exam data found for this department.')
        return redirect('billing_program_workspace', pk=pk)
    copied = _copy_program_seed_data(previous, exam_program)
    messages.success(request, f'Copied {copied["faculty"]} faculty and {copied["courses"]} courses from {previous.exam}.')
    log_activity(request, 'CREATE', 'exam_billing', f'Copied previous exam seed data into {exam_program}', object_id=str(exam_program.id), scope=exam_program.program.short_name)
    return redirect('billing_program_workspace', pk=pk)


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_submit(request, pk):
    if request.method != 'POST':
        raise PermissionDenied
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    if not exam_program.is_editable:
        messages.error(request, 'This department bill is locked or submitted.')
        return redirect('billing_program_workspace', pk=pk)
    exam_program.mark_submitted(request.user)
    log_activity(request, 'UPDATE', 'exam_billing', f'Submitted department bill: {exam_program}', object_id=str(exam_program.id), scope=exam_program.program.short_name)
    messages.success(request, 'Department bill submitted for review.')
    return redirect('billing_program_workspace', pk=pk)


@login_required
@require_access('exam_billing', 'approve_finalize')
def program_status(request, pk, action):
    if request.method != 'POST':
        raise PermissionDenied
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    if action == 'approve':
        exam_program.mark_approved(request.user)
    elif action == 'lock':
        summary = calculate_exam_program_summary(exam_program)
        exam_program.mark_finalized(summary['grand_total'], _summary_payload(summary))
    elif action == 'reopen':
        exam_program.status = 'draft'
        exam_program.save(update_fields=['status'])
    else:
        raise PermissionDenied
    log_activity(request, 'UPDATE', 'exam_billing', f'{action.title()} department bill: {exam_program}', object_id=str(exam_program.id), scope=exam_program.program.short_name, is_system_alert=True)
    messages.success(request, f'Department bill {action} complete.')
    return redirect('billing_program_workspace', pk=pk)


@login_required
def individual_bill(request, pk, faculty_id):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    faculty = get_object_or_404(FacultyProfile, pk=faculty_id)
    
    # Check if user has administrative permission OR is viewing their own bill
    has_admin_perm = request.user.profile.has_access('exam_billing', 'export_print')
    is_self = hasattr(request.user, 'faculty_profile') and request.user.faculty_profile.id == int(faculty_id)
    
    if not (has_admin_perm or is_self):
        raise PermissionDenied
    
    settings = getattr(exam_program.exam, 'settings', None)
    if settings is None:
        messages.error(request, 'No billing settings configured for this exam.')
        return redirect('billing_program_workspace', pk=pk)

    # Pre-fetch all assignments for full_or_half calculation
    all_qsetters = list(QuestionSetterAssignment.objects.filter(exam_program=exam_program, is_deleted=False).select_related('course'))
    all_examiners = list(ScriptExaminerAssignment.objects.filter(exam_program=exam_program, is_deleted=False).select_related('course'))
    all_scrutinizers = list(ScriptScrutinizerAssignment.objects.filter(exam_program=exam_program, is_deleted=False).select_related('course'))

    section_a_data = []
    for item in [a for a in all_qsetters if a.faculty_id == faculty.id]:
        mode = 'engineering' if item.course.is_engineering else 'non_engineering'
        size = full_or_half(all_qsetters, item)
        rate = getattr(settings, f'qsetter_{size}_{mode}_rate')
        section_a_data.append({'obj': item, 'rate': rate, 'amount': rate})

    section_b_data = []
    for item in [a for a in all_examiners if a.faculty_id == faculty.id]:
        mode = 'engineering' if item.course.is_engineering else 'non_engineering'
        size = full_or_half(all_examiners, item)
        rate = getattr(settings, f'examiner_{size}_{mode}_rate')
        qty = item.course.no_of_scripts
        section_b_data.append({'obj': item, 'rate': rate, 'qty': qty, 'amount': rate * qty})

    section_c_data = []
    for item in [a for a in all_scrutinizers if a.faculty_id == faculty.id]:
        mode = 'engineering' if item.course.is_engineering else 'non_engineering'
        size = full_or_half(all_scrutinizers, item)
        rate = getattr(settings, f'scrutinizer_{size}_{mode}_rate')
        qty = item.course.no_of_scripts
        section_c_data.append({'obj': item, 'rate': rate, 'qty': qty, 'amount': rate * qty})

    # Committee details (Section D)
    rpsc_counts = {f"{s.level}-{s.term}": s.total_students for s in exam_program.level_term_summaries.all()}
    total_all_students = sum(rpsc_counts.values())
    committees = []

    cecc = CECCAssignment.objects.filter(exam_program=exam_program, faculty=faculty, is_deleted=False).first()
    if cecc:
        role = (cecc.role or '').lower()
        rate = settings.cecc_chairman_rate if 'chair' in role or 'advisor' in role or 'invigilator' in role else settings.cecc_member_rate
        committees.append({'name': 'CECC', 'role': cecc.role, 'amount': rate})

    ec = ECMember.objects.filter(exam_program=exam_program, faculty=faculty, is_deleted=False).first()
    if ec:
        role = (ec.role or '').lower()
        rate = settings.ec_chairman_rate if 'chair' in role else settings.ec_member_rate
        committees.append({'name': 'EC', 'role': ec.role, 'amount': rate})

    for rpsc in RPSCAssignment.objects.filter(exam_program=exam_program, faculty=faculty, is_deleted=False):
        role = (rpsc.role or '').lower()
        rate = settings.rpsc_chairman_rate if 'chair' in role else settings.rpsc_member_rate
        students = total_all_students if rpsc.level == 'All' else rpsc_counts.get(f"{rpsc.level}-{rpsc.term}", 0)
        label = 'All Levels/Terms' if rpsc.level == 'All' else f'{rpsc.level}-{rpsc.term}'
        committees.append({'name': 'RPSC', 'role': f"{label} {rpsc.role}", 'qty': students, 'rate': rate, 'amount': rate * students})

    qmsc = QMSCAssignment.objects.filter(exam_program=exam_program, faculty=faculty, is_deleted=False).first()
    if qmsc:
        role = (qmsc.role or '').lower()
        rate = settings.qmsc_chairman_rate if 'chair' in role else settings.qmsc_member_rate
        committees.append({'name': 'QMSC', 'role': qmsc.role, 'rate': rate, 'amount': rate})

    qpsc = QPSCMember.objects.filter(exam_program=exam_program, faculty=faculty, is_deleted=False).first()
    if qpsc:
        rate = settings.qpsc_member_rate
        committees.append({'name': 'QPSC', 'role': qpsc.role, 'qty': qpsc.question_count, 'rate': rate, 'amount': rate * qpsc.question_count})
    
    bill = calculate_faculty_bill(exam_program, faculty_id)
    if not bill:
        messages.error(request, 'No bill found for selected faculty.')
        return redirect('billing_program_workspace', pk=pk)
        
    context = {
        'exam_program': exam_program,
        'faculty': faculty,
        'bill': bill,
        'section_a': section_a_data,
        'section_b': section_b_data,
        'section_c': section_c_data,
        'committees': committees,
        'today': timezone.now(),
    }
    return render(request, 'exam_billing/individual_bill.html', context)


@login_required
def faculty_bill_excel(request, pk, faculty_id):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    faculty = get_object_or_404(FacultyProfile, pk=faculty_id)
    require_exam_program_access(request.user, exam_program)
    
    bill = calculate_faculty_bill(exam_program, faculty_id)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Section A: Question Setting
        section_a = QuestionSetterAssignment.objects.filter(exam_program=exam_program, faculty=faculty, is_deleted=False).select_related('course')
        df_a = pd.DataFrame([{
            'SL': i+1,
            'Course Code': item.course.course_code,
            'PART': item.part,
            'Department': item.exam_program.program.short_name,
            'Course Title': item.course.course_title
        } for i, item in enumerate(section_a)])
        df_a.to_excel(writer, sheet_name='A-Question-Setting', index=False)
        
        # Section B: Evaluation
        section_b = ScriptExaminerAssignment.objects.filter(exam_program=exam_program, faculty=faculty, is_deleted=False).select_related('course')
        df_b = pd.DataFrame([{
            'SL': i+1,
            'Course Code': item.course.course_code,
            'PART': item.part,
            'Quantity': item.course.no_of_scripts
        } for i, item in enumerate(section_b)])
        df_b.to_excel(writer, sheet_name='B-Evaluation', index=False)
        
        # Summary Sheet
        summary_data = [
            ['Section', 'Amount (BDT)'],
            ['A. Question Paper Setting', str(bill['question_setting'])],
            ['B. Answer Script Evaluation', str(bill['script_examining'])],
            ['C. Answer Script Scrutiny', str(bill['scrutiny'])],
            ['D. Committee Bills', str(bill['committee_total'])],
            ['', ''],
            ['Grand Total', str(bill['total'])],
            ['Amount in words', bill['amount_in_words']]
        ]
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', header=False, index=False)
        
    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Bill-{faculty.name}-{exam_program.program.short_name}.xlsx"'
    return response


@login_required
@require_access('exam_billing', 'export_print')
def summary_csv(request, pk):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    summary = calculate_exam_program_summary(exam_program)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{exam_program.program.short_name}-bill-summary.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Designation', 'CECC', 'EC', 'RPSC', 'QMSC', 'QPSC', 'Q Setter', 'Examiner', 'Scrutiny', 'Total'])
    for row in summary['rows']:
        writer.writerow([
            row['faculty'].name,
            row['designation'],
            str(row['cecc']),
            str(row['ec']),
            str(row['rpsc']),
            str(row['qmsc']),
            str(row['qpsc']),
            str(row['question_setting']),
            str(row['script_examining']),
            str(row['scrutiny']),
            str(row['total']),
        ])
    return response


@login_required
@require_access('exam_billing', 'export_print')
def printable_package(request, pk):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    summary = calculate_exam_program_summary(exam_program)
    sheets = {key: _sheet_config(key)['queryset'](exam_program) for key in ['courses', 'cecc', 'ec', 'rpsc', 'qmsc', 'qpsc', 'qsetter', 'examiner', 'scrutinizer']}
    return render(request, 'exam_billing/printable_package.html', {
        'exam_program': exam_program,
        'summary': summary,
        'sheets': sheets,
    })


@login_required
@require_access('exam_billing', 'export_print')
def export_sheet_excel(request, pk, sheet):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    
    config = _sheet_config(sheet)
    queryset = config['queryset'](exam_program)
    
    # Handle RPSC specially as it has no columns defined in config (handled in template)
    if sheet == 'rpsc':
        data = []
        for i, obj in enumerate(queryset):
            data.append({
                'SL': i+1,
                'Level': obj.level,
                'Term': obj.term,
                'Role': obj.role,
                'Faculty': obj.faculty.name,
                'Designation': obj.faculty.designation
            })
    else:
        data = []
        for i, obj in enumerate(queryset):
            row = {'SL': i+1}
            for path, label in config.get('columns', []):
                val = obj
                for part in path.split('.'):
                    if val:
                        val = getattr(val, part, '')
                row[label] = val
            data.append(row)
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=config['title'][:31], index=False)
        
        # Formatting
        workbook = writer.book
        worksheet = writer.sheets[config['title'][:31]]
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 20)

    filename = f"{exam_program.program.short_name}_{sheet}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _sheet_config(sheet):
    configs = {
        'faculty': {
            'title': 'Faculty-Bills',
            'model': ExamFaculty,
            'form': ExamFacultyForm,
            'needs_ep': True,
            'queryset': lambda ep: ExamFaculty.objects.select_related('faculty').filter(exam_program=ep),
            'columns': [('faculty.name', 'Name'), ('designation_snapshot', 'Designation')],
        },
        'courses': {
            'title': 'Fundamentals',
            'model': ExamCourse,
            'form': ExamCourseForm,
            'needs_ep': True,
            'queryset': lambda ep: ExamCourse.objects.filter(exam_program=ep),
            'columns': [('level', 'Level'), ('term', 'Term'), ('course_code', 'Course Code'), ('course_title', 'Course Title'), ('no_of_scripts', 'Scripts')],
        },
        'cecc':        {'title': 'CECC',       'model': CECCAssignment,            'form': CECCAssignmentForm,            'needs_ep': True, 'queryset': lambda ep: CECCAssignment.objects.select_related('faculty').filter(exam_program=ep),                  'columns': [('faculty.name', 'Name'), ('faculty.designation', 'Designation'), ('role', 'Role')]},
        'ec':          {'title': 'EC',         'model': ECMember,                  'form': ECMemberForm,                  'needs_ep': True, 'queryset': lambda ep: ECMember.objects.select_related('faculty').filter(exam_program=ep),                      'columns': [('faculty.name', 'Name'), ('faculty.designation', 'Designation'), ('role', 'Role')]},
        'rpsc':        {'title': 'RPSC',       'model': RPSCAssignment,            'form': RPSCAssignmentForm,            'needs_ep': True, 'queryset': lambda ep: RPSCAssignment.objects.select_related('faculty').filter(exam_program=ep),                  'columns': []},
        'qmsc':        {'title': 'QMSC',       'model': QMSCAssignment,            'form': QMSCMemberForm,                'needs_ep': True, 'queryset': lambda ep: QMSCAssignment.objects.select_related('faculty', 'course').filter(exam_program=ep),     'columns': []},
        'qpsc':        {'title': 'QPSC',       'model': QPSCMember,                'form': QPSCMemberForm,                'needs_ep': True, 'queryset': lambda ep: QPSCMember.objects.select_related('faculty').filter(exam_program=ep),                    'columns': [('faculty.name', 'Name'), ('faculty.designation', 'Designation'), ('role', 'Role')]},
        'qsetter':     {'title': 'Q Setter',   'model': QuestionSetterAssignment,  'form': QuestionSetterAssignmentForm,  'needs_ep': True, 'queryset': lambda ep: QuestionSetterAssignment.objects.select_related('faculty', 'course').filter(exam_program=ep), 'columns': [('course.course_code', 'Course'), ('faculty.name', 'Question Setter'), ('part', 'Part')]},
        'examiner':    {'title': 'Examiner',   'model': ScriptExaminerAssignment,  'form': ScriptExaminerAssignmentForm,  'needs_ep': True, 'queryset': lambda ep: ScriptExaminerAssignment.objects.select_related('faculty', 'course').filter(exam_program=ep), 'columns': [('course.course_code', 'Course'), ('faculty.name', 'Examiner'), ('part', 'Part')]},
        'scrutinizer': {'title': 'Scrutinizer','model': ScriptScrutinizerAssignment,'form': ScriptScrutinizerAssignmentForm,'needs_ep': True, 'queryset': lambda ep: ScriptScrutinizerAssignment.objects.select_related('faculty', 'course').filter(exam_program=ep), 'columns': [('course.course_code', 'Course'), ('faculty.name', 'Scrutinizer'), ('part', 'Part')]},
        'summaries':   {'title': 'Student Counts','model': ExamLevelTermSummary,    'form': ExamLevelTermSummaryForm,     'needs_ep': True, 'queryset': lambda ep: ExamLevelTermSummary.objects.filter(exam_program=ep),                     'columns': [('level', 'Level'), ('term', 'Term'), ('total_students', 'Total Students')]},
    }
    if sheet not in configs:
        raise PermissionDenied
    return configs[sheet]


def _settings_defaults():
    template = BillingRateTemplate.objects.filter(is_default=True).first() or BillingRateTemplate.objects.create(name='Default', is_default=True)
    field_names = [
        field.name for field in BillingRateTemplate._meta.fields
        if field.name.endswith('_rate') or field.name.endswith('_mode')
    ]
    return {name: getattr(template, name) for name in field_names}


def _copy_program_seed_data(source, target):
    faculty_count = 0
    course_count = 0
    for exam_faculty in source.faculty.select_related('faculty').filter(is_deleted=False):
        _, created = ExamFaculty.objects.get_or_create(exam_program=target, faculty=exam_faculty.faculty)
        faculty_count += int(created)
    for course in source.courses.filter(is_deleted=False):
        _, created = ExamCourse.objects.get_or_create(
            exam_program=target,
            course_code=course.course_code,
            defaults={
                'level': course.level,
                'term': course.term,
                'offering_department': course.offering_department,
                'no_of_scripts': course.no_of_scripts,
                'syllabus': course.syllabus,
                'course_title': course.course_title,
            },
        )
        course_count += int(created)
    return {'faculty': faculty_count, 'courses': course_count}


def _summary_payload(summary):
    rows = []
    for row in summary['rows']:
        rows.append({
            'faculty_id': row['faculty'].id,
            'faculty_name': row['faculty'].name,
            'designation': row['designation'],
            'cecc': str(row['cecc']),
            'ec': str(row['ec']),
            'rpsc': str(row['rpsc']),
            'qmsc': str(row['qmsc']),
            'qpsc': str(row['qpsc']),
            'question_setting': str(row['question_setting']),
            'script_examining': str(row['script_examining']),
            'scrutiny': str(row['scrutiny']),
            'total': str(row['total']),
        })
    return {'grand_total': str(summary['grand_total']), 'rows': rows}
