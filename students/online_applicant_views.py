import io
import os
import shutil
import pandas as pd
from datetime import datetime
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import models, transaction
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.core.paginator import Paginator
from django.conf import settings

from core.decorators import require_access
from core.utils import log_activity, send_sms
from students.models import AdmissionIntake, OnlineApplicant, Student
from master_data.models import Program, Hall, AdmissionYear, Semester
from students.application_utils import (
    normalize_mobile,
    generate_application_qr_code_base64
)
from students.utils import generate_next_ugc_id
from students.utils_board import BoardVerificationEngine, BTEBVerificationEngine, is_technical_board


# ==============================================================================
# ONLINE APPLICANTS HUB (ADMIN)
# ==============================================================================

@login_required
@require_access('students', 'manage_online_applicants')
def admin_online_applicant_list(request):
    """
    Admin Applicant Hub matching Screenshot 3 layout:
    - Search by mobile, filter by intake, program, status.
    - Toggle Show Trash Data.
    - Column toggles and download options.
    - Page size clamping: [10, 20, 50, 100].
    """
    show_trash = request.GET.get('show_trash') in ['1', 'true', 'on', True]
    mobile_query = request.GET.get('mobile', '').strip()
    selected_intake_id = request.GET.get('intake', '').strip()
    selected_program = request.GET.get('program', '').strip()
    selected_status = request.GET.get('status', '').strip()

    # Base queryset
    queryset = OnlineApplicant.objects.filter(is_trashed=show_trash)

    # Filter by mobile
    if mobile_query:
        norm_mobile = normalize_mobile(mobile_query)
        queryset = queryset.filter(models.Q(mobile__icontains=norm_mobile) | models.Q(name__icontains=mobile_query) | models.Q(exam_roll__icontains=mobile_query))

    # Filter by intake
    if selected_intake_id:
        queryset = queryset.filter(intake_id=selected_intake_id)

    # Filter by program
    if selected_program and selected_program != 'All':
        queryset = queryset.filter(desired_program=selected_program)

    # Filter by status
    if selected_status and selected_status != 'All':
        queryset = queryset.filter(status=selected_status)

    # Clamped page size (DoS prevention)
    try:
        page_size = int(request.GET.get('page_size', 20))
        if page_size not in [10, 20, 50, 100]:
            page_size = 20
    except (ValueError, TypeError):
        page_size = 20

    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Dropdown choices for filter bar
    all_intakes = AdmissionIntake.objects.all().order_by('-id')
    all_programs = Program.objects.all().order_by('name')
    halls = Hall.objects.all().order_by('full_name')

    context = {
        'page_obj': page_obj,
        'show_trash': show_trash,
        'mobile_query': mobile_query,
        'selected_intake_id': selected_intake_id,
        'selected_program': selected_program,
        'selected_status': selected_status,
        'page_size': page_size,
        'all_intakes': all_intakes,
        'all_programs': all_programs,
        'halls': halls,
        'status_choices': OnlineApplicant.STATUS_CHOICES,
        'total_count': queryset.count(),
    }
    return render(request, 'students/admission/applicant_list.html', context)


@login_required
@require_access('students', 'manage_online_applicants')
def admin_applicant_detail_modal(request, pk):
    """
    Returns HTML fragment for applicant detail modal.
    """
    applicant = get_object_or_404(OnlineApplicant, pk=pk)
    halls = Hall.objects.all().order_by('full_name')
    context = {
        'applicant': applicant,
        'halls': halls,
    }
    return render(request, 'students/admission/applicant_detail_modal.html', context)


@login_required
@require_POST
@require_access('students', 'manage_online_applicants')
def admin_update_applicant_status(request, pk):
    """
    Update applicant review status (PENDING, VERIFIED, APPROVED, REJECTED, ADMITTED).
    """
    applicant = get_object_or_404(OnlineApplicant, pk=pk)
    new_status = request.POST.get('status', '').strip()
    remarks = request.POST.get('remarks', '').strip()

    valid_statuses = [s[0] for s in OnlineApplicant.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return JsonResponse({'status': 'error', 'message': 'Invalid status choice.'}, status=400)

    old_status = applicant.status
    applicant.status = new_status
    if remarks:
        applicant.office_remarks = f"[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {remarks}\n" + (applicant.office_remarks or '')
    applicant.save()

    log_activity(
        request, 'UPDATE', 'students',
        f"Updated status for applicant {applicant.application_no} ({applicant.name}) from {old_status} to {new_status}",
        object_id=str(applicant.pk)
    )

    # Send SMS notification on status change if requested
    notify_student = request.POST.get('notify_student') in ['1', 'true', 'on', True]
    if notify_student and new_status in ['APPROVED', 'REJECTED']:
        if new_status == 'APPROVED':
            msg = f"BAUST Admission: Congratulations {applicant.name}! Your application has been APPROVED. You can now download your admit card at /admission-portal/status/ with your roll {applicant.exam_roll}."
        else:
            msg = f"BAUST Admission: Dear {applicant.name}, your application for {applicant.intake_name} could not be approved. Office note: {remarks or 'Contact admission office for details.'}"
        send_sms(applicant.mobile, msg, module='ADMISSION', use_case_event='online_application_status_change', recipient_name=applicant.name)

    return JsonResponse({
        'status': 'success',
        'message': f'Status updated to {applicant.get_status_display()}.',
        'new_status': applicant.status,
        'status_display': applicant.get_status_display()
    })


@login_required
@require_POST
@require_access('students', 'manage_online_applicants')
def admin_verify_payment(request, pk):
    """
    Fast toggle to verify bKash TrxID with transaction notes and audit trail.
    """
    applicant = get_object_or_404(OnlineApplicant, pk=pk)
    payment_status = request.POST.get('payment_status', 'VERIFIED').strip()
    notes = request.POST.get('payment_notes', '').strip()

    if payment_status not in ['VERIFIED', 'INVALID', 'PENDING']:
        return JsonResponse({'status': 'error', 'message': 'Invalid payment status.'}, status=400)

    applicant.payment_status = payment_status
    applicant.payment_notes = notes
    applicant.payment_verified_by = request.user
    applicant.payment_verified_at = timezone.now()
    applicant.save()

    log_activity(
        request, 'UPDATE', 'students',
        f"Verified payment for applicant {applicant.application_no} (TrxID: {applicant.payment_trx_id}) -> {payment_status}",
        object_id=str(applicant.pk)
    )

    return JsonResponse({
        'status': 'success',
        'message': f'Payment marked as {applicant.get_payment_status_display()}.',
        'payment_status': applicant.payment_status,
        'payment_status_display': applicant.get_payment_status_display()
    })


@login_required
@require_POST
@require_access('students', 'manage_online_applicants')
def api_verify_applicant_board_result(request, pk):
    """
    Education Board verification bridge for Online Applicants using BoardVerificationEngine.
    """
    applicant = get_object_or_404(OnlineApplicant, pk=pk)
    exam_type = request.POST.get('exam_type', 'ssc').lower()  # 'ssc' or 'hsc'
    captcha = request.POST.get('captcha', '').strip()

    board = getattr(applicant, f"{exam_type}_board", "")
    year = getattr(applicant, f"{exam_type}_year", "")
    roll = getattr(applicant, f"{exam_type}_roll", "")
    reg = getattr(applicant, f"{exam_type}_reg", "")

    if not all([board, year, roll]):
        return JsonResponse({
            'success': False,
            'error': f'Missing {exam_type.upper()} details (Board, Year, or Roll).'
        }, status=400)

    try:
        if is_technical_board(board):
            bteb_engine = BTEBVerificationEngine()
            result = bteb_engine.verify_result(roll=roll, reg=reg, exam=exam_type.upper(), year=year)
        else:
            engine = BoardVerificationEngine()
            saved_cookies = request.session.get('board_session_cookies')
            if saved_cookies:
                import requests.utils
                engine.session.cookies.update(saved_cookies)
            result = engine.verify_result(
                exam=exam_type.upper(),
                board=board,
                year=year,
                roll=roll,
                reg=reg,
                captcha=captcha
            )

        if result.get('success'):
            if exam_type == 'ssc':
                applicant.ssc_verified = True
            else:
                applicant.hsc_verified = True

            logs = applicant.board_verification_logs or {}
            logs[exam_type] = {
                'verified_at': timezone.now().isoformat(),
                'verified_by': request.user.username,
                'data': result.get('data', {})
            }
            applicant.board_verification_logs = logs
            applicant.save()

            log_activity(
                request, 'AUDIT', 'students',
                f"Verified {exam_type.upper()} board data for applicant {applicant.application_no}",
                object_id=str(applicant.pk)
            )
            return JsonResponse({'success': True, 'data': result.get('data')})
        else:
            return JsonResponse({'success': False, 'error': result.get('error', 'Verification failed.')})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Verification error: {str(e)}"}, status=500)


@login_required
@require_http_methods(["GET", "POST"])
@require_access('students', 'manage_online_applicants')
def admin_edit_applicant(request, pk):
    """
    Edit applicant biographical, academic, and contact details.
    """
    applicant = get_object_or_404(OnlineApplicant, pk=pk)

    if request.method == 'POST':
        applicant.name = request.POST.get('name', applicant.name).strip()
        applicant.mobile = normalize_mobile(request.POST.get('mobile', applicant.mobile))
        applicant.email = request.POST.get('email', '').strip() or None
        applicant.national_id = request.POST.get('national_id', '').strip() or None
        applicant.gender = request.POST.get('gender', applicant.gender)
        applicant.blood_group = request.POST.get('blood_group', '').strip() or None
        applicant.desired_program = request.POST.get('desired_program', applicant.desired_program).strip()
        applicant.father_name = request.POST.get('father_name', applicant.father_name).strip()
        applicant.father_occupation = request.POST.get('father_occupation', '').strip() or None
        applicant.father_mobile = request.POST.get('father_mobile', '').strip() or None
        applicant.mother_name = request.POST.get('mother_name', applicant.mother_name).strip()
        applicant.mother_occupation = request.POST.get('mother_occupation', '').strip() or None
        applicant.mother_mobile = request.POST.get('mother_mobile', '').strip() or None

        applicant.present_house = request.POST.get('present_house', '').strip() or None
        applicant.present_district = request.POST.get('present_district', '').strip() or None
        applicant.permanent_house = request.POST.get('permanent_house', '').strip() or None
        applicant.permanent_district = request.POST.get('permanent_district', '').strip() or None

        applicant.ssc_system = request.POST.get('ssc_system', applicant.ssc_system or 'GPA')
        applicant.ssc_school = request.POST.get('ssc_school', '').strip() or None
        applicant.ssc_board = request.POST.get('ssc_board', '').strip() or None
        applicant.ssc_roll = request.POST.get('ssc_roll', '').strip() or None
        applicant.ssc_reg = request.POST.get('ssc_reg', '').strip() or None
        applicant.ssc_year = request.POST.get('ssc_year', '').strip() or None
        applicant.ssc_division = request.POST.get('ssc_division', '').strip() or None
        ssc_m = request.POST.get('ssc_marks', '').strip()
        applicant.ssc_marks = int(ssc_m) if ssc_m.isdigit() else None

        from .utils import get_division_equivalent_gpa

        if applicant.ssc_system == 'DIVISION':
            applicant.ssc_gpa = get_division_equivalent_gpa(applicant.ssc_division, applicant.ssc_marks)
        else:
            try:
                raw_gpa = request.POST.get('ssc_gpa')
                applicant.ssc_gpa = float(raw_gpa) if raw_gpa not in (None, '') else None
            except ValueError:
                pass

        applicant.hsc_system = request.POST.get('hsc_system', applicant.hsc_system or 'GPA')
        applicant.hsc_college = request.POST.get('hsc_college', '').strip() or None
        applicant.hsc_board = request.POST.get('hsc_board', '').strip() or None
        applicant.hsc_roll = request.POST.get('hsc_roll', '').strip() or None
        applicant.hsc_reg = request.POST.get('hsc_reg', '').strip() or None
        applicant.hsc_year = request.POST.get('hsc_year', '').strip() or None
        applicant.hsc_division = request.POST.get('hsc_division', '').strip() or None
        hsc_m = request.POST.get('hsc_marks', '').strip()
        applicant.hsc_marks = int(hsc_m) if hsc_m.isdigit() else None

        if applicant.hsc_system == 'DIVISION':
            applicant.hsc_gpa = get_division_equivalent_gpa(applicant.hsc_division, applicant.hsc_marks)
        else:
            try:
                raw_gpa = request.POST.get('hsc_gpa')
                applicant.hsc_gpa = float(raw_gpa) if raw_gpa not in (None, '') else None
            except ValueError:
                pass

        if applicant.ssc_gpa is not None and applicant.hsc_gpa is not None:
            applicant.total_gpa = round(applicant.ssc_gpa + applicant.hsc_gpa, 2)
        else:
            applicant.total_gpa = applicant.ssc_gpa or applicant.hsc_gpa or None
        applicant.payment_trx_id = request.POST.get('payment_trx_id', applicant.payment_trx_id).strip()

        # Handle photo update if uploaded
        new_photo = request.FILES.get('photo')
        if new_photo:
            applicant.photo = new_photo

        applicant.save()
        log_activity(request, 'UPDATE', 'students', f'Edited applicant {applicant.application_no}', object_id=str(applicant.pk))

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'Applicant data updated successfully.'})

        messages.success(request, 'Applicant data updated successfully.')
        return redirect('admin_online_applicant_list')

    all_programs = Program.objects.all().order_by('name')
    context = {
        'applicant': applicant,
        'all_programs': all_programs,
    }
    return render(request, 'students/admission/applicant_edit_modal.html', context)


@login_required
@require_access('students', 'manage_online_applicants')
def admin_print_application(request, pk):
    """
    Printable application summary and admit card view for admin.
    """
    applicant = get_object_or_404(OnlineApplicant, pk=pk)
    qr_payload = f"BAUST Online Admission Summary\nRoll: {applicant.exam_roll}\nName: {applicant.name}\nProgram: {applicant.desired_program}\nStatus: {applicant.status}"
    qr_code_b64 = generate_application_qr_code_base64(qr_payload)
    context = {
        'applicant': applicant,
        'intake': applicant.intake,
        'qr_code_b64': qr_code_b64,
        'is_admin_view': True,
    }
    return render(request, 'students/admission/admit_card.html', context)


# ==============================================================================
# 1-CLICK ENROLLMENT TO MAIN STUDENT DATABASE
# ==============================================================================

@login_required
@require_POST
@require_access('students', 'manage_online_applicants')
@require_access('students', 'add_student')  # Both permissions required
def admin_enroll_to_database(request, pk):
    """
    1-Click enrollment to main Student DB:
    - Atomically creates Student record
    - Generates dynamic UGC ID using Master Data
    - Copies photo file and sets relative photo_path
    - Marks applicant as ADMITTED and links Student record
    - Sends Welcome SMS
    - Prevents double-enrollment race condition
    """
    with transaction.atomic():
        applicant = OnlineApplicant.objects.select_for_update().get(pk=pk, is_trashed=False)

        # B9: Guard against double-enrollment
        if applicant.admitted_student:
            return JsonResponse({
                'status': 'error',
                'message': f'This applicant is already enrolled as Student ID: {applicant.admitted_student.student_id}'
            }, status=400)

        hall_name = request.POST.get('hall_name', '').strip()
        batch_name = request.POST.get('batch_name', '').strip()
        custom_student_id = request.POST.get('custom_student_id', '').strip()
        program_name = applicant.desired_program or ''

        # Academic year from intake or current year
        intake_year = applicant.intake.academic_year.year if applicant.intake.academic_year else timezone.now().year

        # CC6: Verify AdmissionYear exists
        if not AdmissionYear.objects.filter(year=intake_year).exists():
            return JsonResponse({
                'status': 'error',
                'message': f'Admission Year {intake_year} is not configured in Master Data. Please add it first.'
            }, status=400)

        # Program lookup
        prog_obj = Program.objects.filter(
            models.Q(short_name__iexact=program_name) | models.Q(name__iexact=program_name)
        ).first()
        cluster_name = prog_obj.cluster.name if prog_obj else ''
        program_level = prog_obj.get_level_code_display() if prog_obj else 'Bachelor'

        # Student ID Generation
        if custom_student_id:
            student_id = custom_student_id
            if Student.objects.filter(student_id=student_id).exists():
                return JsonResponse({
                    'status': 'error',
                    'message': f'Student ID {student_id} already exists in database.'
                }, status=400)
        else:
            student_id = generate_next_ugc_id(
                admission_year=intake_year,
                semester_name=applicant.intake_name,
                hall_name=hall_name,
                program_name=program_name,
                cluster_name=cluster_name,
                program_level=program_level,
            )

        # Create Student record (only existing fields on Student model)
        student = Student(
            student_id=student_id,
            student_name=applicant.name,
            program=program_name,
            admission_year=intake_year,
            cluster=cluster_name,
            batch=batch_name,
            semester_name=applicant.intake_name,
            program_type=program_level,
            gender=applicant.gender,
            dob=applicant.dob,
            blood_group=applicant.blood_group or '',
            national_id=applicant.national_id or '',
            father_name=applicant.father_name,
            father_occupation=applicant.father_occupation or '',
            father_mobile=applicant.father_mobile or '',
            mother_name=applicant.mother_name,
            mother_mobile=applicant.mother_mobile or '',
            student_mobile=applicant.mobile,
            student_email=applicant.email or '',
            present_address=f"{applicant.present_house or ''}, {applicant.present_district or ''}, {applicant.present_country}",
            permanent_address=f"{applicant.permanent_house or ''}, {applicant.permanent_district or ''}, {applicant.permanent_country}",
            present_district=applicant.present_district or '',
            permanent_district=applicant.permanent_district or '',
            ssc_system=applicant.ssc_system,
            ssc_school=applicant.ssc_school or '',
            ssc_board=applicant.ssc_board or '',
            ssc_roll=applicant.ssc_roll or '',
            ssc_reg=applicant.ssc_reg or '',
            ssc_year=applicant.ssc_year or '',
            ssc_division=applicant.ssc_division,
            ssc_marks=applicant.ssc_marks,
            ssc_gpa=applicant.ssc_gpa,
            hsc_system=applicant.hsc_system,
            hsc_college=applicant.hsc_college or '',
            hsc_board=applicant.hsc_board or '',
            hsc_roll=applicant.hsc_roll or '',
            hsc_reg=applicant.hsc_reg or '',
            hsc_year=applicant.hsc_year or '',
            hsc_division=applicant.hsc_division,
            hsc_marks=applicant.hsc_marks,
            hsc_gpa=applicant.hsc_gpa,
            ssc_verified=applicant.ssc_verified,
            hsc_verified=applicant.hsc_verified,
            academic_verification_logs=applicant.board_verification_logs,
            hall_attached=hall_name,
            admission_payment=float(applicant.intake.form_fee_bdt),
            admission_status='Active',
        )

        # Photo handling: Copy file to student_photos/{student_id}.jpg and set photo_path
        if applicant.photo:
            try:
                src = applicant.photo.path
                ext = os.path.splitext(src)[1].lower() or '.jpg'
                dest_rel = f"student_photos/{student_id}{ext}"
                dest_abs = os.path.join(settings.MEDIA_ROOT, dest_rel)
                os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
                shutil.copy2(src, dest_abs)
                student.photo_path = dest_rel
            except Exception:
                pass

        student.save()

        # Update applicant record
        applicant.status = 'ADMITTED'
        applicant.admitted_student = student
        applicant.save()

        # Log activity
        log_activity(
            request, 'CREATE', 'students',
            f'Enrolled online applicant {applicant.application_no} as Student {student_id}',
            object_id=student_id
        )

        # Send welcome SMS
        try:
            sms_text = f"Congratulations {student.student_name}! You have been successfully admitted to BAUST. Your Student ID: {student_id}. Keep this for your official records."
            send_sms(
                student.student_mobile,
                sms_text,
                module='ADMISSION',
                use_case_event='online_application_enrolled',
                recipient_name=student.student_name,
                student_id=student_id
            )
        except Exception:
            pass

        return JsonResponse({
            'status': 'success',
            'student_id': student_id,
            'message': f'Successfully enrolled {student.student_name} as Student ID: {student_id}'
        })


# ==============================================================================
# SOFT DELETE & RESTORE
# ==============================================================================

@login_required
@require_POST
@require_access('students', 'manage_online_applicants')
def admin_trash_applicant(request, pk):
    """
    Soft delete applicant.
    """
    applicant = get_object_or_404(OnlineApplicant, pk=pk)
    applicant.is_trashed = True
    applicant.trashed_by = request.user
    applicant.trashed_at = timezone.now()
    applicant.save()

    log_activity(
        request, 'DELETE', 'students',
        f'Trashed online applicant {applicant.application_no} ({applicant.name})',
        object_id=str(applicant.pk)
    )
    return JsonResponse({'status': 'success', 'message': f'Applicant {applicant.name} moved to trash.'})


@login_required
@require_POST
@require_access('students', 'manage_online_applicants')
def admin_restore_applicant(request, pk):
    """
    Restore trashed applicant with reactivation guard (B4).
    """
    applicant = get_object_or_404(OnlineApplicant, pk=pk)

    # Check if another active record exists for this mobile + intake
    if OnlineApplicant.objects.filter(
        intake=applicant.intake,
        mobile=applicant.mobile,
        is_trashed=False
    ).exclude(pk=applicant.pk).exists():
        return JsonResponse({
            'status': 'error',
            'message': f'Cannot restore: another active application already exists for mobile {applicant.mobile} in {applicant.intake_name}.'
        }, status=400)

    applicant.is_trashed = False
    applicant.trashed_by = None
    applicant.trashed_at = None
    applicant.save()

    log_activity(
        request, 'RESTORE', 'students',
        f'Restored online applicant {applicant.application_no} ({applicant.name})',
        object_id=str(applicant.pk)
    )
    return JsonResponse({'status': 'success', 'message': f'Applicant {applicant.name} restored from trash.'})


@login_required
@require_access('students', 'manage_online_applicants')
def admin_export_applicants(request):
    """
    Export online applicant list to Excel using pandas / openpyxl.
    """
    show_trash = request.GET.get('show_trash') in ['1', 'true', 'on', True]
    mobile_query = request.GET.get('mobile', '').strip()
    selected_intake_id = request.GET.get('intake', '').strip()
    selected_program = request.GET.get('program', '').strip()
    selected_status = request.GET.get('status', '').strip()

    queryset = OnlineApplicant.objects.filter(is_trashed=show_trash)
    if mobile_query:
        norm_mobile = normalize_mobile(mobile_query)
        queryset = queryset.filter(models.Q(mobile__icontains=norm_mobile) | models.Q(name__icontains=mobile_query))
    if selected_intake_id:
        queryset = queryset.filter(intake_id=selected_intake_id)
    if selected_program and selected_program != 'All':
        queryset = queryset.filter(desired_program=selected_program)
    if selected_status and selected_status != 'All':
        queryset = queryset.filter(status=selected_status)

    data = []
    for idx, a in enumerate(queryset, start=1):
        data.append({
            'SL': idx,
            'App No': a.application_no,
            'Exam Roll': a.exam_roll or '',
            'Name': a.name,
            'Mobile': a.mobile,
            'Email': a.email or '',
            'Semester': a.intake_name,
            'Program': a.desired_program or '',
            'Category': a.program_category,
            'Gender': a.gender,
            'SSC System': a.get_ssc_system_display() if hasattr(a, 'get_ssc_system_display') else a.ssc_system,
            'SSC Board': a.ssc_board or '',
            'SSC Roll': a.ssc_roll or '',
            'SSC Division': a.get_ssc_division_display() if a.ssc_division else '',
            'SSC Marks': a.ssc_marks if a.ssc_marks else '',
            'SSC GPA': a.ssc_gpa,
            'HSC System': a.get_hsc_system_display() if hasattr(a, 'get_hsc_system_display') else a.hsc_system,
            'HSC Board': a.hsc_board or '',
            'HSC Roll': a.hsc_roll or '',
            'HSC Division': a.get_hsc_division_display() if a.hsc_division else '',
            'HSC Marks': a.hsc_marks if a.hsc_marks else '',
            'HSC GPA': a.hsc_gpa,
            'Total GPA': a.total_gpa,
            'Payment Method': a.payment_method,
            'TrxID': a.payment_trx_id,
            'Payment Status': a.get_payment_status_display(),
            'Status': a.get_status_display(),
            'Enrolled Student ID': a.admitted_student.student_id if a.admitted_student else '',
            'Applied Date': a.applied_at.strftime('%Y-%m-%d %H:%M:%S'),
        })

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Online Applicants')
    output.seek(0)

    log_activity(request, 'EXPORT', 'students', f'Exported {len(data)} online applicants to Excel')

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    response['Content-Disposition'] = f'attachment; filename="Online_Applicants_{timestamp}.xlsx"'
    return response


# ==============================================================================
# INTAKE / SEMESTER MANAGEMENT (ADMIN)
# ==============================================================================

@login_required
@require_access('students', 'manage_admission_intakes')
def admin_intake_list(request):
    """
    Intake / Semester Manager page.
    """
    intakes = AdmissionIntake.objects.all().order_by('-id')
    academic_years = AdmissionYear.objects.all().order_by('-year')

    # Add dynamic counts to each intake
    intakes_with_counts = []
    for intake in intakes:
        intakes_with_counts.append({
            'intake': intake,
            'total_applicants': intake.applicants.filter(is_trashed=False).count(),
            'pending_count': intake.applicants.filter(is_trashed=False, status='PENDING').count(),
            'approved_count': intake.applicants.filter(is_trashed=False, status='APPROVED').count(),
            'admitted_count': intake.applicants.filter(is_trashed=False, status='ADMITTED').count(),
            'is_open': intake.is_currently_open,
        })

    context = {
        'intakes_with_counts': intakes_with_counts,
        'academic_years': academic_years,
    }
    return render(request, 'students/admission/intake_list.html', context)


@login_required
@require_POST
@require_access('students', 'manage_admission_intakes')
def admin_intake_add(request):
    """
    Add a new Admission Intake.
    """
    intake_name = request.POST.get('intake_name', '').strip()
    if not intake_name:
        messages.error(request, "Intake Name is required.")
        return redirect('admin_intake_list')

    if AdmissionIntake.objects.filter(intake_name=intake_name).exists():
        messages.error(request, f"Intake '{intake_name}' already exists.")
        return redirect('admin_intake_list')

    academic_year_id = request.POST.get('academic_year') or None
    is_open = request.POST.get('is_open_for_application') in ['1', 'true', 'on', True]
    deadline_val = request.POST.get('application_deadline', '').strip() or None
    exam_date_val = request.POST.get('exam_date', '').strip() or None
    exam_venue = request.POST.get('exam_venue', 'BAUST Campus (Saidpur)').strip()

    try:
        form_fee = Decimal(request.POST.get('form_fee_bdt', '750.00'))
        bkash_charge = Decimal(request.POST.get('bkash_charge_bdt', '12.00'))
    except Exception:
        form_fee = Decimal('750.00')
        bkash_charge = Decimal('12.00')

    bkash_number = request.POST.get('bkash_number', '01769675556').strip()
    roll_prefix = request.POST.get('exam_roll_prefix', 'BAUST-').strip()

    try:
        start_roll = int(request.POST.get('next_roll_number', 1001))
    except ValueError:
        start_roll = 1001

    intake = AdmissionIntake.objects.create(
        intake_name=intake_name,
        academic_year_id=academic_year_id,
        is_open_for_application=is_open,
        application_deadline=deadline_val,
        exam_date=exam_date_val,
        exam_venue=exam_venue,
        form_fee_bdt=form_fee,
        bkash_charge_bdt=bkash_charge,
        bkash_number=bkash_number,
        exam_roll_prefix=roll_prefix,
        next_roll_number=start_roll,
        notice_html=request.POST.get('notice_html', '').strip() or None
    )

    log_activity(request, 'CREATE', 'students', f'Created admission intake {intake.intake_name}', object_id=str(intake.pk))
    messages.success(request, f"Intake '{intake.intake_name}' created successfully.")
    return redirect('admin_intake_list')


@login_required
@require_http_methods(["GET", "POST"])
@require_access('students', 'manage_admission_intakes')
def admin_intake_edit(request, pk):
    """
    Edit intake settings.
    """
    intake = get_object_or_404(AdmissionIntake, pk=pk)

    if request.method == 'POST':
        intake.intake_name = request.POST.get('intake_name', intake.intake_name).strip()
        intake.academic_year_id = request.POST.get('academic_year') or None
        intake.is_open_for_application = request.POST.get('is_open_for_application') in ['1', 'true', 'on', True]
        intake.application_deadline = request.POST.get('application_deadline', '').strip() or None
        intake.exam_date = request.POST.get('exam_date', '').strip() or None
        intake.exam_venue = request.POST.get('exam_venue', intake.exam_venue).strip()

        try:
            intake.form_fee_bdt = Decimal(request.POST.get('form_fee_bdt', str(intake.form_fee_bdt)))
            intake.bkash_charge_bdt = Decimal(request.POST.get('bkash_charge_bdt', str(intake.bkash_charge_bdt)))
        except Exception:
            pass

        intake.bkash_number = request.POST.get('bkash_number', intake.bkash_number).strip()
        intake.exam_roll_prefix = request.POST.get('exam_roll_prefix', intake.exam_roll_prefix).strip()
        intake.notice_html = request.POST.get('notice_html', '').strip() or None
        intake.save()

        log_activity(request, 'UPDATE', 'students', f'Updated admission intake {intake.intake_name}', object_id=str(intake.pk))
        messages.success(request, f"Intake '{intake.intake_name}' updated successfully.")
        return redirect('admin_intake_list')

    academic_years = AdmissionYear.objects.all().order_by('-year')
    context = {
        'intake': intake,
        'academic_years': academic_years,
    }
    return render(request, 'students/admission/intake_edit_modal.html', context)


@login_required
@require_POST
@require_access('students', 'manage_admission_intakes')
def admin_intake_toggle(request, pk):
    """
    Toggle is_open_for_application for an intake.
    """
    intake = get_object_or_404(AdmissionIntake, pk=pk)
    intake.is_open_for_application = not intake.is_open_for_application
    intake.save()

    status_str = "Open" if intake.is_open_for_application else "Closed"
    log_activity(request, 'UPDATE', 'students', f"Toggled intake {intake.intake_name} to {status_str}", object_id=str(intake.pk))

    return JsonResponse({
        'status': 'success',
        'is_open': intake.is_open_for_application,
        'is_currently_open': intake.is_currently_open,
        'message': f"Intake '{intake.intake_name}' is now {status_str}."
    })


@require_POST
@require_access('students', 'manage_online_applicants')
def admin_toggle_login_admission_visibility(request):
    """Toggles the show_online_admission_on_login flag in SystemSettings."""
    from core.models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(id=1)
    settings_obj.show_online_admission_on_login = not settings_obj.show_online_admission_on_login
    settings_obj.save(update_fields=['show_online_admission_on_login'])

    state_str = "Visible" if settings_obj.show_online_admission_on_login else "Hidden"
    log_activity(
        request, 'UPDATE', 'students',
        f"Toggled Login Page Online Admission Portal visibility to {state_str}"
    )

    return JsonResponse({
        'status': 'success',
        'is_visible': settings_obj.show_online_admission_on_login,
        'message': f"Login page admission portal is now {state_str}."
    })
