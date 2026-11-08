"""
Admission Applications Views:
Handles public submission portal, auto-fill API, tracking, printable PDFs,
and administrative management hub (staff review, status workflow, template manager, profile sync).
"""

import json
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import transaction, models
from django.utils import timezone
from django.urls import reverse

from core.decorators import require_access
from students.models import (
    Student,
    AdmissionApplicationType,
    AdmissionApplicationConfig,
    StudentApplication,
    StudentFieldHistory
)
from master_data.models import Program, Hall, Semester
from students.application_utils import (
    generate_admn_tracking_number,
    detect_profile_mismatches,
    build_application_pdf_context,
    render_application_to_pdf_bytes,
)


# ──────────────────────────────────────────────────────────────────────────────
# Public Portal Views (No Login Required)
# ──────────────────────────────────────────────────────────────────────────────

@ensure_csrf_cookie
def public_apply(request):
    """
    Public student application submission portal.
    Bilingual (Bangla / English), mobile-responsive, supports auto-fill for enrolled students,
    duplicate check, and flexible/strict ID validation.
    """
    app_types = AdmissionApplicationType.objects.filter(is_active=True).order_by('order', 'id')
    config = AdmissionApplicationConfig.get_config()

    if request.method == 'POST':
        app_type_code = request.POST.get('application_type')
        if not app_type_code:
            return JsonResponse({'status': 'error', 'message': 'Please select an application type.'}, status=400)

        app_type = get_object_or_404(AdmissionApplicationType, code=app_type_code, is_active=True)

        student_name = request.POST.get('student_name', '').strip()
        applicant_id = request.POST.get('student_id', '').strip()
        department = request.POST.get('department', '').strip()
        phone_no = request.POST.get('phone_no', '').strip()

        if not student_name:
            return JsonResponse({'status': 'error', 'message': 'Student name is required.'}, status=400)
        if not phone_no:
            return JsonResponse({'status': 'error', 'message': 'Phone number is required.'}, status=400)

        is_id_optional = (app_type.code in ['scholarship_admission', 'direct_admission', 'submitted_papers', 'credit_transfer'])
        if not is_id_optional and not applicant_id:
            return JsonResponse({'status': 'error', 'message': 'Student ID is required for enrolled student applications.'}, status=400)

        # Build dynamic form_data dictionary
        form_data = {}
        for field in app_type.fields_schema:
            field_name = field['name']
            val = request.POST.get(field_name, '').strip()
            if field.get('required') and not val:
                return JsonResponse({
                    'status': 'error',
                    'message': f"Field '{field.get('label_en', field_name)}' is required."
                }, status=400)
            form_data[field_name] = val

        # CC2: Self-referential sibling check on Application 09
        if app_type.code == 'sibling_waiver':
            sibling_id = form_data.get('sibling_id', '').strip()
            if sibling_id and applicant_id and sibling_id.lower() == applicant_id.lower():
                return JsonResponse({
                    'status': 'error',
                    'message': 'You cannot list yourself as your own sibling.'
                }, status=400)

        # CC8: Application 10 resubmit date must be >= today + 7 days
        if app_type.code == 'withdraw_academic_papers':
            resubmit_str = form_data.get('resubmit_date', '')
            if resubmit_str:
                try:
                    from datetime import datetime
                    resubmit_date = datetime.strptime(resubmit_str, '%Y-%m-%d').date()
                    min_date = timezone.now().date() + timedelta(days=7)
                    if resubmit_date < min_date:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Resubmit date must be at least 7 days from today (on or after {min_date.strftime("%d-%b-%Y")}).'
                        }, status=400)
                except ValueError:
                    return JsonResponse({'status': 'error', 'message': 'Invalid resubmit date format.'}, status=400)

        # CC1: Check 24-hour duplicate submission
        confirm_duplicate = request.POST.get('confirm_duplicate') == 'true'
        since_24h = timezone.now() - timedelta(hours=24)
        duplicate_query = StudentApplication.objects.filter(
            application_type=app_type,
            submitted_at__gte=since_24h
        )
        if applicant_id:
            duplicate_query = duplicate_query.filter(
                models.Q(applicant_student_id__iexact=applicant_id) | models.Q(phone_no=phone_no)
            )
        else:
            duplicate_query = duplicate_query.filter(phone_no=phone_no)

        existing_sub = duplicate_query.order_by('-submitted_at').first()
        if existing_sub and not confirm_duplicate:
            return JsonResponse({
                'status': 'duplicate_warning',
                'tracking_number': existing_sub.tracking_number,
                'submitted_at': existing_sub.submitted_at.strftime("%d %b %Y %I:%M %p"),
                'message': (
                    f"You have already submitted this application today "
                    f"(Tracking ID: {existing_sub.tracking_number} at {existing_sub.submitted_at.strftime('%I:%M %p')}). "
                    f"Do you still want to submit another application?"
                )
            })

        # ID Verification against Student database
        student_obj = None
        is_id_verified = False
        if applicant_id:
            student_obj = Student.objects.filter(student_id__iexact=applicant_id).first()
            if student_obj:
                is_id_verified = True
            else:
                # Handle unrecorded ID based on policy
                if not is_id_optional:
                    if config.id_validation_policy == 'STRICT':
                        return JsonResponse({
                            'status': 'error',
                            'message': f"Student ID '{applicant_id}' is not recorded in the university database. Strict validation policy is active."
                        }, status=400)
                    else:
                        is_id_verified = False

        # Profile Mismatch Check
        has_mismatch, mismatch_details = False, {}
        if student_obj:
            submission_compare = {
                'student_name': student_name,
                'phone_no': phone_no,
                'department': department,
            }
            has_mismatch, mismatch_details = detect_profile_mismatches(student_obj, submission_compare)

        # Create Application Record
        tracking_number = generate_admn_tracking_number()
        app_record = StudentApplication.objects.create(
            tracking_number=tracking_number,
            application_type=app_type,
            student=student_obj,
            student_name=student_name,
            applicant_student_id=applicant_id,
            is_id_verified=is_id_verified,
            department=department,
            phone_no=phone_no,
            form_data=form_data,
            has_profile_mismatch=has_mismatch,
            mismatch_details=mismatch_details,
            status='SUBMITTED',
        )

        return JsonResponse({
            'status': 'success',
            'tracking_number': tracking_number,
            'pdf_url': reverse('download_filled_pdf', kwargs={'tracking_number': tracking_number}),
            'has_mismatch': has_mismatch,
            'is_id_verified': is_id_verified,
            'message': 'Application submitted successfully! Your tracking ID has been generated.'
        })

    # GET Request: Prepare form options
    programs = Program.objects.all().order_by('-sort_order', 'name')
    halls = Hall.objects.all().order_by('short_name')
    semesters = Semester.objects.all().order_by('-id')[:10]

    # Convert application types to JSON for fast dynamic client rendering
    app_types_json = []
    for at in app_types:
        app_types_json.append({
            'code': at.code,
            'order': at.order,
            'title_en': at.title_en,
            'title_bn': at.title_bn,
            'addressed_to': at.addressed_to,
            'through_dept_head': at.through_dept_head,
            'subject': at.subject,
            'fields_schema': at.fields_schema or [],
            'has_docx': bool(at.docx_template),
            'has_pdf': bool(at.pdf_template),
            'is_id_optional': at.code in ['scholarship_admission', 'direct_admission', 'submitted_papers', 'credit_transfer'],
        })

    return render(request, 'students/applications/public_apply.html', {
        'app_types': app_types,
        'app_types_json': json.dumps(app_types_json),
        'programs': programs,
        'halls': halls,
        'semesters': semesters,
        'config': config,
    })


@require_POST
def api_secure_autofill(request):
    """
    Secure student profile autofill endpoint.
    Requires student_id + mobile number (primary) or DOB (fallback).
    Rate-limited per session + IP to prevent enumeration.
    """
    ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    session_key = request.session.session_key or 'nosession'
    rate_key = f"autofill_rate_{session_key}_{ip}"
    attempts = cache.get(rate_key, 0)

    if attempts >= 5:
        return JsonResponse({
            'status': 'throttled',
            'message': 'Too many verification attempts. Please wait 5 minutes before trying again.'
        }, status=429)

    student_id = request.POST.get('student_id', '').strip()
    verify_type = request.POST.get('verify_type', 'mobile').strip()  # 'mobile' or 'dob'
    verify_value = request.POST.get('verify_value', '').strip()

    if not student_id or not verify_value:
        return JsonResponse({'status': 'error', 'message': 'Student ID and verification credential are required.'}, status=400)

    student = Student.objects.filter(student_id__iexact=student_id).first()

    matched = False
    if student:
        raw_student_mobile = getattr(student, 'student_mobile', None) or getattr(student, 'mobile', '') or ""
        student_dob = getattr(student, 'dob', None) or getattr(student, 'date_of_birth', None)

        if verify_type == 'mobile':
            clean_input = verify_value.replace(" ", "").replace("+88", "").replace("-", "")
            clean_student_mobile = raw_student_mobile.replace(" ", "").replace("+88", "").replace("-", "")
            if clean_input and clean_student_mobile and (clean_input == clean_student_mobile or clean_student_mobile.endswith(clean_input) or clean_input.endswith(clean_student_mobile)):
                matched = True
        elif verify_type == 'dob':
            input_dob = verify_value.strip()
            if student_dob:
                student_dob_str1 = student_dob.strftime('%Y-%m-%d')
                student_dob_str2 = student_dob.strftime('%d/%m/%Y')
                if input_dob in [student_dob_str1, student_dob_str2]:
                    matched = True

    if not matched:
        cache.set(rate_key, attempts + 1, timeout=300)
        remaining = 5 - (attempts + 1)
        return JsonResponse({
            'status': 'error',
            'message': f"Student ID and verification credentials do not match our records. ({remaining} attempts remaining)",
            'remaining_attempts': remaining
        }, status=403)

    # Success: reset fail counter
    cache.delete(rate_key)

    # Extract academic metadata
    dept_name = ""
    if hasattr(student, 'program') and student.program:
        if isinstance(student.program, str):
            dept_name = student.program
        else:
            dept_name = getattr(student.program, 'short_name', None) or getattr(student.program, 'name', '')

    hall_name = ""
    if hasattr(student, 'hall') and student.hall:
        hall_name = getattr(student.hall, 'name', '') or getattr(student.hall, 'short_name', '')

    batch_name = getattr(student, 'batch', '') or ""
    if not batch_name and hasattr(student, 'admission_sub_session') and student.admission_sub_session:
        batch_name = student.admission_sub_session.name
    elif not batch_name and hasattr(student, 'admission_year') and student.admission_year:
        batch_name = str(student.admission_year)

    # Mask phone for privacy preview
    full_mobile = raw_student_mobile
    masked_phone = full_mobile
    if len(full_mobile) >= 8:
        masked_phone = full_mobile[:3] + "****" + full_mobile[-3:]

    student_name_val = getattr(student, 'student_name', None) or getattr(student, 'student_name_english', '') or ''

    return JsonResponse({
        'status': 'success',
        'student_id': student.student_id,
        'student_name': student_name_val,
        'department': dept_name,
        'phone_no': full_mobile,
        'masked_phone': masked_phone,
        'hall_name': hall_name,
        'batch': batch_name,
        'sex': getattr(student, 'gender', '') or '',
        'father_profession': getattr(student, 'father_occupation', '') or '',
        'father_name_capital': (getattr(student, 'father_name', '') or '').upper(),
        'mother_name_capital': (getattr(student, 'mother_name', '') or '').upper(),
        'warning': 'Data auto-populated from official university records. Please review all fields carefully. Any modified values will be flagged for staff verification.'
    })


def api_check_sibling(request):
    """
    Checks sibling Student ID for Application 09 (Sibling Waiver).
    Rejects self-referential sibling ID.
    """
    sibling_id = request.GET.get('sibling_id', '').strip()
    student_id = request.GET.get('student_id', '').strip()

    if not sibling_id:
        return JsonResponse({'status': 'error', 'message': 'Sibling ID is required.'}, status=400)

    if student_id and sibling_id.lower() == student_id.lower():
        return JsonResponse({
            'status': 'self_reference',
            'message': 'You cannot list yourself as your own sibling.'
        }, status=400)

    sibling = Student.objects.filter(student_id__iexact=sibling_id).first()
    if sibling:
        dept_name = sibling.program.short_name if sibling.program else ""
        batch_name = sibling.admission_sub_session.name if sibling.admission_sub_session else ""
        return JsonResponse({
            'status': 'found',
            'sibling_name': sibling.student_name_english or '',
            'sibling_dept': dept_name,
            'sibling_batch': batch_name,
            'message': f"Verified: {sibling.student_name_english} ({dept_name})"
        })
    else:
        return JsonResponse({
            'status': 'not_found',
            'message': 'Sibling ID not found in current database. You can still type details manually for manual office review.'
        })


def api_validate_id(request):
    """Live validation of Student ID against database."""
    student_id = request.GET.get('student_id', '').strip()
    config = AdmissionApplicationConfig.get_config()

    if not student_id:
        return JsonResponse({'valid': False, 'policy': config.id_validation_policy})

    student = Student.objects.filter(student_id__iexact=student_id).first()
    if student:
        return JsonResponse({
            'valid': True,
            'name': student.student_name_english,
            'dept': student.program.short_name if student.program else '',
            'policy': config.id_validation_policy
        })
    else:
        return JsonResponse({
            'valid': False,
            'policy': config.id_validation_policy,
            'warning': 'Student ID not recorded in university records.'
        })


def public_track_application(request):
    """
    Public tracking view: Search by ADMN- tracking number OR phone number.
    Returns status progression timeline and re-download button.
    """
    tracking_query = request.GET.get('tracking', '').strip()
    phone_query = request.GET.get('phone', '').strip()

    applications = []
    searched = False

    if tracking_query:
        searched = True
        app = StudentApplication.objects.filter(tracking_number__iexact=tracking_query).first()
        if app:
            applications = [app]
    elif phone_query:
        searched = True
        clean_phone = phone_query.replace(" ", "").replace("+88", "").replace("-", "")
        # B8: Search returns a list of applications for this phone number
        applications = StudentApplication.objects.filter(
            models.Q(phone_no__icontains=clean_phone) | models.Q(phone_no=phone_query)
        ).order_by('-submitted_at')

    return render(request, 'students/applications/track_application.html', {
        'tracking_query': tracking_query,
        'phone_query': phone_query,
        'searched': searched,
        'applications': applications,
    })


def download_blank_pdf(request, app_type_code):
    """
    Generates and downloads a clean blank PDF template for printing and manual filling.
    Creates 0 database records.
    """
    app_type = get_object_or_404(AdmissionApplicationType, code=app_type_code)

    # Check if a custom uploaded PDF template exists
    if app_type.pdf_template:
        try:
            return FileResponse(
                app_type.pdf_template.open('rb'),
                as_attachment=False,
                filename=f"BAUST_{app_type.code}_blank.pdf"
            )
        except Exception:
            pass

    # Otherwise dynamically render blank academic letterhead
    context = build_application_pdf_context(app_type=app_type, is_blank=True, request=request)
    pdf_bytes = render_application_to_pdf_bytes(context)

    if pdf_bytes:
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="BAUST_Application_{app_type.code}_Blank.pdf"'
        return response

    # Fallback to printable HTML if PDF generation is not available
    return render(request, 'students/applications/pdf_layout.html', context)


def download_blank_docx(request, app_type_code):
    """
    Downloads custom Word (.docx) template if uploaded, otherwise falls back gracefully to blank PDF.
    """
    app_type = get_object_or_404(AdmissionApplicationType, code=app_type_code)

    if app_type.docx_template:
        try:
            return FileResponse(
                app_type.docx_template.open('rb'),
                as_attachment=True,
                filename=f"BAUST_{app_type.code}_template.docx"
            )
        except Exception:
            pass

    # B5 Fallback: Serve blank PDF with notice
    return redirect(reverse('download_blank_pdf', kwargs={'app_type_code': app_type.code}))


def download_filled_pdf(request, tracking_number):
    """
    Renders official English letterhead for a submitted application with QR code.
    Supports ?view=print for high-fidelity browser print mode.
    """
    application = get_object_or_404(StudentApplication, tracking_number=tracking_number)
    context = build_application_pdf_context(application_obj=application, request=request)

    # Browser print mode
    if request.GET.get('view') == 'print':
        return render(request, 'students/applications/pdf_layout.html', context)

    # Generated PDF stream
    pdf_bytes = render_application_to_pdf_bytes(context)
    if pdf_bytes:
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{application.tracking_number}.pdf"'
        return response

    return render(request, 'students/applications/pdf_layout.html', context)


# ──────────────────────────────────────────────────────────────────────────────
# Staff / Administrative Hub Views (Protected)
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@require_access('students', 'view_applications')
def admin_application_list(request):
    """
    Staff dashboard: Filter, search, and manage submitted student applications.
    """
    queryset = StudentApplication.objects.select_related('application_type', 'student', 'received_by').all()

    # Search query
    search_q = request.GET.get('q', '').strip()
    if search_q:
        queryset = queryset.filter(
            models.Q(tracking_number__icontains=search_q) |
            models.Q(student_name__icontains=search_q) |
            models.Q(applicant_student_id__icontains=search_q) |
            models.Q(phone_no__icontains=search_q)
        )

    # Filters
    app_type_filter = request.GET.get('type')
    if app_type_filter:
        queryset = queryset.filter(application_type__code=app_type_filter)

    status_filter = request.GET.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    mismatch_filter = request.GET.get('mismatch')
    if mismatch_filter == 'yes':
        queryset = queryset.filter(has_profile_mismatch=True)
    elif mismatch_filter == 'no':
        queryset = queryset.filter(has_profile_mismatch=False)

    verified_filter = request.GET.get('verified')
    if verified_filter == 'yes':
        queryset = queryset.filter(is_id_verified=True)
    elif verified_filter == 'no':
        queryset = queryset.filter(is_id_verified=False)

    date_from = request.GET.get('date_from')
    if date_from:
        queryset = queryset.filter(submitted_at__date__gte=date_from)

    date_to = request.GET.get('date_to')
    if date_to:
        queryset = queryset.filter(submitted_at__date__lte=date_to)

    # Metrics Summary
    total_count = StudentApplication.objects.count()
    submitted_count = StudentApplication.objects.filter(status='SUBMITTED').count()
    received_count = StudentApplication.objects.filter(status='RECEIVED').count()
    verified_count = StudentApplication.objects.filter(status='VERIFIED').count()
    approved_count = StudentApplication.objects.filter(status='APPROVED').count()
    rejected_count = StudentApplication.objects.filter(status='REJECTED').count()
    mismatch_count = StudentApplication.objects.filter(has_profile_mismatch=True).count()

    # Pagination
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    app_types = AdmissionApplicationType.objects.all().order_by('order')
    config = AdmissionApplicationConfig.get_config()

    return render(request, 'students/applications/admin_list.html', {
        'page_obj': page_obj,
        'app_types': app_types,
        'config': config,
        'search_q': search_q,
        'selected_type': app_type_filter,
        'selected_status': status_filter,
        'selected_mismatch': mismatch_filter,
        'selected_verified': verified_filter,
        'date_from': date_from,
        'date_to': date_to,
        'total_count': total_count,
        'submitted_count': submitted_count,
        'received_count': received_count,
        'verified_count': verified_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'mismatch_count': mismatch_count,
    })


@login_required
@require_access('students', 'view_applications')
def admin_application_detail_modal(request, tracking_number):
    """
    Renders detail modal with application fields, profile diff, and status actions.
    """
    application = get_object_or_404(StudentApplication, tracking_number=tracking_number)
    return render(request, 'students/applications/modals/application_detail_modal.html', {
        'app': application,
        'form_data': application.form_data,
        'mismatches': application.mismatch_details,
    })


@login_required
@require_POST
@require_access('students', 'view_applications')
def admin_update_application_status(request, tracking_number):
    """
    Staff action: Updates application status, office notes, and marks physical receipt.
    """
    application = get_object_or_404(StudentApplication, tracking_number=tracking_number)
    new_status = request.POST.get('status')
    notes = request.POST.get('office_notes', '').strip()

    valid_statuses = dict(StudentApplication.STATUS_CHOICES)
    if new_status not in valid_statuses:
        return JsonResponse({'status': 'error', 'message': 'Invalid status choice.'}, status=400)

    application.status = new_status
    if notes:
        application.office_notes = notes

    if new_status in ['RECEIVED', 'VERIFIED', 'APPROVED']:
        if not application.received_by:
            application.received_by = request.user
            application.received_at = timezone.now()

    application.save()
    return JsonResponse({
        'status': 'success',
        'message': f"Application status updated to '{valid_statuses[new_status]}'."
    })


@login_required
@require_POST
@require_access('students', 'delete_application')
def admin_delete_application(request, tracking_number):
    """
    Permanently deletes a student application.
    Requires 'delete_application' permission (Super Admin or authorized roles) and logs audit activity.
    """
    application = get_object_or_404(StudentApplication, tracking_number=tracking_number)
    student_name = application.student_name
    tracking_id = application.tracking_number
    app_type_title = application.application_type.title_en

    with transaction.atomic():
        application.delete()
        from core.utils import log_activity
        log_activity(
            request,
            'DELETE',
            'students',
            f"Permanently deleted student admission application {tracking_id} ({app_type_title}) submitted for {student_name}",
            object_id=tracking_id
        )

    return JsonResponse({
        'status': 'success',
        'message': f"Application {tracking_id} has been permanently deleted."
    })


@login_required
@require_POST
@require_access('students', 'edit_profile')
def admin_sync_student_profile(request, tracking_number):
    """
    B6: 1-click profile sync from application to official Student profile.
    Requires 'edit_profile' permission and logs StudentFieldHistory for every updated field.
    """
    application = get_object_or_404(StudentApplication, tracking_number=tracking_number)

    if not application.student:
        return JsonResponse({
            'status': 'error',
            'message': 'Cannot sync: Application is not linked to an existing Student profile in the database.'
        }, status=400)

    student = application.student
    mismatches = application.mismatch_details or {}

    if not mismatches:
        return JsonResponse({
            'status': 'info',
            'message': 'No profile mismatches detected for this application.'
        })

    ip = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    synced_fields = []

    with transaction.atomic():
        if 'student_name' in mismatches:
            old_name = getattr(student, 'student_name', None) or getattr(student, 'student_name_english', '')
            new_name = mismatches['student_name']['submitted']
            if hasattr(student, 'student_name'):
                student.student_name = new_name
            if hasattr(student, 'student_name_english'):
                student.student_name_english = new_name

            StudentFieldHistory.objects.create(
                student=student,
                field_name='student_name' if hasattr(student, 'student_name') else 'student_name_english',
                old_value=old_name,
                new_value=new_name,
                changed_by=request.user,
                ip_address=ip,
                user_agent=user_agent
            )
            synced_fields.append('Student Name')

        if 'mobile' in mismatches:
            old_mobile = getattr(student, 'student_mobile', None) or getattr(student, 'mobile', '')
            new_mobile = mismatches['mobile']['submitted']
            if hasattr(student, 'student_mobile'):
                student.student_mobile = new_mobile
            if hasattr(student, 'mobile'):
                student.mobile = new_mobile

            StudentFieldHistory.objects.create(
                student=student,
                field_name='student_mobile' if hasattr(student, 'student_mobile') else 'mobile',
                old_value=old_mobile,
                new_value=new_mobile,
                changed_by=request.user,
                ip_address=ip,
                user_agent=user_agent
            )
            synced_fields.append('Mobile Number')

        student.save()

        # Update application state
        application.has_profile_mismatch = False
        application.office_notes = (application.office_notes or "") + f"\n[Profile Synced on {timezone.now().strftime('%d-%b-%Y %I:%M %p')} by {request.user.username}]"
        application.save()

    return JsonResponse({
        'status': 'success',
        'message': f"Successfully synced {', '.join(synced_fields)} to student profile with audit history."
    })


@login_required
@require_POST
@require_access('students', 'manage_application_templates')
def admin_toggle_validation_policy(request):
    """Toggles student ID validation policy between FLEXIBLE and STRICT."""
    config = AdmissionApplicationConfig.get_config()
    current = config.id_validation_policy
    config.id_validation_policy = 'STRICT' if current == 'FLEXIBLE' else 'FLEXIBLE'
    config.save()

    return JsonResponse({
        'status': 'success',
        'new_policy': config.id_validation_policy,
        'message': f"ID Validation Policy switched to {config.get_id_validation_policy_display()}."
    })


@login_required
@require_access('students', 'manage_application_templates')
def admin_template_manager_modal(request):
    """Renders modal listing all 15 formats with upload/replace/delete controls."""
    app_types = AdmissionApplicationType.objects.all().order_by('order', 'id')
    return render(request, 'students/applications/modals/template_manager_modal.html', {
        'app_types': app_types,
    })


@login_required
@require_POST
@require_access('students', 'manage_application_templates')
def admin_upload_template(request, app_type_code):
    """
    Uploads or replaces Word (.docx) or PDF (.pdf) template.
    CC6: Enforces 5MB max file size limit and valid extensions.
    """
    app_type = get_object_or_404(AdmissionApplicationType, code=app_type_code)
    template_file = request.FILES.get('template_file')
    file_type = request.POST.get('file_type', 'docx').lower()

    if not template_file:
        return JsonResponse({'status': 'error', 'message': 'No file uploaded.'}, status=400)

    # 5MB size limit
    if template_file.size > 5 * 1024 * 1024:
        return JsonResponse({'status': 'error', 'message': 'File exceeds maximum 5MB size limit.'}, status=400)

    filename = template_file.name.lower()
    if file_type == 'docx':
        if not filename.endswith('.docx'):
            return JsonResponse({'status': 'error', 'message': 'Only .docx files are allowed for Word templates.'}, status=400)
        app_type.docx_template = template_file
    elif file_type == 'pdf':
        if not filename.endswith('.pdf'):
            return JsonResponse({'status': 'error', 'message': 'Only .pdf files are allowed for PDF templates.'}, status=400)
        app_type.pdf_template = template_file
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid file type.'}, status=400)

    app_type.save()
    return JsonResponse({
        'status': 'success',
        'message': f"Successfully updated {file_type.upper()} template for {app_type.title_en}."
    })


@login_required
@require_POST
@require_access('students', 'manage_application_templates')
def admin_delete_template(request, app_type_code, file_type):
    """Removes an uploaded DOCX or PDF template."""
    app_type = get_object_or_404(AdmissionApplicationType, code=app_type_code)
    file_type = file_type.lower()

    if file_type == 'docx' and app_type.docx_template:
        app_type.docx_template.delete(save=False)
        app_type.docx_template = None
        app_type.save()
    elif file_type == 'pdf' and app_type.pdf_template:
        app_type.pdf_template.delete(save=False)
        app_type.pdf_template = None
        app_type.save()
    else:
        return JsonResponse({'status': 'error', 'message': 'No template to remove.'}, status=400)

    return JsonResponse({
        'status': 'success',
        'message': f"Removed {file_type.upper()} template for {app_type.title_en}."
    })
