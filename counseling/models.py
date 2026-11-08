"""
counseling/models.py
====================
Data models for the University Psychological Counseling & Student Wellbeing Module.
Implements clinical cases, appointments, SOAP session records, psychometric assessments,
emergency interventions, workshops, and singleton settings.
"""

from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from students.models import Student
from master_data.models import Program, Hall
import datetime


# ============================================================================
# Enumerations & Choices (TextChoices)
# ============================================================================

class CaseCategory(models.TextChoices):
    ACADEMIC_STRESS   = 'academic_stress',   _('Academic Stress & Performance')
    EXAM_ANXIETY      = 'exam_anxiety',      _('Exam & Test Anxiety')
    HALL_HOMESICK     = 'hall_homesick',     _('Hall Life & Homesickness')
    FAMILY_RELATIONS  = 'family_relations',  _('Family & Relationship Dynamics')
    GRIEF_TRAUMA      = 'grief_trauma',      _('Grief, Loss & Trauma')
    SUBSTANCE         = 'substance',         _('Habit & Substance Intervention')
    CAREER_ESTEEM     = 'career_esteem',     _('Career Uncertainty & Self-Esteem')
    OTHER             = 'other',             _('Other (See Notes)')


class RiskLevel(models.TextChoices):
    LOW      = 'low',      _('Low — General Wellbeing')
    MODERATE = 'moderate', _('Moderate — Requires Monitoring')
    HIGH     = 'high',     _('High — Priority Intervention')
    CRITICAL = 'critical', _('Critical / Acute Crisis')


class CaseStatus(models.TextChoices):
    OPEN        = 'open',        _('Open — Initial Intake')
    IN_THERAPY  = 'in_therapy',  _('In Therapy — Active Sessions')
    ON_HOLD     = 'on_hold',     _('On Hold — Pending Follow-up')
    REFERRED    = 'referred',    _('Referred Out — Medical/Psychiatric')
    DISCHARGED  = 'discharged',  _('Completed & Discharged')


class AppointmentMode(models.TextChoices):
    IN_PERSON = 'in_person', _('In-Person (Counseling Center)')
    TELE_CONF = 'tele_conf', _('Confidential Tele-Counseling')
    EMERGENCY = 'emergency', _('Urgent Crisis Walk-in')


class AppointmentStatus(models.TextChoices):
    REQUESTED   = 'requested',   _('Requested')
    CONFIRMED   = 'confirmed',   _('Confirmed')
    COMPLETED   = 'completed',   _('Completed')
    RESCHEDULED = 'rescheduled', _('Rescheduled')
    CANCELLED   = 'cancelled',   _('Cancelled')
    NO_SHOW     = 'no_show',     _('No Show')


class ReferralSource(models.TextChoices):
    SELF            = 'self',            _('Self-Booking (Student Portal)')
    HALL_PROVOST    = 'hall_provost',    _('Hall Provost / Residential Wing')
    DEPT_ADVISOR    = 'dept_advisor',    _('Department Head / Academic Advisor')
    PROCTORIAL      = 'proctorial',      _('Proctorial Body')
    MEDICAL_CENTER  = 'medical_center',  _('University Medical Center / Doctor')


class AssessmentType(models.TextChoices):
    PHQ9   = 'PHQ9',   _('PHQ-9 (Depression Screener)')
    GAD7   = 'GAD7',   _('GAD-7 (Anxiety Screener)')
    DASS21 = 'DASS21', _('DASS-21 (Depression, Anxiety, Stress Scale)')


# ============================================================================
# Model Managers
# ============================================================================

class ActiveCaseManager(models.Manager):
    """Excludes soft-deleted cases from default querysets."""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# ============================================================================
# Model 1: CounselingSettings (Singleton)
# ============================================================================

class CounselingSettings(models.Model):
    enable_sms_notifications        = models.BooleanField(default=True, verbose_name=_('Enable SMS Notifications'))
    sms_template_appointment_confirm = models.CharField(
        max_length=500,
        default='Your counseling session is confirmed for {date} at {time} in Room {room}. BAUST Counseling Center.',
        verbose_name=_('SMS: Appointment Confirmation')
    )
    sms_template_crisis_alert       = models.CharField(
        max_length=500,
        default='Urgent counseling check-in requested for student {student_id}. Case ID: {case_number}.',
        verbose_name=_('SMS: Crisis Alert')
    )
    session_lock_hours              = models.IntegerField(default=24, verbose_name=_('SOAP Note Edit Window (Hours)'))
    crisis_sla_hours                = models.IntegerField(default=2, verbose_name=_('Crisis Response SLA (Hours)'))
    default_slot_duration_minutes   = models.IntegerField(default=50, verbose_name=_('Default Slot Length (Minutes)'))
    counselor_room_default          = models.CharField(max_length=50, default='Room 204', verbose_name=_('Default Room'))
    updated_at                      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Counseling Settings')
        verbose_name_plural = _('Counseling Settings')

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Counseling System Settings"


# ============================================================================
# Model 2: CounselorProfile
# ============================================================================

class CounselorProfile(models.Model):
    user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name='counselor_profile')
    designation         = models.CharField(max_length=150, default='Clinical Psychologist', verbose_name=_('Designation'))
    license_number      = models.CharField(max_length=100, blank=True, verbose_name=_('License / Registration No.'))
    room_number         = models.CharField(max_length=50, default='Room 204', verbose_name=_('Chamber / Room'))
    contact_number      = models.CharField(max_length=20, blank=True, verbose_name=_('Official Contact'))
    is_active_counselor = models.BooleanField(default=True, verbose_name=_('Is Available for Sessions'))
    weekly_slots_json   = models.JSONField(default=dict, blank=True, help_text=_('Available weekday time slots JSON'))
    bio                 = models.TextField(blank=True, verbose_name=_('Biography / Specialization'))
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Counselor Profile')
        verbose_name_plural = _('Counselor Profiles')

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f"{name} ({self.designation})"

    def get_default_slots(self):
        """Returns standard consultation hours if custom JSON not set."""
        if self.weekly_slots_json:
            if isinstance(self.weekly_slots_json, dict):
                return self.weekly_slots_json
            if isinstance(self.weekly_slots_json, str):
                try:
                    parsed = json.loads(self.weekly_slots_json)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
        return {
            "Sunday":    ["09:00 AM - 09:50 AM", "10:00 AM - 10:50 AM", "11:00 AM - 11:50 AM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM"],
            "Monday":    ["09:00 AM - 09:50 AM", "10:00 AM - 10:50 AM", "11:00 AM - 11:50 AM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM"],
            "Tuesday":   ["09:00 AM - 09:50 AM", "10:00 AM - 10:50 AM", "11:00 AM - 11:50 AM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM"],
            "Wednesday": ["09:00 AM - 09:50 AM", "10:00 AM - 10:50 AM", "11:00 AM - 11:50 AM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM"],
            "Thursday":  ["09:00 AM - 09:50 AM", "10:00 AM - 10:50 AM", "11:00 AM - 11:50 AM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM"],
        }


# ============================================================================
# Model 3: CounselingCase
# ============================================================================

class CounselingCase(models.Model):
    case_number         = models.CharField(max_length=30, unique=True, editable=False, db_index=True, verbose_name=_('Case ID'))
    student             = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='counseling_cases', verbose_name=_('Student'))
    alias_code          = models.CharField(max_length=50, blank=True, null=True, help_text=_('Pseudonym for confidential referral'))
    category            = models.CharField(max_length=30, choices=CaseCategory.choices, default=CaseCategory.ACADEMIC_STRESS, db_index=True, verbose_name=_('Primary Concern'))
    risk_level          = models.CharField(max_length=20, choices=RiskLevel.choices, default=RiskLevel.LOW, db_index=True, verbose_name=_('Risk Stratification'))
    status              = models.CharField(max_length=20, choices=CaseStatus.choices, default=CaseStatus.OPEN, db_index=True, verbose_name=_('Case Status'))
    assigned_counselor  = models.ForeignKey(CounselorProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_cases', verbose_name=_('Assigned Psychologist'))
    intake_date         = models.DateField(default=timezone.localdate, db_index=True, verbose_name=_('Intake Date'))
    
    # Clinical Intake Notes
    presenting_complaints = models.TextField(verbose_name=_('Presenting Complaints & History'))
    sleep_appetite_notes = models.TextField(blank=True, verbose_name=_('Sleep & Appetite Patterns'))
    family_social_notes  = models.TextField(blank=True, verbose_name=_('Family & Social Background'))
    medication_history   = models.TextField(blank=True, verbose_name=_('Psychiatric / Medication History'))
    
    # Soft Delete & Audit
    is_deleted          = models.BooleanField(default=False, db_index=True, verbose_name=_('Is Soft Deleted'))
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_counseling_cases')
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    objects     = ActiveCaseManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-intake_date', '-created_at']
        verbose_name = _('Counseling Case')
        verbose_name_plural = _('Counseling Cases')

    def save(self, *args, **kwargs):
        if not self.case_number:
            year = datetime.date.today().year
            with transaction.atomic():
                max_id = CounselingCase.all_objects.select_for_update().aggregate(models.Max('id'))['id__max'] or 0
                seq = max_id + 1
                candidate = f"CASE-{year}-{seq:04d}"
                while CounselingCase.all_objects.filter(case_number=candidate).exists():
                    seq += 1
                    candidate = f"CASE-{year}-{seq:04d}"
                self.case_number = candidate
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        name = self.alias_code if self.alias_code else self.student.student_name
        return f"{self.case_number} — {name} ({self.get_category_display()})"

    def get_risk_badge_class(self):
        return {
            RiskLevel.LOW:      'badge-success',
            RiskLevel.MODERATE: 'badge-warning',
            RiskLevel.HIGH:     'badge-orange',
            RiskLevel.CRITICAL: 'badge-danger pulse-danger',
        }.get(self.risk_level, 'badge-secondary')

    def get_status_badge_class(self):
        return {
            CaseStatus.OPEN:       'badge-info',
            CaseStatus.IN_THERAPY: 'badge-primary',
            CaseStatus.ON_HOLD:    'badge-warning',
            CaseStatus.REFERRED:   'badge-secondary',
            CaseStatus.DISCHARGED: 'badge-success',
        }.get(self.status, 'badge-secondary')


# ============================================================================
# Model 4: CaseStatusLog (Clinical Audit Trail)
# ============================================================================

class CaseStatusLog(models.Model):
    case        = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='status_logs')
    old_status  = models.CharField(max_length=30, blank=True)
    new_status  = models.CharField(max_length=30)
    changed_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    note        = models.TextField(blank=True, verbose_name=_('Reason / Clinical Transition Note'))
    changed_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name = _('Case Status Log')
        verbose_name_plural = _('Case Status Logs')

    def __str__(self):
        return f"{self.case.case_number}: {self.old_status} ➔ {self.new_status}"


# ============================================================================
# Model 5: CounselingAppointment
# ============================================================================

class CounselingAppointment(models.Model):
    case                = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='appointments')
    counselor           = models.ForeignKey(CounselorProfile, on_delete=models.CASCADE, related_name='appointments')
    appointment_date    = models.DateField(db_index=True, verbose_name=_('Appointment Date'))
    time_slot           = models.CharField(max_length=50, verbose_name=_('Time Slot'))
    session_mode        = models.CharField(max_length=20, choices=AppointmentMode.choices, default=AppointmentMode.IN_PERSON, verbose_name=_('Mode'))
    referral_source     = models.CharField(max_length=30, choices=ReferralSource.choices, default=ReferralSource.SELF, verbose_name=_('Referral Source'))
    status              = models.CharField(max_length=20, choices=AppointmentStatus.choices, default=AppointmentStatus.CONFIRMED, db_index=True, verbose_name=_('Status'))
    student_notes       = models.TextField(blank=True, verbose_name=_('Student Notes / Requests'))
    contact_mobile      = models.CharField(max_length=20, blank=True, verbose_name=_('Contact Mobile for Session/SMS'))
    secret_token        = models.CharField(max_length=50, blank=True, null=True, unique=True, db_index=True, verbose_name=_('Secret Tracking Token'))
    sms_reminder_sent   = models.BooleanField(default=False)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    @staticmethod
    def generate_secret_token():
        import random, string
        year = timezone.now().year
        chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ' # Exclude easily confused chars (0,1,O,I)
        for _ in range(20):
            token = f"CARE-{year}-{''.join(random.choices(chars, k=5))}"
            if not CounselingAppointment.objects.filter(secret_token=token).exists():
                return token
        return f"CARE-{year}-{''.join(random.choices(chars, k=7))}"

    def save(self, *args, **kwargs):
        if not self.secret_token:
            self.secret_token = self.generate_secret_token()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-appointment_date', 'time_slot']
        unique_together = ('counselor', 'appointment_date', 'time_slot')
        verbose_name = _('Counseling Appointment')
        verbose_name_plural = _('Counseling Appointments')

    def __str__(self):
        return f"{self.case.case_number} | {self.appointment_date} at {self.time_slot}"

    def get_status_badge_class(self):
        return {
            AppointmentStatus.REQUESTED:   'badge-warning',
            AppointmentStatus.CONFIRMED:   'badge-info',
            AppointmentStatus.COMPLETED:   'badge-success',
            AppointmentStatus.RESCHEDULED: 'badge-secondary',
            AppointmentStatus.CANCELLED:   'badge-danger',
            AppointmentStatus.NO_SHOW:     'badge-dark',
        }.get(self.status, 'badge-secondary')


# ============================================================================
# Model 6: SessionRecord (SOAP Clinical Notes)
# ============================================================================

class SessionRecord(models.Model):
    case                = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='session_records')
    appointment         = models.ForeignKey(CounselingAppointment, on_delete=models.SET_NULL, null=True, blank=True, related_name='session_record')
    session_number      = models.PositiveIntegerField(default=1, verbose_name=_('Session No.'))
    session_date        = models.DateField(default=timezone.localdate, db_index=True, verbose_name=_('Session Date'))
    
    # 4-Quadrant SOAP Structure
    subjective_notes    = models.TextField(verbose_name=_('Subjective (S) — Client Narrative & Reported Feelings'))
    objective_notes     = models.TextField(verbose_name=_('Objective (O) — Behavioral & Affect Observations'))
    assessment          = models.TextField(verbose_name=_('Assessment (A) — Diagnostic Formulation & Progress'))
    plan                = models.TextField(verbose_name=_('Plan (P) — Therapeutic Interventions & Homework'))
    
    next_session_date   = models.DateField(null=True, blank=True, verbose_name=_('Next Follow-up Date'))
    is_locked           = models.BooleanField(default=False, verbose_name=_('Is Record Locked'))
    locked_at           = models.DateTimeField(null=True, blank=True)
    recorded_by         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-session_date', '-session_number']
        verbose_name = _('Session Record (SOAP)')
        verbose_name_plural = _('Session Records (SOAP)')

    def __str__(self):
        return f"{self.case.case_number} — Session #{self.session_number} ({self.session_date})"

    def save(self, *args, **kwargs):
        if not self.session_number and self.case_id:
            count = SessionRecord.objects.filter(case_id=self.case_id).count()
            self.session_number = count + 1
        super().save(*args, **kwargs)


# ============================================================================
# Model 7: MentalHealthAssessment (PHQ-9 / GAD-7 / DASS-21)
# ============================================================================

class MentalHealthAssessment(models.Model):
    case                = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='assessments')
    assessment_type     = models.CharField(max_length=10, choices=AssessmentType.choices, db_index=True, verbose_name=_('Scale Type'))
    item_responses      = models.JSONField(default=dict, verbose_name=_('Item Responses JSON'))
    total_score         = models.IntegerField(default=0, verbose_name=_('Total Score'))
    sub_scores          = models.JSONField(default=dict, blank=True, verbose_name=_('Subscale Scores JSON'))
    severity_tier       = models.CharField(max_length=50, verbose_name=_('Severity Tier'))
    assessed_date       = models.DateField(default=timezone.localdate, db_index=True, verbose_name=_('Assessment Date'))
    administered_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes               = models.TextField(blank=True, verbose_name=_('Clinical Notes / Interpretation'))
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assessed_date', '-created_at']
        verbose_name = _('Mental Health Assessment')
        verbose_name_plural = _('Mental Health Assessments')

    def __str__(self):
        return f"{self.case.case_number} — {self.get_assessment_type_display()}: {self.total_score} ({self.severity_tier})"

    def get_severity_badge_class(self):
        lowered = self.severity_tier.lower()
        if 'minimal' in lowered or 'normal' in lowered:
            return 'badge-success'
        elif 'mild' in lowered:
            return 'badge-info'
        elif 'moderate' in lowered:
            return 'badge-warning'
        elif 'severe' in lowered or 'extremely' in lowered:
            return 'badge-danger'
        return 'badge-secondary'


# ============================================================================
# Model 8: EmergencyIntervention
# ============================================================================

class EmergencyIntervention(models.Model):
    case                = models.ForeignKey(CounselingCase, on_delete=models.CASCADE, related_name='emergency_interventions')
    incident_date       = models.DateTimeField(default=timezone.now, verbose_name=_('Incident Timestamp'))
    incident_type       = models.CharField(max_length=100, verbose_name=_('Crisis Nature (e.g. Suicidal Ideation, Panic, Self-Harm)'))
    actions_taken       = models.TextField(verbose_name=_('Immediate Actions Taken'))
    medical_referral_made = models.BooleanField(default=False, verbose_name=_('Referred to Medical Center / Hospital'))
    hospital_name       = models.CharField(max_length=200, blank=True, verbose_name=_('Hospital / Facility Name (e.g. CMH)'))
    authorities_notified = models.TextField(blank=True, verbose_name=_('Authorities & Guardians Notified'))
    safety_contract_signed = models.BooleanField(default=False, verbose_name=_('Safety Contract Signed'))
    resolved            = models.BooleanField(default=False, db_index=True, verbose_name=_('Is Crisis Resolved'))
    resolution_notes    = models.TextField(blank=True, verbose_name=_('Resolution / Follow-up Notes'))
    logged_by           = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-incident_date']
        verbose_name = _('Emergency Intervention')
        verbose_name_plural = _('Emergency Interventions')

    def __str__(self):
        return f"CRISIS: {self.case.case_number} on {self.incident_date.strftime('%Y-%m-%d %H:%M')}"


# ============================================================================
# Model 9 & 10: WellbeingWorkshop & Participant
# ============================================================================

class WellbeingWorkshop(models.Model):
    title               = models.CharField(max_length=255, verbose_name=_('Workshop Title'))
    speaker             = models.CharField(max_length=200, verbose_name=_('Speaker / Facilitator'))
    venue               = models.CharField(max_length=200, verbose_name=_('Venue / Hall'))
    event_date          = models.DateField(db_index=True, verbose_name=_('Event Date'))
    start_time          = models.TimeField(null=True, blank=True, verbose_name=_('Start Time'))
    target_audience     = models.CharField(max_length=200, verbose_name=_('Target Audience (e.g. Batch 25, Resident Students)'))
    description         = models.TextField(blank=True, verbose_name=_('Description / Objectives'))
    capacity            = models.PositiveIntegerField(default=100, verbose_name=_('Max Capacity'))
    is_cancelled        = models.BooleanField(default=False)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-event_date']
        verbose_name = _('Wellbeing Workshop')
        verbose_name_plural = _('Wellbeing Workshops')

    def __str__(self):
        return f"{self.title} ({self.event_date})"

    @property
    def registered_count(self):
        return self.participants.count()


class WellbeingWorkshopParticipant(models.Model):
    workshop            = models.ForeignKey(WellbeingWorkshop, on_delete=models.CASCADE, related_name='participants')
    student             = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='wellness_workshops')
    registered_at       = models.DateTimeField(auto_now_add=True)
    attended            = models.BooleanField(default=False, verbose_name=_('Attended Event'))

    class Meta:
        unique_together = ('workshop', 'student')
        verbose_name = _('Workshop Participant')
        verbose_name_plural = _('Workshop Participants')

    def __str__(self):
        return f"{self.student.student_name} ➔ {self.workshop.title}"
