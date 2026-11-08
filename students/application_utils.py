"""
Application Utilities:
- Tracking Number Generator (ADMN-YYYY-XXXX)
- QR Code Generator
- Student Profile Mismatch Detection
- Application Letterhead Context Builder
- PDF Generation
"""

import io
import base64
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django.template import Template, Context
from django.template.loader import get_template


def generate_admn_tracking_number() -> str:
    """
    Generates a unique, non-colliding tracking number for admission applications.
    Format: ADMN-YYYY-XXXX (e.g. ADMN-2026-0001).
    Uses atomic transaction with select_for_update to guarantee uniqueness.
    """
    from students.models import StudentApplication
    year = timezone.now().year
    prefix = f"ADMN-{year}-"

    with transaction.atomic():
        # Find latest tracking number for this year
        latest = (
            StudentApplication.objects
            .filter(tracking_number__startswith=prefix)
            .select_for_update()
            .order_by('-id')
            .first()
        )
        if latest and latest.tracking_number:
            try:
                last_seq = int(latest.tracking_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1

        candidate = f"{prefix}{next_seq:04d}"
        while StudentApplication.objects.filter(tracking_number=candidate).exists():
            next_seq += 1
            candidate = f"{prefix}{next_seq:04d}"

        return candidate


def generate_application_qr_code_base64(data: str) -> str:
    """Generate a high-quality QR code PNG as base64 data URI for letterhead rendering."""
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=5,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1a365d", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    except Exception:
        return ""


def detect_profile_mismatches(student, submitted_data: dict) -> tuple[bool, dict]:
    """
    Compares submitted form data with existing Student record.
    Returns (has_mismatch, mismatch_dict).
    """
    if not student:
        return False, {}

    mismatches = {}

    # Check Student Name
    current_name = (getattr(student, 'student_name', None) or getattr(student, 'student_name_english', '') or "").strip()
    submitted_name = (submitted_data.get('student_name') or "").strip()
    if current_name and submitted_name and current_name.lower() != submitted_name.lower():
        mismatches['student_name'] = {
            'field_label': 'Student Name',
            'current': current_name,
            'submitted': submitted_name
        }

    # Check Mobile Number (strip spaces and +88)
    raw_mobile = getattr(student, 'student_mobile', None) or getattr(student, 'mobile', '') or ""
    current_mobile = raw_mobile.replace(" ", "").replace("+88", "").replace("-", "").strip()
    submitted_mobile = (submitted_data.get('phone_no') or "").replace(" ", "").replace("+88", "").replace("-", "").strip()
    if current_mobile and submitted_mobile and current_mobile != submitted_mobile:
        mismatches['mobile'] = {
            'field_label': 'Mobile Number',
            'current': raw_mobile,
            'submitted': submitted_data.get('phone_no')
        }

    # Check Department / Program
    current_dept = ""
    if hasattr(student, 'program') and student.program:
        if isinstance(student.program, str):
            current_dept = student.program.strip()
        else:
            current_dept = (getattr(student.program, 'short_name', None) or getattr(student.program, 'name', '') or "").strip()
    submitted_dept = (submitted_data.get('department') or "").strip()
    if current_dept and submitted_dept and current_dept.lower() != submitted_dept.lower():
        mismatches['department'] = {
            'field_label': 'Department / Program',
            'current': current_dept,
            'submitted': submitted_dept
        }

    return bool(mismatches), mismatches


def build_application_pdf_context(application_obj=None, app_type=None, form_data=None, is_blank=False, request=None) -> dict:
    """
    Builds context dictionary for rendering official English academic PDF letterhead.
    Supports both filled applications and blank template downloads.
    """
    if application_obj:
        app_type = application_obj.application_type
        form_data = application_obj.form_data or {}
        tracking_number = application_obj.tracking_number
        student_name = application_obj.student_name
        applicant_student_id = application_obj.applicant_student_id or (application_obj.student.student_id if application_obj.student else "")
        department = application_obj.department
        phone_no = application_obj.phone_no
        submitted_at = application_obj.submitted_at
        status = application_obj.get_status_display()
    else:
        form_data = form_data or {}
        tracking_number = "BLANK-FORM-PREVIEW" if is_blank else form_data.get('tracking_number', '')
        student_name = "" if is_blank else form_data.get('student_name', '')
        applicant_student_id = "" if is_blank else form_data.get('applicant_student_id', '')
        department = "" if is_blank else form_data.get('department', '')
        phone_no = "" if is_blank else form_data.get('phone_no', '')
        submitted_at = timezone.now()
        status = "BLANK FORM" if is_blank else "SUBMITTED"

    # Determine Addressed To
    code = app_type.code if app_type else ""
    addressed_to = app_type.addressed_to if app_type else "The Registrar"

    # App 12 / 13 dynamic Hall Provost address
    hall_name = form_data.get('hall_name', '')
    if code in ['hall_cancel', 'seat_in_hostel']:
        if hall_name:
            addressed_to = f"The Hall Provost, {hall_name}"
        else:
            addressed_to = "The Hall Provost"

    # Render Subject and Body using Django Template engine
    render_context = {
        'student_name': student_name or ("........................................" if is_blank else ""),
        'student_id': applicant_student_id or ("...................." if is_blank else ""),
        'department': department or ("...................." if is_blank else ""),
        'phone_no': phone_no or ("...................." if is_blank else ""),
        'hall_name': hall_name or ("...................." if is_blank else ""),
        **{k: (v if not is_blank else "....................") for k, v in form_data.items()}
    }

    try:
        subject_tpl = Template(app_type.subject if app_type else "")
        subject_rendered = subject_tpl.render(Context(render_context))
    except Exception:
        subject_rendered = app_type.subject if app_type else ""

    try:
        body_tpl = Template(app_type.body_template if app_type else "")
        body_rendered = body_tpl.render(Context(render_context))
    except Exception:
        body_rendered = app_type.body_template if app_type else ""

    # Generate QR Code URL
    if request and tracking_number and not is_blank:
        verify_url = request.build_absolute_uri(f"/apply/track/?tracking={tracking_number}")
    else:
        verify_url = f"https://baust.edu.bd/admission/track/{tracking_number}" if not is_blank else "https://baust.edu.bd"

    qr_code_b64 = generate_application_qr_code_base64(verify_url)

    # Determine layout flags
    is_army_waiver = (code == 'army_waiver')
    is_drop_semester = (code == 'drop_semester')
    is_no_through = (not app_type.through_dept_head) if app_type else False
    is_id_optional = (code in ['scholarship_admission', 'direct_admission', 'submitted_papers', 'credit_transfer'])

    context = {
        'is_blank': is_blank,
        'app_type': app_type,
        'code': code,
        'tracking_number': tracking_number,
        'student_name': student_name,
        'student_id': applicant_student_id,
        'department': department,
        'phone_no': phone_no,
        'submitted_at': submitted_at,
        'status': status,
        'addressed_to': addressed_to,
        'through_dept_head': app_type.through_dept_head if app_type else True,
        'subject': subject_rendered,
        'body': body_rendered,
        'form_data': form_data,
        'qr_code_b64': qr_code_b64,
        'verify_url': verify_url,
        'is_army_waiver': is_army_waiver,
        'is_drop_semester': is_drop_semester,
        'is_no_through': is_no_through,
        'is_id_optional': is_id_optional,
        'hall_name': hall_name,
    }

    return context


def render_application_to_pdf_bytes(context_dict: dict) -> bytes:
    """Renders academic letterhead to PDF bytes using xhtml2pdf."""
    try:
        from xhtml2pdf import pisa
        template = get_template('students/applications/pdf_layout.html')
        html = template.render(context_dict)
        result = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
        if not pdf.err:
            return result.getvalue()
    except Exception:
        pass
    return b""


def generate_exam_roll(intake) -> str:
    """Atomically generates the next unique exam roll for an intake."""
    from students.models import AdmissionIntake
    with transaction.atomic():
        intake_locked = AdmissionIntake.objects.select_for_update().get(pk=intake.pk)
        roll = f"{intake_locked.exam_roll_prefix}{intake_locked.next_roll_number:04d}"
        intake_locked.next_roll_number += 1
        intake_locked.save(update_fields=['next_roll_number'])
    return roll


def generate_application_no(intake=None) -> str:
    """Generates a unique application tracking number (e.g. OA-2027-00001)."""
    from students.models import OnlineApplicant
    year = timezone.now().year
    prefix = f"OA-{year}-"
    with transaction.atomic():
        latest = (
            OnlineApplicant.objects
            .filter(application_no__startswith=prefix)
            .select_for_update()
            .order_by('-id')
            .first()
        )
        if latest and latest.application_no:
            try:
                last_seq = int(latest.application_no.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        candidate = f"{prefix}{next_seq:05d}"
        while OnlineApplicant.objects.filter(application_no=candidate).exists():
            next_seq += 1
            candidate = f"{prefix}{next_seq:05d}"
        return candidate


def validate_applicant_photo(photo_file) -> bool:
    """Validate photo using Pillow — detects spoofed extensions."""
    from PIL import Image
    try:
        img = Image.open(photo_file)
        img.verify()
        photo_file.seek(0)
        return True
    except Exception:
        return False


def normalize_mobile(raw_mobile: str) -> str:
    """Normalize BD mobile to 01XXXXXXXXX (11 digits)."""
    import re
    num = re.sub(r'[^0-9]', '', str(raw_mobile or ''))
    if num.startswith('880'):
        num = '0' + num[3:]
    elif num.startswith('88'):
        num = '0' + num[2:]
    return num if len(num) == 11 and num.startswith('01') else str(raw_mobile or '').strip()

