from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q, Case, When, IntegerField, Sum, Max, Value
from django.db.models.functions import Cast, Coalesce, Lower, Right, TruncMonth
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.html import escape
from django.utils import timezone
from core.decorators import require_access
from exam_billing.models import BillingExam, ExamProgram
from exam_billing.scope import get_allowed_programs
import xhtml2pdf.pisa as pisa
from io import BytesIO
from django.template.loader import get_template
from urllib.parse import urlencode
from master_data.models import Program
from .models import Student, ProgramChangeHistory, SMSHistory, AdmissionStatusHistory
from .geo_data import BANGLADESH_GEO
import json
import os
from django.conf import settings

def link_callback(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those
    resources on local disk.
    """
    import os
    from django.conf import settings
    from django.contrib.staticfiles import finders

    # Handle media files
    if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    # Handle static files
    elif settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
    else:
        return uri

    # make sure that file exists
    if not os.path.isfile(path):
        # Fallback to staticfiles finders if not in STATIC_ROOT (useful during dev)
        found_path = finders.find(uri.replace(settings.STATIC_URL, "")) if settings.STATIC_URL else None
        if found_path:
            return found_path
        return uri
    return path

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, link_callback=link_callback)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None

@require_access('students', 'view_directory')
def print_blank_form(request):
    """Generates a blank PDF admission form for manual data collection."""
    from core.models import SystemSettings
    sys_settings = SystemSettings.objects.first()
    context = {
        'current_time': timezone.now(),
        'sys_settings': sys_settings
    }
    pdf_response = render_to_pdf('students/pdf/blank_form.html', context)
    if pdf_response:
        pdf_response['Content-Disposition'] = 'filename="Blank_Admission_Form.pdf"'
        return pdf_response
    return HttpResponse("Error generating PDF", status=500)

@require_access('dashboard', 'view')
def dashboard(request):
    """Main dashboard view with summary statistics."""
    # Initialize all date variables at the very beginning
    _now = timezone.now()
    _today = _now.date()
    _start_of_week = _today - timezone.timedelta(days=_today.weekday())
    _start_of_month = _today.replace(day=1)
    _twelve_months_ago = _today - timezone.timedelta(days=365)

    # Monthly Admission Trends (Last 12 months) based on Admission Date
    monthly_data = Student.objects.filter(admission_date__gte=_twelve_months_ago) \
        .annotate(month=TruncMonth('admission_date')) \
        .values('month') \
        .annotate(count=Count('student_id')) \
        .order_by('month')

    # Format monthly data for Chart.js (YYYY-MM)
    monthly_admissions = [
        {'month': entry['month'].strftime('%Y-%m') if entry['month'] else 'Unknown', 'count': entry['count']}
        for entry in monthly_data
    ]

    # Fetch Program Name to Short Name mapping for tooltips and display
    program_map = {p.name: p.short_name or p.name for p in Program.objects.all()}

    # Program Distribution
    program_dist_qs = Student.objects.values('program').annotate(count=Count('student_id'))
    agg_dist = {}
    for item in program_dist_qs:
        full_name = item['program'] or 'Unknown'
        short = program_map.get(full_name, full_name).strip().upper()
        if short not in agg_dist:
            agg_dist[short] = {
                'program': full_name,
                'short_name': short,
                'count': 0
            }
        agg_dist[short]['count'] += item['count']
        
    program_dist = list(agg_dist.values())
    program_dist.sort(key=lambda x: x['count'], reverse=True)

    # Gender Distribution (Enhanced with Coalesce)
    from django.db.models.functions import Coalesce
    from django.db.models import Value
    gender_dist = Student.objects.annotate(
        gender_label=Coalesce('gender', Value('Unknown'))
    ).values('gender_label').annotate(count=Count('student_id')).order_by('-count')
    
    # Format for chart (handling potentially empty list)
    gender_chart_data = [{'gender': g['gender_label'] or 'Unknown', 'count': g['count']} for g in gender_dist]

    # Financial Summary
    financials = Student.objects.aggregate(
        total_payments=Sum('admission_payment'),
        total_waivers=Sum('waiver'),
        total_second_installments=Sum('second_installment')
    )

    # 1. Identify Latest Batch (Numeric Extraction)
    import re
    all_batches = list(Student.objects.values_list('batch', flat=True).distinct())
    latest_batch = None
    max_num = -1
    
    for b in all_batches:
        if b:
            nums = re.findall(r'\d+', b)
            if nums:
                n = int(nums[0])
                if n > max_num:
                    max_num = n
                    latest_batch = b

    # 2. Intake stats for the latest batch (Enhanced)
    latest_batch_intake = []
    total_batch_students = 0
    if latest_batch:
        batch_students = Student.objects.filter(batch=latest_batch)
        total_batch_students = batch_students.count()
        
        latest_intake_qs = batch_students.values('program').annotate(
            total=Count('student_id'),
            male=Count('student_id', filter=Q(gender='Male')),
            female=Count('student_id', filter=Q(gender='Female')),
            active=Count('student_id', filter=Q(admission_status='Active')),
            cancelled=Count('student_id', filter=Q(admission_status='Cancelled')),
            non_residential=Count('student_id', filter=Q(is_non_residential=True)),
            revenue=Sum('admission_payment'),
            quota=Count('student_id', filter=Q(is_armed_forces_child=True) | Q(is_freedom_fighter_child=True) | Q(is_july_joddha_2024=True))
        ).order_by('-total')

        aggregated_intake = {}
        for item in latest_intake_qs:
            full_name = item['program'] or 'Unknown'
            short = program_map.get(full_name, full_name).strip().upper()
            
            if short not in aggregated_intake:
                aggregated_intake[short] = {
                    'program': full_name,
                    'short_name': short,
                    'count': 0,
                    'male': 0,
                    'female': 0,
                    'active': 0,
                    'cancelled': 0,
                    'non_residential': 0,
                    'revenue': 0.0,
                    'quota': 0
                }
                
            aggregated_intake[short]['count'] += item['total']
            aggregated_intake[short]['male'] += item['male']
            aggregated_intake[short]['female'] += item['female']
            aggregated_intake[short]['active'] += item['active']
            aggregated_intake[short]['cancelled'] += item['cancelled']
            aggregated_intake[short]['non_residential'] += item['non_residential']
            aggregated_intake[short]['revenue'] += float(item['revenue'] or 0)
            aggregated_intake[short]['quota'] += item['quota']

        latest_batch_intake = list(aggregated_intake.values())
        latest_batch_intake.sort(key=lambda x: x['count'], reverse=True)

    # Periodic Admission Stats (Filtered by Latest Batch only)
    periodic_qs = Student.objects.filter(batch=latest_batch) if latest_batch else Student.objects.all()
    today_qs = periodic_qs.filter(admission_date=_today)
    week_qs = periodic_qs.filter(admission_date__gte=_start_of_week)
    month_qs = periodic_qs.filter(admission_date__gte=_start_of_month)

    def _get_periodic_breakdown(qs):
        agg_bd = {}
        for item in qs.values('program').annotate(count=Count('student_id')):
            full_name = item['program'] or 'Unknown'
            short = program_map.get(full_name, full_name).strip().upper()
            if short not in agg_bd:
                agg_bd[short] = {
                    'program': full_name,
                    'short_name': short,
                    'count': 0
                }
            agg_bd[short]['count'] += item['count']
            
        breakdown = list(agg_bd.values())
        breakdown.sort(key=lambda x: x['count'], reverse=True)
        return breakdown

    # Get semester name for the latest intake
    latest_semester = Student.objects.filter(batch=latest_batch).values_list('semester_name', flat=True).first() if latest_batch else "Unknown"

    periodic_stats = {
        'batch': latest_batch,
        'semester': latest_semester,
        'today': {
            'label': _now.strftime('%B %d, %Y'),
            'count': today_qs.count(),
            'breakdown': _get_periodic_breakdown(today_qs)
        },
        'week': {
            'label': f"{_start_of_week.strftime('%b %d')} - {_today.strftime('%b %d')}",
            'count': week_qs.count(),
            'breakdown': _get_periodic_breakdown(week_qs)
        },
        'month': {
            'label': _now.strftime('%B %Y'),
            'count': month_qs.count(),
            'breakdown': _get_periodic_breakdown(month_qs)
        }
    }

    # Recent Students with Short Names (Ordered by Creation Date)
    recent_students = []
    for s in Student.objects.order_by('-created_at')[:10]:
        recent_students.append({
            'student_id': s.student_id,
            'student_name': s.student_name,
            'program': s.program,
            'short_name': program_map.get(s.program, s.program),
            'batch': s.batch,
            'admission_status': s.admission_status
        })

    # Enrollment Insights
    cancelled_admissions = Student.objects.filter(admission_status='Cancelled').count()
    special_stats = Student.objects.aggregate(
        freedom_fighter=Count('student_id', filter=Q(is_freedom_fighter_child=True)),
        july_joddha=Count('student_id', filter=Q(is_july_joddha_2024=True)),
        armed_forces=Count('student_id', filter=Q(is_armed_forces_child=True)),
        credit_transfer=Count('student_id', filter=Q(is_credit_transfer=True)),
        non_residential=Count('student_id', filter=Q(is_non_residential=True)),
    )

    stats = {
        'total_students': Student.objects.count(),
        'active_students': Student.objects.filter(admission_status='Active').count(),
        'male_students': Student.objects.filter(gender='Male').count(),
        'female_students': Student.objects.filter(gender='Female').count(),
        'by_program': program_dist[:5],
        'recent_students': recent_students,
        'monthly_admissions': monthly_admissions,
        'program_chart': program_dist,
        'gender_chart': gender_chart_data,
        'cancelled_admissions': cancelled_admissions,
        'special': special_stats,
        'non_residential_count': special_stats['non_residential'],
        'latest_batch_name': latest_batch,
        'latest_batch_intake': latest_batch_intake,
        'total_batch_students': total_batch_students,
        'periodic': periodic_stats,
        'all_batches': sorted([b for b in all_batches if b], reverse=True),
        'pending_registrations': User.objects.filter(profile__registration_status='PENDING').count()
    }
    # --- Exam Billing Integration ---
    billing_stats = {
        'has_access': request.user.profile.has_access('exam_billing', 'view_dashboard'),
        'active_exams': [],
        'pending_approvals': 0,
        'my_pending_tasks': 0
    }
    
    if billing_stats['has_access']:
        allowed_programs = get_allowed_programs(request.user)
        active_exams = BillingExam.objects.exclude(status='finalized').prefetch_related('programs')
        
        # Filter exams where the user has at least one allowed program
        if not request.user.is_superuser and not request.user.profile.has_access('exam_billing', 'view_all_departments'):
            active_exams = active_exams.filter(programs__program__in=allowed_programs).distinct()
            billing_stats['my_pending_tasks'] = ExamProgram.objects.filter(
                program__in=allowed_programs, 
                status__in=['draft']
            ).count()
        else:
            billing_stats['pending_approvals'] = ExamProgram.objects.filter(status='submitted').count()

        billing_stats['active_exams'] = active_exams[:5]

    return render(request, 'students/dashboard.html', {
        'stats': stats,
        'monthly_admissions': json.dumps(monthly_admissions),
        'program_dist': json.dumps(program_dist),
        'gender_chart_data': json.dumps(gender_chart_data),
        'financials': financials,
        'latest_batch': latest_batch,
        'latest_batch_intake': latest_batch_intake,
        'billing_stats': billing_stats
    })

from django.core.paginator import Paginator

DIRECTORY_DEFAULT_PER_PAGE = 25
DIRECTORY_DEFAULT_SORT = 'dept_batch_serial'
DIRECTORY_FILTER_FIELDS = (
    'search',
    'year',
    'dept',
    'program',
    'batch',
    'type',
    'gender',
    'status',
    'special_category',
    'sort',
)
DIRECTORY_SORT_OPTIONS = (
    ('dept_batch_serial', 'Department -> Latest Batch -> ID Serial'),
    ('batch_dept_serial', 'Latest Batch -> Department -> ID Serial'),
)


def _get_directory_sort_choices():
    return DIRECTORY_SORT_OPTIONS


def _get_directory_params(request):
    params = {
        key: request.GET.get(key, '').strip()
        for key in DIRECTORY_FILTER_FIELDS
    }

    valid_sort_values = {choice[0] for choice in DIRECTORY_SORT_OPTIONS}
    if params['sort'] not in valid_sort_values:
        params['sort'] = DIRECTORY_DEFAULT_SORT

    try:
        per_page = int(request.GET.get('per_page', DIRECTORY_DEFAULT_PER_PAGE))
    except (TypeError, ValueError):
        per_page = DIRECTORY_DEFAULT_PER_PAGE

    params['per_page'] = per_page if per_page > 0 else DIRECTORY_DEFAULT_PER_PAGE
    params['page'] = request.GET.get('page', '1').strip() or '1'
    return params


def _build_directory_scope_query(user):
    if user.is_superuser:
        return Q()

    profile = getattr(user, 'profile', None)
    scope = (getattr(profile, 'department_scope', '') or '').strip()
    if not scope:
        return Q()

    scope_values = {scope}
    program = Program.objects.filter(
        Q(short_name__iexact=scope) | Q(name__iexact=scope)
    ).first()
    if program:
        scope_values.add(program.name)
        if program.short_name:
            scope_values.add(program.short_name)

    scope_query = Q()
    for value in scope_values:
        scope_query |= Q(program__iexact=value)
    return scope_query


def _get_directory_base_queryset(user):
    queryset = Student.objects.annotate(
        normalized_program=Lower(Coalesce('program', Value(''))),
        batch_sort_value=Coalesce('batch_number', Value(0)),
        student_serial=Case(
            When(
                student_id__regex=r'[0-9]{3}$',
                then=Cast(Right('student_id', 3), IntegerField()),
            ),
            default=Value(9999),
            output_field=IntegerField(),
        ),
    )
    scope_query = _build_directory_scope_query(user)
    if scope_query:
        queryset = queryset.filter(scope_query)
    return queryset


def _apply_directory_filters(queryset, params):
    query = params['search']
    if query:
        queryset = queryset.filter(
            Q(student_name__icontains=query) |
            Q(student_id__icontains=query) |
            Q(student_mobile__icontains=query) |
            Q(father_name__icontains=query)
        )

    if params['program']:
        queryset = queryset.filter(program=params['program'])
    if params['batch']:
        queryset = queryset.filter(batch=params['batch'])
    if params['year']:
        queryset = queryset.filter(admission_year=params['year'])
    if params['dept']:
        queryset = queryset.filter(cluster=params['dept'])
    if params['gender']:
        queryset = queryset.filter(gender=params['gender'])
    if params['status']:
        queryset = queryset.filter(admission_status=params['status'])
    else:
        queryset = queryset.exclude(admission_status='Cancelled')
    if params['type']:
        queryset = queryset.filter(program_type=params['type'])

    if params['special_category']:
        cat = params['special_category']
        if cat == 'non_residential':
            queryset = queryset.filter(is_non_residential=True)
        elif cat == 'freedom_fighter':
            queryset = queryset.filter(is_freedom_fighter_child=True)
        elif cat == 'armed_forces':
            queryset = queryset.filter(is_armed_forces_child=True)
        elif cat == 'july_joddha':
            queryset = queryset.filter(is_july_joddha_2024=True)
        elif cat == 'credit_transfer':
            queryset = queryset.filter(is_credit_transfer=True)
        elif cat == 'temp_cancel':
            queryset = queryset.filter(is_temp_admission_cancel=True)

    return queryset


def _apply_directory_sorting(queryset, params):
    if params['sort'] == 'batch_dept_serial':
        return queryset.order_by(
            '-batch_sort_value',
            '-admission_year',
            'normalized_program',
            'student_serial',
            'student_id',
        )

    return queryset.order_by(
        'normalized_program',
        '-batch_sort_value',
        '-admission_year',
        'student_serial',
        'student_id',
    )


def _get_non_empty_values(queryset, field_name, order_by):
    queryset = queryset.exclude(**{f'{field_name}__isnull': True})
    field = queryset.model._meta.get_field(field_name)
    if getattr(field, 'empty_strings_allowed', False):
        queryset = queryset.exclude(**{field_name: ''})

    return queryset.values_list(field_name, flat=True).distinct().order_by(order_by)


def _get_batch_filter_values(base_queryset):
    return (
        base_queryset.exclude(batch__isnull=True)
        .exclude(batch='')
        .values('batch')
        .annotate(
            max_batch_number=Coalesce(Max('batch_number'), Value(0)),
            max_admission_year=Coalesce(Max('admission_year'), Value(0)),
        )
        .order_by('-max_batch_number', '-max_admission_year', 'batch')
        .values_list('batch', flat=True)
    )


def _build_directory_filter_metadata(base_queryset):
    return {
        'years': _get_non_empty_values(base_queryset, 'admission_year', '-admission_year'),
        'clusters': _get_non_empty_values(base_queryset, 'cluster', 'cluster'),
        'programs': _get_non_empty_values(base_queryset, 'program', 'program'),
        'batches': _get_batch_filter_values(base_queryset),
        'genders': ['Male', 'Female', 'Other'],
        'statuses': _get_non_empty_values(base_queryset, 'admission_status', 'admission_status'),
    }


def _build_directory_state(request):
    params = _get_directory_params(request)
    base_queryset = _get_directory_base_queryset(request.user)
    filtered_queryset = _apply_directory_sorting(_apply_directory_filters(base_queryset, params), params)
    total_count = filtered_queryset.count()
    paginator = Paginator(filtered_queryset, params['per_page'])
    page_obj = paginator.get_page(params['page'])

    export_querystring = urlencode({
        key: value
        for key, value in params.items()
        if key in DIRECTORY_FILTER_FIELDS and value
    })

    return {
        'params': params,
        'filtered_queryset': filtered_queryset,
        'page_obj': page_obj,
        'page_range': paginator.get_elided_page_range(number=page_obj.number),
        'page_ellipsis': paginator.ELLIPSIS,
        'per_page': params['per_page'],
        'total_count': total_count,
        'filter_metadata': _build_directory_filter_metadata(base_queryset),
        'export_querystring': export_querystring,
    }

@require_access('students', 'view_directory')
def student_list(request):
    """Full student list with advanced numeric sorting and multi-field filtering."""
    directory_state = _build_directory_state(request)
    params = directory_state['params']
    context = {
        'page_obj': directory_state['page_obj'],
        'page_range': directory_state['page_range'],
        'page_ellipsis': directory_state['page_ellipsis'],
        'query': params['search'],
        'per_page': directory_state['per_page'],
        'total_count': directory_state['total_count'],
        'selected_program': params['program'],
        'selected_batch': params['batch'],
        'selected_year': params['year'],
        'selected_dept': params['dept'],
        'selected_gender': params['gender'],
        'selected_status': params['status'],
        'selected_type': params['type'],
        'selected_special_category': params['special_category'],
        'selected_sort': params['sort'],
        'sort_options': _get_directory_sort_choices(),
        'filter_metadata': directory_state['filter_metadata'],
        'export_querystring': directory_state['export_querystring'],
        'program_map': {p.name: p.short_name or p.name for p in Program.objects.all()},
    }

    template = 'students/partials/directory_results.html' if request.headers.get('HX-Request') else 'students/list.html'
    return render(request, template, context)

@require_access('students', 'view_directory')
def student_short_info(request, student_id):
    """Returns a compact card with student info not visible in the main directory."""
    student = get_object_or_404(
        Student.objects.only(
            'student_id',
            'student_name',
            'photo_path',
            'student_email',
            'blood_group',
            'religion',
            'father_mobile',
            'mother_mobile',
            'emergency_contact',
            'present_address',
            'permanent_address',
        ),
        student_id=student_id,
    )
    return render(request, 'students/partials/short_info_card.html', {'student': student})

@require_access('students', 'delete_record')
def delete_student(request, student_id):
    """Permanently delete a student record with audit logging."""
    student = get_object_or_404(Student, student_id=student_id)
    if request.method == 'POST':
        student_name = student.student_name
        student.delete()
        from core.utils import log_activity
        log_activity(request, 'DELETE', 'students', f'Permanently deleted student record: {student_name}', object_id=student_id)
        messages.success(request, f"Student {student_id} has been permanently removed.")
        return redirect('student_list')
    return redirect('student_profile', student_id=student_id)

@require_access('students', 'manage_migrations')
def migration_center(request):
    """Refined Migration Center with Search-First logic and History."""
    query = request.GET.get('search', '').strip()
    per_page = request.GET.get('per_page', 10)
    page_number = request.GET.get('page', 1)
    
    # Context initialization
    context = {'query': query, 'per_page': int(per_page)}
    
    if query:
        # State 1: Search Active
        students_queryset = Student.objects.filter(
            Q(student_name__icontains=query) | 
            Q(student_id__icontains=query) |
            Q(student_mobile__icontains=query)
        ).order_by('student_id')
        
        paginator = Paginator(students_queryset, per_page)
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        context['page_range'] = paginator.get_elided_page_range(number=page_obj.number, on_each_side=2, on_ends=1)
        
        template = 'students/partials/migration_table.html' if request.headers.get('HX-Request') else 'students/migration_list.html'
    else:
        # State 2: No Search (Show History)
        migration_history = ProgramChangeHistory.objects.order_by('-change_date')[:15]
        context['migration_history'] = migration_history
        
        template = 'students/partials/migration_history_table.html' if request.headers.get('HX-Request') else 'students/migration_list.html'
        
    return render(request, template, context)

@require_access('students', 'cancel_admission')
def cancellation_hub(request):
    """Search-First hub for managing admission cancellations and suspensions."""
    query = request.GET.get('search', '').strip()
    
    # Aggregate Analytics for the Stat Card
    cancelled_count = Student.objects.filter(admission_status='Cancelled').count()
    
    context = {
        'query': query,
        'cancelled_count': cancelled_count,
    }
    
    if query:
        # Search for students eligible for status change (Active/Inactive)
        students = Student.objects.filter(
            Q(student_name__icontains=query) | 
            Q(student_id__icontains=query)
        ).exclude(admission_status='Cancelled').order_by('student_id')[:20]
        context['students'] = students
    
    template = 'students/partials/cancellation_results.html' if request.headers.get('HX-Request') else 'students/cancellation_hub.html'
    return render(request, template, context)

@require_access('students', 'cancel_admission')
def cancellation_list_modal(request):
    """Returns a partial list of cancelled students for the drill-down modal."""
    cancelled_students = Student.objects.filter(admission_status='Cancelled').order_by('-last_updated')
    return render(request, 'students/partials/cancelled_list_modal.html', {'students': cancelled_students})

@require_access('students', 'cancel_admission')
def cancel_admission(request, student_id):
    """View to handle the actual cancellation logic with history logging."""
    student = get_object_or_404(Student, pk=student_id)
    if request.method == "POST":
        data = request.POST
        reason_cat = data.get('reason_category')
        notes = data.get('notes')
        
        try:
            with transaction.atomic():
                old_status = student.admission_status
                # Update Student
                student.admission_status = 'Cancelled'
                student.is_temp_admission_cancel = (reason_cat == 'Temporary')
                student.save()
                
                # Log History
                AdmissionStatusHistory.objects.create(
                    student=student,
                    old_status=old_status,
                    new_status='Cancelled',
                    reason_category=reason_cat,
                    custom_notes=notes,
                    performed_by=request.user
                )
            from core.utils import log_activity
            log_activity(request, 'UPDATE', 'students', f'Cancelled admission for {student.student_name} (Reason: {reason_cat})', object_id=student.student_id)
            messages.success(request, f"Admission for {student.student_name} has been CANCELLED successfully.")
        except Exception as e:
            messages.error(request, f"Error processing cancellation: {str(e)}")
        return redirect('cancellation_hub')
    
    return render(request, 'students/cancel_form.html', {'student': student})

@require_access('students', 'cancel_admission')
def api_bulk_cancel_admission(request):
    """Bulk cancel admissions for selected student IDs with HTMX support."""
    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids')
        reason_cat = request.POST.get('reason_category', 'Other')
        notes = request.POST.get('notes', 'Bulk cancelled')
        
        if not student_ids:
            if request.headers.get('HX-Request'):
                return HttpResponse('<script>Swal.fire("Warning", "No students selected.", "warning");</script>')
            messages.warning(request, "No students selected for cancellation.")
            return redirect('student_list')
            
        cancelled_count = 0
        try:
            with transaction.atomic():
                students = Student.objects.filter(student_id__in=student_ids).exclude(admission_status='Cancelled')
                for student in students:
                    old_status = student.admission_status
                    student.admission_status = 'Cancelled'
                    student.save()
                    
                    AdmissionStatusHistory.objects.create(
                        student=student,
                        old_status=old_status,
                        new_status='Cancelled',
                        reason_category=reason_cat,
                        custom_notes=notes,
                        performed_by=request.user
                    )
                    cancelled_count += 1
            
            success_msg = f"Successfully cancelled {cancelled_count} admissions."
            from core.utils import log_activity
            log_activity(request, 'UPDATE', 'students', f'Bulk cancelled {cancelled_count} admissions (Reason: {reason_cat})', object_id=f"BATCH-{cancelled_count}")
            
            if request.headers.get('HX-Request'):
                response = HttpResponse(f'<div class="alert alert-success"><i class="fas fa-check-circle mr-2"></i> {escape(success_msg)}</div>')
                response['HX-Trigger'] = json.dumps({
                    "refreshCancelledCount": True,
                    "clearSearchResults": True
                })
                return response
            
            messages.success(request, success_msg)
        except Exception as e:
            if request.headers.get('HX-Request'):
                return HttpResponse(f'<div class="alert alert-danger">Error: {escape(str(e))}</div>')
            messages.error(request, f"Bulk cancellation failed: {str(e)}")
            
    return redirect('student_list')

def _get_history_suggestions():
    """Extracts unique values from existing student records for autocomplete suggestions."""
    schools = Student.objects.exclude(ssc_school__isnull=True).exclude(ssc_school='') \
        .values_list('ssc_school', flat=True).distinct().order_by('ssc_school')
    colleges = Student.objects.exclude(hsc_college__isnull=True).exclude(hsc_college='') \
        .values_list('hsc_college', flat=True).distinct().order_by('hsc_college')
    
    # Years logic: Combine SSC and HSC years, sort descending
    ssc_years = set(Student.objects.exclude(ssc_year__isnull=True).exclude(ssc_year='') \
        .values_list('ssc_year', flat=True).distinct())
    hsc_years = set(Student.objects.exclude(hsc_year__isnull=True).exclude(hsc_year='') \
        .values_list('hsc_year', flat=True).distinct())
    years = sorted(list(ssc_years | hsc_years), reverse=True)
    
    return {
        'existing_schools': list(schools),
        'existing_colleges': list(colleges),
        'existing_years': years
    }

@require_access('dashboard', 'view')
def api_periodic_students(request):
    """Returns a partial list of students for the periodic drill-down modal."""
    period = request.GET.get('period')
    program = request.GET.get('program')
    
    _now = timezone.now()
    _today = _now.date()
    
    # Identify Latest Batch
    import re
    all_batches = list(Student.objects.values_list('batch', flat=True).distinct())
    latest_batch = None
    max_num = -1
    for b in all_batches:
        if b:
            nums = re.findall(r'\d+', b)
            if nums:
                n = int(nums[0])
                if n > max_num:
                    max_num = n
                    latest_batch = b

    qs = Student.objects.filter(batch=latest_batch) if latest_batch else Student.objects.all()
    
    if period == 'today':
        qs = qs.filter(admission_date=_today)
    elif period == 'week':
        _start_of_week = _today - timezone.timedelta(days=_today.weekday())
        qs = qs.filter(admission_date__gte=_start_of_week)
    elif period == 'month':
        _start_of_month = _today.replace(day=1)
        qs = qs.filter(admission_date__gte=_start_of_month)
        
    if program:
        qs = qs.filter(program=program)
        
    students = qs.order_by('-created_at')[:50] # Limit to 50 for quick view
    
    return render(request, 'students/partials/periodic_student_list.html', {
        'students': students,
        'period': period,
        'program': program,
        'count': qs.count()
    })

@require_access('dashboard', 'view')
def api_program_distribution(request):
    """Returns JSON data for program distribution, optionally filtered by batch."""
    batch = request.GET.get('batch')
    
    qs = Student.objects.all()
    if batch and batch != 'all':
        qs = qs.filter(batch=batch)
        
    # Program Distribution logic (same as in dashboard)
    program_map = {p.name: p.short_name or p.name for p in Program.objects.all()}
    dist_qs = qs.values('program').annotate(count=Count('student_id'))
    
    agg_dist = {}
    for item in dist_qs:
        full_name = item['program'] or 'Unknown'
        short = program_map.get(full_name, full_name).strip().upper()
        if short not in agg_dist:
            agg_dist[short] = {'short_name': short, 'count': 0}
        agg_dist[short]['count'] += item['count']
        
    data = sorted(list(agg_dist.values()), key=lambda x: x['count'], reverse=True)
    return JsonResponse({'distribution': data})

@require_access('dashboard', 'view')
def api_gender_distribution(request):
    """Returns JSON data for gender distribution, optionally filtered by batch."""
    batch = request.GET.get('batch')
    
    qs = Student.objects.all()
    if batch and batch != 'all':
        qs = qs.filter(batch=batch)
        
    # Gender Distribution (Enhanced with Coalesce)
    from django.db.models.functions import Coalesce
    from django.db.models import Value
    gender_dist = qs.annotate(
        gender_label=Coalesce('gender', Value('Unknown'))
    ).values('gender_label').annotate(count=Count('student_id')).order_by('-count')
    
    total = sum(g['count'] for g in gender_dist)
    data = [
        {
            'gender': g['gender_label'] or 'Unknown', 
            'count': g['count'],
            'percentage': round((g['count'] / total * 100), 1) if total > 0 else 0
        } 
        for g in gender_dist
    ]
    return JsonResponse({'distribution': data, 'total': total})

def _handle_student_photo(request, student):
    """Saves student photo and returns the relative path."""
    photo = request.FILES.get('student_photo')
    if not photo:
        return None
        
    # Ensure directory exists
    photo_dir = os.path.join(settings.MEDIA_ROOT, 'student_photos')
    if not os.path.exists(photo_dir):
        os.makedirs(photo_dir, exist_ok=True)
        
    # Create filename: student_id.extension
    ext = os.path.splitext(photo.name)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png']:
        return None
        
    filename = f"{student.student_id}{ext}"
    file_path = os.path.join(photo_dir, filename)
    
    # Delete old file if it's different
    if student.photo_path:
        # Check if the path is already media-relative
        old_rel_path = student.photo_path.replace(settings.MEDIA_URL, '').lstrip('/')
        old_full_path = os.path.join(settings.MEDIA_ROOT, old_rel_path)
        if os.path.exists(old_full_path) and old_full_path != file_path:
            try:
                os.remove(old_full_path)
            except:
                pass
                
    # Save new file
    with open(file_path, 'wb+') as destination:
        for chunk in photo.chunks():
            destination.write(chunk)
            
    return f"student_photos/{filename}"

from .forms import StudentForm

@require_access('students', 'add_student')
def add_student(request):
    """View to handle single student admission."""
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save(commit=False)
            if not student.student_id:
                data = request.POST
                new_id = generate_next_ugc_id(
                    admission_year=data.get('admission_year'),
                    semester_name=data.get('semester_name'),
                    hall_name=data.get('hall_attached'),
                    program_name=data.get('program'),
                    cluster_name=data.get('cluster'),
                    program_level=data.get('program_type', 'Bachelor'),
                    subject_code=data.get('subject_code', '01')
                )
                student.student_id = new_id
            
            # Handle Photo Upload
            photo_path = _handle_student_photo(request, student)
            if photo_path:
                student.photo_path = photo_path
                
            student.save()
            from core.utils import log_activity
            log_activity(request, 'CREATE', 'students', f'Admitted new student: {student.student_name}', object_id=student.student_id)
            
            # Automated Welcome SMS
            if student.student_mobile:
                msg_body = f"Welcome {student.student_name} to BAUST! Your Student ID is {student.student_id}. Please keep this for your records."
                from core.utils import send_sms
                from .models import SMSHistory
                success, response_text = send_sms(student.student_mobile, msg_body)
                SMSHistory.objects.create(
                    recipient_name=student.student_name,
                    student_id=student.student_id,
                    recipient_contact=student.student_mobile,
                    sms_delivery_type="Transaction",
                    message_type="SMS",
                    message_body=msg_body,
                    status="Delivered" if success else "Failed",
                    api_response=response_text,
                    api_profile_name="AdmissionWelcomeSystem"
                )

            messages.success(request, f"Student {student.student_name} admitted successfully with ID {student.student_id}")
            return redirect('student_list')
        else:
            error_count = len(form.errors)
            messages.error(request, f"Admission failed. Please fix the {error_count} error(s) in the form.")
    else:
        form = StudentForm()
    
    # Pass program mapping for auto-selection logic
    from master_data.models import Program
    programs = Program.objects.all()
    program_mapping = {
        p.name: {
            'cluster': p.cluster.name,
            'type': p.get_level_code_display()
        } for p in programs
    }
    
    return render(request, 'students/add.html', {
        'form': form,
        'program_mapping_json': json.dumps(program_mapping),
        'geo_data_json': json.dumps(BANGLADESH_GEO),
        **_get_history_suggestions()
    })

@require_access('students', 'edit_profile')
def edit_student(request, student_id):
    """View to edit an existing student record with strict ID-field locking."""
    student = get_object_or_404(Student, student_id=student_id)
    
    # Identify fields that must remain constant to maintain ID and academic integrity
    locked_fields = ['program', 'admission_year', 'cluster', 'hall_attached', 'semester_name', 'program_type', 'batch', 'student_id']
    
    if request.method == "POST":
        # Capture original values from the already-fetched instance before form processing
        original_values = {field: getattr(student, field) for field in locked_fields}
        
        form = StudentForm(request.POST, request.FILES, instance=student)
        
        # Ensure form doesn't fail validation for locked fields that aren't in POST
        for field in locked_fields:
            if field in form.fields:
                form.fields[field].required = False

        if form.is_valid():
            # This updates the instance but might clear fields missing from POST
            student = form.save(commit=False)
            
            # RE-ENFORCE LOCKED FIELDS: Restore the values captured before form processing
            for field, value in original_values.items():
                setattr(student, field, value)

            # Handle Photo Removal
            if request.POST.get('remove_photo') == 'true':
                student.photo_path = None
                from core.utils import log_activity
                log_activity(request, 'UPDATE', 'students', f'Removed photo for {student.student_name}', object_id=student.student_id)

            # Handle Photo Upload
            photo_path = _handle_student_photo(request, student)
            if photo_path:
                student.photo_path = photo_path
                from core.utils import log_activity
                log_activity(request, 'UPDATE', 'students', f'Updated photo for {student.student_name}', object_id=student.student_id)
                
            student.save()
            from core.utils import log_activity
            log_activity(request, 'UPDATE', 'students', f'Updated profile for {student.student_name}', object_id=student.student_id)
            messages.success(request, f"Profile for {student.student_name} updated successfully.")
            return redirect('student_profile', student_id=student_id)
        else:
            # Provide a cleaner summary of validation errors
            error_count = len(form.errors)
            messages.error(request, f"Could not update profile. Please correct the {error_count} error(s) highlighted in the form.")
    else:
        form = StudentForm(instance=student)
        # Lock identity fields in the UI
        for field in locked_fields:
            if field in form.fields:
                form.fields[field].widget.attrs['disabled'] = 'disabled'
                # Add a visual class to indicate it's locked
                existing_class = form.fields[field].widget.attrs.get('class', '')
                form.fields[field].widget.attrs['class'] = f"{existing_class} readonly-field"
        
    # Pass program mapping for auto-selection logic (even if disabled, for UI consistency)
    from master_data.models import Program
    programs = Program.objects.all()
    program_mapping = {
        p.name: {
            'cluster': p.cluster.name,
            'type': p.get_level_code_display()
        } for p in programs
    }

    return render(request, 'students/edit.html', {
        'form': form, 
        'student': student,
        'program_mapping_json': json.dumps(program_mapping),
        'geo_data_json': json.dumps(BANGLADESH_GEO),
        **_get_history_suggestions()
    })

@require_access('students', 'add_student')
def api_preview_id(request):
    """Helper view for HTMX to suggest the next available ID with breakdown."""
    try:
        from .utils import decompose_ugc_id
        
        new_id = generate_next_ugc_id(
            admission_year=request.GET.get('admission_year', 2026),
            semester_name=request.GET.get('semester_name', 'Spring'),
            hall_name=request.GET.get('hall_name', 'Non-Residential'),
            program_name=request.GET.get('program', 'CSE'),
            cluster_name=request.GET.get('cluster', 'Engineering & Technology'),
            program_level=request.GET.get('program_type', 'Bachelor'),
            mba_credits=int(request.GET.get('mba_credits', 0)) if request.GET.get('mba_credits') else None
        )
        
        components = decompose_ugc_id(new_id)
        return JsonResponse({
            'suggested_id': new_id,
            'components': components
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_access('students', 'bulk_import')
def import_students(request):
    """View to handle bulk Excel import and return an HTMX partial report."""
    if request.method == "POST" and request.FILES.get('excel_file'):
        update_existing = request.POST.get('update_existing') == 'on'
        result = import_students_from_excel(request.FILES['excel_file'], update_existing=update_existing)
        
        # Determine success/failure messages
        if result['success']:
            action = "updated/imported" if update_existing else "imported"
            messages.success(request, f"Successfully {action} {result['count']} students.")
            if result['total_errors'] > 0:
                messages.warning(request, f"Skipped {result['total_errors']} records due to errors.")
        else:
            messages.error(request, f"Import failed: {result['error']}")
            
        # Return the partial view instead of redirecting
        return render(request, 'students/partials/import_report.html', {'result': result, 'update_existing': update_existing})
    return render(request, 'students/import.html')

@require_access('students', 'bulk_import')
def import_preview(request):
    """Parses Excel and returns HTML partial for preview modal."""
    if request.method == "POST" and request.FILES.get('excel_file'):
        show_all = request.POST.get('show_all') == 'on'
        try:
            file_obj = request.FILES['excel_file']
            df = pd.read_excel(file_obj)
            
            # Standardize headers to see mapping (case-insensitive, snake_case)
            original_headers = list(df.columns)
            
            # Standardize logic matching utils.py
            standardized_headers = [str(c).strip().lower().replace(' ', '_') for c in original_headers]
            
            # Map headers to model fields
            valid_fields = [f.name for f in Student._meta.get_fields()]
            mapping = {orig: std for orig, std in zip(original_headers, standardized_headers)}
            
            # Record counting
            total_records = len(df)
            
            # Preview first 10 rows OR all rows
            preview_df = df if show_all else df.head(10).copy()
            
            # Core fields for compact view
            core_fields = ['student_id', 'student_name', 'program', 'batch', 'student_mobile', 'admission_status']
            
            # Convert NaN to empty string for clean template rendering
            data = preview_df.replace({pd.NA: '', float('nan'): ''}).to_dict(orient='records')
            
            existing_ids = set(Student.objects.values_list('student_id', flat=True))
            new_count = 0
            update_count = 0
            
            for row in data:
                # Find the actual header for student_id handling case and spaces
                s_id_key = next((k for k, v in mapping.items() if v == 'student_id'), None)
                s_id = str(row.get(s_id_key, '')).strip() if s_id_key else ''
                
                if len(s_id) == 15 and s_id.startswith('80'):
                    s_id = '0' + s_id
                
                if s_id in existing_ids:
                    row['row_status'] = 'Update'
                    update_count += 1
                else:
                    row['row_status'] = 'New'
                    new_count += 1
            
            # If show_all, new_count/update_count is accurate for whole file, else we need to count whole df
            if not show_all:
                all_s_ids = []
                s_id_key = next((k for k, v in mapping.items() if v == 'student_id'), None)
                if s_id_key:
                    all_s_ids = df[s_id_key].astype(str).str.strip().tolist()
                
                new_count = 0
                update_count = 0
                for s_id in all_s_ids:
                    if len(s_id) == 15 and s_id.startswith('80'):
                        s_id = '0' + s_id
                    if s_id in existing_ids:
                        update_count += 1
                    else:
                        new_count += 1
            
            response = render(request, 'students/partials/import_preview.html', {
                'headers': original_headers,
                'mapping': mapping,
                'data': data,
                'valid_fields': valid_fields,
                'core_fields': core_fields,
                'total_records': total_records,
                'new_count': new_count,
                'update_count': update_count,
                'update_existing': request.POST.get('update_existing') == 'on',
                'is_full_list': show_all
            })
            response['HX-Trigger'] = 'showPreviewModal'
            return response
        except Exception as e:
            response = HttpResponse(f'<div class="alert alert-danger"><i class="fas fa-exclamation-triangle mr-2"></i> Error reading file: {escape(str(e))}</div>')
            response['HX-Trigger'] = 'showPreviewModal'
            return response
    return JsonResponse({'error': 'No file provide or invalid request'}, status=400)

@require_access('students', 'bulk_import')
def download_import_template(request):
    """Generates an empty Excel template for student import."""
    columns = [
        'student_id', 'student_name', 'old_student_id', 'program', 'admission_year',
        'cluster', 'batch', 'semester_name', 'program_type', 'admission_date',
        'admission_status', 'gender', 'dob', 'blood_group', 'religion', 'national_id',
        'father_name', 'mother_name', 'father_occupation', 'student_mobile',
        'father_mobile', 'mother_mobile', 'student_email', 'emergency_contact',
        'present_address', 'permanent_address', 'ssc_school', 'ssc_year',
        'ssc_board', 'ssc_roll', 'ssc_reg', 'ssc_gpa', 'hsc_college', 'hsc_year',
        'hsc_board', 'hsc_roll', 'hsc_reg', 'hsc_gpa', 'hall_attached',
        'is_non_residential', 'admission_payment', 'second_installment',
        'waiver', 'others', 'reference', 'remarks'
    ]
    df = pd.DataFrame(columns=columns)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Import Template')
    
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="student_import_template.xlsx"'
    return response

@require_access('students', 'edit_profile')
def change_program(request, student_id):
    """View to handle program change for a student with full master data support."""
    student = Student.objects.get(pk=student_id)
    if request.method == "POST":
        data = request.POST
        result = execute_program_change_web(
            student=student,
            new_program=data.get('new_program'),
            new_cluster=data.get('new_cluster'),
            new_year=data.get('new_year'),
            new_semester=data.get('new_semester'),
            hall_name=data.get('hall_name'),
            notes=data.get('notes', 'Web migration')
        )
        if result['success']:
            messages.success(request, f"Program changed successfully! New ID: {result['new_id']}")
        else:
            messages.error(request, f"Error changing program: {result['error']}")
        return redirect('student_list')
    
    # Pass full master data for dynamic dropdowns and mapping
    from master_data.models import Program, Cluster, Semester, Hall
    programs = Program.objects.all().order_by('name')
    clusters = Cluster.objects.all().order_by('name')
    semesters = Semester.objects.all().order_by('name')
    halls = Hall.objects.all().order_by('name')
    
    program_mapping = {
        p.name: {
            'cluster': p.cluster.name,
            'type': p.get_level_code_display()
        } for p in programs
    }
    
    return render(request, 'students/change_program.html', {
        'student': student,
        'programs': programs,
        'clusters': clusters,
        'semesters': semesters,
        'halls': halls,
        'program_mapping_json': json.dumps(program_mapping)
    })

@require_access('students', 'view_directory')
def student_profile(request, student_id):
    """Full detail view for a student profile."""
    student = Student.objects.get(pk=student_id)
    program_history = ProgramChangeHistory.objects.filter(
        Q(old_student_id=student_id) | Q(new_student_id=student_id)
    ).order_by('-change_date')
    return render(request, 'students/profile.html', {
        'student': student,
        'program_history': program_history
    })

@require_access('reports', 'view_analytics')
def academic_intake_report(request):
    """Generates the Academic Intake Quality Report."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year_filter = request.GET.get('year', latest_year)
    batch_filter = request.GET.get('batch')
    program_filter = request.GET.get('program')
    
    students = Student.objects.exclude(program__isnull=True).exclude(program='')
    if year_filter:
        students = students.filter(admission_year=year_filter)
    if batch_filter:
        students = students.filter(batch=batch_filter)
    if program_filter:
        students = students.filter(program=program_filter)
        
    report_data = students.values('program').annotate(
        gpa_5_ssc=Count(Case(When(ssc_gpa=5.0, then=1), output_field=IntegerField())),
        gpa_45_499_ssc=Count(Case(When(ssc_gpa__gte=4.5, ssc_gpa__lt=5.0, then=1), output_field=IntegerField())),
        gpa_40_449_ssc=Count(Case(When(ssc_gpa__gte=4.0, ssc_gpa__lt=4.5, then=1), output_field=IntegerField())),
        gpa_less_4_ssc=Count(Case(When(ssc_gpa__lt=4.0, then=1), output_field=IntegerField())),
        gpa_5_hsc=Count(Case(When(hsc_gpa=5.0, then=1), output_field=IntegerField())),
        gpa_45_499_hsc=Count(Case(When(hsc_gpa__gte=4.5, hsc_gpa__lt=5.0, then=1), output_field=IntegerField())),
        gpa_40_449_hsc=Count(Case(When(hsc_gpa__gte=4.0, hsc_gpa__lt=4.5, then=1), output_field=IntegerField())),
        gpa_less_4_hsc=Count(Case(When(hsc_gpa__lt=4.0, then=1), output_field=IntegerField())),
    ).order_by('program')
    
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    
    return render(request, 'students/academic_intake.html', {
        'report_data': report_data,
        'years': list(years),
        'programs': list(programs),
        'batches': list(batches),
        'selected_year': str(year_filter) if year_filter else None,
        'selected_batch': batch_filter,
        'selected_program': program_filter
    })

import pandas as pd
from io import BytesIO

@require_access('students', 'export_excel')
def export_students(request):
    """Generates the official 44-column Excel export."""
    students = _build_directory_state(request)['filtered_queryset']
    data = []
    for i, s in enumerate(students, start=1):
        data.append({
            'SL': i, 'student_id': s.student_id, 'student_name': s.student_name,
            'program': s.program, 'batch': s.batch, 'semester_name': s.semester_name,
            'admission_status': s.admission_status, 'student_mobile': s.student_mobile,
            'father_name': s.father_name, 'father_mobile': s.father_mobile,
            'mother_name': s.mother_name, 'gender': s.gender, 'blood_group': s.blood_group,
            'religion': s.religion, 'dob': s.dob, 'national_id': s.national_id,
            'present_address': s.present_address, 'permanent_address': s.permanent_address,
            'ssc_gpa': s.ssc_gpa, 'hsc_gpa': s.hsc_gpa, 'hall_attached': s.hall_attached,
            'cluster': s.cluster, 'program_type': s.program_type, 'emergency_contact': s.emergency_contact,
            'mother_mobile': s.mother_mobile, 'father_occupation': s.father_occupation,
            'ssc_school': s.ssc_school, 'ssc_year': s.ssc_year, 'ssc_board': s.ssc_board,
            'ssc_roll': s.ssc_roll, 'ssc_reg': s.ssc_reg, 'hsc_college': s.hsc_college,
            'hsc_year': s.hsc_year, 'hsc_board': s.hsc_board, 'hsc_roll': s.hsc_roll,
            'hsc_reg': s.hsc_reg, 'admission_date': s.admission_date, 'is_non_residential': s.is_non_residential,
            'admission_payment': s.admission_payment, 'second_installment': s.second_installment,
            'waiver': s.waiver, 'others': s.others, 'reference': s.reference, 'remarks': s.remarks,
        })
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Students')
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="students_export_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    return response


@require_access('students', 'export_excel')
def export_students_all(request):
    """Exports all concrete student fields for the current directory dataset."""
    students = _build_directory_state(request)['filtered_queryset']
    concrete_fields = list(Student._meta.concrete_fields)
    field_names = [field.name for field in concrete_fields]
    data = []

    for student in students:
        row = {}
        for field in concrete_fields:
            value = getattr(student, field.name)
            if field.get_internal_type() == 'DateTimeField' and value and timezone.is_aware(value):
                value = timezone.make_naive(value, timezone.get_current_timezone())
            row[field.name] = value
        data.append(row)

    df = pd.DataFrame(data, columns=field_names)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Students')

    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="students_all_info_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    return response

@require_access('reports', 'generate_pdf')
def download_master_sheet(request, student_id):
    """Generates a high-impact PDF Master Sheet for a student."""
    from core.models import SystemSettings
    student = get_object_or_404(Student, pk=student_id)
    sys_settings = SystemSettings.objects.first()
    context = {
        'student': student, 
        'today': timezone.now(),
        'sys_settings': sys_settings
    }
    pdf_response = render_to_pdf('students/reports/pdf/master_sheet.html', context)
    if pdf_response:
        filename = f"MasterSheet_{student_id}.pdf"
        pdf_response['Content-Disposition'] = f"inline; filename={filename}"
        return pdf_response
    return HttpResponse("Error generating PDF", status=400)

@require_access('reports', 'view_analytics')
def export_center(request):
    """The central hub for all high-fidelity dynamic exports."""
    field_groups = {
        'Identity': ['student_id', 'student_name', 'gender', 'dob', 'national_id', 'religion', 'blood_group'],
        'Contact': ['student_mobile', 'student_email', 'present_address', 'permanent_address', 'emergency_contact'],
        'Family': ['father_name', 'mother_name', 'father_mobile', 'mother_mobile', 'father_occupation'],
        'Academic': ['ssc_school', 'ssc_year', 'ssc_board', 'ssc_roll', 'ssc_reg', 'ssc_gpa', 'hsc_college', 'hsc_year', 'hsc_board', 'hsc_roll', 'hsc_reg', 'hsc_gpa'],
        'Financial': ['admission_payment', 'second_installment', 'waiver', 'others'],
        'Institutional': ['program', 'cluster', 'batch', 'semester_name', 'hall_attached', 'reference', 'remarks', 'admission_status', 'admission_date']
    }
    return render(request, 'students/reports/export_center.html', {'field_groups': field_groups})

@require_access('reports', 'view_analytics')
def export_students_dynamic(request):
    """Dynamic student export with field selection and multi-filtering."""
    if request.method == "POST":
        selected_fields = request.POST.getlist('fields')
        query = request.POST.get('search', '')
        program = request.POST.get('program')
        status = request.POST.get('status')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        queryset = Student.objects.all()

        # Apply Filters
        if query:
            queryset = queryset.filter(Q(student_name__icontains=query) | Q(student_id__icontains=query))
        if program and program != 'All':
            queryset = queryset.filter(program=program)
        if status and status != 'All':
            queryset = queryset.filter(admission_status=status)
        if start_date:
            queryset = queryset.filter(admission_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(admission_date__lte=end_date)

        # Build DataFrame
        if not selected_fields:
            selected_fields = ['student_id', 'student_name', 'program', 'admission_status']
        
        data = []
        for s in queryset:
            row = {}
            for field in selected_fields:
                row[field] = getattr(s, field)
            data.append(row)
        
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Students')
        
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="Students_Export_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        return response
    return redirect('export_center')

@require_access('reports', 'view_analytics')
def export_migrations_dynamic(request):
    """Date-range based export for program migration history."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    query = request.GET.get('search')

    queryset = ProgramChangeHistory.objects.all()
    if start_date: queryset = queryset.filter(change_date__gte=start_date)
    if end_date: queryset = queryset.filter(change_date__lte=end_date)
    if query:
        queryset = queryset.filter(Q(old_student_id__icontains=query) | Q(new_student_id__icontains=query))

    data = list(queryset.values('old_student_id', 'new_student_id', 'old_program', 'new_program', 'change_date', 'notes'))
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='MigrationHistory')
    
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Migrations_Audit_{timezone.now().strftime("%Y%m%d")}.xlsx"'
    return response

@require_access('reports', 'view_analytics')
def export_cancellations_dynamic(request):
    """Date-range based export for admission cancellation history."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    query = request.GET.get('search')

    queryset = AdmissionStatusHistory.objects.filter(new_status='Cancelled')
    if start_date: queryset = queryset.filter(change_date__gte=start_date)
    if end_date: queryset = queryset.filter(change_date__lte=end_date)
    if query:
        queryset = queryset.filter(student__student_id__icontains=query)

    data = []
    for item in queryset:
        data.append({
            'student_id': item.student.student_id,
            'student_name': item.student.student_name,
            'reason': item.reason_category,
            'notes': item.custom_notes,
            'date': item.change_date,
            'performed_by': item.performed_by.username if item.performed_by else 'System'
        })
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Cancellations')
    
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Cancellations_Audit_{timezone.now().strftime("%Y%m%d")}.xlsx"'
    return response

from .reports import (
    get_academic_analytics, get_financial_summary, 
    get_institutional_intelligence, get_geographic_insights, 
    get_research_demographics, get_subject_performance,
    get_reference_intelligence, get_financial_intelligence,
    get_diversity_intelligence, get_age_gap_analysis,
    get_migration_intelligence
)

@require_access('reports', 'view_analytics')
def institutional_report(request):
    """Feeder institution intelligence dashboard."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year', latest_year)
    batch = request.GET.get('batch')
    program = request.GET.get('program')
    
    data = get_institutional_intelligence(year=year, batch=batch, program=program)
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    
    return render(request, 'students/reports/institutional.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': list(years),
        'batches': list(batches),
        'programs': list(programs),
        'selected_year': str(year) if year else None,
        'selected_batch': batch,
        'selected_program': program
    })

@require_access('reports', 'view_analytics')
def geographic_report(request):
    """Geographic outreach and student distribution dashboard."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year', latest_year)
    batch = request.GET.get('batch')
    program = request.GET.get('program')
    
    data = get_geographic_insights(year=year, batch=batch, program=program)
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    
    return render(request, 'students/reports/geographic.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': list(years),
        'batches': list(batches),
        'programs': list(programs),
        'selected_year': str(year) if year else None,
        'selected_batch': batch,
        'selected_program': program
    })

@require_access('reports', 'view_analytics')
def socio_economic_report(request):
    """Research-grade demographics: Occupation and Financial aid splits."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year', latest_year)
    batch = request.GET.get('batch')
    program = request.GET.get('program')
    
    data = get_research_demographics(year=year, batch=batch, program=program)
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    
    return render(request, 'students/reports/socio_economic.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': list(years),
        'batches': list(batches),
        'programs': list(programs),
        'selected_year': str(year) if year else None,
        'selected_batch': batch,
        'selected_program': program
    })

@require_access('reports', 'view_analytics')
def subject_report(request):
    """Science subject performance analysis (Physics, Chemistry, Math)."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year', latest_year)
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    data = get_subject_performance(year=year, program=program, batch=batch)
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    
    return render(request, 'students/reports/subject_performance.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': list(years),
        'programs': list(programs),
        'batches': list(batches),
        'selected_year': str(year) if year else None,
        'selected_program': program,
        'selected_batch': batch
    })

@require_access('reports', 'view_analytics')
def reference_report(request):
    """Reference efficiency and recruitment source analysis."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year', latest_year)
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    data = get_reference_intelligence(year=year, program=program, batch=batch)
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    
    return render(request, 'students/reports/reference_intelligence.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': list(years),
        'programs': list(programs),
        'batches': list(batches),
        'selected_year': str(year) if year else None,
        'selected_program': program,
        'selected_batch': batch
    })

@require_access('reports', 'view_analytics')
def financial_intelligence_report(request):
    """Revenue forecasting and financial impact analysis."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year', latest_year)
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    data = get_financial_intelligence(year=year, program=program, batch=batch)
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    
    return render(request, 'students/reports/financial_intelligence.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': list(years),
        'programs': list(programs),
        'batches': list(batches),
        'selected_year': str(year) if year else None,
        'selected_program': program,
        'selected_batch': batch
    })

@require_access('reports', 'view_analytics')
def diversity_report(request):
    """Gender parity and religious diversity dashboard."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year', latest_year)
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    data = get_diversity_intelligence(year=year, program=program, batch=batch)
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    
    return render(request, 'students/reports/diversity_intelligence.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': list(years),
        'programs': list(programs),
        'batches': list(batches),
        'selected_year': str(year) if year else None,
        'selected_program': program,
        'selected_batch': batch
    })

@require_access('reports', 'view_analytics')
def age_gap_report(request):
    """Age distribution and gap-year analysis."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year', latest_year)
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    data = get_age_gap_analysis(year=year, program=program, batch=batch)
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    
    return render(request, 'students/reports/age_gap_analysis.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': list(years),
        'programs': list(programs),
        'batches': list(batches),
        'selected_year': str(year) if year else None,
        'selected_program': program,
        'selected_batch': batch
    })

@require_access('reports', 'view_analytics')
def migration_report(request):
    """Program migration patterns and student flow analysis."""
    data = get_migration_intelligence()
    return render(request, 'students/reports/migration_intelligence.html', {
        'data': data,
        'data_json': json.dumps(data)
    })

@require_access('reports', 'view_analytics')
def subject_report(request):
    """Science subject performance analysis (Physics, Chemistry, Math)."""
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    data = get_subject_performance(year=year, program=program, batch=batch)
    
    years = Student.objects.values_list('admission_year', flat=True).distinct().order_by('-admission_year')
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    
    return render(request, 'students/reports/subject_performance.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': [y for y in years if y],
        'programs': list(programs),
        'batches': list(batches),
        'selected_year': year,
        'selected_program': program,
        'selected_batch': batch
    })

@require_access('reports', 'view_analytics')
def reports_center(request):
    """The central hub for all high-impact reports."""
    return render(request, 'students/reports/report_center.html')

@require_access('reports', 'view_analytics')
def demographic_insights(request):
    """Visual dashboard for student demographic distributions."""
    year = request.GET.get('year')
    data = get_academic_analytics(year=year)
    years = Student.objects.values_list('admission_year', flat=True).distinct().order_by('-admission_year')
    return render(request, 'students/reports/demographics.html', {
        'data': data,
        'data_json': json.dumps(data),
        'selected_year': year,
        'years': [y for y in years if y]
    })

@require_access('reports', 'view_analytics')
def analytics_dashboard(request):
    """Visual dashboard for academic and demographic analytics."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year', latest_year)
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    data = get_academic_analytics(year=year, program=program, batch=batch)
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    
    return render(request, 'students/reports/analytics.html', {
        'data': data,
        'data_json': json.dumps(data),
        'selected_year': str(year) if year else None,
        'selected_program': program,
        'selected_batch': batch,
        'years': list(years),
        'programs': list(programs),
        'batches': list(batches)
    })

@login_required
def api_global_search(request):
    """Real-time global search engine for the header."""
    from django.http import HttpResponse
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return HttpResponse("") # Return empty if query is too short

    from django.db.models import Q
    students = Student.objects.filter(
        Q(student_id__icontains=query) |
        Q(student_name__icontains=query) |
        Q(student_mobile__icontains=query) |
        Q(student_email__icontains=query) |
        Q(father_name__icontains=query) |
        Q(father_mobile__icontains=query)
    ).only('student_id', 'student_name', 'program', 'batch', 'admission_status', 'photo_path')[:8]

    return render(request, 'students/partials/global_search_results.html', {
        'students': students,
        'query': query
    })

@require_access('students', 'data_integrity')
def data_integrity(request):
    """Main page for Data Integrity and Deduplication Scanner."""
    fields = [
        {'name': 'student_name', 'label': 'Student Name'},
        {'name': 'father_name', 'label': "Father's Name"},
        {'name': 'mother_name', 'label': "Mother's Name"},
        {'name': 'student_mobile', 'label': 'Mobile Number'},
        {'name': 'student_email', 'label': 'Email Address'},
        {'name': 'dob', 'label': 'Date of Birth'},
        {'name': 'national_id_birth_certificate', 'label': 'NID / Birth Cert.'},
    ]
    
    from master_data.models import Program, Batch
    programs = Program.objects.all().order_by('name')
    batches = Batch.objects.all().order_by('-sort_order')
    
    return render(request, 'students/data_integrity.html', {
        'fields': fields,
        'programs': programs,
        'batches': batches,
    })

@require_access('students', 'data_integrity')
def api_scan_duplicates(request):
    """HTMX endpoint to run the dynamic deduplication scan."""
    selected_fields = request.POST.getlist('fields')
    if not selected_fields:
        return HttpResponse("<div class='alert alert-warning border-0 shadow-sm'><i class='fas fa-exclamation-triangle mr-2'></i> Please select at least one field to scan.</div>")
    
    from django.db.models.functions import Lower, Trim, Replace, Right
    from django.db.models import Value, F, Count

    annotations = {}
    normalized_fields = []

    for field in selected_fields:
        norm_name = f"norm_{field}"
        normalized_fields.append(norm_name)
        
        if field in ['student_name', 'father_name', 'mother_name']:
            # Lowercase, remove spaces, dots, and hyphens
            annotations[norm_name] = Replace(
                Replace(
                    Replace(
                        Lower(field), 
                        Value('.'), Value('')
                    ), 
                    Value('-'), Value('')
                ), 
                Value(' '), Value('')
            )
        elif 'mobile' in field or 'phone' in field:
            # Phone number normalization (Last 11 digits)
            clean_phone = Replace(Replace(field, Value(' '), Value('')), Value('-'), Value(''))
            annotations[norm_name] = Right(clean_phone, 11)
        elif field in ['student_email']:
            annotations[norm_name] = Trim(Lower(field))
        else:
            annotations[norm_name] = F(field)

    # Apply database filters to narrow the working area
    filter_program = request.POST.get('filter_program')
    filter_batch = request.POST.get('filter_batch')
    filter_status = request.POST.get('filter_status')
    
    base_qs = Student.objects.all()
    if filter_program:
        base_qs = base_qs.filter(program=filter_program)
    if filter_batch:
        base_qs = base_qs.filter(batch=filter_batch)
    if filter_status:
        base_qs = base_qs.filter(admission_status=filter_status)

    # Dynamic ORM query to find groups with same normalized fields
    qs = base_qs.annotate(**annotations)
    duplicates = qs.values(*normalized_fields).annotate(count=Count('student_id')).filter(count__gt=1).order_by('-count')
    
    match_groups = []
    for dup in duplicates:
        # Build filter kwargs from the duplicate group, ignoring null/empty strings
        filter_kwargs = {norm_field: dup[norm_field] for norm_field in normalized_fields if dup[norm_field] and str(dup[norm_field]).strip() != ''}
        
        # We only want to match if all selected fields have valid data to match on
        if len(filter_kwargs) == len(selected_fields):
            students = qs.filter(**filter_kwargs)
            if students.count() > 1:
                # Build human readable criteria for display
                criteria_display = {f.replace('norm_', ''): v for f, v in filter_kwargs.items()}
                match_groups.append({
                    'criteria': criteria_display,
                    'students': students
                })
            
    all_fields = [f for f in Student._meta.fields if f.name not in ['id', 'student_id', 'created_at', 'last_updated', 'photo_path']]

    return render(request, 'students/partials/duplicate_scan_results.html', {
        'match_groups': match_groups,
        'selected_fields': selected_fields,
        'all_fields': all_fields
    })

@require_access('students', 'data_integrity')
def api_export_duplicates(request):
    """Generates an Excel report of the duplicate scan."""
    import pandas as pd
    from django.http import HttpResponse
    from io import BytesIO
    from django.db.models.functions import Lower, Trim, Replace, Right
    from django.db.models import Value, F, Count

    selected_fields = request.POST.getlist('fields')
    if not selected_fields:
        return HttpResponse("No fields selected for export.", status=400)
    
    annotations = {}
    normalized_fields = []

    for field in selected_fields:
        norm_name = f"norm_{field}"
        normalized_fields.append(norm_name)
        if field in ['student_name', 'father_name', 'mother_name']:
            annotations[norm_name] = Replace(Replace(Replace(Lower(field), Value('.'), Value('')), Value('-'), Value('')), Value(' '), Value(''))
        elif 'mobile' in field or 'phone' in field:
            clean_phone = Replace(Replace(field, Value(' '), Value('')), Value('-'), Value(''))
            annotations[norm_name] = Right(clean_phone, 11)
        elif field in ['student_email']:
            annotations[norm_name] = Trim(Lower(field))
        else:
            annotations[norm_name] = F(field)

    filter_program = request.POST.get('filter_program')
    filter_batch = request.POST.get('filter_batch')
    filter_status = request.POST.get('filter_status')
    
    base_qs = Student.objects.all()
    if filter_program: base_qs = base_qs.filter(program=filter_program)
    if filter_batch: base_qs = base_qs.filter(batch=filter_batch)
    if filter_status: base_qs = base_qs.filter(admission_status=filter_status)

    qs = base_qs.annotate(**annotations)
    duplicates = qs.values(*normalized_fields).annotate(count=Count('student_id')).filter(count__gt=1).order_by('-count')
    
    data = []
    group_num = 1
    for dup in duplicates:
        filter_kwargs = {norm_field: dup[norm_field] for norm_field in normalized_fields if dup[norm_field] and str(dup[norm_field]).strip() != ''}
        if len(filter_kwargs) == len(selected_fields):
            students = qs.filter(**filter_kwargs)
            if students.count() > 1:
                criteria_str = ", ".join([f"{f.replace('norm_', '').title()}: {v}" for f, v in filter_kwargs.items()])
                for s in students:
                    data.append({
                        'Group ID': f"Group {group_num}",
                        'Match Criteria': criteria_str,
                        'Student ID': s.student_id,
                        'Name': s.student_name,
                        'Program': s.program,
                        'Batch': s.batch,
                        'Mobile': s.student_mobile,
                        'Status': s.admission_status,
                    })
                group_num += 1

    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Duplicates')
        # Auto-adjust column widths
        worksheet = writer.sheets['Duplicates']
        for idx, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = max_len

    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Duplicate_Students_Report.xlsx"'
    return response

@require_access('students', 'data_integrity')
def api_merge_duplicates(request):
    """HTMX endpoint to merge records."""
    if request.method == "POST":
        primary_id = request.POST.get('primary_id')
        duplicate_ids = request.POST.getlist('duplicate_ids')
        
        try:
            primary = Student.objects.get(student_id=primary_id)
            duplicates = Student.objects.filter(student_id__in=duplicate_ids).exclude(student_id=primary_id)
            
            with transaction.atomic():
                for dup in duplicates:
                    # Merge empty fields from duplicate into primary
                    for field in primary._meta.fields:
                        if field.name not in ['student_id', 'created_at', 'last_updated']:
                            primary_val = getattr(primary, field.name)
                            dup_val = getattr(dup, field.name)
                            if not primary_val and dup_val:
                                setattr(primary, field.name, dup_val)
                    
                    # Delete the duplicate record safely
                    dup.delete()
                    
                primary.save()
            return HttpResponse(f"<div class='alert alert-success border-0 shadow-sm'><i class='fas fa-check-circle mr-2'></i> Successfully merged into Primary ID: <strong>{escape(primary_id)}</strong>. The duplicate records have been deleted.</div>")
        except Exception as e:
            return HttpResponse(f"<div class='alert alert-danger border-0 shadow-sm'><i class='fas fa-times-circle mr-2'></i> Merge failed: {escape(str(e))}</div>")
    return HttpResponse("Invalid request.")

@require_access('students', 'bulk_update')
def api_bulk_update_modal(request):
    """Returns the initial bulk update modal structure."""
    if request.method == "POST":
        student_ids = request.POST.get('student_ids', '').split(',')
        student_ids = [s for s in student_ids if s.strip()]
        if not student_ids:
            return HttpResponse("No students selected.")
            
        updatable_fields = [
            {'name': 'gender', 'label': 'Gender'},
            {'name': 'religion', 'label': 'Religion'},
            {'name': 'blood_group', 'label': 'Blood Group'},
            {'name': 'batch', 'label': 'Batch (Foreign Key)'},
            {'name': 'is_non_residential', 'label': 'Non-Residential'},
            {'name': 'is_freedom_fighter_child', 'label': 'Freedom Fighter Child'},
            {'name': 'is_july_joddha_2024', 'label': 'July Joddha 2024'},
            {'name': 'admission_status', 'label': 'Admission Status'},
        ]
        
        return render(request, 'students/partials/bulk_update_modal.html', {
            'student_ids': ','.join(student_ids),
            'student_count': len(student_ids),
            'updatable_fields': updatable_fields
        })

@require_access('students', 'bulk_update')
def api_bulk_update_field_input(request):
    """Returns the appropriate HTML input for the selected field."""
    field_name = request.GET.get('field_name')
    context = {'field_name': field_name}
    
    if field_name == 'batch':
        from master_data.models import Batch
        context['batches'] = Batch.objects.all()
        
    return render(request, 'students/partials/bulk_update_input.html', context)

@require_access('students', 'bulk_update')
def api_bulk_update_execute(request):
    """Executes the mass update."""
    if request.method == "POST":
        student_ids = request.POST.get('student_ids', '').split(',')
        field_name = request.POST.get('field_name')
        new_value = request.POST.get('new_value')
        allowed_fields = {
            'gender',
            'religion',
            'blood_group',
            'batch',
            'is_non_residential',
            'is_freedom_fighter_child',
            'is_july_joddha_2024',
            'admission_status',
        }
        
        if not field_name:
            return HttpResponse("<div class='alert alert-danger'>Please select a field.</div>")

        if field_name not in allowed_fields:
            return HttpResponse("<div class='alert alert-danger'>This field cannot be updated in bulk.</div>", status=400)
            
        if field_name in ['is_non_residential', 'is_freedom_fighter_child', 'is_july_joddha_2024']:
            new_value = True if new_value == 'True' else False
            
        if field_name == 'batch' and new_value:
            from master_data.models import Batch
            try:
                new_value = Batch.objects.get(id=new_value)
            except Exception:
                return HttpResponse("<div class='alert alert-danger'>Invalid Batch Selected.</div>")
                
        try:
            with transaction.atomic():
                updated_count = Student.objects.filter(student_id__in=student_ids).update(**{field_name: new_value})
            return HttpResponse(f"<script>Swal.fire('Success', '{updated_count} students updated successfully!', 'success').then(() => location.reload());</script>")
        except Exception as e:
            return HttpResponse(f"<div class='alert alert-danger'>Update failed: {escape(str(e))}</div>")
    return HttpResponse("Invalid Request.")
