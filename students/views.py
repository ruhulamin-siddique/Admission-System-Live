from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import Count, Q, Case, When, IntegerField, Sum, Max, Value
from django.db.models.functions import Cast, Coalesce, Lower, Right, TruncMonth
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Student, ProgramChangeHistory, AdmissionStatusHistory
from .utils import generate_next_ugc_id, import_students_from_excel, execute_program_change_web
from core.decorators import require_access
import xhtml2pdf.pisa as pisa
from io import BytesIO
from django.template.loader import get_template
from urllib.parse import urlencode
from master_data.models import Program
from .geo_data import BANGLADESH_GEO
import json
import os
from django.conf import settings

def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None

@require_access('dashboard', 'view')
def dashboard(request):
    """Main dashboard view with summary statistics."""
    # Monthly Admission Trends (Last 6 months)
    six_months_ago = timezone.now() - timezone.timedelta(days=180)
    monthly_data = Student.objects.filter(created_at__gte=six_months_ago) \
        .annotate(month=TruncMonth('created_at')) \
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
    program_dist_qs = Student.objects.values('program').annotate(count=Count('student_id')).order_by('-count')
    program_dist = []
    for item in program_dist_qs:
        full_name = item['program'] or 'Unknown'
        program_dist.append({
            'program': full_name,
            'short_name': program_map.get(full_name, full_name),
            'count': item['count']
        })

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

        for item in latest_intake_qs:
            full_name = item['program'] or 'Unknown'
            latest_batch_intake.append({
                'program': full_name,
                'short_name': program_map.get(full_name, full_name),
                'count': item['total'],
                'male': item['male'],
                'female': item['female'],
                'active': item['active'],
                'cancelled': item['cancelled'],
                'non_residential': item['non_residential'],
                'revenue': float(item['revenue'] or 0),
                'quota': item['quota']
            })

    # Periodic Admission Stats
    now = timezone.now()
    today_date = now.date()
    start_of_week = today_date - timezone.timedelta(days=today_date.weekday())
    start_of_month = today_date.replace(day=1)

    today_qs = Student.objects.filter(admission_date=today_date)
    week_qs = Student.objects.filter(admission_date__gte=start_of_week)
    month_qs = Student.objects.filter(admission_date__gte=start_of_month)

    def _get_periodic_breakdown(qs):
        breakdown = []
        for item in qs.values('program').annotate(count=Count('student_id')).order_by('-count'):
            full_name = item['program'] or 'Unknown'
            breakdown.append({
                'program': full_name,
                'short_name': program_map.get(full_name, full_name),
                'count': item['count']
            })
        return breakdown

    periodic_stats = {
        'today': {
            'label': now.strftime('%B %d, %Y'),
            'count': today_qs.count(),
            'breakdown': _get_periodic_breakdown(today_qs)
        },
        'week': {
            'label': f"{start_of_week.strftime('%b %d')} - {today_date.strftime('%b %d')}",
            'count': week_qs.count(),
            'breakdown': _get_periodic_breakdown(week_qs)
        },
        'month': {
            'label': now.strftime('%B %Y'),
            'count': month_qs.count(),
            'breakdown': _get_periodic_breakdown(month_qs)
        }
    }

    # Recent Students with Short Names
    recent_students = []
    for s in Student.objects.order_by('-created_at')[:10]:
        recent_students.append({
            'student_id': s.student_id,
            'student_name': s.student_name,
            'program': s.program,
            'short_name': program_map.get(s.program, s.program),
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
        'periodic': periodic_stats
    }
    return render(request, 'students/dashboard.html', {'stats': stats})

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

@require_access('students', 'delete_profile')
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
                response = HttpResponse(f'<div class="alert alert-success"><i class="fas fa-check-circle mr-2"></i> {success_msg}</div>')
                response['HX-Trigger'] = json.dumps({
                    "refreshCancelledCount": True,
                    "clearSearchResults": True
                })
                return response
            
            messages.success(request, success_msg)
        except Exception as e:
            if request.headers.get('HX-Request'):
                return HttpResponse(f'<div class="alert alert-danger">Error: {str(e)}</div>')
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

@require_access('security', 'manage_users')
def import_students(request):
    """View to handle bulk Excel import."""
    if request.method == "POST" and request.FILES.get('excel_file'):
        update_existing = request.POST.get('update_existing') == 'on'
        result = import_students_from_excel(request.FILES['excel_file'], update_existing=update_existing)
        if result['success']:
            action = "updated/imported" if update_existing else "imported"
            messages.success(request, f"Successfully {action} {result['count']} students.")
            if result['total_errors'] > 0:
                messages.warning(request, f"Skipped {result['total_errors']} records due to errors.")
        else:
            messages.error(request, f"Import failed: {result['error']}")
        return redirect('student_list')
    return render(request, 'students/import.html')

@require_access('security', 'manage_users')
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
            
            response = render(request, 'students/partials/import_preview.html', {
                'headers': original_headers,
                'mapping': mapping,
                'data': data,
                'valid_fields': valid_fields,
                'core_fields': core_fields,
                'total_records': total_records,
                'update_existing': request.POST.get('update_existing') == 'on',
                'is_full_list': show_all
            })
            response['HX-Trigger'] = 'showPreviewModal'
            return response
        except Exception as e:
            response = HttpResponse(f'<div class="alert alert-danger"><i class="fas fa-exclamation-triangle mr-2"></i> Error reading file: {str(e)}</div>')
            response['HX-Trigger'] = 'showPreviewModal'
            return response
    return JsonResponse({'error': 'No file provide or invalid request'}, status=400)

@require_access('security', 'manage_users')
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
    year_filter = request.GET.get('year')
    batch_filter = request.GET.get('batch')
    students = Student.objects.exclude(program__isnull=True).exclude(program='')
    if year_filter:
        students = students.filter(admission_year=year_filter)
    if batch_filter:
        students = students.filter(batch=batch_filter)
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
    years = Student.objects.values_list('admission_year', flat=True).distinct().order_by('-admission_year')
    batches = Student.objects.values_list('batch', flat=True).distinct().order_by('batch')
    return render(request, 'students/academic_intake.html', {
        'report_data': report_data,
        'years': [y for y in years if y],
        'batches': [b for b in batches if b],
        'selected_year': year_filter,
        'selected_batch': batch_filter
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
    student = get_object_or_404(Student, pk=student_id)
    context = {'student': student, 'today': timezone.now()}
    pdf = render_to_pdf('students/reports/pdf/master_sheet.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"MasterSheet_{student_id}.pdf"
        content = f"inline; filename={filename}"
        response['Content-Disposition'] = content
        return response
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

from .reports import get_academic_analytics, get_financial_summary

@require_access('reports', 'view_analytics')
def reports_center(request):
    """The central hub for all high-impact reports."""
    return render(request, 'students/reports/report_center.html')

@require_access('reports', 'view_analytics')
def analytics_dashboard(request):
    """Visual dashboard for academic and demographic analytics."""
    year = request.GET.get('year')
    data = get_academic_analytics(year=year)
    return render(request, 'students/reports/analytics.html', {
        'data': data,
        'selected_year': year
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
    ).only('student_id', 'student_name', 'program', 'admission_status', 'photo_path')[:8]

    return render(request, 'students/partials/global_search_results.html', {
        'students': students,
        'query': query
    })
