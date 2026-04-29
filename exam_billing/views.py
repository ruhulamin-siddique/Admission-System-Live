from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.decorators import require_access
from core.utils import log_activity

from .billing_calculator import calculate_exam_program_summary, calculate_faculty_bill
from .forms import (
    BillingExamForm,
    BillingRateTemplateForm,
    CECCAssignmentForm,
    ECMemberForm,
    ExamCourseForm,
    ExamFacultyForm,
    FacultyProfileForm,
    QMSCAssignmentForm,
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
    total_payable = sum((calculate_exam_program_summary(ep)['grand_total'] for ep in active_exam_programs), 0)
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
    return render(request, 'exam_billing/exam_list.html', {'exams': exams})


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
@require_access('exam_billing', 'manage_department_data')
def faculty_directory(request):
    queryset = filter_by_user_scope(FacultyProfile.objects.select_related('program'), request.user)
    form = FacultyProfileForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        faculty = form.save()
        log_activity(request, 'CREATE', 'exam_billing', f'Added faculty profile: {faculty.name}', object_id=str(faculty.id), scope=faculty.program.short_name)
        messages.success(request, 'Faculty profile saved.')
        return redirect('billing_faculty_directory')
    return render(request, 'exam_billing/faculty_directory.html', {'faculty_list': queryset, 'form': form})


@login_required
@require_access('exam_billing', 'manage_department_data')
def faculty_delete(request, pk):
    faculty = get_object_or_404(filter_by_user_scope(FacultyProfile.objects.all(), request.user), pk=pk)
    faculty.is_deleted = True
    faculty.is_active = False
    faculty.save(update_fields=['is_deleted', 'is_active'])
    log_activity(request, 'DELETE', 'exam_billing', f'Deactivated faculty profile: {faculty.name}', object_id=str(faculty.id), scope=faculty.program.short_name)
    messages.success(request, 'Faculty profile deactivated.')
    return redirect('billing_faculty_directory')


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_workspace(request, pk):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    summary = calculate_exam_program_summary(exam_program)
    context = {
        'exam_program': exam_program,
        'summary': summary,
        'faculty_count': ExamFaculty.objects.filter(exam_program=exam_program).count(),
        'course_count': ExamCourse.objects.filter(exam_program=exam_program).count(),
    }
    return render(request, 'exam_billing/program_workspace.html', context)


@login_required
@require_access('exam_billing', 'manage_department_data')
def program_sheet(request, pk, sheet):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    config = _sheet_config(sheet)
    if request.method == 'POST':
        form = config['form'](request.POST, exam_program=exam_program) if config['needs_ep'] else config['form'](request.POST)
        if form.is_valid() and exam_program.is_editable:
            obj = form.save(commit=False)
            if hasattr(obj, 'exam_program'):
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
    return render(request, 'exam_billing/sheet_form.html', {
        'exam_program': exam_program,
        'sheet': sheet,
        'title': config['title'],
        'columns': config['columns'],
        'rows': queryset,
        'form': form,
        'summary': calculate_exam_program_summary(exam_program),
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
    obj = get_object_or_404(config['queryset'](exam_program), pk=row_id)
    if hasattr(obj, 'is_deleted'):
        obj.is_deleted = True
        obj.save(update_fields=['is_deleted'])
    else:
        obj.delete()
    messages.success(request, 'Row removed.')
    return redirect('billing_program_sheet', pk=pk, sheet=sheet)


@login_required
@require_access('exam_billing', 'manage_department_data')
def copy_faculty_to_exam(request, pk):
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
def program_submit(request, pk):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    exam_program.mark_submitted(request.user)
    log_activity(request, 'UPDATE', 'exam_billing', f'Submitted department bill: {exam_program}', object_id=str(exam_program.id), scope=exam_program.program.short_name)
    messages.success(request, 'Department bill submitted for review.')
    return redirect('billing_program_workspace', pk=pk)


@login_required
@require_access('exam_billing', 'approve_finalize')
def program_status(request, pk, action):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    if action == 'approve':
        exam_program.mark_approved(request.user)
    elif action == 'lock':
        exam_program.mark_locked()
    elif action == 'reopen':
        exam_program.status = 'draft'
        exam_program.save(update_fields=['status'])
    else:
        raise PermissionDenied
    log_activity(request, 'UPDATE', 'exam_billing', f'{action.title()} department bill: {exam_program}', object_id=str(exam_program.id), scope=exam_program.program.short_name, is_system_alert=True)
    messages.success(request, f'Department bill {action} complete.')
    return redirect('billing_program_workspace', pk=pk)


@login_required
@require_access('exam_billing', 'export_print')
def individual_bill(request, pk, faculty_id):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    bill = calculate_faculty_bill(exam_program, faculty_id)
    if not bill:
        messages.error(request, 'No bill found for selected faculty.')
        return redirect('billing_program_workspace', pk=pk)
    return render(request, 'exam_billing/individual_bill.html', {'exam_program': exam_program, 'bill': bill})


@login_required
@require_access('exam_billing', 'export_print')
def summary_csv(request, pk):
    exam_program = get_object_or_404(ExamProgram.objects.select_related('exam', 'program'), pk=pk)
    require_exam_program_access(request.user, exam_program)
    summary = calculate_exam_program_summary(exam_program)
    lines = ['Name,Designation,CECC,EC,RPSC,QMSC,QPSC,Q Setter,Examiner,Scrutiny,Total']
    for row in summary['rows']:
        lines.append(','.join([
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
        ]))
    response = HttpResponse('\n'.join(lines), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{exam_program.program.short_name}-bill-summary.csv"'
    return response


def _sheet_config(sheet):
    configs = {
        'faculty': {
            'title': 'Faculty-Bills',
            'form': ExamFacultyForm,
            'needs_ep': True,
            'queryset': lambda ep: ExamFaculty.objects.select_related('faculty').filter(exam_program=ep),
            'columns': [('faculty.name', 'Name'), ('designation_snapshot', 'Designation')],
        },
        'courses': {
            'title': 'Fundamentals',
            'form': ExamCourseForm,
            'needs_ep': False,
            'queryset': lambda ep: ExamCourse.objects.filter(exam_program=ep),
            'columns': [('level', 'Level'), ('term', 'Term'), ('course_code', 'Course Code'), ('course_title', 'Course Title'), ('no_of_scripts', 'Scripts'), ('total_students', 'Students')],
        },
        'cecc': {'title': 'CECC', 'form': CECCAssignmentForm, 'needs_ep': True, 'queryset': lambda ep: CECCAssignment.objects.select_related('faculty').filter(exam_program=ep), 'columns': [('faculty.name', 'Name'), ('faculty.designation', 'Designation'), ('role', 'Role')]},
        'ec': {'title': 'EC', 'form': ECMemberForm, 'needs_ep': True, 'queryset': lambda ep: ECMember.objects.select_related('faculty').filter(exam_program=ep), 'columns': [('faculty.name', 'Name'), ('faculty.designation', 'Designation'), ('role', 'Role'), ('level', 'Level'), ('term', 'Term')]},
        'rpsc': {'title': 'RPSC', 'form': RPSCAssignmentForm, 'needs_ep': True, 'queryset': lambda ep: RPSCAssignment.objects.select_related('faculty').filter(exam_program=ep), 'columns': [('level', 'Level'), ('term', 'Term'), ('faculty.name', 'Tabulator'), ('role', 'Role'), ('total_students', 'Students')]},
        'qmsc': {'title': 'QMSC', 'form': QMSCAssignmentForm, 'needs_ep': True, 'queryset': lambda ep: QMSCAssignment.objects.select_related('faculty', 'course').filter(exam_program=ep), 'columns': [('course.course_code', 'Course'), ('faculty.name', 'Member'), ('role', 'Role'), ('is_external', 'External')]},
        'qpsc': {'title': 'QPSC', 'form': QPSCMemberForm, 'needs_ep': True, 'queryset': lambda ep: QPSCMember.objects.select_related('faculty').filter(exam_program=ep), 'columns': [('faculty.name', 'Name'), ('role', 'Role'), ('question_count', 'Questions')]},
        'qsetter': {'title': 'Q Setter', 'form': QuestionSetterAssignmentForm, 'needs_ep': True, 'queryset': lambda ep: QuestionSetterAssignment.objects.select_related('faculty', 'course').filter(exam_program=ep), 'columns': [('course.course_code', 'Course'), ('faculty.name', 'Question Setter'), ('part', 'Part')]},
        'examiner': {'title': 'Examiner', 'form': ScriptExaminerAssignmentForm, 'needs_ep': True, 'queryset': lambda ep: ScriptExaminerAssignment.objects.select_related('faculty', 'course').filter(exam_program=ep), 'columns': [('course.course_code', 'Course'), ('faculty.name', 'Examiner'), ('part', 'Part')]},
        'scrutinizer': {'title': 'Scrutinizer', 'form': ScriptScrutinizerAssignmentForm, 'needs_ep': True, 'queryset': lambda ep: ScriptScrutinizerAssignment.objects.select_related('faculty', 'course').filter(exam_program=ep), 'columns': [('course.course_code', 'Course'), ('faculty.name', 'Scrutinizer'), ('part', 'Part')]},
    }
    if sheet not in configs:
        raise PermissionDenied
    return configs[sheet]
