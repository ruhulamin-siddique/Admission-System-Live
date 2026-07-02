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
import xhtml2pdf.pisa as pisa
import json
import zipfile
from io import BytesIO
from django.template.loader import get_template
from urllib.parse import urlencode
from master_data.models import Program, Hall
from .models import Student, ProgramChangeHistory, SMSHistory, AdmissionStatusHistory
from .geo_data import BANGLADESH_GEO
from .utils import (
    generate_next_ugc_id,
    generate_ugc_prefix,
    decompose_ugc_id,
    import_students_from_excel,
    execute_program_change_web,
    patch_academic_data_from_excel,
    SSC_FIELDS,
    HSC_FIELDS,
    ALL_ACADEMIC_FIELDS,
    FIELD_LABELS,
    FIELD_PRESETS,
    get_academic_patch_fields,
    derive_field_groups,
)
import json
import os
import requests
import base64
from django.core.files.base import ContentFile
from django.conf import settings
from .utils_board import BoardVerificationEngine

def link_callback(uri, rel):
    """
    Convert HTML URIs to absolute system paths so xhtml2pdf can access those
    resources on local disk.
    """
    import os
    from django.conf import settings
    from django.contrib.staticfiles import finders

    media_url_clean = settings.MEDIA_URL.strip('/')
    static_url_clean = settings.STATIC_URL.strip('/')
    uri_clean = uri.lstrip('/')

    # Check for media files
    if media_url_clean and uri_clean.startswith(media_url_clean + '/'):
        path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, uri_clean[len(media_url_clean)+1:]))
        if os.path.isfile(path):
            return path
        return uri

    # Check for static files
    if static_url_clean and uri_clean.startswith(static_url_clean + '/'):
        path = os.path.normpath(os.path.join(settings.STATIC_ROOT, uri_clean[len(static_url_clean)+1:]))
        if os.path.isfile(path):
            return path
        # Fallback to staticfiles finders if not in STATIC_ROOT (useful during dev)
        rel_static_path = uri_clean[len(static_url_clean)+1:]
        found_path = finders.find(rel_static_path)
        if found_path:
            return os.path.normpath(found_path)

    return uri

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
    _now = timezone.localtime(timezone.now())
    _today = _now.date()
    _start_of_week = _today - timezone.timedelta(days=_today.weekday())
    _start_of_month = _today.replace(day=1)
    _twelve_months_ago = _today - timezone.timedelta(days=365)

    # Intake-wise Analysis (Last 7 Intakes)
    import re
    all_batches_raw = list(Student.objects.values_list('batch', flat=True).distinct().exclude(batch=''))
    
    # Parse batches and sort them numerically
    batch_objects = []
    for b in all_batches_raw:
        if b:
            nums = re.findall(r'\d+', b)
            if nums:
                batch_objects.append({'name': b, 'num': int(nums[0])})
    
    # Sort by number descending and take last 7
    batch_objects.sort(key=lambda x: x['num'], reverse=True)
    top_7_batches = batch_objects[:7]
    top_7_batches.reverse() # Show in chronological order on chart
    
    intake_trends = []
    for b_obj in top_7_batches:
        count = Student.objects.filter(batch=b_obj['name']).count()
        intake_trends.append({'batch': b_obj['name'], 'count': count})

    # Fetch Program Name to Short Name mapping for tooltips and display (case-insensitive lookup helper)
    program_map = {}
    for p in Program.objects.all():
        canonical = p.short_name or p.name
        program_map[p.name.lower()] = canonical
        if p.short_name:
            program_map[p.short_name.lower()] = canonical

    # Program Distribution
    program_dist_qs = Student.objects.values('program').annotate(count=Count('student_id'))
    agg_dist = {}
    for item in program_dist_qs:
        full_name = item['program'] or 'Unknown'
        short = program_map.get(full_name.lower(), full_name).strip().upper()
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
            hall_auah=Count('student_id', filter=Q(is_non_residential=False) & Q(hall_attached='AUAH')),
            hall_btbh=Count('student_id', filter=Q(is_non_residential=False) & (Q(hall_attached='BTBH') | Q(hall_attached='TBH'))),
            hall_zh=Count('student_id', filter=Q(is_non_residential=False) & Q(hall_attached='ZH')),
            unspecified=Count('student_id', filter=Q(is_non_residential=False) & (Q(hall_attached__isnull=True) | Q(hall_attached=''))),
            revenue=Sum('admission_payment'),
            quota=Count('student_id', filter=Q(is_armed_forces_child=True) | Q(is_freedom_fighter_child=True) | Q(is_july_joddha_2024=True))
        ).order_by('-total')

        aggregated_intake = {}
        for item in latest_intake_qs:
            full_name = item['program'] or 'Unknown'
            short = program_map.get(full_name.lower(), full_name).strip().upper()
            
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
                    'hall_auah': 0,
                    'hall_btbh': 0,
                    'hall_zh': 0,
                    'unspecified': 0,
                    'revenue': 0.0,
                    'quota': 0
                }
                
            aggregated_intake[short]['count'] += item['total']
            aggregated_intake[short]['male'] += item['male']
            aggregated_intake[short]['female'] += item['female']
            aggregated_intake[short]['active'] += item['active']
            aggregated_intake[short]['cancelled'] += item['cancelled']
            aggregated_intake[short]['non_residential'] += item['non_residential']
            aggregated_intake[short]['hall_auah'] += item['hall_auah']
            aggregated_intake[short]['hall_btbh'] += item['hall_btbh']
            aggregated_intake[short]['hall_zh'] += item['hall_zh']
            aggregated_intake[short]['unspecified'] += item['unspecified']
            aggregated_intake[short]['revenue'] += float(item['revenue'] or 0)
            aggregated_intake[short]['quota'] += item['quota']

        latest_batch_intake = list(aggregated_intake.values())
        latest_batch_intake.sort(key=lambda x: x['count'], reverse=True)

    # Periodic Admission Stats (System-wide)
    periodic_qs = Student.objects.all()
    today_qs = periodic_qs.filter(admission_date=_today)
    week_qs = periodic_qs.filter(admission_date__gte=_start_of_week)
    month_qs = periodic_qs.filter(admission_date__gte=_start_of_month)

    def _get_periodic_breakdown(qs):
        agg_bd = {}
        for item in qs.values('program').annotate(count=Count('student_id')):
            full_name = item['program'] or 'Unknown'
            short = program_map.get(full_name.lower(), full_name).strip().upper()
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
    for s in Student.objects.order_by('-created_at')[:20]:
        recent_students.append({
            'student_id': s.student_id,
            'student_name': s.student_name,
            'program': s.program,
            'short_name': program_map.get(s.program.lower() if s.program else '', s.program),
            'batch': s.batch,
            'admission_status': s.admission_status,
            'created_at': s.created_at
        })

    # Enrollment Insights
    cancelled_admissions = Student.objects.filter(admission_status='Cancelled').count()
    special_stats = Student.objects.aggregate(
        freedom_fighter=Count('student_id', filter=Q(is_freedom_fighter_child=True)),
        july_joddha=Count('student_id', filter=Q(is_july_joddha_2024=True)),
        armed_forces=Count('student_id', filter=Q(is_armed_forces_child=True)),
        credit_transfer=Count('student_id', filter=Q(is_credit_transfer=True)),
        non_residential=Count('student_id', filter=Q(is_non_residential=True)),
        residential=Count('student_id', filter=Q(is_non_residential=False) & ~Q(hall_attached__isnull=True) & ~Q(hall_attached='')),
        unspecified=Count('student_id', filter=Q(is_non_residential=False) & (Q(hall_attached__isnull=True) | Q(hall_attached=''))),
    )

    # Top References (Sources / Channels) for the current batch
    ref_qs = Student.objects.filter(batch=latest_batch) if latest_batch else Student.objects.all()
    from django.db.models import F
    
    # Employee references
    emp_qs = ref_qs.exclude(reference__isnull=True).values(
        name=F('reference__name_en'),
        designation=F('reference__designation'),
        category=F('reference__category')
    ).annotate(count=Count('student_id'))
    emp_list = [{
        'reference': item['name'], 
        'type': item['category'] or 'Employee',
        'designation': item['designation'] or 'Employee',
        'student_info': 'N/A',
        'count': item['count']
    } for item in emp_qs]
    
    # Student references
    stud_qs = ref_qs.exclude(referred_by_student__isnull=True).values(
        name=F('referred_by_student__student_name'),
        ref_id=F('referred_by_student__student_id'),
        referred_program=F('referred_by_student__program'),
        batch_name=F('referred_by_student__batch')
    ).annotate(count=Count('student_id'))
    stud_list = [{
        'reference': item['name'], 
        'type': 'Student',
        'designation': 'N/A',
        'student_info': f"ID: {item['ref_id']} - {item['referred_program'] or 'No Dept'} ({item['batch_name'] or 'Unknown'})",
        'count': item['count']
    } for item in stud_qs]
    
    # Combine and sort
    combined_refs = emp_list + stud_list
    combined_refs.sort(key=lambda x: x['count'], reverse=True)
    top_references = combined_refs[:5]

    stats = {
        'total_students': Student.objects.count(),
        'active_students': Student.objects.filter(admission_status='Active').count(),
        'male_students': Student.objects.filter(gender='Male').count(),
        'female_students': Student.objects.filter(gender='Female').count(),
        'by_program': program_dist[:5],
        'recent_students': recent_students,
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
        'pending_registrations': User.objects.filter(profile__registration_status='PENDING').count(),
        'top_references': top_references
    }
    # Calculate Batch-Department matrix
    raw_matrix_data = Student.objects.values('batch', 'batch_number', 'program').annotate(count=Count('student_id'))
    unique_matrix_programs = set()
    for item in raw_matrix_data:
        prog = item['program'] or 'Unknown'
        short_prog = program_map.get(prog.lower(), prog).strip().upper()
        unique_matrix_programs.add(short_prog)
    
    matrix_cols = sorted(list(unique_matrix_programs))
    
    matrix_dict = {}
    for item in raw_matrix_data:
        b_name = item['batch'] or 'Unknown'
        b_num = item['batch_number'] or 0
        prog = item['program'] or 'Unknown'
        short_prog = program_map.get(prog.lower(), prog).strip().upper()
        count = item['count']
        
        if b_name not in matrix_dict:
            matrix_dict[b_name] = {
                'batch_name': b_name,
                'batch_number': b_num,
                'counts': {},
                'row_total': 0
            }
            
        matrix_dict[b_name]['counts'][short_prog] = matrix_dict[b_name]['counts'].get(short_prog, 0) + count
        matrix_dict[b_name]['row_total'] += count

    # Sort rows by batch_number descending, then batch name descending
    sorted_batches = sorted(
        matrix_dict.keys(),
        key=lambda k: (matrix_dict[k]['batch_number'] or 0, matrix_dict[k]['batch_name']),
        reverse=True
    )
    
    matrix_rows = []
    for b_key in sorted_batches:
        row = matrix_dict[b_key]
        prog_counts = []
        for p in matrix_cols:
            prog_counts.append(row['counts'].get(p, 0))
        row['prog_counts'] = prog_counts
        matrix_rows.append(row)
        
    column_totals = []
    grand_total = 0
    for p in matrix_cols:
        col_total = sum(row['counts'].get(p, 0) for row in matrix_dict.values())
        column_totals.append(col_total)
        grand_total += col_total

    return render(request, 'students/dashboard.html', {
        'stats': stats,
        'intake_trends': json.dumps(intake_trends),
        'program_dist': json.dumps(program_dist),
        'gender_chart_data': json.dumps(gender_chart_data),
        'financials': financials,
        'latest_batch': latest_batch,
        'latest_batch_intake': latest_batch_intake,
        'matrix_cols': matrix_cols,
        'matrix_rows': matrix_rows,
        'column_totals': column_totals,
        'grand_total': grand_total,
    })

from django.core.paginator import Paginator

DIRECTORY_DEFAULT_PER_PAGE = 25
DIRECTORY_DEFAULT_SORT = 'batch_dept_serial'
DIRECTORY_FILTER_FIELDS = (
    'search',
    'year',
    'dept',
    'program',
    'batch',
    'current_batch',
    'type',
    'gender',
    'status',
    'verification',
    'special_category',
    'sort',
    'hall',
)
DIRECTORY_SORT_OPTIONS = (
    ('dept_batch_serial', 'Dept > Batch > Serial'),
    ('batch_dept_serial', 'Batch > Dept > Serial'),
)


def _get_directory_sort_choices():
    return DIRECTORY_SORT_OPTIONS


def _get_directory_params(request):
    params = {
        key: request.GET.get(key, '').strip()
        for key in DIRECTORY_FILTER_FIELDS
    }
    
    # Alias support: 'q' maps to 'search'
    if not params['search'] and request.GET.get('q'):
        params['search'] = request.GET.get('q').strip()

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


def _apply_directory_filters(queryset, params, include_cancelled=False):
    query = params['search']
    if query:
        queryset = queryset.filter(
            Q(student_name__icontains=query) |
            Q(student_id__icontains=query) |
            Q(old_student_id__icontains=query) |
            Q(student_mobile__icontains=query) |
            Q(father_name__icontains=query)
        )

    if params['program']:
        queryset = queryset.filter(program=params['program'])
    if params['batch']:
        queryset = queryset.filter(batch=params['batch'])
    if params['current_batch']:
        queryset = queryset.filter(current_batch=params['current_batch'])
    if params['year']:
        queryset = queryset.filter(admission_year=params['year'])
    if params['dept']:
        queryset = queryset.filter(cluster=params['dept'])
    if params['gender']:
        if params['gender'] == 'Unspecified':
            queryset = queryset.filter(Q(gender__isnull=True) | Q(gender='') | Q(gender='Unknown') | Q(gender='Unspecified'))
        else:
            queryset = queryset.filter(gender=params['gender'])
    if params['status']:
        queryset = queryset.filter(admission_status=params['status'])
    elif not include_cancelled:
        queryset = queryset.exclude(admission_status='Cancelled')
    if params['type']:
        queryset = queryset.filter(program_type=params['type'])
    if params.get('hall'):
        hall_val = params['hall']
        if hall_val in ['Non-Residential', 'non_residential']:
            queryset = queryset.filter(is_non_residential=True)
        elif hall_val in ['Unspecified', 'unspecified']:
            queryset = queryset.filter(is_non_residential=False).filter(Q(hall_attached__isnull=True) | Q(hall_attached=''))
        else:
            queryset = queryset.filter(hall_attached=hall_val)

    if params.get('verification'):
        v_status = params['verification']
        if v_status == 'ssc_pending':
            queryset = queryset.filter(ssc_verified=False)
        elif v_status == 'hsc_pending':
            queryset = queryset.filter(hsc_verified=False)
        elif v_status == 'unverified':
            queryset = queryset.filter(Q(ssc_verified=False) | Q(hsc_verified=False))
        elif v_status == 'fully_verified':
            queryset = queryset.filter(ssc_verified=True, hsc_verified=True)

    if params['special_category']:
        cat = params['special_category']
        if cat == 'non_residential':
            queryset = queryset.filter(is_non_residential=True)
        elif cat == 'residential':
            queryset = queryset.filter(is_non_residential=False).exclude(hall_attached__isnull=True).exclude(hall_attached='')
        elif cat == 'unspecified':
            queryset = queryset.filter(is_non_residential=False).filter(Q(hall_attached__isnull=True) | Q(hall_attached=''))
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
        elif cat == 'ugc_migrated':
            queryset = queryset.exclude(old_student_id__isnull=True).exclude(old_student_id='')
        elif cat == 'legacy_student':
            queryset = queryset.filter(is_legacy_student=True)

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


def _get_current_batch_filter_values(base_queryset):
    from master_data.models import Batch
    existing_batches = set(base_queryset.exclude(current_batch__isnull=True).exclude(current_batch='').values_list('current_batch', flat=True))
    all_sorted_batches = Batch.objects.all().order_by('-sort_order', 'name').values_list('name', flat=True)
    return [b for b in all_sorted_batches if b in existing_batches]


def _build_directory_filter_metadata(base_queryset):
    return {
        'years': _get_non_empty_values(base_queryset, 'admission_year', '-admission_year'),
        'clusters': _get_non_empty_values(base_queryset, 'cluster', 'cluster'),
        'programs': _get_non_empty_values(base_queryset, 'program', 'program'),
        'batches': _get_batch_filter_values(base_queryset),
        'current_batches': _get_current_batch_filter_values(base_queryset),
        'genders': ['Male', 'Female', 'Other', 'Unspecified'],
        'statuses': _get_non_empty_values(base_queryset, 'admission_status', 'admission_status'),
        'halls': _get_non_empty_values(base_queryset, 'hall_attached', 'hall_attached'),
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
        'is_htmx': request.headers.get('HX-Request') == 'true',
        'selected_program': params['program'],
        'selected_batch': params['batch'],
        'selected_current_batch': params['current_batch'],
        'selected_year': params['year'],
        'selected_dept': params['dept'],
        'selected_gender': params['gender'],
        'selected_status': params['status'],
        'selected_type': params['type'],
        'selected_verification': params['verification'],
        'selected_special_category': params['special_category'],
        'selected_sort': params['sort'],
        'selected_hall': params['hall'],
        'sort_options': _get_directory_sort_choices(),
        'filter_metadata': directory_state['filter_metadata'],
        'export_querystring': directory_state['export_querystring'],
        'hall_map': {h.short_name: h.full_name or h.short_name for h in Hall.objects.all()},
        'program_map': {
            **{p.name.lower(): p.short_name or p.name for p in Program.objects.all()},
            **{p.name: p.short_name or p.name for p in Program.objects.all()},
            **{p.name.upper(): p.short_name or p.name for p in Program.objects.all()},
            **{p.short_name.lower(): p.short_name or p.name for p in Program.objects.all() if p.short_name},
            **{p.short_name: p.short_name or p.name for p in Program.objects.all() if p.short_name},
            **{p.short_name.upper(): p.short_name or p.name for p in Program.objects.all() if p.short_name}
        },
    }

    # --- Smart Redirect: If search finds exactly 1 student, go to profile ---
    # We look for 'search' in params which now includes 'q' aliases
    search_query = params.get('search')
    if search_query and not request.headers.get('HX-Request'):
        page_obj = directory_state['page_obj']
        # If exactly one result is found across all filtered data
        if page_obj.paginator.count == 1:
            single_student = page_obj.object_list[0]
            # Redirect to profile
            return redirect('student_profile', student_id=single_student.student_id)

    template = 'students/partials/directory_results.html' if request.headers.get('HX-Request') else 'students/list.html'
    return render(request, template, context)


def _resolve_student(student_id):
    """
    Resolve a student by 16-digit system ID (primary key) OR by legacy 9-digit
    old_student_id. Returns (student, canonical_student_id, was_legacy_lookup).
    Raises Http404 if not found by either method.
    """
    try:
        student = Student.objects.get(pk=student_id)
        return student, student.student_id, False
    except Student.DoesNotExist:
        pass
    # Fallback: try legacy old_student_id lookup
    student = get_object_or_404(Student, old_student_id=student_id)
    return student, student.student_id, True


@require_access('students', 'view_directory')
@require_access('students', 'view_directory')
def student_short_info(request, student_id):
    """Returns a compact card with student info not visible in the main directory."""
    student, canonical_id, was_legacy = _resolve_student(student_id)
    if was_legacy:
        # short_info might be loaded via AJAX, just serve the content with canonical student object.
        pass
    # We could restrict .only() here but _resolve_student already loaded the full object.
    return render(request, 'students/partials/short_info_card.html', {'student': student})

@require_access('students', 'delete_record')
def delete_student(request, student_id):
    """Permanently delete a student record with audit logging."""
    student, canonical_id, was_legacy = _resolve_student(student_id)
    if was_legacy:
        return redirect('delete_student', student_id=canonical_id)
    if request.method == 'POST':
        student_name = student.student_name
        student.delete()
        from core.utils import log_activity
        log_activity(request, 'DELETE', 'students', f'Permanently deleted student record: {student_name}', object_id=student_id)
        messages.success(request, f"Student {student_id} has been permanently removed.")
        return redirect('student_list')
    return redirect('student_profile', student_id=student_id)

@require_access('students', 'view_migrations')
def migration_center(request):
    """Unified Academic Migration & History Hub."""
    # Active search for candidates (Tab 2)
    search_active = request.GET.get('search_active', '').strip()
    
    # History search & filters (Tab 1)
    search_history = request.GET.get('search_history', '').strip()
    selected_old_program = request.GET.get('old_program', '').strip()
    selected_new_program = request.GET.get('new_program', '').strip()
    page_number = request.GET.get('page', 1)
    
    # 1. Query Migration History Log
    history_queryset = ProgramChangeHistory.objects.all()
    if selected_old_program:
        history_queryset = history_queryset.filter(old_program=selected_old_program)
    if selected_new_program:
        history_queryset = history_queryset.filter(new_program=selected_new_program)
    if search_history:
        history_queryset = history_queryset.filter(
            Q(old_student_id__icontains=search_history) |
            Q(new_student_id__icontains=search_history)
        )
    
    history_queryset = history_queryset.order_by('-change_date')
    
    # Paginate History
    paginator_history = Paginator(history_queryset, 20)
    history_page_obj = paginator_history.get_page(page_number)
    
    # 2. Query Candidate Active Students
    active_candidates = []
    if search_active:
        active_candidates = Student.objects.filter(
            Q(student_name__icontains=search_active) | 
            Q(student_id__icontains=search_active) |
            Q(old_student_id__icontains=search_active) |
            Q(student_mobile__icontains=search_active)
        ).exclude(admission_status='Cancelled').order_by('student_id')[:25]
        
    # Dynamic Program Filters
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program=None).order_by('program')
    
    # Build export parameters
    import urllib.parse
    export_params = {}
    if search_history: export_params['search'] = search_history
    if selected_old_program: export_params['old_program'] = selected_old_program
    if selected_new_program: export_params['new_program'] = selected_new_program
    export_querystring = urllib.parse.urlencode(export_params) if export_params else ""

    context = {
        'search_active': search_active,
        'search_history': search_history,
        'selected_old_program': selected_old_program,
        'selected_new_program': selected_new_program,
        'history_page_obj': history_page_obj,
        'active_candidates': active_candidates,
        'programs': programs,
        'export_querystring': export_querystring,
        'total_migrations': ProgramChangeHistory.objects.count(),
    }

    if request.headers.get('HX-Request'):
        target = request.GET.get('target', 'history')
        if target == 'active':
            # Render candidates table (renamed from page_obj inside migration_table)
            context['page_obj'] = active_candidates
            return render(request, 'students/partials/migration_table.html', context)
        else:
            return render(request, 'students/partials/migration_history_list.html', context)

    return render(request, 'students/migration_list.html', context)

@require_access('students', 'view_cancellations')
def cancellation_hub(request):
    """Unified Admission Cancellation & Status Hub."""
    # Active search (Tab 2)
    search_active = request.GET.get('search_active', '').strip()
    
    # Cancelled search & filters (Tab 1)
    search_cancelled = request.GET.get('search_cancelled', '').strip()
    selected_program = request.GET.get('program', '').strip()
    selected_batch = request.GET.get('batch', '').strip()
    selected_reason = request.GET.get('reason', '').strip()
    
    # 1. Query Cancelled students
    cancelled_queryset = Student.objects.filter(admission_status='Cancelled').prefetch_related('status_history')
    if selected_program:
        cancelled_queryset = cancelled_queryset.filter(program=selected_program)
    if selected_batch:
        cancelled_queryset = cancelled_queryset.filter(batch=selected_batch)
    if selected_reason:
        cancelled_queryset = cancelled_queryset.filter(
            status_history__new_status='Cancelled',
            status_history__reason_category=selected_reason
        )
    if search_cancelled:
        cancelled_queryset = cancelled_queryset.filter(
            Q(student_id__icontains=search_cancelled) |
            Q(student_name__icontains=search_cancelled)
        )
    
    cancelled_queryset = cancelled_queryset.distinct().order_by('-last_updated')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(cancelled_queryset, 20)
    page_number = request.GET.get('page', 1)
    cancelled_page_obj = paginator.get_page(page_number)
    
    # 2. Query Active students for new cancellations
    active_students = []
    if search_active:
        active_students = Student.objects.filter(
            Q(student_name__icontains=search_active) | 
            Q(student_id__icontains=search_active) |
            Q(old_student_id__icontains=search_active)
        ).exclude(admission_status='Cancelled').order_by('student_id')[:25]

    # Dynamic Filter Choices
    programs = Student.objects.filter(admission_status='Cancelled').values_list('program', flat=True).distinct().order_by('program')
    batches = Student.objects.filter(admission_status='Cancelled').values_list('batch', flat=True).distinct().exclude(batch=None).order_by('batch')
    reasons = [
        ('Migration', 'Migration to other University'),
        ('Financial', 'Financial/Non-Payment'),
        ('Personal', 'Personal Reasons'),
        ('Academic', 'Academic Non-Performance'),
        ('Disciplinary', 'Disciplinary Action'),
        ('Other', 'Other (See Notes)'),
    ]
    reasons_map = dict(reasons)
    
    # Build export query parameters string
    import urllib.parse
    export_params = {}
    if search_cancelled: export_params['search'] = search_cancelled
    if selected_program: export_params['program'] = selected_program
    if selected_batch: export_params['batch'] = selected_batch
    if selected_reason: export_params['reason'] = selected_reason
    export_querystring = urllib.parse.urlencode(export_params) if export_params else ""

    context = {
        'search_active': search_active,
        'search_cancelled': search_cancelled,
        'selected_program': selected_program,
        'selected_batch': selected_batch,
        'selected_reason': selected_reason,
        'cancelled_page_obj': cancelled_page_obj,
        'active_students': active_students,
        'programs': programs,
        'batches': batches,
        'reasons': reasons,
        'reasons_map': reasons_map,
        'export_querystring': export_querystring,
        'cancelled_count': Student.objects.filter(admission_status='Cancelled').count(),
    }

    if request.headers.get('HX-Request'):
        target = request.GET.get('target', 'cancelled')
        if target == 'active':
            return render(request, 'students/partials/cancellation_results.html', context)
        else:
            return render(request, 'students/partials/cancellation_list.html', context)

    return render(request, 'students/cancellation_hub.html', context)

@require_access('students', 'view_cancellations')
def cancellation_list_modal(request):
    """Returns a partial list of cancelled students for the drill-down modal."""
    cancelled_students = Student.objects.filter(admission_status='Cancelled').order_by('-last_updated')
    return render(request, 'students/partials/cancelled_list_modal.html', {'students': cancelled_students})

@require_access('students', 'cancel_admission')
def cancel_admission(request, student_id):
    """View to handle the actual cancellation logic with history logging."""
    student, canonical_id, was_legacy = _resolve_student(student_id)
    if was_legacy:
        return redirect('cancel_admission', student_id=canonical_id)
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
    
    _now = timezone.localtime(timezone.now())
    _today = _now.date()
    
    qs = Student.objects.all()
    
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
def api_matrix_students(request):
    """Returns a partial list of students for matrix drill-down selection."""
    batch = request.GET.get('batch')
    program_code = request.GET.get('program')
    
    qs = Student.objects.all()
    
    if batch and batch != 'all' and batch != 'Total':
        if batch == 'Unknown':
            qs = qs.filter(Q(batch__isnull=True) | Q(batch=''))
        else:
            qs = qs.filter(batch=batch)
            
    if program_code and program_code != 'all' and program_code != 'Total':
        if program_code == 'Unknown':
            qs = qs.filter(Q(program__isnull=True) | Q(program=''))
        else:
            from master_data.models import Program
            # Find matching program names in master data (short name or full name match)
            matching_programs = list(Program.objects.filter(
                Q(name__iexact=program_code) | Q(short_name__iexact=program_code)
            ).values_list('name', flat=True))
            # Also include the program code itself
            matching_programs.append(program_code)
            
            # Filter student records by matching programs
            qs = qs.filter(program__in=matching_programs)
            
    students = qs.order_by('student_id')[:100] # Limit to 100 for quick view in modal
    
    return render(request, 'students/partials/matrix_student_list.html', {
        'students': students,
        'batch': batch,
        'program': program_code,
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
    program_map = {}
    for p in Program.objects.all():
        canonical = p.short_name or p.name
        program_map[p.name.lower()] = canonical
        if p.short_name:
            program_map[p.short_name.lower()] = canonical
            
    dist_qs = qs.values('program').annotate(count=Count('student_id'))
    
    agg_dist = {}
    for item in dist_qs:
        full_name = item['program'] or 'Unknown'
        short = program_map.get(full_name.lower(), full_name).strip().upper()
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

@require_access('dashboard', 'view')
def api_special_distribution(request):
    """Returns JSON data for special designations, optionally filtered by batch."""
    batch = request.GET.get('batch')
    
    qs = Student.objects.all()
    if batch and batch != 'all':
        qs = qs.filter(batch=batch)
        
    stats = qs.aggregate(
        freedom_fighter=Count('student_id', filter=Q(is_freedom_fighter_child=True)),
        july_joddha=Count('student_id', filter=Q(is_july_joddha_2024=True)),
        armed_forces=Count('student_id', filter=Q(is_armed_forces_child=True)),
        credit_transfer=Count('student_id', filter=Q(is_credit_transfer=True)),
        non_residential=Count('student_id', filter=Q(is_non_residential=True)),
        residential=Count('student_id', filter=Q(is_non_residential=False) & ~Q(hall_attached__isnull=True) & ~Q(hall_attached='')),
        unspecified=Count('student_id', filter=Q(is_non_residential=False) & (Q(hall_attached__isnull=True) | Q(hall_attached=''))),
    )
    return JsonResponse(stats)

@require_access('dashboard', 'view')
def api_hall_distribution(request):
    """Returns JSON data for hall distribution, optionally filtered by batch."""
    batch = request.GET.get('batch')
    
    qs = Student.objects.all()
    if batch and batch != 'all':
        qs = qs.filter(batch=batch)
        
    hall_map = {
        'AUAH': 'Abbas Uddin Ahmed Hall',
        'BTBH': 'Taramon Bibi Hall',
        'TBH': 'Taramon Bibi Hall',
        'ZH': 'Zikrul Hoque Hall'
    }
    
    # Exclude non-residential from hall counts, count separately
    non_res_count = qs.filter(is_non_residential=True).count()
    unspec_count = qs.filter(is_non_residential=False).filter(Q(hall_attached__isnull=True) | Q(hall_attached='')).count()
    
    dist_qs = qs.filter(is_non_residential=False).exclude(hall_attached__isnull=True).exclude(hall_attached='').values('hall_attached').annotate(count=Count('student_id'))
    
    agg_dist = {}
    total = qs.count()
    
    for item in dist_qs:
        hall_code = item['hall_attached']
        count = item['count']
        name = hall_map.get(hall_code, hall_code)
        if name not in agg_dist:
            agg_dist[name] = {'hall': name, 'count': 0, 'code': hall_code}
        agg_dist[name]['count'] += count
        
    data = [
        {
            'hall': name,
            'count': info['count'],
            'percentage': round((info['count'] / total * 100), 1) if total > 0 else 0,
            'code': info.get('code')
        }
        for name, info in agg_dist.items()
    ]
    
    if unspec_count > 0:
        data.append({
            'hall': 'Unspecified',
            'count': unspec_count,
            'percentage': round((unspec_count / total * 100), 1) if total > 0 else 0,
            'code': 'unspecified'
        })
        
    if non_res_count > 0:
        data.append({
            'hall': 'Non-Residential',
            'count': non_res_count,
            'percentage': round((non_res_count / total * 100), 1) if total > 0 else 0,
            'code': 'non_residential'
        })
        
    data.sort(key=lambda x: x['count'], reverse=True)
    return JsonResponse({'distribution': data, 'total': total})

@require_access('dashboard', 'view')
def api_intake_distribution(request):
    """Returns JSON data containing program-wise intake breakdown for a requested batch."""
    batch = request.GET.get('batch')
    
    program_map = {}
    for p in Program.objects.all():
        canonical = p.short_name or p.name
        program_map[p.name.lower()] = canonical
        if p.short_name:
            program_map[p.short_name.lower()] = canonical

    if batch == 'all' or not batch:
        batch_students = Student.objects.all()
        batch_title = "Overall System"
    else:
        batch_students = Student.objects.filter(batch=batch)
        batch_title = f"{batch} Batch"

    total_batch_students = batch_students.count()

    intake_qs = batch_students.values('program').annotate(
        total=Count('student_id'),
        male=Count('student_id', filter=Q(gender='Male')),
        female=Count('student_id', filter=Q(gender='Female')),
        active=Count('student_id', filter=Q(admission_status='Active')),
        cancelled=Count('student_id', filter=Q(admission_status='Cancelled')),
        non_residential=Count('student_id', filter=Q(is_non_residential=True)),
        hall_auah=Count('student_id', filter=Q(is_non_residential=False) & Q(hall_attached='AUAH')),
        hall_btbh=Count('student_id', filter=Q(is_non_residential=False) & (Q(hall_attached='BTBH') | Q(hall_attached='TBH'))),
        hall_zh=Count('student_id', filter=Q(is_non_residential=False) & Q(hall_attached='ZH')),
        unspecified=Count('student_id', filter=Q(is_non_residential=False) & (Q(hall_attached__isnull=True) | Q(hall_attached=''))),
        quota=Count('student_id', filter=Q(is_armed_forces_child=True) | Q(is_freedom_fighter_child=True) | Q(is_july_joddha_2024=True))
    ).order_by('-total')

    aggregated_intake = {}
    for item in intake_qs:
        full_name = item['program'] or 'Unknown'
        short = program_map.get(full_name.lower(), full_name).strip().upper()
        
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
                'hall_auah': 0,
                'hall_btbh': 0,
                'hall_zh': 0,
                'unspecified': 0,
                'quota': 0
            }
            
        aggregated_intake[short]['count'] += item['total']
        aggregated_intake[short]['male'] += item['male']
        aggregated_intake[short]['female'] += item['female']
        aggregated_intake[short]['active'] += item['active']
        aggregated_intake[short]['cancelled'] += item['cancelled']
        aggregated_intake[short]['non_residential'] += item['non_residential']
        aggregated_intake[short]['hall_auah'] += item['hall_auah']
        aggregated_intake[short]['hall_btbh'] += item['hall_btbh']
        aggregated_intake[short]['hall_zh'] += item['hall_zh']
        aggregated_intake[short]['unspecified'] += item['unspecified']
        aggregated_intake[short]['quota'] += item['quota']

    intake_list = list(aggregated_intake.values())
    intake_list.sort(key=lambda x: x['count'], reverse=True)

    return JsonResponse({
        'batch_name': batch_title,
        'total_students': total_batch_students,
        'intake': intake_list
    })

@require_access('dashboard', 'view')
def api_religion_distribution(request):
    """Returns JSON data for religion distribution, optionally filtered by batch."""
    batch = request.GET.get('batch')
    
    qs = Student.objects.all()
    if batch and batch != 'all':
        qs = qs.filter(batch=batch)
        
    religion_dist = qs.annotate(
        religion_label=Coalesce('religion', Value('Unknown'))
    ).values('religion_label').annotate(count=Count('student_id')).order_by('-count')
    
    total = sum(r['count'] for r in religion_dist)
    data = [
        {
            'religion': r['religion_label'] or 'Unknown',
            'count': r['count'],
            'percentage': round((r['count'] / total * 100), 1) if total > 0 else 0
        }
        for r in religion_dist
    ]
    return JsonResponse({'distribution': data, 'total': total})

@require_access('reports', 'view_analytics')
def api_demographic_students(request):
    """Returns a partial list of students filtered by gender or religion for demographic drill-down modals."""
    gender = request.GET.get('gender')
    religion = request.GET.get('religion')
    batch = request.GET.get('batch')
    year = request.GET.get('year')
    program = request.GET.get('program')
    
    queryset = Student.objects.all()
    
    # Apply standard page filters
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
    if program:
        queryset = queryset.filter(program=program)
        
    # Apply demographic filter
    if gender is not None:
        if gender == 'Unspecified' or gender == '' or gender.lower() == 'unknown':
            queryset = queryset.filter(Q(gender__isnull=True) | Q(gender='') | Q(gender='Unknown'))
            gender = 'Unspecified'
        else:
            queryset = queryset.filter(gender=gender)
            
    if religion is not None:
        if religion == 'Unspecified' or religion == '' or religion.lower() == 'unknown':
            queryset = queryset.filter(Q(religion__isnull=True) | Q(religion='') | Q(religion='Unknown'))
            religion = 'Unspecified'
        else:
            queryset = queryset.filter(religion=religion)
            
    queryset = queryset.order_by('-created_at')
    count = queryset.count()
    
    return render(request, 'students/partials/demographic_student_list.html', {
        'students': queryset[:100],  # Limit to 100 for modal preview performance
        'count': count,
        'gender': gender,
        'religion': religion,
        'batch': batch,
        'year': year,
        'program': program,
    })

@login_required
@require_access('students', 'export_excel')
def api_bulk_photo_zip(request):
    """Packages student photos into a ZIP archive with support for direct selection or dynamic filtering."""
    if request.method not in ['GET', 'POST']:
        return HttpResponse("Method not allowed", status=405)
        
    data_source = request.POST if request.method == 'POST' else request.GET
    student_ids = data_source.getlist('student_ids[]')
    
    if student_ids:
        # Priority 1: Specific selection from Directory
        students = Student.objects.filter(student_id__in=student_ids)
    else:
        # Priority 2: Use directory state filtering
        try:
            students = _build_directory_state(request)['filtered_queryset']
        except Exception:
            # Fallback if request cannot build directory state
            query = data_source.get('search', '')
            program = data_source.get('program')
            status = data_source.get('status')
            batch = data_source.get('batch')
            semester = data_source.get('semester')
            hall = data_source.get('hall')
            start_date = data_source.get('start_date')
            end_date = data_source.get('end_date')
            
            students = Student.objects.all()
            if query:
                students = students.filter(Q(student_name__icontains=query) | Q(student_id__icontains=query))
            if program and program != 'All':
                students = students.filter(program=program)
            if status and status != 'All':
                students = students.filter(admission_status=status)
            if batch:
                students = students.filter(batch=batch)
            if semester and semester != 'All':
                students = students.filter(semester_name=semester)
            if hall:
                students = students.filter(hall_attached__icontains=hall)
            if start_date:
                students = students.filter(admission_date__gte=start_date)
            if end_date:
                students = students.filter(admission_date__lte=end_date)
                
    students = students.exclude(photo_path__isnull=True).exclude(photo_path='')
    
    if not students.exists():
        return HttpResponse("Error: No photos found for the selected criteria.", status=404)
        
    # Create ZIP in memory
    buffer = BytesIO()
    try:
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            files_added = 0
            for student in students:
                raw_path = str(student.photo_path or '').strip()
                if not raw_path: continue
                    
                if raw_path.startswith(settings.MEDIA_URL):
                    raw_path = raw_path[len(settings.MEDIA_URL):].lstrip('/')
                elif raw_path.startswith('/media/'):
                    raw_path = raw_path[len('/media/'):].lstrip('/')
                
                full_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, raw_path))
                
                if os.path.exists(full_path):
                    ext = os.path.splitext(full_path)[1].lower() or '.jpg'
                    safe_name = "".join([c for c in student.student_name if c.isalnum() or c==' ']).strip().replace(' ', '_')
                    zip_filename = f"{student.student_id}_{safe_name}{ext}"
                    zip_file.write(full_path, zip_filename)
                    files_added += 1
            
            if files_added == 0:
                return HttpResponse("Error: Physical files missing on server for these records.", status=404)
    except Exception as e:
        return HttpResponse(f"Server Error: {str(e)}", status=500)

    buffer.seek(0)
    
    # Log the export activity
    from core.utils import log_activity
    log_activity(request, 'EXPORT', 'students', f'Exported {files_added} student photos to ZIP', object_id='bulk_zip')
    
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    response['Content-Disposition'] = f'attachment; filename="Student_Photos_Export_{timestamp}.zip"'
    return response

def _handle_student_photo(request, student):
    """Saves student photo (standard upload or Base64 camera data)."""
    photo = request.FILES.get('student_photo')
    camera_data = request.POST.get('camera_photo')
    
    if not photo and not camera_data:
        return None
        
    # Ensure directory exists
    photo_dir = os.path.join(settings.MEDIA_ROOT, 'student_photos')
    if not os.path.exists(photo_dir):
        os.makedirs(photo_dir, exist_ok=True)
        
    if camera_data:
        # Handle Base64 from Camera
        try:
            format, imgstr = camera_data.split(';base64,') 
            ext = "." + format.split('/')[-1]
            photo_content = ContentFile(base64.b64decode(imgstr))
            filename = f"{student.student_id}{ext}"
        except Exception as e:
            return None
    else:
        # Handle Standard File Upload
        ext = os.path.splitext(photo.name)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png']:
            return None
        filename = f"{student.student_id}{ext}"
        photo_content = photo

    file_path = os.path.join(photo_dir, filename)
    
    # Delete old file if it's different
    if student.photo_path:
        old_rel_path = student.photo_path.replace(settings.MEDIA_URL, '').lstrip('/')
        old_full_path = os.path.join(settings.MEDIA_ROOT, old_rel_path)
        if os.path.exists(old_full_path) and old_full_path != file_path:
            try:
                os.remove(old_full_path)
            except:
                pass
                
    # Save new file
    if camera_data:
        with open(file_path, 'wb') as f:
            f.write(photo_content.read())
    else:
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

            # --- Detect Legacy Student Mode ---
            is_legacy = request.POST.get('is_legacy_student') in ('on', 'true', '1')
            student.is_legacy_student = is_legacy

            if is_legacy:
                # Legacy student: always auto-generate a 16-digit system ID.
                from core.models import SystemSettings
                student.student_id = generate_next_ugc_id(
                    admission_year=request.POST.get('admission_year'),
                    semester_name=request.POST.get('semester_name'),
                    hall_name=request.POST.get('hall_attached'),
                    program_name=request.POST.get('program'),
                    cluster_name=request.POST.get('cluster'),
                    program_level=request.POST.get('program_type', 'Bachelor'),
                )

                # Validate mandatory old ID
                old_id = (request.POST.get('old_student_id') or '').strip()
                legacy_error = None
                if not old_id:
                    legacy_error = ('old_student_id', 'Legacy students must have their original ID entered here.')
                elif Student.objects.filter(old_student_id=old_id).exists():
                    legacy_error = ('old_student_id', f'Old ID "{old_id}" is already registered for another student.')

                if legacy_error:
                    form.add_error(*legacy_error)
                    error_count = len(form.errors)
                    messages.error(request, f"Admission failed. Please fix the {error_count} error(s) in the form.")
                else:
                    student.old_student_id = old_id

            if not is_legacy or not form.errors:
                if not is_legacy:
                    # Standard ID Assignment: branch on id_mode
                    from core.models import SystemSettings
                    sys = SystemSettings.objects.get_or_create(id=1)[0]

                    if not student.student_id:
                        if sys.id_mode == 'semi_auto':
                            serial_input = str(request.POST.get('student_id_serial', '')).strip()
                            prefix = generate_ugc_prefix(
                                admission_year=request.POST.get('admission_year'),
                                semester_name=request.POST.get('semester_name'),
                                hall_name=request.POST.get('hall_attached'),
                                program_name=request.POST.get('program'),
                                cluster_name=request.POST.get('cluster'),
                                program_level=request.POST.get('program_type', 'Bachelor'),
                            )
                            if serial_input and serial_input.isdigit() and len(serial_input) == 3:
                                student.student_id = prefix + serial_input
                            else:
                                student.student_id = generate_next_ugc_id(
                                    admission_year=request.POST.get('admission_year'),
                                    semester_name=request.POST.get('semester_name'),
                                    hall_name=request.POST.get('hall_attached'),
                                    program_name=request.POST.get('program'),
                                    cluster_name=request.POST.get('cluster'),
                                    program_level=request.POST.get('program_type', 'Bachelor'),
                                )
                        elif sys.id_mode == 'auto':
                            student.student_id = generate_next_ugc_id(
                                admission_year=request.POST.get('admission_year'),
                                semester_name=request.POST.get('semester_name'),
                                hall_name=request.POST.get('hall_attached'),
                                program_name=request.POST.get('program'),
                                cluster_name=request.POST.get('cluster'),
                                program_level=request.POST.get('program_type', 'Bachelor'),
                            )
                        # manual mode: ID from form field (validated by clean_student_id)

                # Handle Photo Upload
                photo_path = _handle_student_photo(request, student)
                if photo_path:
                    student.photo_path = photo_path

                student.save()
                from core.utils import log_activity
                if is_legacy:
                    log_activity(
                        request, 'CREATE', 'students',
                        f'Added legacy student (Batch {student.batch}): {student.student_name} '
                        f'[Old ID: {student.old_student_id}] [System ID: {student.student_id}]',
                        object_id=student.student_id
                    )
                else:
                    log_activity(request, 'CREATE', 'students', f'Admitted new student: {student.student_name}', object_id=student.student_id)

                # Automated Welcome SMS — suppressed for legacy records (already graduated / not new admissions)
                if student.student_mobile and not is_legacy:
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

                if is_legacy:
                    messages.success(request, f"Legacy student {student.student_name} added. Old ID: {student.old_student_id} | System ID: {student.student_id}")
                else:
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
        (p.short_name if p.short_name else p.name): {
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
    student, canonical_id, was_legacy = _resolve_student(student_id)
    if was_legacy:
        return redirect('edit_student', student_id=canonical_id)
    
    # Identify fields that must remain constant to maintain ID and academic integrity
    # If the student is a legacy student with an ID < 16 digits, we unlock academic fields
    # so the administrator can specify details and perform a UGC ID migration.
    if len(student.student_id) < 16:
        locked_fields = ['student_id']
    else:
        locked_fields = ['program', 'admission_year', 'cluster', 'hall_attached', 'semester_name', 'program_type', 'student_id']
    
    if request.method == "POST":
        # Capture original values for both injection and restoration
        original_values = {field: getattr(student, field) for field in locked_fields}
        
        # Inject original values into a mutable copy of POST data
        post_data = request.POST.copy()
        for field, original_val in original_values.items():
            if field not in post_data or not post_data.get(field):
                post_data[field] = original_val
        
        form = StudentForm(post_data, request.FILES, instance=student)

        if form.is_valid():
            # This updates the instance but might clear fields missing from POST
            student = form.save(commit=False)
            student.changed_by_user = request.user
            
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
            # IMPORTANT: Restore locked fields (like student_id) even on failure 
            # so template rendering (profile links, etc.) doesn't break
            for field, value in original_values.items():
                setattr(student, field, value)
                
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
    from .utils import decompose_ugc_id
    programs = Program.objects.all()
    program_mapping = {
        (p.short_name if p.short_name else p.name): {
            'cluster': p.cluster.name,
            'type': p.get_level_code_display()
        } for p in programs
    }

    return render(request, 'students/edit.html', {
        'form': form, 
        'student': student,
        'id_parts': decompose_ugc_id(student.student_id),
        'program_mapping_json': json.dumps(program_mapping),
        'geo_data_json': json.dumps(BANGLADESH_GEO),
        **_get_history_suggestions()
    })

@require_access('students', 'manage_migrations')
def rectify_student_id(request, student_id):
    """
    Securely re-keys a student's primary ID.
    Clones record, updates relations, renames media, and deletes original.
    """
    if not request.user.is_superuser:
        messages.error(request, "Permission Denied: Only Super-Administrators can rectify Student IDs.")
        return redirect('student_profile', student_id=student_id)

    student, canonical_id, was_legacy = _resolve_student(student_id)
    if was_legacy:
        return redirect('rectify_student_id', student_id=canonical_id)
    
    if request.method == 'POST':
        new_id = request.POST.get('new_id', '').strip()
        reason = request.POST.get('reason', '').strip()
        
        if not new_id or new_id == student_id:
            messages.error(request, "Please provide a new, different Student ID.")
            return redirect('student_profile', student_id=student_id)
            
        if Student.objects.filter(student_id=new_id).exists():
            messages.error(request, f"Collision Error: ID {new_id} is already in use.")
            return redirect('student_profile', student_id=student_id)

        try:
            with transaction.atomic():
                old_id = student.student_id
                
                # Update academic attributes if supplied in POST (e.g. from the migration tool)
                for field in ['program', 'admission_year', 'semester_name', 'hall_attached', 'program_type', 'cluster']:
                    if field in request.POST and request.POST.get(field):
                        val = request.POST.get(field)
                        # Set database correct type for admission_year
                        if field == 'admission_year':
                            val = int(val)
                        setattr(student, field, val)
                
                # Normalize cluster if program changed
                if 'program' in request.POST and request.POST.get('program'):
                    from master_data.models import Program as MasterProgram
                    prog_obj = MasterProgram.objects.filter(
                        Q(name__iexact=student.program) | Q(short_name__iexact=student.program)
                    ).first()
                    if prog_obj:
                        student.cluster = prog_obj.cluster.name
                        if not student.program_type:
                            student.program_type = prog_obj.get_level_code_display()
                
                # 1. Clone the record
                # We do this by changing PK and saving as new
                student.pk = new_id
                student.old_student_id = old_id # Persist alias
                
                # 2. Handle Photo Migration
                if student.photo_path:
                    old_photo_rel = student.photo_path
                    ext = os.path.splitext(old_photo_rel)[1]
                    new_photo_rel = f"students/photos/{new_id}{ext}"
                    
                    old_photo_full = os.path.join(settings.MEDIA_ROOT, old_photo_rel)
                    new_photo_full = os.path.join(settings.MEDIA_ROOT, new_photo_rel)
                    
                    if os.path.exists(old_photo_full):
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(new_photo_full), exist_ok=True)
                        os.rename(old_photo_full, new_photo_full)
                        student.photo_path = new_photo_rel.replace('\\', '/')

                student.save() # Saves as NEW record because PK changed
                
                # 3. Update Hard Relations (FKs)
                AdmissionStatusHistory.objects.filter(student_id=old_id).update(student_id=new_id)
                
                # 4. Update Soft Relations (CharFields)
                ProgramChangeHistory.objects.filter(old_student_id=old_id).update(old_student_id=new_id)
                ProgramChangeHistory.objects.filter(new_student_id=old_id).update(new_student_id=new_id)
                SMSHistory.objects.filter(student_id=old_id).update(student_id=new_id)
                
                # 5. Log & Audit
                from core.utils import log_activity
                log_activity(request, 'UPDATE', 'students', 
                             f"ID RECTIFICATION: {old_id} -> {new_id}. Reason: {reason}", 
                             object_id=new_id)
                
                # 6. Finalize: Remove old record
                Student.objects.filter(student_id=old_id).delete()
                
                messages.success(request, f"Student ID successfully rectified: {old_id} is now {new_id}.")
                return redirect('student_profile', student_id=new_id)
                
        except Exception as e:
            messages.error(request, f"Migration Failed: {str(e)}")
            return redirect('student_profile', student_id=student_id)

    return redirect('student_profile', student_id=student_id)


@require_access('students', 'edit_profile')
def api_student_ugc_id_preview(request, student_id):
    """
    Calculates and returns the suggested 16-digit UGC ID for an existing student,
    allowing optional GET parameters to override the database fields.
    """
    student, _, _ = _resolve_student(student_id)
    
    # Use request params or fall back to student's DB fields
    admission_year = request.GET.get('admission_year') or student.admission_year
    semester_name = request.GET.get('semester_name') or student.semester_name
    hall_attached = request.GET.get('hall_attached') or student.hall_attached
    program = request.GET.get('program') or student.program
    program_type = request.GET.get('program_type') or student.program_type
    
    # Resolve program level/type mapping if program changed
    cluster = student.cluster
    if program:
        from master_data.models import Program as MasterProgram
        prog_obj = MasterProgram.objects.filter(
            Q(name__iexact=program) | Q(short_name__iexact=program)
        ).first()
        if prog_obj:
            cluster = prog_obj.cluster.name
            if not program_type:
                program_type = prog_obj.get_level_code_display()
                
    missing = []
    if not admission_year: missing.append("Admission Year")
    if not semester_name: missing.append("Admitted Semester")
    if not hall_attached: missing.append("Hall Attachment")
    if not program: missing.append("Program")
    
    if missing:
        return JsonResponse({
            'success': False, 
            'missing': missing,
            'error': f"Required academic parameters are missing. Please select: {', '.join(missing)}"
        })
        
    try:
        from .utils import generate_next_ugc_id
        suggested_id = generate_next_ugc_id(
            admission_year=admission_year,
            semester_name=semester_name,
            hall_name=hall_attached,
            program_name=program,
            cluster_name=cluster,
            program_level=program_type or "Bachelor",
            mba_credits=student.mba_credits
        )
        return JsonResponse({
            'success': True,
            'suggested_id': suggested_id,
            'details': {
                'admission_year': admission_year,
                'semester_name': semester_name,
                'hall_attached': hall_attached,
                'program': program,
                'program_type': program_type or "Bachelor",
                'current_id': student.student_id
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def api_preview_id(request):
    """
    Returns the 13-char UGC prefix and 16-char suggested ID for the ID forms.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    has_perm = request.user.is_superuser
    if not has_perm and hasattr(request.user, 'profile'):
        has_perm = (
            request.user.profile.has_access('students', 'add_student') or
            request.user.profile.has_access('students', 'edit_profile') or
            request.user.profile.has_access('students', 'manage_migrations')
        )
    if not has_perm:
        from django.contrib import messages
        messages.error(request, "Access Denied: You do not have permission for 'students.add_student'")
        return redirect('user_profile')

    try:
        admission_year = request.GET.get('admission_year', 2026)
        semester_name = request.GET.get('semester_name', 'Spring')
        hall_name = request.GET.get('hall_name', 'Non-Residential')
        program_name = request.GET.get('program', 'CSE')
        cluster_name = request.GET.get('cluster', 'Engineering & Technology')
        program_level = request.GET.get('program_type', 'Bachelor')
        mba_credits = request.GET.get('mba_credits')
        if mba_credits:
            try:
                mba_credits = int(mba_credits)
            except ValueError:
                mba_credits = None

        from .utils import generate_ugc_prefix, generate_next_ugc_id, decompose_ugc_id

        prefix = generate_ugc_prefix(
            admission_year=admission_year,
            semester_name=semester_name,
            hall_name=hall_name,
            program_name=program_name,
            cluster_name=cluster_name,
            program_level=program_level,
        )
        
        suggested_id = generate_next_ugc_id(
            admission_year=admission_year,
            semester_name=semester_name,
            hall_name=hall_name,
            program_name=program_name,
            cluster_name=cluster_name,
            program_level=program_level,
            mba_credits=mba_credits,
        )
        
        components = decompose_ugc_id(suggested_id)

        return JsonResponse({
            'prefix': prefix,
            'suggested_id': suggested_id,
            'components': components
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def api_check_id_duplicate(request):
    """
    Checks whether a fully assembled 16-digit student ID already exists.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    has_perm = request.user.is_superuser
    if not has_perm and hasattr(request.user, 'profile'):
        has_perm = (
            request.user.profile.has_access('students', 'add_student') or
            request.user.profile.has_access('students', 'edit_profile') or
            request.user.profile.has_access('students', 'manage_migrations')
        )
    if not has_perm:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    student_id = request.GET.get('student_id', '').strip()
    if not student_id or len(student_id) != 16:
        return JsonResponse({'exists': False, 'error': 'Invalid ID length'}, status=400)
    from .models import Student
    student = Student.objects.filter(student_id=student_id).only('student_name').first()
    if student:
        return JsonResponse({'exists': True, 'name': student.student_name})
    return JsonResponse({'exists': False})

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
            
            # Log bulk activity
            from core.models import ActivityLog
            meta = getattr(request, 'META', {})
            x_forwarded_for = meta.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = meta.get('REMOTE_ADDR', None)
            
            logs_to_create = []
            for s_id in result.get('inserted_list', []):
                logs_to_create.append(ActivityLog(
                    user=request.user,
                    action_type='CREATE',
                    module='students',
                    object_id=s_id,
                    description=f"Imported student record {s_id} via Excel sheet",
                    ip_address=ip
                ))
            for s_id in result.get('updated_list', []):
                logs_to_create.append(ActivityLog(
                    user=request.user,
                    action_type='UPDATE',
                    module='students',
                    object_id=s_id,
                    description=f"Updated student record {s_id} via Excel sheet import",
                    ip_address=ip
                ))
            if logs_to_create:
                ActivityLog.objects.bulk_create(logs_to_create)
                
            # Create a shallow copy with sliced lists for the template report
            template_result = result.copy()
            template_result['inserted_list'] = result['inserted_list'][:50]
            template_result['updated_list'] = result['updated_list'][:50]
            template_result['errors'] = result['errors'][:50]
        else:
            messages.error(request, f"Import failed: {result['error']}")
            template_result = result
            
        # Return the partial view instead of redirecting
        return render(request, 'students/partials/import_report.html', {'result': template_result, 'update_existing': update_existing})
    return render(request, 'students/import.html', {'active_tab': 'excel'})

@require_access('students', 'bulk_import')
def bulk_photo_upload(request):
    """Handles mass photo updates from a ZIP archive."""
    if request.method == "POST" and request.FILES.get('zip_file'):
        zip_file = request.FILES['zip_file']
        if not zip_file.name.lower().endswith('.zip'):
            messages.error(request, "Please upload a valid ZIP file.")
            return render(request, 'students/import.html', {'active_tab': 'photo'})

        try:
            with zipfile.ZipFile(zip_file, 'r') as z:
                success_count = 0
                error_count = 0
                not_found = []
                
                # Define and create storage directory
                photo_dir_rel = os.path.join('students', 'photos')
                photo_dir_full = os.path.join(settings.MEDIA_ROOT, photo_dir_rel)
                if not os.path.exists(photo_dir_full):
                    os.makedirs(photo_dir_full)

                for filename in z.namelist():
                    # Skip directories and hidden files
                    if filename.endswith('/') or filename.startswith('__MACOSX'): continue
                    
                    # Process file
                    basename = os.path.basename(filename)
                    if not basename: continue
                    
                    name_parts = os.path.splitext(basename)
                    student_id = name_parts[0].strip()
                    ext = name_parts[1].lower()
                    
                    if ext not in ['.jpg', '.jpeg', '.png']:
                        continue

                    try:
                        # Try to find student
                        student = Student.objects.get(student_id=student_id)
                        
                        # Save content
                        new_filename = f"{student_id}{ext}"
                        target_path_rel = os.path.join(photo_dir_rel, new_filename)
                        target_path_full = os.path.join(settings.MEDIA_ROOT, target_path_rel)
                        
                        with open(target_path_full, 'wb') as f:
                            f.write(z.read(filename))
                        
                        # Update record
                        student.photo_path = target_path_rel.replace('\\', '/')
                        student.save()
                        success_count += 1
                    except Student.DoesNotExist:
                        not_found.append(student_id)
                        error_count += 1
                
                if success_count > 0:
                    messages.success(request, f"Successfully synchronized {success_count} photos.")
                
                if error_count > 0:
                    missing_str = ", ".join(not_found[:5])
                    if len(not_found) > 5: missing_str += "..."
                    messages.warning(request, f"{error_count} photos skipped (IDs not in system: {missing_str})")
                
                if success_count == 0 and error_count == 0:
                    messages.info(request, "The ZIP file did not contain any valid image files named by Student ID.")
                    
                return redirect('student_list')
                
        except zipfile.BadZipFile:
            messages.error(request, "The uploaded file is not a valid ZIP archive.")
        except Exception as e:
            messages.error(request, f"System error during extraction: {str(e)}")
            
    return render(request, 'students/import.html', {'active_tab': 'photo'})

@require_access('students', 'academic_audit')
def academic_audit_center(request):
    """
    Centralized hub for managing student board verification statuses.
    Facilitates mass audit and tracking of academic discrepancies.
    """
    from .models import Student
    from django.db.models import Count, Q
    
    # Verification Statistics
    stats = Student.objects.aggregate(
        total=Count('student_id'),
        ssc_count=Count('student_id', filter=Q(ssc_verified=True)),
        hsc_count=Count('student_id', filter=Q(hsc_verified=True)),
        both_count=Count('student_id', filter=Q(ssc_verified=True, hsc_verified=True)),
        pending_count=Count('student_id', filter=Q(ssc_verified=False) | Q(hsc_verified=False))
    )
    
    # Get students for the Verification Queue
    # Prioritize: 1. Those with logged errors, 2. Unverified students
    queue_queryset = Student.objects.filter(
        Q(ssc_verified=False) | Q(hsc_verified=False) | Q(academic_verification_logs__has_key='error')
    ).order_by('-last_updated')[:25]
    
    context = {
        'stats': stats,
        'recent_discrepancies': queue_queryset,
    }
    return render(request, 'students/reports/academic_audit_center.html', context)

# NOTE: api_get_board_captcha is defined below (consolidated single definition)

# NOTE: api_verify_board_result is defined below (consolidated single definition)

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
            
            # Performance Guard: Even if 'show_all' is checked, limit visual table to 100 rows
            # Rendering 1000+ rows in a modal table causes extreme browser lag.
            # Total counts will still reflect the entire file.
            preview_limit = 100 if show_all else 10
            preview_df = df.head(preview_limit).copy()
            
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
    
    from core.models import SystemSettings
    sys_settings = SystemSettings.objects.get_or_create(id=1)[0]
    id_mode = sys_settings.id_mode  # 'auto' | 'semi_auto' | 'manual'
    
    if request.method == "POST":
        data = request.POST
        new_program = data.get('new_program')
        
        # Prevent same-program change
        from .utils import get_canonical_program_name
        if get_canonical_program_name(student.program) == get_canonical_program_name(new_program):
            messages.error(request, f"Illogical Migration: Student is already in program '{student.program}'.")
            return redirect('change_program', student_id=student_id)
            
        custom_id = None
        if id_mode == 'semi_auto':
            serial_input = str(data.get('student_id_serial', '')).strip()
            if not serial_input or not serial_input.isdigit() or len(serial_input) != 3:
                messages.error(request, "Error: In semi-auto mode, a 3-digit numeric serial must be provided.")
                return redirect('change_program', student_id=student_id)
            
            from .utils import generate_ugc_prefix
            try:
                prefix = generate_ugc_prefix(
                    admission_year=data.get('new_year'),
                    semester_name=data.get('new_semester'),
                    hall_name=data.get('hall_name'),
                    program_name=new_program,
                    cluster_name=data.get('new_cluster'),
                    program_level=student.program_type,
                )
                custom_id = prefix + serial_input
            except Exception as e:
                messages.error(request, f"Error generating prefix: {str(e)}")
                return redirect('change_program', student_id=student_id)
                
            if Student.objects.filter(student_id=custom_id).exists():
                messages.error(request, f"Error: Student ID {custom_id} is already in use. Please select a different serial.")
                return redirect('change_program', student_id=student_id)
                
        elif id_mode == 'manual':
            custom_id = str(data.get('manual_student_id', '')).strip()
            if not custom_id or len(custom_id) != 16 or not custom_id.isdigit():
                messages.error(request, "Error: In manual mode, a valid 16-digit numeric student ID must be provided.")
                return redirect('change_program', student_id=student_id)
            if not custom_id.startswith('080'):
                messages.error(request, "Error: ID must start with university code '080'.")
                return redirect('change_program', student_id=student_id)
            if Student.objects.filter(student_id=custom_id).exists():
                messages.error(request, f"Error: Student ID {custom_id} is already in use.")
                return redirect('change_program', student_id=student_id)

        result = execute_program_change_web(
            student=student,
            new_program=new_program,
            new_cluster=data.get('new_cluster'),
            new_year=data.get('new_year'),
            new_semester=data.get('new_semester'),
            hall_name=data.get('hall_name'),
            notes=data.get('notes', 'Web migration'),
            custom_id=custom_id
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
    halls = Hall.objects.all().order_by('full_name', 'short_name')
    
    program_mapping = {
        (p.short_name if p.short_name else p.name): {
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
        'program_mapping_json': json.dumps(program_mapping),
        'sys_settings': sys_settings,
    })

@require_access('students', 'view_directory')
def student_profile(request, student_id):
    """Full detail view for a student profile with unified timeline."""
    from core.models import ActivityLog
    from django.utils.dateparse import parse_datetime
    
    student, canonical_id, was_legacy = _resolve_student(student_id)
    if was_legacy:
        return redirect('student_profile', student_id=canonical_id)
    timeline = []

    # Gather all linked IDs (including old rectified IDs) for full history lookup
    id_list = [student_id]
    if student.old_student_id:
        id_list.append(student.old_student_id)

    program_history = ProgramChangeHistory.objects.filter(
        Q(old_student_id__in=id_list) | Q(new_student_id__in=id_list)
    ).order_by('change_date')
    
    for entry in program_history:
        # Track previous IDs for full log coverage
        if entry.old_student_id not in id_list: id_list.append(entry.old_student_id)
        if entry.new_student_id not in id_list: id_list.append(entry.new_student_id)

    # 1. Admission Event (dynamically determined who, when, and how)
    create_log = ActivityLog.objects.filter(
        module='students',
        object_id__in=id_list,
        action_type='CREATE'
    ).select_related('user').first()

    creator_user = 'System / Importer'
    creation_timestamp = student.created_at
    creation_title = 'Initial Admission'
    creation_desc = f'Student record created in the system for {student.program}.'
    
    if create_log:
        creation_timestamp = create_log.timestamp
        if create_log.user:
            creator_user = create_log.user.username
        else:
            creator_user = 'System'
            
        desc_lower = create_log.description.lower()
        if 'excel' in desc_lower or 'import' in desc_lower:
            creation_desc = f"Student record imported into the system via Excel spreadsheet for {student.program}."
            creation_title = "Record Imported (Excel)"
        else:
            creation_desc = f"Student record created via New Admission for {student.program}."
            creation_title = "Manual Admission"
    else:
        # Fallback for legacy records or older imports
        creation_desc = f"Student record registered in the system for {student.program} (Legacy/Import)."
        creation_title = "Initial Admission"

    timeline.append({
        'timestamp': creation_timestamp,
        'icon': 'fas fa-user-plus',
        'badge_class': 'bg-success',
        'title': creation_title,
        'description': creation_desc,
        'user': creator_user
    })

    # 2. Program/ID Change Events
    for entry in program_history:
        if entry.old_student_id != entry.new_student_id:
            timeline.append({
                'timestamp': entry.change_date,
                'icon': 'fas fa-fingerprint',
                'badge_class': 'bg-purple',
                'title': 'Student ID Rectified',
                'description': f'ID changed from {entry.old_student_id} to {entry.new_student_id}.',
                'user': 'Registrar'
            })
        if entry.old_program != entry.new_program:
            timeline.append({
                'timestamp': entry.change_date,
                'icon': 'fas fa-exchange-alt',
                'badge_class': 'bg-warning',
                'title': 'Program Migration',
                'description': f'Migrated from {entry.old_program} to {entry.new_program}.',
                'user': 'Academic Office'
            })

    # 3. Admission Status Changes
    status_history = AdmissionStatusHistory.objects.filter(student=student).order_by('change_date')
    for entry in status_history:
        timeline.append({
            'timestamp': entry.change_date,
            'icon': 'fas fa-user-tag',
            'badge_class': 'bg-danger' if entry.new_status != 'Active' else 'bg-primary',
            'title': f'Status Change: {entry.new_status}',
            'description': f'Reason: {entry.get_reason_category_display()}. {entry.custom_notes or ""}',
            'user': entry.performed_by.username if entry.performed_by else 'Admin'
        })

    # 4. Board Verification Events
    if student.academic_verification_logs:
        for exam, data in student.academic_verification_logs.items():
            if isinstance(data, dict) and 'timestamp' in data:
                ts = parse_datetime(data['timestamp']) or student.last_updated
                timeline.append({
                    'timestamp': ts,
                    'icon': 'fas fa-check-double',
                    'badge_class': 'bg-info',
                    'title': f'{exam} Board Verified',
                    'description': f"Successfully cross-checked with Board. Board GPA: {data.get('board_gpa', 'N/A')}.",
                    'user': data.get('verified_by', 'System')
                })

    # 5. Activity Logs (General Updates)
    logs = ActivityLog.objects.filter(module='students', object_id__in=id_list).order_by('timestamp')
    for log in logs:
        # Skip migration/status/creation logs if they contain redundant text already covered by specialized histories
        desc = log.description.lower()
        if log.action_type == 'CREATE' or 'migrated' in desc or 'status change' in desc or 'rectified' in desc:
            continue
            
        icon = 'fas fa-edit'
        badge = 'bg-secondary'
        if 'mobile' in desc:
            icon = 'fas fa-phone-alt'
            badge = 'bg-info'
        elif 'photo' in desc:
            icon = 'fas fa-camera'
            badge = 'bg-teal'
            
        timeline.append({
            'timestamp': log.timestamp,
            'icon': icon,
            'badge_class': badge,
            'title': 'Profile Updated',
            'description': log.description,
            'user': log.user.username if log.user else 'System'
        })

    # Final Sort: Newest First
    timeline.sort(key=lambda x: x['timestamp'], reverse=True)

    # Master Data for UGC Migration
    from master_data.models import Program, Semester, Hall
    programs = Program.objects.all().order_by('name')
    semesters = Semester.objects.all().order_by('name')
    halls = Hall.objects.all().order_by('full_name', 'short_name')
    years_range = list(range(2015, timezone.localtime(timezone.now()).year + 2))

    return render(request, 'students/profile.html', {
        'student': student,
        'program_history': program_history,
        'timeline': timeline,
        'migration_programs': programs,
        'migration_semesters': semesters,
        'migration_halls': halls,
        'migration_years': years_range,
    })

@require_access('reports', 'view_analytics')
def academic_intake_report(request):
    """Generates the Academic Intake Quality Report."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year_filter = request.GET.get('year')
    batch_filter = request.GET.get('batch')
    program_filter = request.GET.get('program')
    
    # Default to latest year only if no other filters are applied
    if year_filter == '': year_filter = None
    if batch_filter == '': batch_filter = None
    if program_filter == '': program_filter = None

    if year_filter is None and batch_filter is None and program_filter is None:
        year_filter = latest_year
    
    students = Student.objects.exclude(program__isnull=True).exclude(program='')
    
    if batch_filter:
        students = students.filter(batch=batch_filter)
    elif year_filter:
        students = students.filter(admission_year=year_filter)
        
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
            'program': s.program, 'batch': s.batch, 'current_batch': s.current_batch,
            'semester_name': s.semester_name, 'current_semester': s.current_semester,
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
def export_students_smart_campus(request):
    """Generates the SMART CAMPUS Excel export without current_batch/semester, and highlighting cancelled rows."""
    from openpyxl.styles import PatternFill
    import re

    params = _get_directory_params(request)
    base_queryset = _get_directory_base_queryset(request.user)
    # Get filtered queryset, allowing cancelled students to be included
    students = _apply_directory_sorting(_apply_directory_filters(base_queryset, params, include_cancelled=True), params)

    data = []
    for i, s in enumerate(students, start=1):
        # Format semester name (e.g., "Summer 2026")
        sem_name = (s.semester_name or "").strip()
        if sem_name and not re.search(r'\b\d{4}\b', sem_name) and s.admission_year:
            formatted_semester = f"{sem_name} {s.admission_year}"
        else:
            formatted_semester = sem_name

        data.append({
            'SL': i, 'student_id': s.student_id, 'student_name': s.student_name,
            'program': s.program, 'batch': s.batch,
            'semester_name': formatted_semester,
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
        workbook = writer.book
        worksheet = writer.sheets['Students']
        
        # Soft pastel yellow color (hex FFF2CC) for cancelled student rows
        yellow_fill = PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')
        
        # openpyxl uses 1-based indexing. Row 1 is header, so data starts at row 2
        for row_idx, s in enumerate(students, start=2):
            if s.admission_status == 'Cancelled':
                for col_idx in range(1, len(df.columns) + 1):
                    worksheet.cell(row=row_idx, column=col_idx).fill = yellow_fill

    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="smart_campus_export_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    return response


@require_access('students', 'export_excel')
def export_students_smart_campus_dept(request):
    """Generates a ZIP file containing separate Excel exports by department (program) in SMART CAMPUS format."""
    from openpyxl.styles import PatternFill
    from collections import defaultdict
    import zipfile
    import re

    params = _get_directory_params(request)
    base_queryset = _get_directory_base_queryset(request.user)
    # Get filtered queryset, allowing cancelled students to be included
    students = _apply_directory_sorting(_apply_directory_filters(base_queryset, params, include_cancelled=True), params)

    # Group students by program
    grouped_students = defaultdict(list)
    for s in students:
        prog = (s.program or "Unspecified").strip()
        grouped_students[prog].append(s)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for program_name, dept_students in grouped_students.items():
            data = []
            for i, s in enumerate(dept_students, start=1):
                # Format semester name (e.g., "Summer 2026")
                sem_name = (s.semester_name or "").strip()
                if sem_name and not re.search(r'\b\d{4}\b', sem_name) and s.admission_year:
                    formatted_semester = f"{sem_name} {s.admission_year}"
                else:
                    formatted_semester = sem_name

                data.append({
                    'SL': i, 'student_id': s.student_id, 'student_name': s.student_name,
                    'program': s.program, 'batch': s.batch,
                    'semester_name': formatted_semester,
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
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Students')
                workbook = writer.book
                worksheet = writer.sheets['Students']
                
                # Soft pastel yellow color (hex FFF2CC) for cancelled student rows
                yellow_fill = PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')
                
                for row_idx, s in enumerate(dept_students, start=2):
                    if s.admission_status == 'Cancelled':
                        for col_idx in range(1, len(df.columns) + 1):
                            worksheet.cell(row=row_idx, column=col_idx).fill = yellow_fill

            # Clean program name for filename (remove invalid filesystem chars)
            clean_program_name = re.sub(r'[\\/*?:"<>|]', "", program_name).replace(" ", "_")
            filename = f"{clean_program_name}_smart_campus_export.xlsx"
            zip_file.writestr(filename, excel_buffer.getvalue())

    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="dept_smart_campus_exports_{timezone.now().strftime("%Y%m%d_%H%M")}.zip"'
    return response


@require_access('students', 'export_excel')
def export_students_smart_campus_dept_modal(request):
    """Returns the HTML for the department-wise export modal enlisting programs and student counts."""
    from django.urls import reverse

    params = _get_directory_params(request)
    base_queryset = _get_directory_base_queryset(request.user)
    # Get filtered queryset, allowing cancelled students to be included
    students = _apply_directory_sorting(_apply_directory_filters(base_queryset, params, include_cancelled=True), params)

    # Group students by program and count
    from collections import defaultdict
    grouped_counts = defaultdict(int)
    for s in students:
        prog = (s.program or "Unspecified").strip()
        grouped_counts[prog] += 1

    # Sort departments alphabetically
    sorted_depts = sorted(grouped_counts.items())

    # Build the list of departments with counts and download URLs
    departments_data = []
    base_get = request.GET.copy()
    for name, count in sorted_depts:
        get_params = base_get.copy()
        get_params['program'] = name
        download_url = reverse('export_students_smart_campus') + '?' + get_params.urlencode()
        departments_data.append({
            'name': name,
            'count': count,
            'download_url': download_url
        })

    # ZIP download URL keeps all current filters
    zip_download_url = reverse('export_students_smart_campus_dept')
    if request.GET:
        zip_download_url += '?' + request.GET.urlencode()

    return render(request, 'students/partials/dept_export_modal.html', {
        'departments': departments_data,
        'zip_download_url': zip_download_url
    })


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
    student, canonical_id, was_legacy = _resolve_student(student_id)
    if was_legacy:
        return redirect('download_master_sheet', student_id=canonical_id)
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
        'Institutional': ['program', 'cluster', 'batch', 'current_batch', 'semester_name', 'current_semester', 'hall_attached', 'reference', 'remarks', 'admission_status', 'admission_date']
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

@require_access('students', 'export_migrations')
def export_migrations_dynamic(request):
    """Excel export for program migration history based on current filters."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    query = request.GET.get('search')
    old_program = request.GET.get('old_program')
    new_program = request.GET.get('new_program')

    queryset = ProgramChangeHistory.objects.all()
    if start_date: queryset = queryset.filter(change_date__gte=start_date)
    if end_date: queryset = queryset.filter(change_date__lte=end_date)
    if query:
        queryset = queryset.filter(
            Q(old_student_id__icontains=query) | 
            Q(new_student_id__icontains=query)
        )
    if old_program:
        queryset = queryset.filter(old_program=old_program)
    if new_program:
        queryset = queryset.filter(new_program=new_program)

    data = []
    for item in queryset:
        data.append({
            'Change Date': item.change_date.strftime('%Y-%m-%d %H:%M') if item.change_date else '',
            'Old Program': item.old_program,
            'New Program': item.new_program,
            'Old Student ID': item.old_student_id,
            'New Student ID': item.new_student_id,
            'Notes': item.notes or '',
        })
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='MigrationHistory')
    
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Migrations_Export_{timezone.now().strftime("%Y%m%d")}.xlsx"'
    return response

@require_access('students', 'export_cancellations')
def export_cancellations_dynamic(request):
    """Excel export for admission cancellation history based on current filters."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    query = request.GET.get('search')
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    reason = request.GET.get('reason')

    queryset = AdmissionStatusHistory.objects.filter(new_status='Cancelled').select_related('student', 'performed_by')
    if start_date: queryset = queryset.filter(change_date__gte=start_date)
    if end_date: queryset = queryset.filter(change_date__lte=end_date)
    if query:
        queryset = queryset.filter(
            Q(student__student_id__icontains=query) |
            Q(student__student_name__icontains=query)
        )
    if program:
        queryset = queryset.filter(student__program=program)
    if batch:
        queryset = queryset.filter(student__batch=batch)
    if reason:
        queryset = queryset.filter(reason_category=reason)

    data = []
    for item in queryset:
        data.append({
            'Student ID': item.student.student_id,
            'Student Name': item.student.student_name,
            'Program': item.student.program,
            'Batch': item.student.batch or '',
            'Reason Category': item.reason_category,
            'Administrative Notes': item.custom_notes or '',
            'Cancellation Date': item.change_date.strftime('%Y-%m-%d %H:%M'),
            'Cancelled By': item.performed_by.username if item.performed_by else 'System'
        })
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Cancellations')
    
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Cancellations_Export_{timezone.now().strftime("%Y%m%d")}.xlsx"'
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
    
    year = request.GET.get('year')
    batch = request.GET.get('batch')
    program = request.GET.get('program')

    # Normalize empty strings and apply default logic
    if year == '': year = None
    if batch == '': batch = None
    if program == '': program = None

    if year is None and batch is None and program is None:
        year = latest_year
    
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
def api_institutional_students(request):
    """Returns a list of students for institutional drill-down modal."""
    school = request.GET.get('school')
    college = request.GET.get('college')
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
    if program:
        queryset = queryset.filter(program=program)
        
    if school:
        queryset = queryset.filter(ssc_school=school)
    elif college:
        queryset = queryset.filter(hsc_college=college)
        
    queryset = queryset.order_by('student_id')
    count = queryset.count()
    
    return render(request, 'students/partials/institution_student_list.html', {
        'students': queryset[:200],
        'count': count,
        'school': school,
        'college': college,
        'year': year,
        'program': program,
        'batch': batch,
    })

@require_access('reports', 'view_analytics')
def print_institutional_students(request):
    """Renders a printer-friendly HTML list of students for a specific institution."""
    school = request.GET.get('school')
    college = request.GET.get('college')
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    queryset = Student.objects.all()
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
    if program:
        queryset = queryset.filter(program=program)
        
    if school:
        queryset = queryset.filter(ssc_school=school)
    elif college:
        queryset = queryset.filter(hsc_college=college)
        
    queryset = queryset.order_by('student_id')
    
    return render(request, 'students/reports/print_institution_students.html', {
        'students': queryset,
        'school': school,
        'college': college,
        'year': year,
        'program': program,
        'batch': batch,
        'print_time': timezone.now(),
    })

@require_access('reports', 'view_analytics')
def geographic_report(request):
    """Geographic outreach and student distribution dashboard."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year')
    batch = request.GET.get('batch')
    program = request.GET.get('program')

    if year == '': year = None
    if batch == '': batch = None
    if program == '': program = None

    if year is None and batch is None and program is None:
        year = latest_year
    
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
def api_geographic_students(request):
    """Returns a list of students for geographic drill-down and correction."""
    division = request.GET.get('division')
    district = request.GET.get('district')
    upazila = request.GET.get('upazila')
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')
    
    queryset = Student.objects.all()
    
    # Apply standard report filters
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
    if program:
        queryset = queryset.filter(program=program)
        
    # Division drill-down
    if division is not None:
        if division == 'Unspecified' or division == '' or division.lower() == 'unknown':
            queryset = queryset.filter(Q(present_division__isnull=True) | Q(present_division=''))
            division = 'Unspecified'
        else:
            queryset = queryset.filter(present_division=division)
            
    # District drill-down
    if district is not None:
        if district == 'Unspecified' or district == '' or district.lower() == 'unknown':
            queryset = queryset.filter(Q(present_district__isnull=True) | Q(present_district=''))
            district = 'Unspecified'
        else:
            queryset = queryset.filter(present_district=district)

    # Upazila drill-down
    if upazila is not None:
        if upazila == 'Unspecified' or upazila == '' or upazila.lower() == 'unknown':
            queryset = queryset.filter(Q(present_upazila__isnull=True) | Q(present_upazila=''))
            upazila = 'Unspecified'
        else:
            queryset = queryset.filter(present_upazila=upazila)
            
    # Order by ID
    queryset = queryset.order_by('student_id')
    count = queryset.count()
    
    return render(request, 'students/partials/geo_student_list.html', {
        'students': queryset[:200],  # limit to 200 for performance
        'count': count,
        'division': division,
        'district': district,
        'upazila': upazila,
    })

@require_access('reports', 'view_analytics')
def socio_economic_report(request):
    """Research-grade demographics: Occupation and Financial aid splits."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year')
    batch = request.GET.get('batch')
    program = request.GET.get('program')

    if year == '': year = None
    if batch == '': batch = None
    if program == '': program = None

    if year is None and batch is None and program is None:
        year = latest_year
    
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
    
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')

    if year == '': year = None
    if batch == '': batch = None
    if program == '': program = None

    if year is None and batch is None and program is None:
        year = latest_year
    
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

@login_required
@require_access('reports', 'view_analytics')
def reference_report(request):
    """Reference efficiency and recruitment source analysis."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')

    if year == '': year = None
    if batch == '': batch = None
    if program == '': program = None

    if year is None and batch is None and program is None:
        year = latest_year
    
    data = get_reference_intelligence(year=year, program=program, batch=batch)
    programs = Student.objects.values_list('program', flat=True).distinct().exclude(program='').order_by('program')
    batches = Student.objects.values_list('batch', flat=True).distinct().exclude(batch='').order_by('batch')
    
    from django.db.models import Count, Q
    from .models import ReferenceNode
    
    # Fetch unique legacy names from Student.reference_legacy and unverified ReferenceNodes
    legacy_texts = list(Student.objects.exclude(
        reference_legacy__isnull=True
    ).exclude(
        reference_legacy=''
    ).values_list('reference_legacy', flat=True).distinct())
    
    unverified_names = list(ReferenceNode.objects.filter(is_verified=False).values_list('name_en', flat=True).distinct())
    
    all_legacy_names = sorted(list(set(legacy_texts + unverified_names)))
    
    legacy_refs = []
    for name in all_legacy_names:
        name_clean = name.strip()
        if not name_clean:
            continue
            
        # Count students having this legacy text or currently linked to a node of this name
        total_students = Student.objects.filter(
            Q(reference_legacy=name) | Q(reference__name_en=name)
        ).count()
        
        if total_students == 0:
            continue
            
        # Count how many of these students are linked to a VERIFIED node
        aligned_count = Student.objects.filter(
            Q(reference_legacy=name) | Q(reference__name_en=name)
        ).filter(
            reference__isnull=False,
            reference__is_verified=True
        ).count()
        
        unaligned_count = total_students - aligned_count
        
        legacy_refs.append({
            'reference_legacy': name,
            'total_students': total_students,
            'unaligned_count': unaligned_count
        })
        
    # Sort by unaligned count first, then total students descending
    legacy_refs.sort(key=lambda x: (x['unaligned_count'], x['total_students']), reverse=True)
    
    all_nodes = ReferenceNode.objects.filter(is_verified=True).order_by('name_en')
    
    return render(request, 'students/reports/reference_intelligence.html', {
        'data': data,
        'data_json': json.dumps(data),
        'years': list(years),
        'programs': list(programs),
        'batches': list(batches),
        'selected_year': str(year) if year else None,
        'selected_program': program,
        'selected_batch': batch,
        'legacy_refs': list(legacy_refs),
        'all_references_list': all_nodes
    })

@require_access('reports', 'view_analytics')
def financial_intelligence_report(request):
    """Revenue forecasting and financial impact analysis."""
    years = Student.objects.values_list('admission_year', flat=True).distinct().exclude(admission_year=None).order_by('-admission_year')
    latest_year = years[0] if years.exists() else None
    
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')

    if year == '': year = None
    if batch == '': batch = None
    if program == '': program = None

    if year is None and batch is None and program is None:
        year = latest_year
    
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
    
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')

    if year == '': year = None
    if batch == '': batch = None
    if program == '': program = None

    if year is None and batch is None and program is None:
        year = latest_year
    
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
    
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')

    if year == '': year = None
    if batch == '': batch = None
    if program == '': program = None

    if year is None and batch is None and program is None:
        year = latest_year
    
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
    
    year = request.GET.get('year')
    program = request.GET.get('program')
    batch = request.GET.get('batch')

    if year == '': year = None
    if batch == '': batch = None
    if program == '': program = None

    if year is None and batch is None and program is None:
        year = latest_year
    
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

@require_access('reports', 'view_analytics')
def intake_performance_report(request):
    """Deep-dive performance report across historical intakes."""
    from .reports import get_intake_performance_analysis, get_admission_trends
    analysis_data = get_intake_performance_analysis()
    trend_data = get_admission_trends()
    
    return render(request, 'students/reports/intake_performance.html', {
        'analysis_data': analysis_data,
        'analysis_json': json.dumps(analysis_data),
        'trend_data': trend_data,
        'trend_json': json.dumps(trend_data)
    })

@login_required
def api_global_search(request):
    """Real-time global search engine for the header."""
    from django.http import HttpResponse
    # Accept both 'search' and 'q'
    query = request.GET.get('search', request.GET.get('q', '')).strip()
    if not query or len(query) < 2:
        return HttpResponse("") # Return empty if query is too short

    from django.db.models import Q
    students = Student.objects.filter(
        Q(student_id__icontains=query) |
        Q(old_student_id__icontains=query) |
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
        {'name': 'student_id', 'label': 'Student ID'},
        {'name': 'old_student_id', 'label': 'Old Student ID'},
        {'name': 'student_name', 'label': 'Student Name'},
        {'name': 'father_name', 'label': "Father's Name"},
        {'name': 'mother_name', 'label': "Mother's Name"},
        {'name': 'student_mobile', 'label': 'Mobile Number'},
        {'name': 'student_email', 'label': 'Email Address'},
        {'name': 'dob', 'label': 'Date of Birth'},
        {'name': 'national_id', 'label': 'NID / Birth Cert.'},
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
            {'name': 'batch', 'label': 'Admission Batch'},
            {'name': 'current_batch', 'label': 'Current Academic Batch'},
            {'name': 'current_semester', 'label': 'Current Semester'},
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
    
    if field_name in ['batch', 'current_batch']:
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
            'current_batch',
            'current_semester',
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
            
        if field_name in ['batch', 'current_batch'] and new_value:
            from master_data.models import Batch
            import re
            try:
                batch_obj = Batch.objects.get(id=new_value)
                new_value = batch_obj.name
                
                if field_name == 'batch':
                    # Calculate batch_number for sorting
                    nums = re.findall(r'\d+', new_value)
                    batch_number = int(nums[0]) if nums else 0
                    
                    try:
                        with transaction.atomic():
                            updated_count = Student.objects.filter(student_id__in=student_ids).update(
                                batch=new_value, 
                                batch_number=batch_number
                            )
                        return HttpResponse(f"<script>Swal.fire('Success', '{updated_count} students updated successfully!', 'success').then(() => location.reload());</script>")
                    except Exception as e:
                        return HttpResponse(f"<div class='alert alert-danger'>Update failed: {escape(str(e))}</div>")
                else:
                    # current_batch
                    try:
                        with transaction.atomic():
                            updated_count = Student.objects.filter(student_id__in=student_ids).update(
                                current_batch=new_value
                            )
                        return HttpResponse(f"<script>Swal.fire('Success', '{updated_count} students updated successfully!', 'success').then(() => location.reload());</script>")
                    except Exception as e:
                        return HttpResponse(f"<div class='alert alert-danger'>Update failed: {escape(str(e))}</div>")
            except Exception:
                return HttpResponse("<div class='alert alert-danger'>Invalid Batch Selected.</div>")
                
        try:
            with transaction.atomic():
                updated_count = Student.objects.filter(student_id__in=student_ids).update(**{field_name: new_value})
            return HttpResponse(f"<script>Swal.fire('Success', '{updated_count} students updated successfully!', 'success').then(() => location.reload());</script>")
        except Exception as e:
            return HttpResponse(f"<div class='alert alert-danger'>Update failed: {escape(str(e))}</div>")
    return HttpResponse("Invalid Request.")

@login_required
def api_get_board_captcha(request):
    """Fetches captcha from education board and saves session (BUG-02/03 fixed)."""
    engine = BoardVerificationEngine()
    
    # Load previously saved cookies if available to speed up captcha loading (fast path)
    saved_cookies = request.session.get('board_session_cookies')
    if saved_cookies:
        import requests.utils
        engine.session.cookies.update(saved_cookies)
        
    captcha_b64 = engine.get_captcha()

    if captcha_b64:
        import requests.utils
        # BUG-02 FIX: Use 'board_session_cookies' — the key api_verify_board_result reads
        request.session['board_session_cookies'] = requests.utils.dict_from_cookiejar(engine.session.cookies)
        # BUG-03 FIX: Key is 'captcha_image' matching what profile.html and edit.html expect
        return JsonResponse({'success': True, 'captcha_image': f"data:image/jpeg;base64,{captcha_b64}"})
    return JsonResponse({'success': False, 'error': 'Failed to load captcha. Please try again.'})


@login_required
def api_verify_board_result(request):
    """Consolidated board verification endpoint — handles both profile & edit page flows.

    Mode 1 (profile.html): POST includes student_id + exam_type.
                           Loads student data from DB, saves verified flag immediately.
    Mode 2 (edit.html):    POST includes exam + board + year + roll + reg.
                           No student lookup; verified flag saved later on form submit.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})

    captcha = request.POST.get('captcha', '')
    student_id = request.POST.get('student_id')
    exam_type = request.POST.get('exam_type')

    exam = request.POST.get('exam', '')
    board = request.POST.get('board', '')
    year = request.POST.get('year', '')
    roll = request.POST.get('roll', '')
    reg = request.POST.get('reg', '')

    student = None
    current_gpa = None

    # Mode 1: profile.html passes student_id + exam_type
    if student_id and exam_type:
        try:
            from .models import Student
            student = Student.objects.get(student_id=student_id)
            exam = exam_type.upper()
            if exam == 'SSC':
                board, year, roll, reg = student.ssc_board, student.ssc_year, student.ssc_roll, student.ssc_reg
                current_gpa = str(student.ssc_gpa)
            elif exam == 'HSC':
                board, year, roll, reg = student.hsc_board, student.hsc_year, student.hsc_roll, student.hsc_reg
                current_gpa = str(student.hsc_gpa)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    engine = BoardVerificationEngine()

    # BUG-02 FIX: Read from the correct session key
    saved_cookies = request.session.get('board_session_cookies')
    if not saved_cookies:
        return JsonResponse({'success': False, 'error': 'Session expired. Please refresh the captcha.'})

    import requests.utils
    engine.session.cookies.update(saved_cookies)

    result = engine.fetch_result(exam, board, year, roll, reg, captcha)

    # Mode 1 only: save verified status to DB immediately
    if student and result.get('success'):
        board_gpa = result.get('gpa', '0.00')
        try:
            is_match = float(current_gpa) == float(board_gpa)
        except (ValueError, TypeError):
            is_match = str(current_gpa) == str(board_gpa)

        result['is_match'] = is_match
        result['board_gpa'] = board_gpa
        result['current_gpa'] = current_gpa

        # Sync official board details if current fields are empty, None, or placeholders
        b_name = result.get('name', '').strip()
        b_fname = result.get('father_name', '').strip()
        b_mname = result.get('mother_name', '').strip()
        b_gender = result.get('gender', '').strip()
        b_dob = result.get('dob', '').strip()

        def is_empty(val):
            s_val = str(val).strip()
            return not val or s_val == '' or s_val.lower() == 'none' or s_val in ('-', '.', 'n/a')

        if b_name and is_empty(student.student_name):
            student.student_name = b_name
        if b_fname and is_empty(student.father_name):
            student.father_name = b_fname
        if b_mname and is_empty(student.mother_name):
            student.mother_name = b_mname
        if b_gender and is_empty(student.gender):
            student.gender = b_gender
        if b_dob and is_empty(student.dob):
            from datetime import datetime
            for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y'):
                try:
                    student.dob = datetime.strptime(b_dob, fmt).date()
                    break
                except ValueError:
                    continue

        # Sync official academic details (GPA, school/college, and subject results)
        grades = result.get('grades', {})
        b_inst = result.get('inst_name', '').strip()
        try:
            b_gpa_float = float(board_gpa)
        except (ValueError, TypeError):
            b_gpa_float = None

        if exam == 'SSC':
            if b_gpa_float is not None:
                student.ssc_gpa = b_gpa_float
            if b_inst and is_empty(student.ssc_school):
                student.ssc_school = b_inst
            if 'physics' in grades:
                student.ssc_physics = grades['physics']
            if 'chemistry' in grades:
                student.ssc_chemistry = grades['chemistry']
            if 'math' in grades:
                student.ssc_math = grades['math']
        elif exam == 'HSC':
            if b_gpa_float is not None:
                student.hsc_gpa = b_gpa_float
            if b_inst and is_empty(student.hsc_college):
                student.hsc_college = b_inst
            if 'physics' in grades:
                student.hsc_physics = grades['physics']
            if 'chemistry' in grades:
                student.hsc_chemistry = grades['chemistry']
            if 'math' in grades:
                student.hsc_math = grades['math']

        # BUG-04 FIX: Mark verified on any successful board fetch, not just on GPA match
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'verified_by': request.user.username,
            'exam': exam,
            'board_gpa': board_gpa,
            'stored_gpa': current_gpa,
            'is_match': is_match,
        }
        try:
            logs = getattr(student, 'academic_verification_logs', None) or {}
            logs[exam] = log_entry
            student.academic_verification_logs = logs
        except AttributeError:
            pass

        if exam == 'SSC':
            student.ssc_verified = True
        elif exam == 'HSC':
            student.hsc_verified = True
        student.save()

        result['details'] = {
            'name': result.get('name'),
            'father_name': result.get('father_name'),
            'mother_name': result.get('mother_name'),
            'dob': result.get('dob'),
            'gender': result.get('gender'),
            'gpa': result.get('gpa'),
            'grades': result.get('grades', {}),
            'all_subjects': result.get('all_subjects', {}),
        }

    return JsonResponse(result)



def _clean_mobile_number(mobile):
    """Helper to strip float suffixes, non-numeric chars, and add missing leading zeros."""
    if not mobile: return None, False
    
    # 1. Stringify and strip .0 (Excel float error)
    s = str(mobile).strip()
    if s.endswith('.0'):
        s = s[:-2]
    
    # 2. Remove all non-digits
    import re
    s = re.sub(r'\D', '', s)
    
    # 3. If 10 digits and starts with 1-9, prepend 0
    if len(s) == 10 and s[0] in '123456789':
        s = '0' + s
        
    # Valid Bangladesh mobile is 11 digits starting with 01
    is_valid = len(s) == 11 and s.startswith('01')
    return s, is_valid

@login_required
@require_access('students', 'mobile_repair')
def mobile_repair_tool(request):
    """Enhanced view to identify and categorize mobile number errors."""
    # Find all students with malformed numbers (excluding null/empty)
    malformed_students = Student.objects.exclude(student_mobile__isnull=True).exclude(student_mobile='').filter(
        ~Q(student_mobile__regex=r'^01\d{9}$')
    )

    audit_list = []
    for s in malformed_students:
        mobile = s.student_mobile
        suggested_fix, is_valid = _clean_mobile_number(mobile)
        
        # Determine Issue Category
        category = "OTHER"
        if str(mobile).endswith('.0'):
            category = "FLOAT"
        elif len(str(mobile)) == 10 and str(mobile)[0] in '123456789':
            category = "MISSING_ZERO"
            
        audit_list.append({
            'id': s.student_id,
            'name': s.student_name,
            'program': s.program,
            'batch': s.batch,
            'mobile': mobile,
            'suggested_fix': suggested_fix,
            'is_valid': is_valid,
            'category': category,
            'fixable': is_valid and suggested_fix != mobile
        })

    return render(request, 'students/tools/mobile_repair.html', {
        'audit_list': audit_list,
        'broken_count': len(audit_list)
    })

@login_required
@require_access('students', 'data_integrity')
def api_bulk_fix_mobile(request):
    """Enhanced API to apply robust mobile repairs with activity logging."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    student_ids = request.POST.getlist('student_ids[]')
    fix_all = request.POST.get('fix_all') == 'true'
    category_filter = request.POST.get('category')

    if fix_all or category_filter:
        # Find candidates for bulk fix
        query = Student.objects.exclude(student_mobile__isnull=True).exclude(student_mobile='')
        if category_filter == 'FLOAT':
            query = query.filter(student_mobile__endswith='.0')
        elif category_filter == 'MISSING_ZERO':
            query = query.filter(student_mobile__regex=r'^\d{10}$')
        else:
            # Fallback to general malformed
            query = query.filter(~Q(student_mobile__regex=r'^01\d{9}$'))
            
        student_ids = list(query.values_list('student_id', flat=True))

    updated_count = 0
    from core.utils import log_activity
    
    with transaction.atomic():
        for sid in student_ids:
            try:
                student = Student.objects.get(student_id=sid)
                old_mobile = student.student_mobile
                new_mobile, is_valid = _clean_mobile_number(old_mobile)
                
                if is_valid and new_mobile != old_mobile:
                    student.student_mobile = new_mobile
                    student.save()
                    
                    # Log to ActivityLog & Unified Timeline
                    log_activity(
                        request, 'UPDATE', 'students', 
                        f'Automated Mobile Repair: Fixed "{old_mobile}" -> "{new_mobile}"',
                        object_id=sid
                    )
                    updated_count += 1
            except Student.DoesNotExist:
                continue
                
    return JsonResponse({
        'success': True, 
        'updated_count': updated_count,
        'message': f'Successfully repaired {updated_count} mobile records.'
    })

@login_required
@require_access('students', 'academic_audit')
def api_bulk_verify_init(request):
    """Prepares a queue of board verification tasks for a batch of students."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    student_ids = request.POST.getlist('student_ids[]')
    types = request.POST.getlist('types[]') # ['SSC', 'HSC']
    
    if not student_ids:
        return JsonResponse({'success': False, 'error': 'No students selected.'})
    
    tasks = []
    # Use filter to get students
    students = Student.objects.filter(student_id__in=student_ids)
    
    for s in students:
        for t in types:
            # Only add task if board data exists for that exam
            has_data = False
            roll = s.ssc_roll if t == 'SSC' else s.hsc_roll
            board = s.ssc_board if t == 'SSC' else s.hsc_board
            
            if roll and board:
                tasks.append({
                    'student_id': s.student_id,
                    'name': s.student_name,
                    'exam': t,
                    'board': board,
                    'year': s.ssc_year if t == 'SSC' else s.hsc_year,
                    'roll': roll,
                    'reg': s.ssc_reg if t == 'SSC' else s.hsc_reg,
                })
                
    return JsonResponse({
        'success': True,
        'total_tasks': len(tasks),
        'tasks': tasks
    })

@login_required
def revert_field_change(request, history_id):
    """Secure API view for superadmins to revert specific student field modifications."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission Denied. Only superadministrators can revert changes.'}, status=403)
        
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method. POST required.'}, status=405)
        
    from .models import StudentFieldHistory
    from core.utils import log_activity
    from django.utils.dateparse import parse_date
    from django.db import models
    from django.utils import timezone
    
    history_entry = get_object_or_404(StudentFieldHistory, id=history_id)
    if history_entry.reverted:
        return JsonResponse({'success': False, 'error': 'This change has already been reverted.'})
        
    student = history_entry.student
    field_name = history_entry.field_name
    old_value_str = history_entry.old_value
    
    try:
        # Get field class and inspect it
        field = Student._meta.get_field(field_name)
        
        # Determine value to set
        target_value = None
        
        if old_value_str is None or old_value_str == 'None' or old_value_str == '':
            if field.null:
                target_value = None
            elif isinstance(field, (models.CharField, models.TextField)):
                target_value = ""
            elif isinstance(field, (models.IntegerField, models.SmallIntegerField, models.PositiveIntegerField)):
                target_value = 0
            elif isinstance(field, models.BooleanField):
                target_value = False
        else:
            if isinstance(field, models.BooleanField):
                target_value = old_value_str.lower() in ('true', '1', 'yes')
            elif isinstance(field, (models.IntegerField, models.SmallIntegerField, models.PositiveIntegerField)):
                try:
                    target_value = int(float(old_value_str))
                except ValueError:
                    target_value = 0
            elif isinstance(field, (models.FloatField, models.DecimalField)):
                try:
                    target_value = float(old_value_str)
                except ValueError:
                    target_value = 0.0
            elif isinstance(field, models.DateField):
                target_value = parse_date(old_value_str)
            else:
                target_value = old_value_str
                
        # Set field value
        setattr(student, field_name, target_value)
        student.changed_by_user = request.user
        student.save()
        
        # Mark history as reverted
        history_entry.reverted = True
        history_entry.reverted_by = request.user
        history_entry.reverted_at = timezone.now()
        history_entry.save()
        
        # Log this rollback to ActivityLog
        log_activity(
            request, 
            'UPDATE', 
            'students', 
            f"Reverted field '{field_name}' on student {student.student_name} back to '{old_value_str or 'None'}'",
            object_id=student.student_id
        )
        
        return JsonResponse({
            'success': True,
            'message': f"Successfully reverted field '{field_name}' to '{old_value_str or 'None'}'."
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Failed to revert field: {str(e)}"}, status=500)


@require_access('students', 'view_directory')
def api_studentship_preview(request, student_id):
    """
    Renders the studentship certificate preview modal with pre-populated, gender-aware values.
    """
    from master_data.models import Program
    from core.models import SystemSettings
    
    student, canonical_id, was_legacy = _resolve_student(student_id)
    if was_legacy:
        # Avoid redirecting AJAX requests, just use canonical ID internally
        pass
        
    sys_settings = SystemSettings.objects.first()
    
    # 1. Resolve full program name
    program_obj = Program.objects.filter(
        Q(short_name=student.program) | Q(name=student.program)
    ).first()
    if program_obj:
        program_full = f"{program_obj.name} ({program_obj.short_name})" if program_obj.short_name else program_obj.name
    else:
        program_full = student.program or ""

    # 2. Parse Level and Term
    current_semester = student.current_semester or 'Level 1 Term I'
    parts = current_semester.split(' ')
    if len(parts) >= 4:
        level = parts[1]
        term = parts[3]
    else:
        level = '1'
        term = 'I'

    # 3. Dynamic formatting of semester name to fit BAUST standards (e.g. "Winter Semester- 2026")
    semester_name = student.semester_name or ""
    sem_display = semester_name
    if sem_display:
        if "semester" not in sem_display.lower():
            words = sem_display.split()
            if len(words) == 2 and words[1].isdigit():
                sem_display = f"{words[0]} Semester- {words[1]}"
            elif student.admission_year:
                sem_display = f"{sem_display} Semester- {student.admission_year}"
        else:
            if "-" not in sem_display:
                sem_display = sem_display.replace("Semester ", "Semester- ")
                if student.admission_year and str(student.admission_year) not in sem_display:
                    sem_display = f"{sem_display}- {student.admission_year}"
    else:
        # Fallback to admission_year
        sem_display = f"Winter Semester- {student.admission_year or timezone.now().year}"

    # 4. Resolve pronouns based on gender
    is_female = student.gender and student.gender.lower() == 'female'
    relation = "daughter" if is_female else "son"
    pronoun = "her" if is_female else "him"

    # 5. Parents names
    parents = ""
    f_name = student.father_name or ""
    m_name = student.mother_name or ""
    if f_name and m_name:
        parents = f"{f_name} & {m_name}"
    elif f_name:
        parents = f_name
    elif m_name:
        parents = m_name

    # 6. Build default body text
    body_text = (
        f"This is to certify that <strong>{student.student_name.upper()}</strong>, {relation} of {parents.upper()}, "
        f"bearing ID No: {student.student_id} is a student of {program_full} Department, "
        f"Level-{level}, Term-{term} of {sem_display} at Bangladesh Army University "
        f"of Science & Technology (BAUST), Saidpur.\n\n"
        f"I wish {pronoun} every success in life."
    )
    
    # 7. Formulate default reference number and date
    ref_no = f"BAUST/Admin-132/2015/"
    default_date = timezone.localdate().strftime("%B %d, %Y")
    
    context = {
        'student': student,
        'ref_no': ref_no,
        'default_date': default_date,
        'body_text': body_text,
        'sys_settings': sys_settings,
    }
    
    return render(request, 'students/partials/studentship_preview_modal.html', context)


@require_access('students', 'view_directory')
def download_studentship_certificate(request, student_id):
    """
    Generates and downloads the customized Studentship Certificate PDF.
    """
    student, canonical_id, was_legacy = _resolve_student(student_id)
    if was_legacy:
        return redirect('download_studentship', student_id=canonical_id)
        
    if request.method == 'POST':
        ref_no = request.POST.get('ref_no', '')
        cert_date = request.POST.get('date', '')
        heading = request.POST.get('heading', 'TO WHOM IT MAY CONCERN')
        body_text = request.POST.get('body_text', '')
        signatory_name = request.POST.get('signatory_name', 'MD. KAZI NAZMUL HAQUE')
        signatory_title = request.POST.get('signatory_title', 'Deputy Registrar (Academic), BAUST')
        signatory_contact = request.POST.get('signatory_contact', 'Mobile: 01769675554')
    else:
        # Fallback values for GET request
        ref_no = f"BAUST/Admin-132/2015/"
        cert_date = timezone.localdate().strftime("%B %d, %Y")
        heading = 'TO WHOM IT MAY CONCERN'
        
        from master_data.models import Program
        program_obj = Program.objects.filter(
            Q(short_name=student.program) | Q(name=student.program)
        ).first()
        program_full = f"{program_obj.name} ({program_obj.short_name})" if (program_obj and program_obj.short_name) else (student.program or "")
        
        current_semester = student.current_semester or 'Level 1 Term I'
        parts = current_semester.split(' ')
        level = parts[1] if len(parts) >= 4 else '1'
        term = parts[3] if len(parts) >= 4 else 'I'
        
        sem_display = student.semester_name or f"Winter Semester- {student.admission_year or timezone.now().year}"
        is_female = student.gender and student.gender.lower() == 'female'
        relation = "daughter" if is_female else "son"
        pronoun = "her" if is_female else "him"
        
        parents = ""
        if student.father_name and student.mother_name:
            parents = f"{student.father_name} & {student.mother_name}"
        elif student.father_name:
            parents = student.father_name
        elif student.mother_name:
            parents = student.mother_name
            
        body_text = (
            f"This is to certify that <strong>{student.student_name.upper()}</strong>, {relation} of {parents.upper()}, "
            f"bearing ID No: {student.student_id} is a student of {program_full} Department, "
            f"Level-{level}, Term-{term} of {sem_display} at Bangladesh Army University "
            f"of Science & Technology (BAUST), Saidpur.\n\n"
            f"I wish {pronoun} every success in life."
        )
        signatory_name = 'MD. KAZI NAZMUL HAQUE'
        signatory_title = 'Deputy Registrar (Academic), BAUST'
        signatory_contact = 'Mobile: 01769675554'

    body_html = body_text.replace('\n', '<br>')
    
    context = {
        'student': student,
        'ref_no': ref_no,
        'cert_date': cert_date,
        'heading': heading,
        'body_html': body_html,
        'signatory_name': signatory_name,
        'signatory_title': signatory_title,
        'signatory_contact': signatory_contact,
        'today': timezone.now(),
    }
    
    pdf_response = render_to_pdf('students/reports/pdf/studentship_certificate.html', context)
    if pdf_response:
        filename = f"Studentship_Certificate_{student_id}.pdf"
        pdf_response['Content-Disposition'] = f"inline; filename={filename}"
        return pdf_response
    return HttpResponse("Error generating Studentship Certificate PDF", status=400)


@login_required
@require_access('reports', 'view_analytics')
def api_search_references(request):
    query = request.GET.get('q', '').strip()
    results = []
    
    from .models import ReferenceNode
    
    if query:
        nodes = ReferenceNode.objects.filter(
            Q(name_en__icontains=query) |
            Q(name_bn__icontains=query) |
            Q(baust_id__icontains=query)
        )[:30]
    else:
        nodes = ReferenceNode.objects.all().order_by('name_en')[:30]
        
    for node in nodes:
        parts = [node.name_en]
        if node.name_bn:
            parts.append(f"({node.name_bn})")
        if node.designation:
            parts.append(f"- {node.designation}")
        if node.baust_id:
            parts.append(f"[{node.baust_id}]")
            
        results.append({
            'id': node.id,
            'text': " ".join(parts)
        })
        
    return JsonResponse({'results': results})


@login_required
@require_access('students', 'view_directory')
def api_search_students(request):
    query = request.GET.get('q', '').strip()
    results = []
    
    if query:
        students = Student.objects.filter(
            Q(student_id__icontains=query) |
            Q(student_name__icontains=query)
        )[:30]
    else:
        students = Student.objects.all().order_by('-created_at')[:30]
        
    for s in students:
        text = f"{s.student_name} ({s.student_id}) - {s.program or 'No Dept'}, Batch {s.batch or 'Unknown'}"
        results.append({
            'id': s.student_id,
            'text': text
        })
        
    return JsonResponse({'results': results})


@login_required
@require_access('students', 'manage_references')
def reference_manage_dashboard(request):
    from .models import ReferenceNode
    
    export_format = request.GET.get('export')
    search_q = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category_filter', '').strip()
    
    queryset = ReferenceNode.objects.filter(is_verified=True).order_by('-id')
    if search_q:
        queryset = queryset.filter(
            Q(name_en__icontains=search_q) |
            Q(name_bn__icontains=search_q) |
            Q(baust_id__icontains=search_q) |
            Q(designation__icontains=search_q) |
            Q(mobile__icontains=search_q) |
            Q(reference_id__icontains=search_q)
        )
    if category_filter in ('Employee', 'External'):
        queryset = queryset.filter(category=category_filter)
        
    if export_format == 'excel':
        import pandas as pd
        data = []
        for r in queryset:
            data.append({
                'Reference ID': r.reference_id,
                'BAUST ID': r.baust_id or '',
                'Category': r.category,
                'English Name': r.name_en,
                'Bangla Name': r.name_bn or '',
                'Designation': r.designation or '',
                'Mobile': r.mobile or ''
            })
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=References_Export.xlsx'
        df.to_excel(response, index=False)
        return response
        
    elif export_format == 'template':
        import pandas as pd
        df = pd.DataFrame([{
            'BAUST ID': '12345',
            'Category': 'Employee',
            'English Name': 'Mohni Rahman',
            'Bangla Name': 'মোহিনী রহমান',
            'Designation': 'Assistant Professor, CSE',
            'Mobile': '01712345678'
        }])
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=References_Import_Template.xlsx'
        df.to_excel(response, index=False)
        return response
        
    elif export_format == 'pdf':
        context = {
            'references': queryset,
            'search_query': search_q,
            'today': timezone.now()
        }
        pdf_response = render_to_pdf('students/references/pdf_list.html', context)
        if pdf_response:
            pdf_response['Content-Disposition'] = 'inline; filename=References_List.pdf'
            return pdf_response
        return HttpResponse("Error generating PDF", status=400)
        
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            name_en = request.POST.get('name_en', '').strip()
            baust_id = request.POST.get('baust_id', '').strip() or None
            name_bn = request.POST.get('name_bn', '').strip() or None
            designation = request.POST.get('designation', '').strip() or None
            mobile = request.POST.get('mobile', '').strip() or None
            category = request.POST.get('category', 'Employee').strip()
            
            if not name_en:
                return HttpResponse('<div class="alert alert-danger font-weight-bold">English Name is required!</div>', status=400)
                
            node = ReferenceNode.objects.create(
                name_en=name_en,
                baust_id=baust_id,
                name_bn=name_bn,
                designation=designation,
                mobile=mobile,
                category=category
            )
            response = render(request, 'students/references/partials/reference_table.html', {
                'references': ReferenceNode.objects.filter(is_verified=True).order_by('-id')[:50]
            })
            response['HX-Trigger'] = 'referenceCreated'
            return response
            
        elif action == 'update':
            node_id = request.POST.get('id')
            node = get_object_or_404(ReferenceNode, id=node_id)
            
            node.name_en = request.POST.get('name_en', '').strip()
            node.baust_id = request.POST.get('baust_id', '').strip() or None
            node.name_bn = request.POST.get('name_bn', '').strip() or None
            node.designation = request.POST.get('designation', '').strip() or None
            node.mobile = request.POST.get('mobile', '').strip() or None
            node.category = request.POST.get('category', 'Employee').strip()
            
            if not node.name_en:
                return HttpResponse('<div class="alert alert-danger font-weight-bold">English Name is required!</div>', status=400)
                
            node.save()
            response = render(request, 'students/references/partials/reference_table.html', {
                'references': ReferenceNode.objects.filter(is_verified=True).order_by('-id')[:50]
            })
            response['HX-Trigger'] = 'referenceUpdated'
            return response
            
        elif action == 'delete':
            node_id = request.POST.get('id')
            node = get_object_or_404(ReferenceNode, id=node_id)
            node.delete()
            response = render(request, 'students/references/partials/reference_table.html', {
                'references': ReferenceNode.objects.filter(is_verified=True).order_by('-id')[:50]
            })
            response['HX-Trigger'] = 'referenceDeleted'
            return response
            
        elif action == 'merge':
            source_id = request.POST.get('source_id')
            target_id = request.POST.get('target_id')
            
            if not source_id or not target_id:
                return HttpResponse('<div class="alert alert-danger font-weight-bold">Both Source and Target references are required!</div>', status=400)
            if source_id == target_id:
                return HttpResponse('<div class="alert alert-danger font-weight-bold">Source and Target references cannot be the same!</div>', status=400)
                
            source_node = get_object_or_404(ReferenceNode, id=source_id)
            target_node = get_object_or_404(ReferenceNode, id=target_id)
            
            # Transfer all linked students from source to target
            linked_students_count = source_node.students.count()
            source_node.students.update(reference=target_node)
            
            # Delete the source node
            source_node_name = source_node.name_en
            source_node.delete()
            
            response = render(request, 'students/references/partials/reference_table.html', {
                'references': ReferenceNode.objects.filter(is_verified=True).order_by('-id')[:50]
            })
            response['HX-Trigger'] = json.dumps({
                'referenceMerged': {
                    'source': source_node_name,
                    'target': target_node.name_en,
                    'count': linked_students_count
                }
            })
            return response
            
        elif action == 'import':
            excel_file = request.FILES.get('excel_file')
            if not excel_file:
                messages.error(request, "Please select an Excel file to upload.")
                return redirect('reference_manage')
                
            try:
                import pandas as pd
                df = pd.read_excel(excel_file)
                
                required_cols = ['English Name']
                for col in required_cols:
                    if col not in df.columns:
                        messages.error(request, f"Missing required column in Excel: '{col}'")
                        return redirect('reference_manage')
                        
                # Pre-fetch all reference nodes for in-memory matching to avoid collation mismatch issues on MySQL
                all_nodes = list(ReferenceNode.objects.all())
                
                created_count = 0
                updated_count = 0
                for _, row in df.iterrows():
                    name_en = str(row.get('English Name', '')).strip()
                    if not name_en or name_en.lower() == 'nan':
                        continue
                        
                    baust_id = str(row.get('BAUST ID', '')).strip() if pd.notna(row.get('BAUST ID')) else None
                    if baust_id and baust_id.lower() == 'nan': baust_id = None
                    
                    name_bn = str(row.get('Bangla Name', '')).strip() if pd.notna(row.get('Bangla Name')) else None
                    if name_bn and name_bn.lower() == 'nan': name_bn = None
                    
                    designation = str(row.get('Designation', '')).strip() if pd.notna(row.get('Designation')) else None
                    if designation and designation.lower() == 'nan': designation = None
                    
                    mobile = str(row.get('Mobile', '')).strip() if pd.notna(row.get('Mobile')) else None
                    if mobile and mobile.lower() == 'nan': mobile = None
                    
                    category = str(row.get('Category', 'Employee')).strip() if pd.notna(row.get('Category')) else 'Employee'
                    if category not in ['Employee', 'External']:
                        category = 'Employee'
                    
                    # Smart Matching to prevent duplicates (in-memory to bypass collation conflicts):
                    node = None
                    if baust_id:
                        node = next((n for n in all_nodes if n.baust_id == baust_id), None)
                    if not node and mobile:
                        node = next((n for n in all_nodes if n.mobile == mobile), None)
                    if not node:
                        node = next((n for n in all_nodes if n.name_en and n.name_en.strip().lower() == name_en.lower()), None)
                        
                    if node:
                        if baust_id: node.baust_id = baust_id
                        if name_bn: node.name_bn = name_bn
                        if designation: node.designation = designation
                        if mobile: node.mobile = mobile
                        if name_en: node.name_en = name_en
                        node.category = category
                        node.save()
                        updated_count += 1
                    else:
                        new_node = ReferenceNode.objects.create(
                            name_en=name_en,
                            baust_id=baust_id,
                            name_bn=name_bn,
                            designation=designation,
                            mobile=mobile,
                            category=category
                        )
                        all_nodes.append(new_node)
                        created_count += 1
                    
                messages.success(request, f"Successfully imported references from Excel! (Created: {created_count}, Updated/Merged: {updated_count})")
            except Exception as e:
                messages.error(request, f"Excel Import failed: {str(e)}")
            return redirect('reference_manage')
            
    all_refs = ReferenceNode.objects.filter(is_verified=True).order_by('name_en')
    total_count = queryset.count()
    
    if request.headers.get('HX-Request'):
        return render(request, 'students/references/partials/reference_table.html', {
            'references': queryset[:50],
            'all_references': all_refs
        })
        
    return render(request, 'students/references/manage.html', {
        'references': queryset[:50],
        'all_references': all_refs,
        'total_count': total_count
    })


@login_required
@require_access('students', 'view_directory')
def api_reference_link_count(request, ref_id):
    """Returns the number of students linked to a given ReferenceNode."""
    from .models import ReferenceNode
    node = get_object_or_404(ReferenceNode, id=ref_id)
    count = node.students.count()
    return JsonResponse({
        'id': node.id,
        'name': node.name_en,
        'linked_students': count
    })


@login_required
@require_access('reports', 'view_analytics')
def api_align_legacy_reference(request):
    """Bulk aligns all students matching a legacy reference string to a selected ReferenceNode."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=400)
        
    legacy_text = request.POST.get('legacy_text', '').strip()
    target_node_id = request.POST.get('target_node_id', '').strip()
    
    if not legacy_text or not target_node_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
        
    from .models import ReferenceNode, Student
    target_node = get_object_or_404(ReferenceNode, id=target_node_id)
    
    # 1. Fetch matching student IDs first (SELECT query allows joins on MySQL/MariaDB)
    matching_student_ids = list(Student.objects.filter(
        Q(reference_legacy=legacy_text) | Q(reference__name_en=legacy_text)
    ).values_list('student_id', flat=True))
    
    # 2. Perform update using ID list (no JOINs in the UPDATE statement)
    updated_count = Student.objects.filter(student_id__in=matching_student_ids).update(reference=target_node)
    
    # 2. Clean up the unverified ReferenceNode with that legacy name if it exists (so it does not clutter database)
    unverified_legacy_nodes = ReferenceNode.objects.filter(name_en=legacy_text, is_verified=False)
    deleted_nodes_count = 0
    if unverified_legacy_nodes.exists():
        deleted_nodes_count = unverified_legacy_nodes.count()
        unverified_legacy_nodes.delete()
        
    # Log activity
    from core.models import ActivityLog
    ActivityLog.objects.create(
        user=request.user,
        action_type="UPDATE",
        module="students",
        scope="Reference Node Alignment",
        description=f"Bulk-mapped {updated_count} students with legacy text '{legacy_text}' to reference node '{target_node.name_en}' ({target_node.reference_id}) and cleaned up {deleted_nodes_count} legacy nodes."
    )
    
    return JsonResponse({
        'success': True,
        'message': f"Linked {updated_count} student(s) to '{target_node.name_en}' and cleaned up legacy nodes.",
        'updated_count': updated_count
    })


@login_required
@require_access('reports', 'view_analytics')
def api_reference_students(request):
    """Returns an HTMX HTML partial snippet containing all students referred by a given referrer."""
    ref_type = request.GET.get('type', '').strip()
    ref_id = request.GET.get('id', '').strip()
    
    if not ref_type or not ref_id:
        return HttpResponse("<div class='alert alert-danger mb-0'>Missing type or id parameters.</div>")
        
    from .models import Student
    
    if ref_type in ('Employee', 'External'):
        queryset = Student.objects.filter(reference_id=ref_id)
    elif ref_type == 'Student':
        queryset = Student.objects.filter(referred_by_student_id=ref_id)
    else:
        queryset = Student.objects.none()
        
    # Respect dashboard filters
    year = request.GET.get('year', '').strip()
    program = request.GET.get('program', '').strip()
    batch = request.GET.get('batch', '').strip()
    
    if batch:
        queryset = queryset.filter(batch=batch)
    elif year:
        queryset = queryset.filter(admission_year=year)
    if program:
        queryset = queryset.filter(program=program)
        
    queryset = queryset.order_by('student_id')
    
    return render(request, 'students/reports/partials/referrer_students_list.html', {
        'students': queryset,
        'referrer_type': ref_type
    })


# ──────────────────────────────────────────────────────────────────────────────
# Academic Data Patch Views
# ──────────────────────────────────────────────────────────────────────────────

@require_access('students', 'patch_academic_data')
def academic_data_patch(request):
    """
    Hub view for the Targeted Academic Data Patch feature.
    Supports three modes:
      GET              → Render the configuration form.
      POST action=preview → Dry-run parse, return HTMX diff preview partial.
      POST action=commit  → Execute the actual bulk_update and return report partial.
    """
    from master_data.models import Batch
    batches = Batch.objects.all().order_by('name')
    programs = Program.objects.all().order_by('name')

    if request.method == 'GET':
        import json as _json
        return render(request, 'students/academic_patch.html', {
            'batches': batches,
            'programs': programs,
            'ssc_fields': SSC_FIELDS,
            'hsc_fields': HSC_FIELDS,
            'all_fields': ALL_ACADEMIC_FIELDS,
            'field_labels': FIELD_LABELS,
            'field_labels_json': _json.dumps(FIELD_LABELS),
            'presets': FIELD_PRESETS,
        })

    # ── Common POST setup ──────────────────────────────────────────────────
    batch_name = request.POST.get('batch', '').strip()
    program_name = request.POST.get('program', '').strip()

    # Collect selected fields from checkboxes (name="patch_fields")
    selected_fields = request.POST.getlist('patch_fields')
    # Filter to only valid academic field names (security)
    selected_fields = [f for f in selected_fields if f in ALL_ACADEMIC_FIELDS]

    if not selected_fields:
        return HttpResponse(
            "<div class='alert alert-danger mt-3'>"
            "<i class='fas fa-exclamation-triangle mr-2'></i>"
            "Please select at least one field to patch."
            "</div>"
        )

    scope_qs = Student.objects.all()
    if batch_name:
        scope_qs = scope_qs.filter(batch=batch_name)
    if program_name:
        scope_qs = scope_qs.filter(program=program_name)

    action = request.POST.get('action', 'preview')

    if action == 'preview':
        if not request.FILES.get('excel_file'):
            return HttpResponse("<div class='alert alert-danger'>Please select an Excel file.</div>")

        result = patch_academic_data_from_excel(
            file_obj=request.FILES['excel_file'],
            selected_fields=selected_fields,
            scope_queryset=scope_qs,
            dry_run=True,
            changed_by_user=request.user,
        )
        if not result['success']:
            return HttpResponse(f"<div class='alert alert-danger mt-3'><strong>Error:</strong> {escape(result['error'])}</div>")

        return render(request, 'students/partials/academic_patch_preview.html', {
            'result': result,
            'batch_name': batch_name,
            'program_name': program_name,
            'selected_fields': selected_fields,
        })

    elif action == 'commit':
        if not request.FILES.get('excel_file'):
            return HttpResponse("<div class='alert alert-danger'>Please re-upload the Excel file to confirm.</div>")

        result = patch_academic_data_from_excel(
            file_obj=request.FILES['excel_file'],
            selected_fields=selected_fields,
            scope_queryset=scope_qs,
            dry_run=False,
            changed_by_user=request.user,
        )

        if result.get('success') and result.get('updated_count', 0) > 0:
            from core.models import ActivityLog
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR', None)
            ActivityLog.objects.create(
                user=request.user,
                action_type='UPDATE',
                module='students',
                object_id='batch_patch',
                description=(
                    f"Academic Data Patch: {result['updated_count']} students updated. "
                    f"Fields: {', '.join(result.get('fields_patched', selected_fields))}. "
                    f"Batch: '{batch_name or 'All'}', Program: '{program_name or 'All'}'"
                ),
                ip_address=ip
            )

        return render(request, 'students/partials/academic_patch_report.html', {
            'result': result,
            'batch_name': batch_name,
            'program_name': program_name,
            'selected_fields': selected_fields,
        })

    return redirect('academic_data_patch')


@require_access('students', 'patch_academic_data')
def download_academic_patch_template(request):
    """
    Generates a pre-filled Excel template for the Academic Data Patch.
    Query params:
      fields  : comma-separated list of field names to include (e.g. ssc_board,ssc_year,ssc_roll,ssc_reg)
      batch   : batch name filter (optional)
      program : program name filter (optional)
    """
    import pandas as pd

    batch_name = request.GET.get('batch', '').strip()
    program_name = request.GET.get('program', '').strip()

    # Accept either comma-sep 'fields' param or multiple 'fields' GET params
    raw_fields = request.GET.get('fields', '')
    if raw_fields:
        patch_fields = [f.strip() for f in raw_fields.split(',') if f.strip()]
    else:
        patch_fields = request.GET.getlist('fields')

    # Validate and preserve order
    patch_fields = [f for f in patch_fields if f in ALL_ACADEMIC_FIELDS]
    if not patch_fields:
        # Fallback to SSC board IDs
        patch_fields = ['ssc_board', 'ssc_year', 'ssc_roll', 'ssc_reg']

    export_columns = ['student_id', 'student_name'] + patch_fields

    qs = Student.objects.all()
    if batch_name:
        qs = qs.filter(batch=batch_name)
    if program_name:
        qs = qs.filter(program=program_name)
    qs = qs.order_by('student_id')

    data = []
    for s in qs:
        row = {}
        for col in export_columns:
            row[col] = getattr(s, col, None)
        data.append(row)

    df = pd.DataFrame(data, columns=export_columns)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Academic Patch')

    scope_label = ''
    if batch_name:
        scope_label += f'_Batch_{batch_name.replace(" ", "_")}'
    if program_name:
        scope_label += f'_{program_name.replace(" ", "_")}'

    fields_label = '_'.join(patch_fields[:3])  # cap label length
    filename = f'Academic_Patch_{fields_label}{scope_label}.xlsx'
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
