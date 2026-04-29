from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.decorators import require_access
from core.utils import log_activity
from students.models import Student

from .auth import require_api_scope
from .forms import APIClientForm
from .models import APIClient, APIRequestLog


def _student_payload(student, include_pii=False):
    data = {
        'student_id': student.student_id,
        'student_name': student.student_name,
        'old_student_id': student.old_student_id,
        'program': student.program,
        'admission_year': student.admission_year,
        'cluster': student.cluster,
        'batch': student.batch,
        'semester_name': student.semester_name,
        'program_type': student.program_type,
        'admission_date': student.admission_date.isoformat() if student.admission_date else None,
        'admission_status': student.admission_status,
        'gender': student.gender,
        'dob': student.dob.isoformat() if student.dob else None,
        'blood_group': student.blood_group,
        'hall_attached': student.hall_attached,
        'is_non_residential': student.is_non_residential,
        'is_credit_transfer': student.is_credit_transfer,
        'photo_url': student.photo_url,
        'created_at': student.created_at.isoformat() if student.created_at else None,
        'last_updated': student.last_updated.isoformat() if student.last_updated else None,
    }
    if include_pii:
        data.update({
            'religion': student.religion,
            'national_id': student.national_id,
            'father_name': student.father_name,
            'mother_name': student.mother_name,
            'father_occupation': student.father_occupation,
            'student_mobile': student.student_mobile,
            'father_mobile': student.father_mobile,
            'mother_mobile': student.mother_mobile,
            'student_email': student.student_email,
            'emergency_contact': student.emergency_contact,
            'present_address': student.present_address,
            'permanent_address': student.permanent_address,
            'present_division': student.present_division,
            'present_district': student.present_district,
            'present_upazila': student.present_upazila,
            'permanent_division': student.permanent_division,
            'permanent_district': student.permanent_district,
            'permanent_upazila': student.permanent_upazila,
        })
    return data


def _filter_students(request):
    students = Student.objects.all().order_by('student_id')
    query = request.GET.get('q', '').strip()
    if query:
        students = students.filter(
            Q(student_id__icontains=query) |
            Q(student_name__icontains=query) |
            Q(student_mobile__icontains=query) |
            Q(student_email__icontains=query)
        )
    for field in ['program', 'admission_year', 'batch', 'admission_status', 'gender']:
        value = request.GET.get(field, '').strip()
        if value:
            students = students.filter(**{field: value})
    return students


def _positive_int_param(request, name, default=None, maximum=None):
    raw_value = request.GET.get(name)
    if raw_value in (None, ''):
        return default, None
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None, f'{name} must be a positive number.'
    if value < 1:
        return None, f'{name} must be a positive number.'
    if maximum:
        value = min(value, maximum)
    return value, None


@require_access('security', 'manage_api')
def api_client_management(request):
    created_key = None
    editing_client = None

    if request.method == 'POST':
        action = request.POST.get('action', 'create')
        client_id = request.POST.get('client_id')
        instance = get_object_or_404(APIClient, id=client_id) if client_id else None
        form = APIClientForm(request.POST, instance=instance)
        if form.is_valid():
            client = form.save(commit=False)
            if not client.pk:
                created_key = client.set_new_key()
                client.created_by = request.user
            client.save()
            action_label = 'created' if action == 'create' else 'updated'
            messages.success(request, f'API client "{client.name}" {action_label} successfully.')
            log_activity(request, 'SECURITY', 'external_api', f'API client {action_label}: {client.name}', object_id=str(client.id), is_system_alert=True)
            if not created_key:
                return redirect('api_client_management')
        else:
            messages.error(request, 'Could not save API client. Please review the highlighted fields.')
    else:
        edit_id = request.GET.get('edit')
        if edit_id:
            editing_client = get_object_or_404(APIClient, id=edit_id)
            form = APIClientForm(instance=editing_client)
        else:
            form = APIClientForm(initial={'scopes': ['students:read'], 'rate_limit_per_minute': 120, 'is_active': True})

    clients = APIClient.objects.annotate(request_count=Count('request_logs')).order_by('name')
    recent_logs = APIRequestLog.objects.select_related('client')[:12]
    total_requests = APIRequestLog.objects.count()
    denied_requests = APIRequestLog.objects.exclude(status='SUCCESS').count()
    active_clients = APIClient.objects.filter(is_active=True).count()

    return render(request, 'external_api/client_management.html', {
        'form': form,
        'clients': clients,
        'recent_logs': recent_logs,
        'created_key': created_key,
        'editing_client': editing_client,
        'total_requests': total_requests,
        'denied_requests': denied_requests,
        'active_clients': active_clients,
    })


@require_access('security', 'manage_api')
@require_POST
def api_client_toggle(request, client_id):
    client = get_object_or_404(APIClient, id=client_id)
    client.is_active = not client.is_active
    if client.is_active:
        client.revoked_at = None
    client.save(update_fields=['is_active', 'revoked_at', 'updated_at'])
    state = 'activated' if client.is_active else 'deactivated'
    messages.success(request, f'API client "{client.name}" {state}.')
    log_activity(request, 'SECURITY', 'external_api', f'API client {state}: {client.name}', object_id=str(client.id), is_system_alert=True)
    return redirect('api_client_management')


@require_access('security', 'manage_api')
@require_POST
def api_client_rotate(request, client_id):
    client = get_object_or_404(APIClient, id=client_id)
    raw_key = client.set_new_key()
    client.save(update_fields=['key_prefix', 'key_hash', 'updated_at'])
    messages.warning(request, f'API key rotated for "{client.name}". Copy the new key now; it will not be shown again.')
    log_activity(request, 'SECURITY', 'external_api', f'Rotated API key for client: {client.name}', object_id=str(client.id), is_system_alert=True)
    clients = APIClient.objects.annotate(request_count=Count('request_logs')).order_by('name')
    return render(request, 'external_api/client_management.html', {
        'form': APIClientForm(initial={'scopes': ['students:read'], 'rate_limit_per_minute': 120, 'is_active': True}),
        'clients': clients,
        'recent_logs': APIRequestLog.objects.select_related('client')[:12],
        'created_key': raw_key,
        'editing_client': None,
        'total_requests': APIRequestLog.objects.count(),
        'denied_requests': APIRequestLog.objects.exclude(status='SUCCESS').count(),
        'active_clients': APIClient.objects.filter(is_active=True).count(),
    })


@require_access('security', 'manage_api')
@require_POST
def api_client_delete(request, client_id):
    client = get_object_or_404(APIClient, id=client_id)
    name = client.name
    if client.request_logs.exists():
        client.revoke()
        messages.warning(request, f'API client "{name}" has request logs, so it was revoked instead of deleted.')
    else:
        client.delete()
        messages.success(request, f'API client "{name}" deleted.')
    log_activity(request, 'DELETE', 'external_api', f'Removed or revoked API client: {name}', object_id=str(client_id), is_system_alert=True)
    return redirect('api_client_management')


@require_access('security', 'manage_api')
def api_request_logs(request):
    logs = APIRequestLog.objects.select_related('client').all()
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    client_filter = request.GET.get('client', '').strip()

    if query:
        logs = logs.filter(
            Q(path__icontains=query) |
            Q(query_string__icontains=query) |
            Q(ip_address__icontains=query) |
            Q(user_agent__icontains=query) |
            Q(request_id__icontains=query)
        )
    if status_filter:
        logs = logs.filter(status=status_filter)
    if client_filter:
        logs = logs.filter(client_id=client_filter)

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'external_api/request_logs.html', {
        'page_obj': page_obj,
        'clients': APIClient.objects.order_by('name'),
        'statuses': APIRequestLog.STATUS_CHOICES,
        'query': query,
        'status_filter': status_filter,
        'client_filter': client_filter,
    })


@require_GET
@require_api_scope('students:read')
def api_health(request):
    return JsonResponse({
        'status': 'ok',
        'client': request.api_client.name,
        'request_id': request.api_request_id,
    })


@require_GET
@require_api_scope('students:read')
def api_students(request):
    page_size, error = _positive_int_param(request, 'page_size', default=50, maximum=200)
    if error:
        return JsonResponse({'error': 'page_size must be a positive number between 1 and 200.'}, status=400)

    page_number, error = _positive_int_param(request, 'page', default=1)
    if error:
        return JsonResponse({'error': 'page must be a positive number.'}, status=400)

    admission_year = request.GET.get('admission_year', '').strip()
    if admission_year and not admission_year.isdigit():
        return JsonResponse({'error': 'admission_year must be numeric.'}, status=400)

    paginator = Paginator(_filter_students(request), page_size)
    page_obj = paginator.get_page(page_number)
    include_pii = request.api_client.has_scope('students:pii') and request.GET.get('include_pii') == 'true'
    return JsonResponse({
        'count': paginator.count,
        'page': page_obj.number,
        'page_size': page_size,
        'pages': paginator.num_pages,
        'results': [_student_payload(student, include_pii=include_pii) for student in page_obj.object_list],
        'request_id': request.api_request_id,
    })


@require_GET
@require_api_scope('students:read')
def api_student_detail(request, student_id):
    student = Student.objects.filter(student_id=student_id).first()
    if not student:
        return JsonResponse({'error': 'Student not found.'}, status=404)
    include_pii = request.api_client.has_scope('students:pii')
    return JsonResponse({
        'result': _student_payload(student, include_pii=include_pii),
        'request_id': request.api_request_id,
    })


@require_GET
@require_api_scope('reports:read')
def api_report_summary(request):
    total = Student.objects.count()
    by_program = list(Student.objects.values('program').annotate(total=Count('student_id')).order_by('program'))
    by_status = list(Student.objects.values('admission_status').annotate(total=Count('student_id')).order_by('admission_status'))
    finance = Student.objects.aggregate(
        admission_payment=Sum('admission_payment'),
        second_installment=Sum('second_installment'),
        waiver=Sum('waiver'),
        others=Sum('others'),
    )
    return JsonResponse({
        'total_students': total,
        'by_program': by_program,
        'by_status': by_status,
        'finance': finance,
        'request_id': request.api_request_id,
    })
