import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.db import models, transaction
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from students.models import AdmissionIntake, OnlineApplicant
from master_data.models import Program
from students.application_utils import (
    generate_exam_roll,
    generate_application_no,
    validate_applicant_photo,
    normalize_mobile,
    generate_application_qr_code_base64
)
from students.geo_data import BANGLADESH_GEO
from core.utils import send_sms

BOARD_CHOICES = [
    'Dhaka', 'Rajshahi', 'Comilla', 'Jessore', 'Chittagong',
    'Barisal', 'Sylhet', 'Dinajpur', 'Mymensingh',
    'Madrasah', 'Technical', 'Cambridge', 'Edexcel', 'Other'
]


def public_requirements(request):
    """
    Public landing / requirements page for BAUST Online Admission.
    Shows program criteria (Engineering vs Non-Engineering), documents required,
    and current active intake status (or closed banner).
    """
    open_intakes = [i for i in AdmissionIntake.objects.filter(is_open_for_application=True).order_by('-id') if i.is_currently_open]
    active_intake = open_intakes[0] if open_intakes else None
    latest_intake = AdmissionIntake.objects.order_by('-id').first()

    eng_programs = Program.objects.filter(
        cluster__name__icontains='Engineering'
    ).order_by('name')
    
    non_eng_programs = Program.objects.exclude(
        cluster__name__icontains='Engineering'
    ).order_by('name')

    context = {
        'open_intakes': open_intakes,
        'active_intake': active_intake,
        'latest_intake': latest_intake,
        'is_open': active_intake is not None,
        'eng_programs': eng_programs,
        'non_eng_programs': non_eng_programs,
    }
    return render(request, 'students/admission/requirements.html', context)


@require_http_methods(["GET", "POST"])
def public_apply_form(request):
    """
    Online application form for prospective students (Screenshot 2 & 4).
    """
    open_intakes = [i for i in AdmissionIntake.objects.filter(is_open_for_application=True).order_by('-id') if i.is_currently_open]
    
    if not open_intakes:
        messages.warning(request, "Online admission application is currently closed for all semesters.")
        return redirect('public_requirements')

    # Selected intake
    selected_intake_id = request.GET.get('intake_id') or request.POST.get('intake')
    active_intake = None
    if selected_intake_id:
        active_intake = next((i for i in open_intakes if str(i.id) == str(selected_intake_id)), None)
    if not active_intake:
        active_intake = open_intakes[0]

    if request.method == 'POST':
        intake_id = request.POST.get('intake')
        intake = get_object_or_404(AdmissionIntake, pk=intake_id)
        
        if not intake.is_currently_open:
            messages.error(request, f"Applications for {intake.intake_name} are now closed.")
            return redirect('public_requirements')

        raw_mobile = request.POST.get('mobile', '').strip()
        mobile = normalize_mobile(raw_mobile)
        if not mobile or len(mobile) != 11:
            messages.error(request, "Please provide a valid 11-digit Bangladesh mobile number (01XXXXXXXXX).")
            return redirect(request.path_info + f"?intake_id={intake.id}")

        # Unique active application per mobile per intake check
        if OnlineApplicant.objects.filter(intake=intake, mobile=mobile, is_trashed=False).exists():
            messages.error(request, f"An active application already exists for mobile {mobile} in {intake.intake_name}. You can track your status using your mobile number.")
            return redirect('public_application_status')

        # Photo validation
        photo = request.FILES.get('photo')
        if photo:
            if photo.size > 300 * 1024:
                messages.error(request, "Photo size exceeds 300KB limit. Please compress and re-upload.")
                return redirect(request.path_info + f"?intake_id={intake.id}")
            if not validate_applicant_photo(photo):
                messages.error(request, "Uploaded file is not a valid image. Only genuine JPG, JPEG, and PNG images are accepted.")
                return redirect(request.path_info + f"?intake_id={intake.id}")

        # Parse GPA and Division values
        ssc_system = request.POST.get('ssc_system', 'GPA')
        ssc_division = request.POST.get('ssc_division', '').strip() or None
        ssc_marks_raw = request.POST.get('ssc_marks', '').strip()
        ssc_marks = int(ssc_marks_raw) if ssc_marks_raw.isdigit() else None

        hsc_system = request.POST.get('hsc_system', 'GPA')
        hsc_division = request.POST.get('hsc_division', '').strip() or None
        hsc_marks_raw = request.POST.get('hsc_marks', '').strip()
        hsc_marks = int(hsc_marks_raw) if hsc_marks_raw.isdigit() else None

        from .utils import get_division_equivalent_gpa

        # Handle SSC Result
        if ssc_system == 'DIVISION':
            if not ssc_division:
                messages.error(request, "Please select an SSC Division for older/division system result.")
                return redirect(request.path_info + f"?intake_id={intake.id}")
            ssc_gpa = get_division_equivalent_gpa(ssc_division, ssc_marks)
        else:
            try:
                ssc_gpa = float(request.POST.get('ssc_gpa', 0.0) or 0.0)
            except ValueError:
                messages.error(request, "Please enter a valid numeric SSC GPA.")
                return redirect(request.path_info + f"?intake_id={intake.id}")
            if not (0.0 <= ssc_gpa <= 5.0):
                messages.error(request, "SSC GPA must be between 0.00 and 5.00.")
                return redirect(request.path_info + f"?intake_id={intake.id}")

        # Handle HSC Result
        if hsc_system == 'DIVISION':
            if not hsc_division:
                messages.error(request, "Please select an HSC Division for older/division system result.")
                return redirect(request.path_info + f"?intake_id={intake.id}")
            hsc_gpa = get_division_equivalent_gpa(hsc_division, hsc_marks)
        else:
            try:
                hsc_gpa = float(request.POST.get('hsc_gpa', 0.0) or 0.0)
            except ValueError:
                messages.error(request, "Please enter a valid numeric HSC GPA.")
                return redirect(request.path_info + f"?intake_id={intake.id}")
            if not (0.0 <= hsc_gpa <= 5.0):
                messages.error(request, "HSC GPA must be between 0.00 and 5.00.")
                return redirect(request.path_info + f"?intake_id={intake.id}")

        total_gpa = round(ssc_gpa + hsc_gpa, 2) if (ssc_gpa is not None and hsc_gpa is not None) else None

        # TrxID validation
        trx_id = request.POST.get('payment_trx_id', '').strip().upper()
        if not trx_id:
            messages.error(request, "bKash Transaction ID (TRXID) is required.")
            return redirect(request.path_info + f"?intake_id={intake.id}")

        # Create applicant atomically with exam roll and application number
        try:
            with transaction.atomic():
                exam_roll = generate_exam_roll(intake)
                application_no = generate_application_no(intake)

                dob_val = request.POST.get('dob', '').strip() or None

                same_as_present = request.POST.get('same_as_present') in ['on', 'true', 'True', '1']

                applicant = OnlineApplicant(
                    application_no=application_no,
                    exam_roll=exam_roll,
                    intake=intake,
                    intake_name=intake.intake_name,
                    program_category=request.POST.get('program_category', 'Engineering'),
                    desired_program=request.POST.get('desired_program', '').strip(),
                    exam_venue=request.POST.get('exam_venue', intake.exam_venue).strip() or intake.exam_venue,
                    name=request.POST.get('name', '').strip(),
                    mobile=mobile,
                    email=request.POST.get('email', '').strip() or None,
                    national_id=request.POST.get('national_id', '').strip() or None,
                    place_of_birth=request.POST.get('place_of_birth', '').strip() or None,
                    gender=request.POST.get('gender', 'Male'),
                    blood_group=request.POST.get('blood_group', '').strip() or None,
                    dob=dob_val,
                    nationality=request.POST.get('nationality', 'Bangladeshi').strip(),
                    marital_status=request.POST.get('marital_status', 'Single'),
                    student_type=request.POST.get('student_type', 'Regular'),
                    father_name=request.POST.get('father_name', '').strip(),
                    father_occupation=request.POST.get('father_occupation', '').strip() or None,
                    father_mobile=request.POST.get('father_mobile', '').strip() or None,
                    mother_name=request.POST.get('mother_name', '').strip(),
                    mother_occupation=request.POST.get('mother_occupation', '').strip() or None,
                    mother_mobile=request.POST.get('mother_mobile', '').strip() or None,
                    photo=photo,
                    present_house=request.POST.get('present_house', '').strip() or None,
                    present_post_code=request.POST.get('present_post_code', '').strip() or None,
                    present_police_station=request.POST.get('present_police_station', '').strip() or None,
                    present_district=request.POST.get('present_district', '').strip() or None,
                    present_country=request.POST.get('present_country', 'Bangladesh').strip(),
                    same_as_present=same_as_present,
                    permanent_house=request.POST.get('permanent_house', '').strip() or None,
                    permanent_post_code=request.POST.get('permanent_post_code', '').strip() or None,
                    permanent_police_station=request.POST.get('permanent_police_station', '').strip() or None,
                    permanent_district=request.POST.get('permanent_district', '').strip() or None,
                    permanent_country=request.POST.get('permanent_country', 'Bangladesh').strip(),
                    ssc_system=ssc_system,
                    ssc_school=request.POST.get('ssc_school', '').strip() or None,
                    ssc_board=request.POST.get('ssc_board', '').strip() or None,
                    ssc_roll=request.POST.get('ssc_roll', '').strip() or None,
                    ssc_reg=request.POST.get('ssc_reg', '').strip() or None,
                    ssc_year=request.POST.get('ssc_year', '').strip() or None,
                    ssc_division=ssc_division,
                    ssc_marks=ssc_marks,
                    ssc_gpa=ssc_gpa,
                    hsc_system=hsc_system,
                    hsc_college=request.POST.get('hsc_college', '').strip() or None,
                    hsc_board=request.POST.get('hsc_board', '').strip() or None,
                    hsc_roll=request.POST.get('hsc_roll', '').strip() or None,
                    hsc_reg=request.POST.get('hsc_reg', '').strip() or None,
                    hsc_year=request.POST.get('hsc_year', '').strip() or None,
                    hsc_division=hsc_division,
                    hsc_marks=hsc_marks,
                    hsc_gpa=hsc_gpa,
                    total_gpa=total_gpa,
                    payment_method='bKash',
                    payment_trx_id=trx_id,
                    payment_status='PENDING',
                    status='PENDING'
                )
                applicant.save()
        except Exception as e:
            messages.error(request, f"Error saving application: {str(e)}")
            return redirect(request.path_info + f"?intake_id={intake.id}")

        # Send confirmation SMS
        try:
            sms_text = f"BAUST Admission: Dear {applicant.name}, application received! Roll: {applicant.exam_roll}, App No: {applicant.application_no}. Track at: /admission-portal/status/"
            send_sms(
                number=applicant.mobile,
                message=sms_text,
                module='ADMISSION',
                use_case_event='online_application_confirm',
                recipient_name=applicant.name
            )
        except Exception:
            pass  # Non-blocking SMS failure

        return redirect('public_confirmation', exam_roll=applicant.exam_roll)

    # GET Request: Prepare dropdown data
    eng_programs = Program.objects.filter(
        cluster__name__icontains='Engineering'
    ).order_by('name')
    
    non_eng_programs = Program.objects.exclude(
        cluster__name__icontains='Engineering'
    ).order_by('name')

    # Build district list & district-to-police-stations mapping
    district_list = []
    district_police_station_map = {}
    for div_name, dist_dict in BANGLADESH_GEO.items():
        for dist_name, upazila_list in dist_dict.items():
            district_list.append(dist_name)
            district_police_station_map[dist_name] = sorted(upazila_list)
    district_list = sorted(list(set(district_list)))

    context = {
        'open_intakes': open_intakes,
        'active_intake': active_intake,
        'eng_programs': eng_programs,
        'non_eng_programs': non_eng_programs,
        'board_choices': BOARD_CHOICES,
        'district_list': district_list,
        'district_police_station_map_json': json.dumps(district_police_station_map),
    }
    return render(request, 'students/admission/apply_form.html', context)


def public_confirmation(request, exam_roll):
    """
    Confirmation and printable submission receipt page.
    """
    applicant = get_object_or_404(OnlineApplicant, exam_roll=exam_roll, is_trashed=False)
    qr_payload = f"BAUST Online Admission Receipt\nRoll: {applicant.exam_roll}\nApp No: {applicant.application_no}\nName: {applicant.name}\nProgram: {applicant.desired_program}\nDate: {applicant.applied_at.strftime('%Y-%m-%d %H:%M')}"
    qr_code_b64 = generate_application_qr_code_base64(qr_payload)

    context = {
        'applicant': applicant,
        'qr_code_b64': qr_code_b64,
    }
    return render(request, 'students/admission/confirmation.html', context)


@require_http_methods(["GET", "POST"])
def public_application_status(request):
    """
    Application Status & Tracking page (by Semester + Mobile number).
    """
    all_intakes = AdmissionIntake.objects.all().order_by('-id')
    selected_intake_id = request.GET.get('intake') or request.POST.get('intake')
    raw_mobile = request.GET.get('mobile') or request.POST.get('mobile') or ''
    
    applicant = None
    has_searched = False
    error_msg = None

    if raw_mobile:
        has_searched = True
        mobile = normalize_mobile(raw_mobile)
        query = OnlineApplicant.objects.filter(mobile=mobile, is_trashed=False)
        if selected_intake_id:
            query = query.filter(intake_id=selected_intake_id)
        
        applicant = query.order_by('-applied_at').first()
        if not applicant:
            error_msg = f"No application record found for mobile number {raw_mobile}."

    context = {
        'all_intakes': all_intakes,
        'selected_intake_id': selected_intake_id,
        'mobile': raw_mobile,
        'applicant': applicant,
        'has_searched': has_searched,
        'error_msg': error_msg,
    }
    return render(request, 'students/admission/check_status.html', context)


def public_admitcard_download(request):
    """
    Download printable Admit Card with high-security two-factor lookup:
    Requires BOTH exam_roll AND mobile number (Rule B7).
    Available only when status is 'APPROVED' or 'ADMITTED'.
    """
    exam_roll = request.GET.get('exam_roll', '').strip() or request.POST.get('exam_roll', '').strip()
    raw_mobile = request.GET.get('mobile', '').strip() or request.POST.get('mobile', '').strip()

    if not exam_roll or not raw_mobile:
        messages.error(request, "Both Exam Roll and Mobile Number are required to download the admit card.")
        return redirect('public_application_status')

    mobile = normalize_mobile(raw_mobile)
    applicant = OnlineApplicant.objects.filter(
        exam_roll=exam_roll, mobile=mobile, is_trashed=False
    ).first()

    if not applicant:
        messages.error(request, "Verification failed. Please ensure both Exam Roll and registered Mobile Number are entered correctly.")
        return redirect('public_application_status')

    if applicant.status not in ['APPROVED', 'ADMITTED']:
        messages.warning(
            request, 
            f"Admit card is not issued yet. Your application status is currently '{applicant.get_status_display()}'. Admit card will be available once approved by the admission office."
        )
        return redirect('public_application_status')

    # Generate security QR Code
    qr_payload = (
        f"BAUST ADMIT CARD\n"
        f"Roll: {applicant.exam_roll}\n"
        f"Name: {applicant.name}\n"
        f"Category: {applicant.program_category}\n"
        f"Program: {applicant.desired_program or 'Open'}\n"
        f"Venue: {applicant.exam_venue}\n"
        f"Date: {applicant.intake.exam_date.strftime('%d-%b-%Y %I:%M %p') if applicant.intake.exam_date else 'TBA'}"
    )
    qr_code_b64 = generate_application_qr_code_base64(qr_payload)

    context = {
        'applicant': applicant,
        'qr_code_b64': qr_code_b64,
        'intake': applicant.intake,
    }
    return render(request, 'students/admission/admit_card.html', context)


@require_GET
def api_check_open_intakes(request):
    """
    AJAX endpoint to return list of open intakes and their financial configs.
    """
    open_intakes = [i for i in AdmissionIntake.objects.filter(is_open_for_application=True).order_by('-id') if i.is_currently_open]
    data = {
        'has_open_intake': len(open_intakes) > 0,
        'intakes': [
            {
                'id': i.id,
                'intake_name': i.intake_name,
                'form_fee_bdt': float(i.form_fee_bdt),
                'bkash_charge_bdt': float(i.bkash_charge_bdt),
                'total_fee_bdt': float(i.total_fee_bdt),
                'bkash_number': i.bkash_number,
                'exam_venue': i.exam_venue,
                'deadline': i.application_deadline.strftime('%Y-%m-%d %H:%M') if i.application_deadline else None,
                'exam_date': i.exam_date.strftime('%Y-%m-%d %H:%M') if i.exam_date else None,
            }
            for i in open_intakes
        ]
    }
    return JsonResponse(data)
