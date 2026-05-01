from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from master_data.models import Program


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class BillingExam(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('locked', 'Locked'),
        ('finalized', 'Finalized'),
    ]

    name = models.CharField(max_length=150)
    exam_type = models.CharField(max_length=50, default='FINAL')
    semester_label = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', 'name']
        unique_together = ('name', 'exam_type', 'semester_label')

    def __str__(self):
        return f'{self.name} {self.exam_type} ({self.semester_label})'

    @property
    def is_editable(self):
        return self.status in {'draft', 'open'}


class BillingRateTemplate(models.Model):
    QUESTION_MODE_CHOICES = [
        ('UNIQUE', 'Unique Questions'),
        ('DUPLICATE', 'Duplicate Questions'),
    ]

    name = models.CharField(max_length=120, unique=True, default='Default')
    is_default = models.BooleanField(default=False)
    cecc_chairman_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1000.00'))
    cecc_member_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('750.00'))
    ec_chairman_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    ec_member_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    qmsc_chairman_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('200.00'))
    qmsc_member_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('200.00'))
    rpsc_chairman_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('2.50'))
    rpsc_member_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('2.50'))
    qpsc_member_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50.00'))
    qsetter_full_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('400.00'))
    qsetter_full_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('300.00'))
    qsetter_half_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('250.00'))
    qsetter_half_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('150.00'))
    examiner_full_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('25.00'))
    examiner_full_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('25.00'))
    examiner_half_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('15.00'))
    examiner_half_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('15.00'))
    scrutinizer_full_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('5.00'))
    scrutinizer_full_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('5.00'))
    scrutinizer_half_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('3.00'))
    scrutinizer_half_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('3.00'))
    rpsc_question_mode = models.CharField(max_length=20, choices=QUESTION_MODE_CHOICES, default='UNIQUE')
    qpsc_question_mode = models.CharField(max_length=20, choices=QUESTION_MODE_CHOICES, default='DUPLICATE')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            BillingRateTemplate.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class ExamBillingSetting(models.Model):
    exam = models.OneToOneField(BillingExam, on_delete=models.CASCADE, related_name='settings')
    source_template = models.ForeignKey(BillingRateTemplate, on_delete=models.SET_NULL, null=True, blank=True)

    cecc_chairman_rate = models.DecimalField(max_digits=10, decimal_places=2)
    cecc_member_rate = models.DecimalField(max_digits=10, decimal_places=2)
    ec_chairman_rate = models.DecimalField(max_digits=10, decimal_places=2)
    ec_member_rate = models.DecimalField(max_digits=10, decimal_places=2)
    qmsc_chairman_rate = models.DecimalField(max_digits=10, decimal_places=2)
    qmsc_member_rate = models.DecimalField(max_digits=10, decimal_places=2)
    rpsc_chairman_rate = models.DecimalField(max_digits=10, decimal_places=2)
    rpsc_member_rate = models.DecimalField(max_digits=10, decimal_places=2)
    qpsc_member_rate = models.DecimalField(max_digits=10, decimal_places=2)
    qsetter_full_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    qsetter_full_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    qsetter_half_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    qsetter_half_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    examiner_full_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    examiner_full_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    examiner_half_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    examiner_half_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    scrutinizer_full_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    scrutinizer_full_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    scrutinizer_half_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    scrutinizer_half_non_engineering_rate = models.DecimalField(max_digits=10, decimal_places=2)
    rpsc_question_mode = models.CharField(max_length=20, choices=BillingRateTemplate.QUESTION_MODE_CHOICES)
    qpsc_question_mode = models.CharField(max_length=20, choices=BillingRateTemplate.QUESTION_MODE_CHOICES)

    @classmethod
    def create_from_template(cls, exam, template=None):
        template = template or BillingRateTemplate.objects.filter(is_default=True).first() or BillingRateTemplate.objects.create(
            name='Default', is_default=True
        )
        field_names = [
            field.name for field in BillingRateTemplate._meta.fields
            if field.name.endswith('_rate') or field.name.endswith('_mode')
        ]
        payload = {name: getattr(template, name) for name in field_names}
        return cls.objects.create(exam=exam, source_template=template, **payload)

    def __str__(self):
        return f'Settings for {self.exam}'


class ExamProgram(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('locked', 'Locked'),
        ('finalized', 'Finalized'),
    ]

    exam = models.ForeignKey(BillingExam, on_delete=models.CASCADE, related_name='programs')
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='billing_exams')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    approved_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    cached_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    cached_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('exam', 'program')
        ordering = ['exam', 'program__sort_order', 'program__name']

    def __str__(self):
        return f'{self.exam} - {self.program.short_name or self.program.name}'

    @property
    def is_editable(self):
        return self.exam.is_editable and self.status == 'draft'

    def mark_submitted(self, user):
        self.status = 'submitted'
        self.submitted_by = user
        self.submitted_at = timezone.now()
        self.save(update_fields=['status', 'submitted_by', 'submitted_at'])

    def mark_approved(self, user):
        self.status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at'])

    def mark_locked(self):
        self.status = 'locked'
        self.locked_at = timezone.now()
        self.save(update_fields=['status', 'locked_at'])

    def mark_finalized(self, total, summary):
        self.status = 'finalized'
        self.finalized_at = timezone.now()
        self.cached_total = total
        self.cached_summary = summary
        self.save(update_fields=['status', 'finalized_at', 'cached_total', 'cached_summary'])


class FacultyProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='faculty_profile')
    first_name = models.CharField(max_length=75)
    last_name = models.CharField(max_length=75, blank=True)
    
    designation = models.CharField(max_length=120, blank=True)
    employee_id = models.CharField(max_length=50, blank=True)
    email = models.EmailField(max_length=150, null=True, blank=True)
    mobile = models.CharField(max_length=20, null=True, blank=True)
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='faculty_profiles')
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f'{self.name} ({self.designation})'

    class Meta:
        ordering = ['program__name', 'first_name', 'last_name']
        constraints = [
            models.UniqueConstraint(
                fields=['program', 'employee_id'],
                condition=~models.Q(employee_id=''),
                name='unique_billing_faculty_employee_per_program',
            )
        ]



class ExamFaculty(models.Model):
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='faculty')
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.PROTECT, related_name='exam_entries')
    designation_snapshot = models.CharField(max_length=120, blank=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ('exam_program', 'faculty')
        ordering = ['faculty__first_name', 'faculty__last_name']

    def save(self, *args, **kwargs):
        if not self.designation_snapshot and self.faculty_id:
            self.designation_snapshot = self.faculty.designation
        super().save(*args, **kwargs)

    def __str__(self):
        return self.faculty.name


class ExamCourse(models.Model):
    LEVEL_CHOICES = [('1', 'Level 1'), ('2', 'Level 2'), ('3', 'Level 3'), ('4', 'Level 4')]
    TERM_CHOICES = [('I', 'Term I'), ('II', 'Term II')]

    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='courses')
    level = models.CharField(max_length=30, choices=LEVEL_CHOICES)
    term = models.CharField(max_length=30, choices=TERM_CHOICES)
    course_code = models.CharField(max_length=50)
    offering_department = models.CharField(max_length=100, blank=True)
    no_of_scripts = models.PositiveIntegerField(default=0)
    syllabus = models.CharField(max_length=100, blank=True)
    course_title = models.CharField(max_length=255, blank=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    @property
    def is_engineering(self):
        return self.exam_program.program.cluster.is_engineering

    class Meta:
        unique_together = ('exam_program', 'course_code', 'syllabus')
        ordering = ['level', 'term', 'course_code']

    def save(self, *args, **kwargs):
        if self.course_code:
            self.course_code = self.course_code.upper().replace(' ', '')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.course_code} ({self.syllabus})' if self.syllabus else self.course_code


class ExamLevelTermSummary(models.Model):
    LEVEL_CHOICES = [('1', 'Level 1'), ('2', 'Level 2'), ('3', 'Level 3'), ('4', 'Level 4')]
    TERM_CHOICES = [('I', 'Term I'), ('II', 'Term II')]

    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='level_term_summaries')
    level = models.CharField(max_length=30, choices=LEVEL_CHOICES)
    term = models.CharField(max_length=30, choices=TERM_CHOICES)
    total_students = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('exam_program', 'level', 'term')
        ordering = ['level', 'term']

    def __str__(self):
        return f"{self.level}-{self.term} ({self.total_students})"


class AssignmentBase(models.Model):
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE)
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.PROTECT)
    role = models.CharField(max_length=80, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True


class CECCAssignment(AssignmentBase):
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='cecc_assignments')


class ECMember(AssignmentBase):
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='ec_members')
    # level/term removed — EC committee is not per level/term


class RPSCAssignment(AssignmentBase):
    LEVEL_CHOICES = [('All', 'All'), ('1', 'Level 1'), ('2', 'Level 2'), ('3', 'Level 3'), ('4', 'Level 4')]
    TERM_CHOICES  = [('All', 'All'), ('I', 'Term I'), ('II', 'Term II')]
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='rpsc_assignments')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='All')
    term  = models.CharField(max_length=10, choices=TERM_CHOICES, default='All')


class QMSCAssignment(AssignmentBase):
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='qmsc_assignments')
    # Override faculty to be nullable (external-only entries may have no faculty)
    faculty = models.ForeignKey(FacultyProfile, on_delete=models.PROTECT, null=True, blank=True)
    course  = models.ForeignKey(ExamCourse, on_delete=models.PROTECT, related_name='qmsc_assignments', null=True, blank=True)
    external_member_name        = models.CharField(max_length=120, blank=True)
    external_member_designation = models.CharField(max_length=120, blank=True)
    # is_external removed — use external_member_name to detect external entries


class QPSCMember(AssignmentBase):
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='qpsc_members')
    question_count = models.PositiveIntegerField(default=0)


class CourseDutyBase(AssignmentBase):
    PART_CHOICES = [('A', 'A'), ('B', 'B'), ('A+B', 'A+B')]
    course = models.ForeignKey(ExamCourse, on_delete=models.PROTECT)
    part = models.CharField(max_length=10, choices=PART_CHOICES, default='A')

    class Meta:
        abstract = True


class QuestionSetterAssignment(CourseDutyBase):
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='question_setters')
    course = models.ForeignKey(ExamCourse, on_delete=models.PROTECT, related_name='question_setters')


class ScriptExaminerAssignment(CourseDutyBase):
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='script_examiners')
    course = models.ForeignKey(ExamCourse, on_delete=models.PROTECT, related_name='script_examiners')


class ScriptScrutinizerAssignment(CourseDutyBase):
    exam_program = models.ForeignKey(ExamProgram, on_delete=models.CASCADE, related_name='script_scrutinizers')
    course = models.ForeignKey(ExamCourse, on_delete=models.PROTECT, related_name='script_scrutinizers')
