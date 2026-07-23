"""
CoE Module — Data Models

All five models implementing the complete lifecycle of student academic
document applications.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from master_data.models import Program


# ──────────────────────────────────────────────────────────────────────────────
# Choices
# ──────────────────────────────────────────────────────────────────────────────

class ApplicationType(models.TextChoices):
    MAIN_CERTIFICATE        = 'main_certificate',       _('Main/Original Certificate')
    PROVISIONAL_TRANSCRIPT  = 'provisional_transcript', _('Provisional / Main Academic Transcript')
    INCOMPLETE_TRANSCRIPT   = 'incomplete_transcript',  _('Incomplete Academic Transcript')
    NAME_CORRECTION         = 'name_correction',        _('Student\'s Name Correction')
    PARENT_NAME_CORRECTION  = 'parent_name_correction', _('Father/Mother Name Correction')
    RECOMMENDATION_LETTER   = 'recommendation_letter',  _('Recommendation Letter')
    GRADE_SHEET             = 'grade_sheet',            _('Grade Sheet')
    DUPLICATE_DOCUMENT      = 'duplicate_document',     _('Duplicate Documents (as per GD)')


class ApplicationStatus(models.TextChoices):
    SUBMITTED               = 'submitted',              _('Submitted')
    UNDER_HOD_REVIEW        = 'under_hod_review',       _('Under HoD Review')
    PENDING_COE_ASSIGNMENT  = 'pending_coe_assignment', _('Pending CoE Assignment')
    IN_PROCESSING           = 'in_processing',          _('In Processing')
    ACTION_REQUIRED         = 'action_required',        _('Action Required by Student')
    READY_FOR_DELIVERY      = 'ready_for_delivery',     _('Ready for Delivery')
    DELIVERED               = 'delivered',              _('Delivered')
    REJECTED                = 'rejected',               _('Rejected')
    CANCELLED               = 'cancelled',              _('Cancelled')


class AttachmentType(models.TextChoices):
    FINAL_CLEARANCE     = 'final_clearance',    _('Final Clearance')
    PAYMENT_SLIP        = 'payment_slip',        _('Payment Slip')
    SSC_CERTIFICATE     = 'ssc_cert',            _('SSC Certificate')
    HSC_CERTIFICATE     = 'hsc_cert',            _('HSC Certificate')
    NID_PHOTOCOPY       = 'nid_photocopy',       _('NID Photocopy')
    OFFER_LETTER        = 'offer_letter',        _('Offer Letter (Printed Copy)')
    BAUST_MCE           = 'baust_mce',           _('BAUST — Migration Certificate (MCE)')
    BAUST_MOI           = 'baust_moi',           _('BAUST — Migration of Institution (MoI)')
    BAUST_MC            = 'baust_mc',            _('BAUST — Mark Certificate (MC)')
    BAUST_TS            = 'baust_ts',            _('BAUST — Testimonial Sheet (TS)')
    GD_COPY             = 'gd_copy',             _('General Diary (GD) Copy')
    MISSING_DOC_COPY    = 'missing_doc_copy',    _('Missing Document Copy')
    OTHER               = 'other',               _('Other Document')


# ──────────────────────────────────────────────────────────────────────────────
# Custom Manager
# ──────────────────────────────────────────────────────────────────────────────

class ActiveApplicationManager(models.Manager):
    """Excludes soft-deleted applications from default querysets."""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# ──────────────────────────────────────────────────────────────────────────────
# Model 1 — DocumentApplication
# ──────────────────────────────────────────────────────────────────────────────

class DocumentApplication(models.Model):
    # Core identification
    application_number  = models.CharField(max_length=20, unique=True, editable=False, verbose_name=_('Application Number'))
    tracking_pin        = models.CharField(max_length=4, editable=False, verbose_name=_('Tracking PIN'))
    application_type    = models.CharField(max_length=30, choices=ApplicationType.choices, verbose_name=_('Application Type'))
    status              = models.CharField(
        max_length=30, choices=ApplicationStatus.choices,
        default=ApplicationStatus.SUBMITTED, db_index=True, verbose_name=_('Status')
    )

    # Student information
    student_name        = models.CharField(max_length=200, verbose_name=_('Student Name'))
    student_id          = models.CharField(max_length=16, verbose_name=_('Student ID'))
    mobile_number       = models.CharField(max_length=15, verbose_name=_('Mobile Number'))
    email               = models.EmailField(blank=True, verbose_name=_('Email Address'))

    # Academic information
    session             = models.CharField(max_length=20, verbose_name=_('Session'))
    department          = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name='coe_applications',
        verbose_name=_('Department / Program')
    )
    admission_batch     = models.CharField(max_length=10, verbose_name=_('Admission Batch'))
    father_name         = models.CharField(max_length=200, blank=True, verbose_name=_("Father's Name"))
    mother_name         = models.CharField(max_length=200, blank=True, verbose_name=_("Mother's Name"))
    dob                 = models.DateField(null=True, blank=True, verbose_name=_('Date of Birth'))
    passing_semester    = models.CharField(max_length=30, verbose_name=_('Passing Semester'))
    cgpa                = models.DecimalField(max_digits=4, decimal_places=2, verbose_name=_('CGPA'))
    result_date         = models.DateField(null=True, blank=True, verbose_name=_('Result Publication Date'))

    # Type-specific fields
    corrected_name          = models.CharField(max_length=200, blank=True, verbose_name=_('Corrected Student Name'))      # Type 4
    corrected_parent_name   = models.CharField(max_length=200, blank=True, verbose_name=_('Corrected Parent Name'))       # Type 5
    purpose_destination     = models.TextField(blank=True, verbose_name=_('Purpose / Destination'))                       # Type 6
    level_term              = models.CharField(max_length=30, blank=True, verbose_name=_('Level / Term'))                 # Type 7, 8
    missing_doc_type        = models.CharField(max_length=100, blank=True, verbose_name=_('Missing Document Type'))       # Type 8

    # Staff notes
    dept_head_note      = models.TextField(blank=True, verbose_name=_('Dept. Head Note'))
    processing_note     = models.TextField(blank=True, verbose_name=_('Processing Note'))
    rejection_reason    = models.TextField(blank=True, verbose_name=_('Rejection Reason'))

    # Delivery
    delivery_otp            = models.CharField(max_length=6, blank=True, verbose_name=_('Delivery OTP'))
    delivery_otp_verified   = models.BooleanField(default=False, verbose_name=_('OTP Verified'))
    delivered_at            = models.DateTimeField(null=True, blank=True, verbose_name=_('Delivered At'))
    delivered_by            = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coe_deliveries', verbose_name=_('Delivered By')
    )

    # Relationships
    submitted_by        = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coe_submissions', verbose_name=_('Submitted By')
    )
    assigned_to         = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coe_assignments', verbose_name=_('Assigned To (Processing Officer)')
    )

    # Flags & Timestamps
    is_deleted          = models.BooleanField(default=False, verbose_name=_('Soft Deleted'))
    submitted_at        = models.DateTimeField(auto_now_add=True, verbose_name=_('Submitted At'))
    updated_at          = models.DateTimeField(auto_now=True, verbose_name=_('Last Updated'))

    # Managers
    objects     = ActiveApplicationManager()
    all_objects = models.Manager()  # Includes soft-deleted records

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = _('Document Application')
        verbose_name_plural = _('Document Applications')
        indexes = [
            models.Index(fields=['status', 'submitted_at']),
            models.Index(fields=['student_id']),
            models.Index(fields=['application_number']),
        ]

    def __str__(self):
        return f"{self.application_number} — {self.get_application_type_display()} ({self.student_name})"

    def get_status_badge_class(self):
        """Returns Bootstrap badge class based on current status."""
        return {
            ApplicationStatus.SUBMITTED:              'badge-secondary',
            ApplicationStatus.UNDER_HOD_REVIEW:       'badge-info',
            ApplicationStatus.PENDING_COE_ASSIGNMENT: 'badge-warning',
            ApplicationStatus.IN_PROCESSING:          'badge-primary',
            ApplicationStatus.ACTION_REQUIRED:        'badge-danger',
            ApplicationStatus.READY_FOR_DELIVERY:     'badge-success',
            ApplicationStatus.DELIVERED:              'badge-dark',
            ApplicationStatus.REJECTED:               'badge-danger',
            ApplicationStatus.CANCELLED:              'badge-secondary',
        }.get(self.status, 'badge-secondary')

    def get_status_icon(self):
        return {
            ApplicationStatus.SUBMITTED:              'fas fa-paper-plane',
            ApplicationStatus.UNDER_HOD_REVIEW:       'fas fa-user-tie',
            ApplicationStatus.PENDING_COE_ASSIGNMENT: 'fas fa-hourglass-half',
            ApplicationStatus.IN_PROCESSING:          'fas fa-cogs',
            ApplicationStatus.ACTION_REQUIRED:        'fas fa-exclamation-circle',
            ApplicationStatus.READY_FOR_DELIVERY:     'fas fa-box-open',
            ApplicationStatus.DELIVERED:              'fas fa-check-circle',
            ApplicationStatus.REJECTED:               'fas fa-times-circle',
            ApplicationStatus.CANCELLED:              'fas fa-ban',
        }.get(self.status, 'fas fa-circle')

    @property
    def is_stalled(self):
        """Returns True if application has been in a non-terminal state for > 48 hours."""
        from django.utils import timezone
        import datetime
        terminal = {ApplicationStatus.DELIVERED, ApplicationStatus.REJECTED, ApplicationStatus.CANCELLED}
        if self.status in terminal:
            return False
        delta = timezone.now() - self.updated_at
        return delta > datetime.timedelta(hours=48)


# ──────────────────────────────────────────────────────────────────────────────
# Model 2 — ApplicationAttachment
# ──────────────────────────────────────────────────────────────────────────────

class ApplicationAttachment(models.Model):
    application     = models.ForeignKey(
        DocumentApplication, on_delete=models.CASCADE,
        related_name='attachments', verbose_name=_('Application')
    )
    attachment_type = models.CharField(
        max_length=30, choices=AttachmentType.choices,
        verbose_name=_('Attachment Type')
    )
    file            = models.FileField(upload_to='coe/attachments/', verbose_name=_('File'))
    sha256_hash     = models.CharField(max_length=64, blank=True, verbose_name=_('SHA-256 Hash'))
    original_filename = models.CharField(max_length=255, blank=True, verbose_name=_('Original Filename'))
    file_size_kb    = models.IntegerField(default=0, verbose_name=_('File Size (KB)'))
    is_purged       = models.BooleanField(default=False, verbose_name=_('File Purged'))
    uploaded_at     = models.DateTimeField(auto_now_add=True, verbose_name=_('Uploaded At'))

    class Meta:
        ordering = ['attachment_type', 'uploaded_at']
        verbose_name = _('Application Attachment')
        verbose_name_plural = _('Application Attachments')

    def __str__(self):
        return f"{self.get_attachment_type_display()} — {self.application.application_number}"


# ──────────────────────────────────────────────────────────────────────────────
# Model 3 — ApplicationStatusLog
# ──────────────────────────────────────────────────────────────────────────────

class ApplicationStatusLog(models.Model):
    application = models.ForeignKey(
        DocumentApplication, on_delete=models.CASCADE,
        related_name='status_logs', verbose_name=_('Application')
    )
    old_status  = models.CharField(max_length=30, blank=True, verbose_name=_('Previous Status'))
    new_status  = models.CharField(max_length=30, verbose_name=_('New Status'))
    changed_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coe_status_changes', verbose_name=_('Changed By')
    )
    note        = models.TextField(blank=True, verbose_name=_('Note'))
    sms_sent    = models.BooleanField(default=False, verbose_name=_('SMS Sent'))
    changed_at  = models.DateTimeField(auto_now_add=True, verbose_name=_('Changed At'))

    class Meta:
        ordering = ['changed_at']
        verbose_name = _('Status Log Entry')
        verbose_name_plural = _('Status Log Entries')

    def __str__(self):
        return f"{self.application.application_number}: {self.old_status} → {self.new_status}"


# ──────────────────────────────────────────────────────────────────────────────
# Model 4 — ProcessingVerification
# ──────────────────────────────────────────────────────────────────────────────

class ProcessingVerification(models.Model):
    application             = models.OneToOneField(
        DocumentApplication, on_delete=models.CASCADE,
        related_name='verification', verbose_name=_('Application')
    )
    # Admission portal data
    admission_api_fetched   = models.BooleanField(default=False, verbose_name=_('Admission API Fetched'))
    admission_api_data      = models.JSONField(null=True, blank=True, verbose_name=_('Admission API Data'))
    # Education board data
    board_api_fetched       = models.BooleanField(default=False, verbose_name=_('Board API Fetched'))
    board_api_data          = models.JSONField(null=True, blank=True, verbose_name=_('Board API Data'))
    board_roll              = models.CharField(max_length=30, blank=True, verbose_name=_('Board Roll'))
    board_registration      = models.CharField(max_length=30, blank=True, verbose_name=_('Board Registration'))
    board_name              = models.CharField(max_length=100, blank=True, verbose_name=_('Board Name'))
    board_year              = models.CharField(max_length=10, blank=True, verbose_name=_('Board Year'))
    # Officer notes
    verification_notes      = models.TextField(blank=True, verbose_name=_('Verification Notes'))
    verified_by             = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coe_verifications', verbose_name=_('Verified By')
    )
    verified_at             = models.DateTimeField(null=True, blank=True, verbose_name=_('Verified At'))

    class Meta:
        verbose_name = _('Processing Verification')
        verbose_name_plural = _('Processing Verifications')

    def __str__(self):
        return f"Verification for {self.application.application_number}"


# ──────────────────────────────────────────────────────────────────────────────
# Model 5 — CoeSettings  (singleton)
# ──────────────────────────────────────────────────────────────────────────────

class CoeSettings(models.Model):
    tracking_id_prefix      = models.CharField(max_length=10, default='APP', verbose_name=_('Tracking ID Prefix'))
    sms_notify_submit       = models.BooleanField(default=True, verbose_name=_('SMS on Submission'))
    sms_notify_approved     = models.BooleanField(default=True, verbose_name=_('SMS on HoD Approval'))
    sms_notify_ready        = models.BooleanField(default=True, verbose_name=_('SMS When Ready for Delivery'))
    sms_delivery_otp        = models.BooleanField(default=True, verbose_name=_('SMS Delivery OTP'))
    attachment_max_mb       = models.IntegerField(default=2, verbose_name=_('Max Attachment Size (MB)'))
    rejected_purge_days     = models.IntegerField(default=15, verbose_name=_('Rejected File Purge (days)'))
    delivered_purge_days    = models.IntegerField(default=90, verbose_name=_('Delivered File Purge (days)'))
    enable_auto_assignment  = models.BooleanField(default=False, verbose_name=_('Enable Auto Assignment'))
    updated_at              = models.DateTimeField(auto_now=True, verbose_name=_('Last Updated'))

    class Meta:
        verbose_name = _('CoE Settings')
        verbose_name_plural = _('CoE Settings')

    def __str__(self):
        return f"CoE Settings (prefix: {self.tracking_id_prefix})"

    def save(self, *args, **kwargs):
        """Enforce singleton — only one settings record allowed."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ──────────────────────────────────────────────────────────────────────────────
# Model 6 — CoeAssignmentRule
# ──────────────────────────────────────────────────────────────────────────────

class CoeAssignmentRule(models.Model):
    application_type = models.CharField(
        max_length=50,
        choices=ApplicationType.choices,
        unique=True,
        verbose_name=_('Application Type')
    )
    officer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='coe_assignment_rules',
        verbose_name=_('Assigned Officer')
    )

    class Meta:
        verbose_name = _('CoE Assignment Rule')
        verbose_name_plural = _('CoE Assignment Rules')

    def __str__(self):
        return f"{self.get_application_type_display()} -> {self.officer.username}"

