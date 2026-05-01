from django.conf import settings
from django.db import models
from django.utils import timezone

class Student(models.Model):
    # Core Identification
    student_id = models.CharField(max_length=50, primary_key=True, help_text="UGC Compliant ID")
    student_name = models.CharField(max_length=255)
    old_student_id = models.CharField(max_length=50, null=True, blank=True)
    
    # Academic Info
    program = models.CharField(max_length=100, null=True, blank=True)
    admission_year = models.IntegerField(null=True, blank=True)
    cluster = models.CharField(max_length=50, null=True, blank=True)
    batch = models.CharField(max_length=50, null=True, blank=True)
    batch_number = models.IntegerField(null=True, blank=True, help_text="Auto-extracted for numeric sorting")
    semester_name = models.CharField(max_length=50, null=True, blank=True)
    program_type = models.CharField(max_length=50, null=True, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    admission_status = models.CharField(max_length=50, default="Active")
    
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
    student_mobile = models.CharField(max_length=20, null=True, blank=True)
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
    ssc_school = models.CharField(max_length=255, null=True, blank=True)
    ssc_year = models.CharField(max_length=10, null=True, blank=True)
    ssc_board = models.CharField(max_length=50, null=True, blank=True)
    ssc_roll = models.CharField(max_length=50, null=True, blank=True)
    ssc_reg = models.CharField(max_length=50, null=True, blank=True)
    ssc_gpa = models.FloatField(null=True, blank=True)
    ssc_physics = models.FloatField(null=True, blank=True)
    ssc_chemistry = models.FloatField(null=True, blank=True)
    ssc_math = models.FloatField(null=True, blank=True)
    
    # Academic History (HSC)
    hsc_college = models.CharField(max_length=255, null=True, blank=True)
    hsc_year = models.CharField(max_length=10, null=True, blank=True)
    hsc_board = models.CharField(max_length=50, null=True, blank=True)
    hsc_roll = models.CharField(max_length=50, null=True, blank=True)
    hsc_reg = models.CharField(max_length=50, null=True, blank=True)
    hsc_gpa = models.FloatField(null=True, blank=True)
    hsc_physics = models.FloatField(null=True, blank=True)
    hsc_chemistry = models.FloatField(null=True, blank=True)
    hsc_math = models.FloatField(null=True, blank=True)
    
    # Financial & Status
    hall_attached = models.CharField(max_length=100, null=True, blank=True)
    is_non_residential = models.BooleanField(default=False)
    admission_payment = models.FloatField(null=True, blank=True, default=0.0)
    second_installment = models.FloatField(null=True, blank=True, default=0.0)
    waiver = models.FloatField(null=True, blank=True, default=0.0)
    others = models.FloatField(null=True, blank=True, default=0.0)
    
    # Miscellaneous Flags
    reference = models.CharField(max_length=255, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    is_temp_admission_cancel = models.BooleanField(default=False)
    is_credit_transfer = models.BooleanField(default=False)
    is_armed_forces_child = models.BooleanField(default=False)
    is_freedom_fighter_child = models.BooleanField(default=False)
    is_july_joddha_2024 = models.BooleanField(default=False)
    
    # Metadata
    photo_path = models.CharField(max_length=255, null=True, blank=True)
    mba_credits = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
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
            self.admission_date = timezone.now().date()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_name} ({self.student_id})"

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
    recipient_name = models.CharField(max_length=255, null=True, blank=True)
    student_id = models.CharField(max_length=50, null=True, blank=True)
    recipient_contact = models.CharField(max_length=50)
    sms_delivery_type = models.CharField(max_length=50, null=True, blank=True)
    message_type = models.CharField(max_length=20) # SMS or Email
    message_body = models.TextField()
    status = models.CharField(max_length=50)
    api_response = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    api_profile_name = models.CharField(max_length=100, null=True, blank=True)

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
