"""
CoE Module — Utility Functions

Tracking ID generation, PIN/OTP generation, SMS dispatch, and
file purge helpers.
"""

import hashlib
import os
import random
import string
from datetime import date

from django.conf import settings as django_settings
from django.utils import timezone

from .models import ApplicationStatusLog, CoeSettings


def get_coe_processing_officers():
    """
    Return active users specifically designated as CoE processing officers or CoE department staff.
    Filters by RolePermission (module='coe', task='processing_officer') or UserProfile.department containing CoE/Controller/Exam.
    Falls back to active staff/superusers if no specific CoE staff exist.
    """
    from django.contrib.auth.models import User
    from django.db.models import Q
    from core.models import RolePermission

    role_ids = RolePermission.objects.filter(
        module='coe', task='processing_officer'
    ).values_list('role_id', flat=True)

    qs = User.objects.filter(
        Q(profile__role_id__in=role_ids)
        | Q(profile__department__icontains='coe')
        | Q(profile__department__icontains='controller')
        | Q(profile__department__icontains='exam'),
        is_active=True
    ).distinct().order_by('first_name', 'username')

    if not qs.exists():
        qs = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True), is_active=True).order_by('first_name', 'username')

    return qs


# ──────────────────────────────────────────────────────────────────────────────
# ID / PIN / OTP Generation
# ──────────────────────────────────────────────────────────────────────────────

def generate_tracking_number(year: int | None = None) -> str:
    """
    Generate a unique sequential tracking number in format APP-YYYY-XXXX.
    Uses the CoeSettings prefix (default 'APP').
    BUG-9 FIX: Wrapped in transaction.atomic + select_for_update to prevent
    duplicate tracking numbers under concurrent submissions.
    """
    from django.db import transaction
    from .models import DocumentApplication
    cfg = CoeSettings.get_settings()
    prefix = cfg.tracking_id_prefix or 'APP'
    year = year or date.today().year
    base = f"{prefix}-{year}-"

    with transaction.atomic():
        records = (
            DocumentApplication.all_objects
            .select_for_update()              # row-level lock prevents concurrent reads
            .filter(application_number__startswith=base)
            .values_list('application_number', flat=True)
        )
        max_seq = 0
        for app_num in records:
            try:
                seq_part = int(app_num.split('-')[-1])
                if seq_part > max_seq:
                    max_seq = seq_part
            except (ValueError, IndexError):
                pass

        seq = max_seq + 1
        return f"{prefix}-{year}-{seq:04d}"


def generate_pin() -> str:
    """Generate a random 4-digit numeric PIN (zero-padded)."""
    return str(random.randint(0, 9999)).zfill(4)


def generate_delivery_otp() -> str:
    """Generate a random 6-digit numeric OTP."""
    return str(random.randint(0, 999999)).zfill(6)


# ──────────────────────────────────────────────────────────────────────────────
# File Utilities
# ──────────────────────────────────────────────────────────────────────────────

def compute_sha256(file_obj) -> str:
    """Compute SHA-256 hash of an uploaded file object."""
    sha = hashlib.sha256()
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(65536), b''):
        sha.update(chunk)
    file_obj.seek(0)
    return sha.hexdigest()


def validate_attachment_size(file_obj) -> tuple[bool, str]:
    """
    Returns (True, '') if file size is within the configured limit,
    or (False, error_message) if it exceeds the limit.
    """
    cfg = CoeSettings.get_settings()
    max_bytes = cfg.attachment_max_mb * 1024 * 1024
    file_size = getattr(file_obj, 'size', None)
    if file_size is None:
        file_obj.seek(0, 2)
        file_size = file_obj.tell()
        file_obj.seek(0)
    if file_size > max_bytes:
        return False, f"File size {file_size // 1024} KB exceeds the maximum allowed {cfg.attachment_max_mb} MB."
    return True, ''


# ──────────────────────────────────────────────────────────────────────────────
# QR Code & PDF Generation Helpers
# ──────────────────────────────────────────────────────────────────────────────

def generate_qr_code_base64(data: str) -> str:
    """Generate a QR code PNG image as a base64 encoded string for embedding in HTML/PDF."""
    try:
        import qrcode
        import io
        import base64
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1e3a5f", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    except Exception:
        return ""


def render_to_pdf_bytes(template_src: str, context_dict: dict) -> bytes:
    """Render a Django template into PDF bytes using xhtml2pdf."""
    import io
    from django.template.loader import get_template
    from xhtml2pdf import pisa
    try:
        template = get_template(template_src)
        html = template.render(context_dict)
        result = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
        if not pdf.err:
            return result.getvalue()
    except Exception:
        pass
    return b""


# ──────────────────────────────────────────────────────────────────────────────
# Dual-Channel Notifications (SMS + Email)
# ──────────────────────────────────────────────────────────────────────────────

SMS_TEMPLATES = {
    'submit': (
        "আপনার আবেদন গৃহীত হয়েছে। ট্র্যাকিং আইডি: {tracking_number}, পিন: {pin}। "
        "BAUST CoE পোর্টালে আবেদনের অবস্থা জানতে পারবেন।"
    ),
    'hod_approved': (
        "আপনার আবেদন ({tracking_number}) বিভাগীয় প্রধান অনুমোদন করেছেন। "
        "প্রক্রিয়াকরণ চলমান।"
    ),
    'action_required': (
        "আপনার আবেদন ({tracking_number}) সংক্রান্ত সমস্যা: {note}। "
        "অনুগ্রহ করে পুনরায় ডকুমেন্ট আপলোড করুন।"
    ),
    'ready_for_delivery': (
        "আপনার {doc_type} প্রস্তুত ({tracking_number})। "
        "BAUST CoE ডেস্ক থেকে সংগ্রহ করুন। OTP পরবর্তী SMS-এ আসবে।"
    ),
    'delivery_otp': (
        "BAUST CoE ডেলিভারি OTP: {otp}। "
        "এই কোডটি ক্লার্ককে প্রদান করুন — কাউকে শেয়ার করবেন না।"
    ),
    'reupload_complete': (
        "আপনার আবেদন ({tracking_number}) পুনঃআপলোডকৃত ডকুমেন্ট গ্রহণ করা হয়েছে। "
        "প্রক্রিয়াকরণ পুনরায় শুরু হয়েছে।"
    ),
}


def send_coe_sms(mobile: str, template_key: str, context: dict) -> tuple[bool, str]:
    """
    Send an SMS using the existing core.utils.send_sms gateway.
    template_key must be one of SMS_TEMPLATES keys.
    context is a dict of template variables.
    Returns (success_bool, response_text).
    """
    if template_key not in SMS_TEMPLATES:
        return False, f"Unknown SMS template: {template_key}"

    message = SMS_TEMPLATES[template_key].format(**context)

    try:
        from core.utils import send_sms
        return send_sms(mobile, message)
    except Exception as exc:
        return False, str(exc)


def send_coe_email(recipient_email: str, subject: str, template_name: str, context: dict,
                   attachment_bytes: bytes | None = None, attachment_filename: str | None = None) -> bool:
    """Send an HTML email notification with optional PDF receipt attached."""
    if not recipient_email:
        return False
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags

        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'coe@baust.edu.bd'),
            to=[recipient_email],
        )
        msg.attach_alternative(html_content, "text/html")
        if attachment_bytes and attachment_filename:
            msg.attach(attachment_filename, attachment_bytes, "application/pdf")
        msg.send(fail_silently=True)
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Status Transition Helper
# ──────────────────────────────────────────────────────────────────────────────

def transition_status(application, new_status: str, changed_by=None, note: str = '',
                      send_sms_key: str | None = None, sms_context: dict | None = None) -> None:
    """
    Transition a DocumentApplication to a new status, record the audit log,
    and optionally dispatch SMS + Email notifications.
    Saves the entire application instance to persist any field changes.
    """
    old_status = application.status
    
    # Intercept for Auto-Assignment based on application type mapping
    if new_status == 'pending_coe_assignment':
        cfg = CoeSettings.get_settings()
        if getattr(cfg, 'enable_auto_assignment', False):
            from .models import CoeAssignmentRule, ApplicationStatus
            rule = CoeAssignmentRule.objects.filter(application_type=application.application_type).first()
            if rule and rule.officer and rule.officer.is_active:
                application.assigned_to = rule.officer
                new_status = ApplicationStatus.IN_PROCESSING
                note = f"{note or ''} | Auto-assigned to {rule.officer.get_full_name() or rule.officer.username} based on application type rule.".strip(" |")
                
    application.status = new_status
    application.updated_at = timezone.now()
    application.save()  # Persists all instance mutations

    sms_sent = False
    if send_sms_key:
        cfg = CoeSettings.get_settings()
        sms_gate = {
            'submit':            cfg.sms_notify_submit,
            'hod_approved':      cfg.sms_notify_approved,
            'ready_for_delivery': cfg.sms_notify_ready,
            'delivery_otp':      cfg.sms_delivery_otp,
        }
        if sms_gate.get(send_sms_key, True):
            ctx = sms_context or {}
            ctx.setdefault('tracking_number', application.application_number)
            success, _ = send_coe_sms(application.mobile_number, send_sms_key, ctx)
            sms_sent = success

            # Also dispatch HTML Email if email is present
            if application.email:
                subject_map = {
                    'submit': f"Application Received — {application.application_number}",
                    'hod_approved': f"Department Head Approved — {application.application_number}",
                    'action_required': f"Action Required — {application.application_number}",
                    'ready_for_delivery': f"Document Ready for Delivery — {application.application_number}",
                    'delivery_otp': f"Delivery OTP — {application.application_number}",
                }
                send_coe_email(
                    recipient_email=application.email,
                    subject=subject_map.get(send_sms_key, f"CoE Update — {application.application_number}"),
                    template_name='coe/emails/status_update_email.html',
                    context={
                        'app': application,
                        'event': send_sms_key,
                        'note': note or ctx.get('note', ''),
                        'tracking_number': application.application_number,
                    }
                )

    ApplicationStatusLog.objects.create(
        application=application,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        note=note,
        sms_sent=sms_sent,
    )


# ──────────────────────────────────────────────────────────────────────────────
# File Purge Helpers
# ──────────────────────────────────────────────────────────────────────────────

def purge_attachments(application) -> int:
    """
    Delete physical files for all non-purged attachments of an application.
    Marks each attachment as is_purged=True.
    MINOR-8 FIX: Uses storage-backend-safe delete (works with S3/GCS/local).
    Returns the count of files purged.
    """
    count = 0
    for att in application.attachments.filter(is_purged=False):
        try:
            if att.file:
                att.file.storage.delete(att.file.name)  # storage-backend-safe
        except Exception:
            pass
        att.is_purged = True
        att.save(update_fields=['is_purged'])
        count += 1
    return count


def cleanup_rejected_applications() -> dict:
    """
    Purge files and soft-delete rejected/cancelled applications
    older than CoeSettings.rejected_purge_days.
    Returns a summary dict.
    """
    from .models import DocumentApplication, ApplicationStatus
    import datetime

    cfg = CoeSettings.get_settings()
    cutoff = timezone.now() - datetime.timedelta(days=cfg.rejected_purge_days)
    apps = DocumentApplication.all_objects.filter(
        status__in=[ApplicationStatus.REJECTED, ApplicationStatus.CANCELLED],
        updated_at__lt=cutoff,
        is_deleted=False,
    )
    purged_files = 0
    soft_deleted = 0
    for app in apps:
        purged_files += purge_attachments(app)
        app.is_deleted = True
        app.save(update_fields=['is_deleted'])
        soft_deleted += 1

    return {'soft_deleted': soft_deleted, 'purged_files': purged_files}


def cleanup_delivered_applications() -> dict:
    """
    Purge files for delivered applications older than CoeSettings.delivered_purge_days.
    Metadata (model rows) are preserved.
    Returns a summary dict.
    """
    from .models import DocumentApplication, ApplicationStatus
    import datetime

    cfg = CoeSettings.get_settings()
    cutoff = timezone.now() - datetime.timedelta(days=cfg.delivered_purge_days)
    apps = DocumentApplication.objects.filter(
        status=ApplicationStatus.DELIVERED,
        delivered_at__lt=cutoff,
    )
    purged_files = 0
    for app in apps:
        purged_files += purge_attachments(app)

    return {'purged_files': purged_files}
