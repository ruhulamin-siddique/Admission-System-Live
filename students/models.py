from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError

class ReferenceNode(models.Model):
    reference_id = models.CharField(max_length=50, unique=True, db_index=True, blank=True)
    baust_id = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    name_en = models.CharField(max_length=255)
    name_bn = models.CharField(max_length=255, blank=True, null=True)
    designation = models.CharField(max_length=255, blank=True, null=True)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    category = models.CharField(
        max_length=20, 
        choices=[('Employee', 'Employee'), ('External', 'External')], 
        default='Employee'
    )
    is_verified = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.reference_id:
            from django.db import transaction
            with transaction.atomic():
                max_id = ReferenceNode.objects.select_for_update().aggregate(models.Max('id'))['id__max'] or 0
                next_id = max_id + 1
                ref_id = f"REF-{next_id:05d}"
                while ReferenceNode.objects.filter(reference_id=ref_id).exists():
                    next_id += 1
                    ref_id = f"REF-{next_id:05d}"
                self.reference_id = ref_id
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        parts = [self.name_en]
        if self.designation:
            parts.append(self.designation)
        if self.baust_id:
            parts.append(self.baust_id)
        return " - ".join(parts)

RESULT_SYSTEM_CHOICES = [
    ('GPA', 'GPA System (Scale 5.00)'),
    ('DIVISION', 'Division System (Pre-GPA)'),
]

DIVISION_CHOICES = [
    ('FIRST_STAR', '1st Division with Star Marks (≥75%)'),
    ('FIRST', '1st Division (≥60%)'),
    ('SECOND', '2nd Division (45%–59%)'),
    ('THIRD', '3rd Division (33%–44%)'),
    ('PASS', 'Pass / Compartmental'),
]

class Student(models.Model):
    # Core Identification
    student_id = models.CharField(max_length=50, primary_key=True, help_text="UGC Compliant ID")
    student_name = models.CharField(max_length=255)
    old_student_id = models.CharField(max_length=50, null=True, blank=True)
    is_legacy_student = models.BooleanField(
        default=False,
        help_text="True for pre-digital-era students (Batch 1–12) added retrospectively with their original 9-digit ID."
    )
    
    # Academic Info
    program = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    admission_year = models.IntegerField(null=True, blank=True)
    cluster = models.CharField(max_length=50, null=True, blank=True)
    batch = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    batch_number = models.IntegerField(null=True, blank=True, help_text="Auto-extracted for numeric sorting")
    current_batch = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    semester_name = models.CharField(max_length=50, null=True, blank=True)
    current_semester = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    program_type = models.CharField(max_length=50, null=True, blank=True)
    admission_date = models.DateField(null=True, blank=True, db_index=True)
    admission_status = models.CharField(max_length=50, default="Active", db_index=True)
    
    # Personal Info
    gender = models.CharField(max_length=20, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=10, null=True, blank=True)
    religion = models.CharField(max_length=50, null=True, blank=True)
    national_id = models.CharField(max_length=50, null=True, blank=True)
    
    # Family Info
    father_name = models.CharField(max_length=255, null=True, blank=True)
    mother_name = models.CharField(max_length=255, null=True, blank=True)
    father_occupation = models.CharField(max_length=100, null=True, blank=True)
    
    # Contact Info
    student_mobile = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    father_mobile = models.CharField(max_length=20, null=True, blank=True)
    mother_mobile = models.CharField(max_length=20, null=True, blank=True)
    student_email = models.EmailField(null=True, blank=True)
    emergency_contact = models.CharField(max_length=255, null=True, blank=True)
    
    # Addresses (Legacy Text)
    present_address = models.TextField(null=True, blank=True)
    permanent_address = models.TextField(null=True, blank=True)
    
    # Structured Address Components
    present_division = models.CharField(max_length=50, null=True, blank=True)
    present_district = models.CharField(max_length=50, null=True, blank=True)
    present_upazila = models.CharField(max_length=50, null=True, blank=True)
    present_village = models.CharField(max_length=255, null=True, blank=True)
    
    permanent_division = models.CharField(max_length=50, null=True, blank=True)
    permanent_district = models.CharField(max_length=50, null=True, blank=True)
    permanent_upazila = models.CharField(max_length=50, null=True, blank=True)
    permanent_village = models.CharField(max_length=255, null=True, blank=True)
    
    # Academic History (SSC)
    ssc_system = models.CharField(
        max_length=10,
        choices=RESULT_SYSTEM_CHOICES,
        default='GPA',
        blank=True,
        help_text="Evaluation system: GPA (post-2001) or Division (pre-GPA era)."
    )
    ssc_school = models.CharField(max_length=255, null=True, blank=True)
    ssc_year = models.CharField(max_length=10, null=True, blank=True)
    ssc_board = models.CharField(max_length=50, null=True, blank=True)
    ssc_roll = models.CharField(max_length=50, null=True, blank=True)
    ssc_reg = models.CharField(max_length=50, null=True, blank=True)
    ssc_division = models.CharField(
        max_length=20,
        choices=DIVISION_CHOICES,
        null=True,
        blank=True,
        help_text="For pre-GPA students: 1st, 2nd, 3rd Division or Pass."
    )
    ssc_marks = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total marks obtained in SSC (out of 1000 for pre-GPA)."
    )
    ssc_gpa = models.FloatField(null=True, blank=True)
    ssc_physics = models.FloatField(null=True, blank=True)
    ssc_chemistry = models.FloatField(null=True, blank=True)
    ssc_math = models.FloatField(null=True, blank=True)
    
    # Academic History (HSC)
    hsc_system = models.CharField(
        max_length=10,
        choices=RESULT_SYSTEM_CHOICES,
        default='GPA',
        blank=True,
        help_text="Evaluation system: GPA (post-2003) or Division (pre-GPA era)."
    )
    hsc_college = models.CharField(max_length=255, null=True, blank=True)
    hsc_year = models.CharField(max_length=10, null=True, blank=True)
    hsc_board = models.CharField(max_length=50, null=True, blank=True)
    hsc_roll = models.CharField(max_length=50, null=True, blank=True)
    hsc_reg = models.CharField(max_length=50, null=True, blank=True)
    hsc_division = models.CharField(
        max_length=20,
        choices=DIVISION_CHOICES,
        null=True,
        blank=True,
        help_text="For pre-GPA students: 1st, 2nd, 3rd Division or Pass."
    )
    hsc_marks = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total marks obtained in HSC (out of 1000 for pre-GPA)."
    )
    hsc_gpa = models.FloatField(null=True, blank=True)
    hsc_physics = models.FloatField(null=True, blank=True)
    hsc_chemistry = models.FloatField(null=True, blank=True)
    hsc_math = models.FloatField(null=True, blank=True)
    
    # Financial & Status
    hall_attached = models.CharField(max_length=100, null=True, blank=True)
    hall_residential = models.ForeignKey('master_data.Hall', on_delete=models.SET_NULL, null=True, blank=True, related_name='residents', help_text="The actual hall where the student physically resides.")
    is_non_residential = models.BooleanField(default=False)
    admission_payment = models.FloatField(null=True, blank=True, default=0.0)
    second_installment = models.FloatField(null=True, blank=True, default=0.0)
    waiver = models.FloatField(null=True, blank=True, default=0.0)
    others = models.FloatField(null=True, blank=True, default=0.0)
    
    # Additional Fees Tracking (Medical/BNCC/Scout & Uniform)
    medical_scout_paid = models.BooleanField(default=False, db_index=True)
    medical_scout_amount = models.FloatField(default=0.0, blank=True)
    medical_scout_receipt = models.CharField(max_length=100, blank=True, null=True)
    medical_scout_date = models.DateField(blank=True, null=True)
    
    uniform_status = models.CharField(
        max_length=30,
        choices=[
            ('OPTED_OUT', 'Opted Out (Outside Preparation)'),
            ('PAID', 'Opted In - Paid'),
            ('PARTIAL', 'Opted In - Partial Paid'),
            ('DUE', 'Opted In - Due / Pending')
        ],
        default='OPTED_OUT',
        blank=True,
        db_index=True
    )
    uniform_package = models.CharField(max_length=100, blank=True, null=True)
    uniform_amount = models.FloatField(default=0.0, blank=True)
    uniform_paid_amount = models.FloatField(default=0.0, blank=True)
    uniform_receipt = models.CharField(max_length=100, blank=True, null=True)
    uniform_date = models.DateField(blank=True, null=True)
    uniform_remarks = models.CharField(max_length=255, blank=True, null=True)
    
    # Miscellaneous Flags
    reference_legacy = models.CharField(max_length=255, null=True, blank=True)
    reference = models.ForeignKey(ReferenceNode, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    referred_by_student = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_students', help_text="Referrer if they are an existing student")
    remarks = models.TextField(null=True, blank=True)
    is_temp_admission_cancel = models.BooleanField(default=False)
    is_credit_transfer = models.BooleanField(default=False)
    is_armed_forces_child = models.BooleanField(default=False)
    is_freedom_fighter_child = models.BooleanField(default=False)
    is_july_joddha_2024 = models.BooleanField(default=False)
    
    # Metadata
    photo_path = models.CharField(max_length=255, null=True, blank=True)
    mba_credits = models.IntegerField(null=True, blank=True)
    # Academic Board Verification
    ssc_verified = models.BooleanField(default=False)
    hsc_verified = models.BooleanField(default=False)
    academic_verification_logs = models.JSONField(default=dict, blank=True) # Stores Board Name, Official GPA, Match Status, etc.

    # BTEB (Technical Board) Verification
    bteb_curriculum = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="BTEB Curriculum code+name, e.g. '27 - SSC (Vocational)' or '10 - Diploma in Engineering'"
    )
    bteb_semester = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="BTEB Semester/Class number, e.g. '1', '4', '8'"
    )
    bteb_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-sync physical hall_residential if attached hall is set and physical is empty
        if not self.is_non_residential and self.hall_attached and not self.hall_residential_id:
            from master_data.models import Hall
            hall_obj = Hall.objects.filter(short_name=self.hall_attached).first()
            if hall_obj:
                self.hall_residential = hall_obj
        elif self.is_non_residential:
            self.hall_residential = None

        # Auto-detect legacy student status (batch 1-12 or short ID)
        is_legacy = False
        if self.is_legacy_student:
            is_legacy = True
        if self.student_id and len(str(self.student_id).strip()) < 16:
            is_legacy = True
        if self.batch:
            import re
            nums = re.findall(r'\d+', self.batch)
            if nums:
                batch_num = int(nums[0])
                if 1 <= batch_num <= 12:
                    is_legacy = True
        if is_legacy:
            self.is_legacy_student = True

        # Auto-normalize program to canonical short name if available
        if self.program:
            from .utils import get_canonical_program_name
            self.program = get_canonical_program_name(self.program)

        # Auto-populate current_batch if null/blank
        if not self.current_batch:
            self.current_batch = self.batch

        # Auto-populate current_semester if null/blank
        if not self.current_semester:
            self.current_semester = 'Level 1 Term I'

        # Auto-extract numeric batch number for sorting
        if self.batch:
            import re
            nums = re.findall(r'\d+', self.batch)
            if nums:
                self.batch_number = int(nums[0])
            else:
                self.batch_number = 0

        # Auto-sync structured address to legacy text if provided
        def _build_address(v, u, d, div):
            parts = [p for p in [v, u, d, div] if p]
            return ", ".join(parts) if parts else None

        if self.present_division or self.present_district:
            addr = _build_address(self.present_village, self.present_upazila, self.present_district, self.present_division)
            if addr: self.present_address = addr

        if self.permanent_division or self.permanent_district:
            addr = _build_address(self.permanent_village, self.permanent_upazila, self.permanent_district, self.permanent_division)
            if addr: self.permanent_address = addr

        # Auto-populate admission_date if null
        if not self.admission_date:
            self.admission_date = timezone.localdate()

        # Auto-clean Roll, Reg, Year (remove .0 from floats)
        def _clean_val(v):
            if v is None: return None
            s = str(v).strip()
            if s.endswith('.0'):
                return s[:-2]
            return s

        self.ssc_roll = _clean_val(self.ssc_roll)
        self.ssc_reg = _clean_val(self.ssc_reg)
        self.ssc_year = _clean_val(self.ssc_year)
        self.hsc_roll = _clean_val(self.hsc_roll)
        self.hsc_reg = _clean_val(self.hsc_reg)
        self.hsc_year = _clean_val(self.hsc_year)

        # Capture and log detailed changes (if update)
        is_update = False
        field_changes = []
        if self.pk:
            try:
                orig = Student.objects.get(pk=self.pk)
                is_update = True
                if not self.created_at and orig.created_at:
                    self.created_at = orig.created_at
                
                # Exclude field list
                exclude_fields = ['last_updated', 'created_at', 'academic_verification_logs']
                
                for field in self._meta.fields:
                    if field.name in exclude_fields:
                        continue
                    
                    old_val = getattr(orig, field.name)
                    new_val = getattr(self, field.name)
                    
                    # Normalize comparison (None vs. empty string, string vs float representation)
                    def normalize_val(val):
                        if val is None:
                            return ""
                        return str(val).strip()
                        
                    if normalize_val(old_val) != normalize_val(new_val):
                        # Save string representations of values
                        field_changes.append({
                            'field_name': field.name,
                            'old_value': str(old_val) if old_val is not None else None,
                            'new_value': str(new_val) if new_val is not None else None,
                        })
            except Student.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if is_update and field_changes:
            from core.middleware import get_current_request
            request = get_current_request()
            
            ip = None
            ua = None
            changed_by_user = getattr(self, 'changed_by_user', None)
            
            if request:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0].strip()
                else:
                    ip = request.META.get('REMOTE_ADDR')
                ua = request.META.get('HTTP_USER_AGENT')
                
                if not changed_by_user and request.user and request.user.is_authenticated:
                    changed_by_user = request.user

            history_objs = [
                StudentFieldHistory(
                    student=self,
                    field_name=change['field_name'],
                    old_value=change['old_value'],
                    new_value=change['new_value'],
                    changed_by=changed_by_user,
                    ip_address=ip,
                    user_agent=ua
                ) for change in field_changes
            ]
            StudentFieldHistory.objects.bulk_create(history_objs)

    def __str__(self):
        return f"{self.student_name} ({self.student_id})"

    def get_ssc_result_display_full(self):
        """Returns human-friendly SSC result regardless of GPA or Division system."""
        if self.ssc_system == 'DIVISION':
            div = self.get_ssc_division_display() or self.ssc_division or 'Division System'
            marks_str = f" ({self.ssc_marks}/1000)" if self.ssc_marks else ""
            equiv_str = f" [Equiv. GPA: {self.ssc_gpa:.2f}]" if self.ssc_gpa is not None else ""
            return f"{div}{marks_str}{equiv_str}"
        return f"GPA {self.ssc_gpa:.2f}" if self.ssc_gpa is not None else "N/A"

    def get_hsc_result_display_full(self):
        """Returns human-friendly HSC result regardless of GPA or Division system."""
        if self.hsc_system == 'DIVISION':
            div = self.get_hsc_division_display() or self.hsc_division or 'Division System'
            marks_str = f" ({self.hsc_marks}/1000)" if self.hsc_marks else ""
            equiv_str = f" [Equiv. GPA: {self.hsc_gpa:.2f}]" if self.hsc_gpa is not None else ""
            return f"{div}{marks_str}{equiv_str}"
        return f"GPA {self.hsc_gpa:.2f}" if self.hsc_gpa is not None else "N/A"

    @property
    def photo_url(self):
        if not self.photo_path:
            return None

        photo = str(self.photo_path).strip()
        if not photo:
            return None

        if photo.startswith(('http://', 'https://', '/')):
            return photo

        media_url = settings.MEDIA_URL or '/media/'
        normalized_media = media_url.strip('/')
        normalized_photo = photo.lstrip('/')

        if normalized_media and normalized_photo.startswith(f'{normalized_media}/'):
            return f'/{normalized_photo}' if media_url.startswith('/') else normalized_photo

        if not media_url.endswith('/'):
            media_url = f'{media_url}/'

        return f"{media_url}{normalized_photo}"

    @property
    def uniform_due_amount(self):
        """Returns remaining due amount for uniform package if PARTIAL or DUE."""
        if self.uniform_status == 'PARTIAL':
            return max(0.0, (self.uniform_amount or 0.0) - (self.uniform_paid_amount or 0.0))
        elif self.uniform_status == 'DUE':
            return self.uniform_amount or 0.0
        return 0.0

    def get_profile_completeness(self):
        """
        Calculates a 100-point weighted profile completeness score.
        Returns a dict suitable for both Django template context and JSON responses.
        """
        score = 0
        missing_items = []

        def _has(val):
            """True if the value is meaningfully filled (not None/blank/placeholder)."""
            if val is None:
                return False
            s = str(val).strip()
            return bool(s) and s.lower() not in ('none', '-', 'n/a', '0', '')

        # ── Personal Information (20 pts, 4 each) ──────────────────────────────
        personal = [
            ('student_name',  'Student Name',   self.student_name),
            ('gender',        'Gender',          self.gender),
            ('dob',           'Date of Birth',   self.dob),
            ('blood_group',   'Blood Group',     self.blood_group),
            ('religion',      'Religion',        self.religion),
        ]
        for _field, label, val in personal:
            if _has(val):
                score += 4
            else:
                missing_items.append(label)

        # ── Family & Contact (25 pts, 5 each) ─────────────────────────────────
        contact = [
            ('father_name',    "Father's Name",   self.father_name),
            ('mother_name',    "Mother's Name",   self.mother_name),
            ('student_mobile', 'Mobile Number',   self.student_mobile),
            ('father_mobile',  "Father's Mobile", self.father_mobile),
            ('student_email',  'Email Address',   self.student_email),
        ]
        for _field, label, val in contact:
            if _has(val):
                score += 5
            else:
                missing_items.append(label)

        # ── Address (15 pts, 7.5 each — stored as int steps of 7 or 8) ────────
        if _has(self.present_address) or _has(self.present_district):
            score += 8
        else:
            missing_items.append('Present Address')

        if _has(self.permanent_address) or _has(self.permanent_district):
            score += 7
        else:
            missing_items.append('Permanent Address')

        # ── Academic — SSC (12 pts, ~2.4 each rounded to int steps) ──────────
        ssc_result_val = (self.ssc_division or self.ssc_gpa) if self.ssc_system == 'DIVISION' else self.ssc_gpa
        ssc_fields = [
            ('SSC School',    self.ssc_school),
            ('SSC Board',     self.ssc_board),
            ('SSC Year',      self.ssc_year),
            ('SSC Roll',      self.ssc_roll),
            ('SSC Result',    ssc_result_val),
        ]
        ssc_pts = 0
        for label, val in ssc_fields:
            if _has(val):
                ssc_pts += 1
            else:
                missing_items.append(label)
        # Map 0–5 filled fields → 0–12 pts proportionally
        score += round(ssc_pts * 12 / 5)

        # ── Academic — HSC (13 pts to hit 100 total) ──────────────────────────
        hsc_result_val = (self.hsc_division or self.hsc_gpa) if self.hsc_system == 'DIVISION' else self.hsc_gpa
        hsc_fields = [
            ('HSC College',   self.hsc_college),
            ('HSC Board',     self.hsc_board),
            ('HSC Year',      self.hsc_year),
            ('HSC Roll',      self.hsc_roll),
            ('HSC Result',    hsc_result_val),
        ]
        hsc_pts = 0
        for label, val in hsc_fields:
            if _has(val):
                hsc_pts += 1
            else:
                missing_items.append(label)
        score += round(hsc_pts * 13 / 5)

        # ── Photo (5 pts) ─────────────────────────────────────────────────────
        if _has(self.photo_path):
            score += 5
        else:
            missing_items.append('Profile Photo')

        # ── Board Verification (5 pts, 2 + 3) ────────────────────────────────
        if self.ssc_verified:
            score += 2
        else:
            missing_items.append('SSC Board Verified')

        if self.hsc_verified:
            score += 3
        else:
            missing_items.append('HSC Board Verified')

        # Clamp to 100
        score = min(score, 100)

        # Determine tier
        if score >= 90:
            tier = 'Excellent'
            bar_class = 'success'
        elif score >= 70:
            tier = 'Good'
            bar_class = 'info'
        elif score >= 50:
            tier = 'Fair'
            bar_class = 'warning'
        else:
            tier = 'Needs Attention'
            bar_class = 'danger'

        return {
            'score': score,
            'tier': tier,
            'bar_class': bar_class,
            'missing_items': missing_items,
        }

class ProgramChangeHistory(models.Model):
    old_student_id = models.CharField(max_length=50)
    new_student_id = models.CharField(max_length=50)
    old_program = models.CharField(max_length=100)
    new_program = models.CharField(max_length=100)
    change_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Program change histories"

class SMSHistory(models.Model):
    MODULE_CHOICES = [
        ('ADMISSION', 'Admission Module'),
        ('COE', 'Controller of Examinations'),
        ('PUBLIC_RELATIONS', 'Public Relations'),
        ('ICT_WING', 'ICT Wing'),
        ('EXAM_BILLING', 'Exam Billing'),
        ('COUNSELING', 'Psychological Counseling & Wellbeing'),
        ('SYSTEM', 'System / Security'),
    ]

    recipient_name = models.CharField(max_length=255, null=True, blank=True)
    student_id = models.CharField(max_length=50, null=True, blank=True)
    recipient_contact = models.CharField(max_length=50)
    sms_delivery_type = models.CharField(max_length=50, null=True, blank=True)
    module_name = models.CharField(max_length=50, choices=MODULE_CHOICES, default='SYSTEM')
    use_case_event = models.CharField(max_length=100, default='general_notification', help_text="Specific trigger event e.g. hod_approved, delivery_ready, status_change, test_sms")
    message_type = models.CharField(max_length=20) # SMS or Email
    message_body = models.TextField()
    status = models.CharField(max_length=50)
    api_response = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    api_profile_name = models.CharField(max_length=100, null=True, blank=True)
    sms_profile = models.ForeignKey('core.SMSProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_logs')

    class Meta:
        ordering = ['-sent_at']


class AdmissionStatusHistory(models.Model):
    REASON_CHOICES = [
        ('Migration', 'Migration to other University'),
        ('Financial', 'Financial/Non-Payment'),
        ('Personal', 'Personal Reasons'),
        ('Academic', 'Academic Non-Performance'),
        ('Disciplinary', 'Disciplinary Action'),
        ('Other', 'Other (See Notes)'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)
    reason_category = models.CharField(max_length=50, choices=REASON_CHOICES)
    custom_notes = models.TextField(null=True, blank=True)
    performed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    change_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Admission status histories"
        ordering = ['-change_date']

    def __str__(self):
        return f"{self.student.student_id} changed to {self.new_status} on {self.change_date}"

class StudentFieldHistory(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='field_history')
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    changed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='student_field_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    # Revert Fields
    reverted = models.BooleanField(default=False)
    reverted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reverted_student_changes')
    reverted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.student.student_id} - {self.field_name} by {self.changed_by.username if self.changed_by else 'System'}"

class HallMigrationHistory(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='migration_history')
    previous_hall = models.ForeignKey('master_data.Hall', on_delete=models.SET_NULL, null=True, blank=True, related_name='migrations_out')
    new_hall = models.ForeignKey('master_data.Hall', on_delete=models.SET_NULL, null=True, blank=True, related_name='migrations_in')
    migration_date = models.DateTimeField(auto_now_add=True)
    previous_residency_status = models.BooleanField(default=False, help_text="True if was non-residential previously")
    new_residency_status = models.BooleanField(default=False, help_text="True if is non-residential now")
    reason = models.TextField(blank=True, null=True)
    authorized_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-migration_date']
        verbose_name_plural = "Hall migration histories"

    def __str__(self):
        return f"Migration for {self.student.student_id} on {self.migration_date}"


class HallSeatCancellation(models.Model):
    CANCELLATION_REASONS = [
        ('GRADUATION', 'Completed Graduation / Completed Program'),
        ('VOLUNTARY', 'Voluntary Release (Commuting / Private Mess)'),
        ('DISCIPLINARY', 'Disciplinary Action'),
        ('TRANSFER', 'Transfer to Another Campus / Institution'),
        ('NON_PAYMENT', 'Non-payment of Hall Dues'),
        ('OTHER', 'Other (Please specify in notes)'),
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='seat_cancellations')
    hall = models.ForeignKey('master_data.Hall', on_delete=models.CASCADE, related_name='cancellations')
    cancellation_date = models.DateField(default=timezone.now)
    academic_year = models.ForeignKey('master_data.AdmissionYear', on_delete=models.SET_NULL, null=True)
    semester = models.ForeignKey('master_data.Semester', on_delete=models.SET_NULL, null=True)
    reason = models.CharField(max_length=30, choices=CANCELLATION_REASONS, default='VOLUNTARY')
    notes = models.TextField(blank=True, null=True, help_text="Additional explanation or context")
    refund_applicable = models.BooleanField(default=False, help_text="Check if student is eligible for caution money/fee refund")
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    authorized_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-cancellation_date']
        verbose_name = "Hall Seat Cancellation"
        verbose_name_plural = "Hall Seat Cancellations"

    def __str__(self):
        return f"{self.student.student_id} - {self.hall.short_name} Cancellation"


def validate_app_template_size(file):
    max_size_mb = 5
    if file and hasattr(file, 'size') and file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"File size exceeds {max_size_mb}MB limit.")


class AdmissionApplicationType(models.Model):
    code = models.CharField(max_length=50, unique=True)
    title_en = models.CharField(max_length=255)
    title_bn = models.CharField(max_length=255)
    addressed_to = models.CharField(max_length=255, default="The Registrar")
    through_dept_head = models.BooleanField(default=True)
    subject = models.CharField(max_length=255)
    body_template = models.TextField()
    fields_schema = models.JSONField(default=list, blank=True)
    docx_template = models.FileField(
        upload_to='admission_app_templates/docx/',
        null=True, blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['docx']), validate_app_template_size]
    )
    pdf_template = models.FileField(
        upload_to='admission_app_templates/pdf/',
        null=True, blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf']), validate_app_template_size]
    )
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Admission Application Type"
        verbose_name_plural = "Admission Application Types"

    def __str__(self):
        return f"{self.order:02d}. {self.title_en}"


class AdmissionApplicationConfig(models.Model):
    VALIDATION_POLICIES = [
        ('FLEXIBLE', 'Flexible — Warn on unrecorded IDs, allow with office flag'),
        ('STRICT',   'Strict — Block unrecorded IDs for enrolled applications'),
    ]
    id_validation_policy = models.CharField(
        max_length=20, choices=VALIDATION_POLICIES, default='FLEXIBLE'
    )
    allow_docx_download = models.BooleanField(default=True)

    @classmethod
    def get_config(cls):
        """Singleton accessor — always returns or creates record with pk=1."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    class Meta:
        verbose_name = "Admission Application Config"
        verbose_name_plural = "Admission Application Config"

    def __str__(self):
        return f"Application Config (Policy: {self.id_validation_policy})"


class StudentApplication(models.Model):
    STATUS_CHOICES = [
        ('SUBMITTED', 'Submitted (Online)'),
        ('RECEIVED',  'Physical Form Received'),
        ('VERIFIED',  'Verified / Under Review'),
        ('APPROVED',  'Approved'),
        ('REJECTED',  'Rejected'),
    ]
    tracking_number = models.CharField(max_length=30, unique=True, db_index=True)
    application_type = models.ForeignKey(
        AdmissionApplicationType, on_delete=models.PROTECT,
        related_name='submissions'
    )
    student = models.ForeignKey('Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='admission_applications')
    student_name = models.CharField(max_length=255)
    applicant_student_id = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    is_id_verified = models.BooleanField(default=False)
    department = models.CharField(max_length=100)
    phone_no = models.CharField(max_length=30, db_index=True)
    form_data = models.JSONField(default=dict, blank=True)
    has_profile_mismatch = models.BooleanField(default=False)
    mismatch_details = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUBMITTED')
    office_notes = models.TextField(blank=True, null=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='received_admission_applications'
    )
    received_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Student Application"
        verbose_name_plural = "Student Applications"

    @property
    def display_student_id(self):
        return self.applicant_student_id or (self.student.student_id if self.student else '')

    def __str__(self):
        return f"{self.tracking_number} - {self.student_name} ({self.application_type.code})"


class AdmissionIntake(models.Model):
    """Represents one admission event (e.g. 'Winter 2027 Intake')."""
    intake_name = models.CharField(
        max_length=100, unique=True,
        help_text="e.g. 'Winter 2027', 'Summer 2027'"
    )
    academic_year = models.ForeignKey(
        'master_data.AdmissionYear', on_delete=models.PROTECT,
        null=True, blank=True
    )
    is_open_for_application = models.BooleanField(
        default=True,
        help_text="Toggle to manually open or close applications"
    )
    application_deadline = models.DateTimeField(
        null=True, blank=True,
        help_text="If set, applications auto-close after this datetime"
    )
    exam_date = models.DateTimeField(
        null=True, blank=True,
        help_text="Admission test date & time"
    )
    exam_venue = models.CharField(
        max_length=255, default="BAUST Campus (Saidpur)"
    )
    
    # Financial settings (displayed dynamically on apply form)
    form_fee_bdt = models.DecimalField(
        max_digits=10, decimal_places=2, default=750.00
    )
    bkash_charge_bdt = models.DecimalField(
        max_digits=10, decimal_places=2, default=12.00
    )
    bkash_number = models.CharField(
        max_length=30, default="01769675556"
    )
    
    # Exam Roll generation
    exam_roll_prefix = models.CharField(
        max_length=50, default="BAUST-",
        help_text="e.g. 'BAUST-Winter2027-' or 'BAUST-'"
    )
    next_roll_number = models.IntegerField(
        default=1001,
        help_text="Auto-incremented atomically on each submission"
    )
    
    # Admin notice for public requirements page
    notice_html = models.TextField(
        blank=True, null=True,
        help_text="Optional HTML notice displayed on public requirements page"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_fee_bdt(self):
        return self.form_fee_bdt + self.bkash_charge_bdt
    
    @property
    def is_currently_open(self):
        """True only if manually open AND deadline has not passed."""
        if not self.is_open_for_application:
            return False
        if self.application_deadline and timezone.now() > self.application_deadline:
            return False
        return True

    class Meta:
        ordering = ['-id']
        verbose_name = "Admission Intake"
        verbose_name_plural = "Admission Intakes"
    
    def __str__(self):
        return self.intake_name


class OnlineApplicant(models.Model):
    STATUS_CHOICES = [
        ('PENDING',  'Pending Review'),
        ('VERIFIED', 'Verified / Under Review'),
        ('APPROVED', 'Approved — Admit Card Ready'),
        ('REJECTED', 'Rejected'),
        ('ADMITTED', 'Enrolled in University Database'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('PENDING',  'Pending Verification'),
        ('VERIFIED', 'Payment Verified'),
        ('INVALID',  'Invalid / Rejected'),
    ]
    
    # Application identifiers
    application_no = models.CharField(
        max_length=50, unique=True, db_index=True
    )  # e.g. "OA-2027-00123"
    exam_roll = models.CharField(
        max_length=80, unique=True, db_index=True, blank=True, null=True
    )  # e.g. "BAUST-Winter2027-1001"
    intake = models.ForeignKey(
        AdmissionIntake, on_delete=models.PROTECT, related_name='applicants'
    )
    intake_name = models.CharField(
        max_length=100, db_index=True
    )  # Cached for fast filtering even if intake is deleted
    
    # Program Selection
    program_category = models.CharField(
        max_length=30,
        choices=[('Engineering', 'Engineering'), ('Non Engineering', 'Non Engineering')]
    )
    desired_program = models.CharField(
        max_length=100, blank=True, null=True
    )  # e.g. "CSE", "BBA"
    exam_venue = models.CharField(
        max_length=255, default="BAUST Campus (Saidpur)"
    )
    
    # Personal Information
    name = models.CharField(max_length=255)
    mobile = models.CharField(max_length=15, db_index=True)  # Normalized: 01XXXXXXXXX
    email = models.EmailField(blank=True, null=True)
    national_id = models.CharField(max_length=50, blank=True, null=True)
    place_of_birth = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=20, choices=[('Male', 'Male'), ('Female', 'Female')])
    blood_group = models.CharField(max_length=10, blank=True, null=True)
    dob = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=50, default='Bangladeshi')
    marital_status = models.CharField(
        max_length=20, default='Single',
        choices=[('Single', 'Single'), ('Married', 'Married')]
    )
    student_type = models.CharField(
        max_length=50, default='Regular',
        choices=[('Regular', 'Regular'), ('Transfer', 'Transfer'), ('Diploma Holder', 'Diploma Holder')]
    )
    
    # Family Information
    father_name = models.CharField(max_length=255)
    father_occupation = models.CharField(max_length=100, blank=True, null=True)
    father_mobile = models.CharField(max_length=15, blank=True, null=True)
    mother_name = models.CharField(max_length=255)
    mother_occupation = models.CharField(max_length=100, blank=True, null=True)  # Stored in applicant only, NOT copied to Student
    mother_mobile = models.CharField(max_length=15, blank=True, null=True)
    
    # Photo (stored as ImageField, converted to photo_path string during enrollment)
    photo = models.ImageField(
        upload_to='applicant_photos/%Y/',
        null=True, blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]
    )
    
    # Address (Present)
    present_house = models.CharField(max_length=255, blank=True, null=True)
    present_post_code = models.CharField(max_length=30, blank=True, null=True)
    present_police_station = models.CharField(max_length=100, blank=True, null=True)
    present_district = models.CharField(max_length=100, blank=True, null=True)
    present_country = models.CharField(max_length=50, default='Bangladesh')
    
    # Address (Permanent)
    same_as_present = models.BooleanField(default=False)
    permanent_house = models.CharField(max_length=255, blank=True, null=True)
    permanent_post_code = models.CharField(max_length=30, blank=True, null=True)
    permanent_police_station = models.CharField(max_length=100, blank=True, null=True)
    permanent_district = models.CharField(max_length=100, blank=True, null=True)
    permanent_country = models.CharField(max_length=50, default='Bangladesh')
    
    # Academic: SSC
    ssc_system = models.CharField(
        max_length=10,
        choices=RESULT_SYSTEM_CHOICES,
        default='GPA',
        blank=True
    )
    ssc_school = models.CharField(max_length=255, blank=True, null=True)
    ssc_board = models.CharField(max_length=50, blank=True, null=True)
    ssc_roll = models.CharField(max_length=50, blank=True, null=True)
    ssc_reg = models.CharField(max_length=50, blank=True, null=True)  # Registration No.
    ssc_year = models.CharField(max_length=10, blank=True, null=True)
    ssc_division = models.CharField(
        max_length=20,
        choices=DIVISION_CHOICES,
        null=True,
        blank=True
    )
    ssc_marks = models.IntegerField(null=True, blank=True)
    ssc_gpa = models.FloatField(null=True, blank=True)  # Range 0.00–5.00 or UGC equivalent
    
    # Academic: HSC
    hsc_system = models.CharField(
        max_length=10,
        choices=RESULT_SYSTEM_CHOICES,
        default='GPA',
        blank=True
    )
    hsc_college = models.CharField(max_length=255, blank=True, null=True)
    hsc_board = models.CharField(max_length=50, blank=True, null=True)
    hsc_roll = models.CharField(max_length=50, blank=True, null=True)
    hsc_reg = models.CharField(max_length=50, blank=True, null=True)  # Registration No.
    hsc_year = models.CharField(max_length=10, blank=True, null=True)
    hsc_division = models.CharField(
        max_length=20,
        choices=DIVISION_CHOICES,
        null=True,
        blank=True
    )
    hsc_marks = models.IntegerField(null=True, blank=True)
    hsc_gpa = models.FloatField(null=True, blank=True)  # Range 0.00–5.00 or UGC equivalent
    
    total_gpa = models.FloatField(null=True, blank=True)  # ssc_gpa + hsc_gpa (or equiv sum)
    
    # Payment (bKash TrxID only for now)
    payment_method = models.CharField(max_length=50, default='bKash')
    payment_trx_id = models.CharField(max_length=100, db_index=True)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING'
    )
    payment_notes = models.TextField(blank=True, null=True)
    payment_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verified_applicant_payments'
    )
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Education Board Verification
    ssc_verified = models.BooleanField(default=False)
    hsc_verified = models.BooleanField(default=False)
    board_verification_logs = models.JSONField(default=dict, blank=True)
    
    # Status & Workflow
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True
    )
    office_remarks = models.TextField(blank=True, null=True)
    
    # Soft Delete
    is_trashed = models.BooleanField(default=False, db_index=True)
    trashed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='trashed_applicants'
    )
    trashed_at = models.DateTimeField(null=True, blank=True)
    
    # Enrollment Bridge
    admitted_student = models.ForeignKey(
        'Student', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='source_online_application'
    )
    
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-applied_at']
        verbose_name = "Online Applicant"
        verbose_name_plural = "Online Applicants"
        constraints = [
            models.UniqueConstraint(
                fields=['intake', 'mobile'],
                condition=models.Q(is_trashed=False),
                name='unique_active_application_per_mobile_per_intake'
            )
        ]
    
    def __str__(self):
        return f"{self.exam_roll or self.application_no} — {self.name} ({self.intake_name})"

    def get_ssc_result_display_full(self):
        """Returns human-friendly SSC result regardless of GPA or Division system."""
        if self.ssc_system == 'DIVISION':
            div = self.get_ssc_division_display() or self.ssc_division or 'Division System'
            marks_str = f" ({self.ssc_marks}/1000)" if self.ssc_marks else ""
            equiv_str = f" [Equiv. GPA: {self.ssc_gpa:.2f}]" if self.ssc_gpa is not None else ""
            return f"{div}{marks_str}{equiv_str}"
        return f"GPA {self.ssc_gpa:.2f}" if self.ssc_gpa is not None else "N/A"

    def get_hsc_result_display_full(self):
        """Returns human-friendly HSC result regardless of GPA or Division system."""
        if self.hsc_system == 'DIVISION':
            div = self.get_hsc_division_display() or self.hsc_division or 'Division System'
            marks_str = f" ({self.hsc_marks}/1000)" if self.hsc_marks else ""
            equiv_str = f" [Equiv. GPA: {self.hsc_gpa:.2f}]" if self.hsc_gpa is not None else ""
            return f"{div}{marks_str}{equiv_str}"
        return f"GPA {self.hsc_gpa:.2f}" if self.hsc_gpa is not None else "N/A"

