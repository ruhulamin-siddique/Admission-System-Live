from django import forms
from django.db.models import Q

from master_data.models import Program

from .models import (
    BillingExam,
    BillingRateTemplate,
    CECCAssignment,
    ECMember,
    ExamBillingSetting,
    ExamCourse,
    ExamFaculty,
    ExamLevelTermSummary,
    ExamProgram,
    FacultyProfile,
    QMSCAssignment,
    QPSCMember,
    QuestionSetterAssignment,
    RPSCAssignment,
    ScriptExaminerAssignment,
    ScriptScrutinizerAssignment,
)
from .scope import get_allowed_programs


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = 'form-control'
            if isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            field.widget.attrs.setdefault('class', css)


class BillingExamForm(StyledModelForm):
    programs = forms.ModelMultipleChoiceField(
        queryset=Program.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        help_text='Departments/programs opened for this exam.',
    )

    class Meta:
        model = BillingExam
        fields = ['name', 'exam_type', 'semester_label', 'status', 'starts_on', 'ends_on', 'remarks']
        widgets = {
            'starts_on': forms.DateInput(attrs={'type': 'date'}),
            'ends_on': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['programs'].queryset = get_allowed_programs(user) if user else Program.objects.all()
        if self.instance.pk:
            self.fields['programs'].initial = self.instance.programs.values_list('program_id', flat=True)


class BillingRateTemplateForm(StyledModelForm):
    class Meta:
        model = BillingRateTemplate
        fields = '__all__'


class ExamBillingSettingForm(StyledModelForm):
    class Meta:
        model = ExamBillingSetting
        exclude = ['exam', 'source_template']


class FacultyProfileForm(StyledModelForm):
    class Meta:
        model = FacultyProfile
        fields = ['user', 'first_name', 'last_name', 'designation', 'employee_id', 'email', 'mobile', 'program', 'is_active']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['program'].queryset = get_allowed_programs(user) if user else Program.objects.all()
        
        # Restrict 'user' field to superusers only
        # Restrict 'user' field to superusers only
        if 'user' in self.fields:
            if user and user.is_superuser:
                self.fields['user'].label = "Linked System User"
                self.fields['user'].help_text = "Admin Only: Connect this profile to a system account for personal billing access."
            else:
                del self.fields['user']

        # Add datalist support for designation
        if 'designation' in self.fields:
            self.fields['designation'].widget.attrs.update({'list': 'designation-list', 'autocomplete': 'off'})


class ExamCourseForm(StyledModelForm):
    class Meta:
        model = ExamCourse
        fields = ['level', 'term', 'course_code', 'offering_department', 'no_of_scripts', 'syllabus', 'course_title']

    def __init__(self, *args, **kwargs):
        self.exam_program = kwargs.pop('exam_program', None)
        super().__init__(*args, **kwargs)

        # Populate offering_department with short names from Program (Academic Setting)
        programs = Program.objects.filter(level_code='1').order_by('short_name') # Usually engineering/undergrad
        dept_choices = [('', '---------')] + list(set([(p.short_name, p.short_name) for p in programs if p.short_name]))
        dept_choices.sort(key=lambda x: x[0])
        
        self.fields['offering_department'] = forms.ChoiceField(
            choices=dept_choices,
            required=False,
            label="Dept",
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        
        if self.exam_program and not self.instance.pk:
            self.fields['offering_department'].initial = self.exam_program.program.short_name

    def clean(self):
        cleaned_data = super().clean()
        course_code = cleaned_data.get('course_code')
        syllabus = cleaned_data.get('syllabus', '')
        
        if self.exam_program and course_code:
            code_clean = course_code.upper().replace(' ', '')
            qs = ExamCourse.objects.filter(
                exam_program=self.exam_program, 
                course_code=code_clean, 
                syllabus=syllabus,
                is_deleted=False
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Course {course_code} with syllabus '{syllabus}' already exists in this exam.")
        return cleaned_data


class ExamFacultyForm(StyledModelForm):
    class Meta:
        model = ExamFaculty
        fields = ['faculty']

    def __init__(self, *args, **kwargs):
        exam_program = kwargs.pop('exam_program')
        super().__init__(*args, **kwargs)
        self.fields['faculty'].queryset = FacultyProfile.objects.filter(program=exam_program.program, is_active=True)


ROLE_CHOICES = [
    ('', '---------'),
    ('Chairman', 'Chairman'),
    ('Member', 'Member'),
    ('Tabulator 1', 'Tabulator 1'),
    ('Tabulator 2', 'Tabulator 2'),
]

class AssignmentFormMixin:
    def __init__(self, *args, **kwargs):
        exam_program = kwargs.pop('exam_program')
        super().__init__(*args, **kwargs)
        self.exam_program = exam_program
        if 'faculty' in self.fields:
            self.fields['faculty'].queryset = FacultyProfile.objects.filter(program=exam_program.program, is_active=True)
        if 'course' in self.fields:
            self.fields['course'].queryset = ExamCourse.objects.filter(exam_program=exam_program)
        if 'role' in self.fields:
            self.fields['role'] = forms.ChoiceField(
                choices=ROLE_CHOICES,
                required=False,
                widget=forms.Select(attrs={'class': 'form-control'}),
            )

    def clean(self):
        cleaned_data = super().clean()
        course = cleaned_data.get('course')
        part = cleaned_data.get('part')
        role = cleaned_data.get('role')
        faculty = cleaned_data.get('faculty')
        model = self.Meta.model

        # 1. Course + Part uniqueness (Qsetter, Examiner, Scrutinizer)
        if course and part:
            qs = model.objects.filter(exam_program=self.exam_program, course=course, part=part, is_deleted=False)
            if self.instance.pk: qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Course {course} already has an assignment for Part {part}.")

        # 2. QMSC uniqueness
        if model == QMSCAssignment:
            if role == 'Member' and course:
                qs = QMSCAssignment.objects.filter(exam_program=self.exam_program, course=course, role='Member', is_deleted=False)
                if self.instance.pk: qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise forms.ValidationError(f"Course {course} already has a QMSC Member assigned.")
            elif role == 'Chairman':
                qs = QMSCAssignment.objects.filter(exam_program=self.exam_program, role='Chairman', is_deleted=False)
                if self.instance.pk: qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise forms.ValidationError("A QMSC Chairman is already assigned to this department bill.")

        # 3. Faculty uniqueness (CECC, EC, QPSC)
        if faculty and model in [CECCAssignment, ECMember, QPSCMember]:
            qs = model.objects.filter(exam_program=self.exam_program, faculty=faculty, is_deleted=False)
            if self.instance.pk: qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"{faculty.name} is already assigned to this sheet.")

        # 4. RPSC uniqueness (Level + Term + Role)
        if model == RPSCAssignment:
            level = cleaned_data.get('level')
            term = cleaned_data.get('term')
            if level and term and role:
                qs = RPSCAssignment.objects.filter(exam_program=self.exam_program, level=level, term=term, role=role, is_deleted=False)
                if self.instance.pk: qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise forms.ValidationError(f"Role '{role}' is already assigned for Level {level} {term}.")

        return cleaned_data



class CECCAssignmentForm(AssignmentFormMixin, StyledModelForm):
    class Meta:
        model = CECCAssignment
        fields = ['faculty', 'role']


class ECMemberForm(AssignmentFormMixin, StyledModelForm):
    """EC has no level/term — just faculty and role."""
    class Meta:
        model = ECMember
        fields = ['faculty', 'role']


class RPSCAssignmentForm(AssignmentFormMixin, StyledModelForm):
    """Level and Term are dropdowns via model choices (All / Level 1-4 / Term I-II)."""
    class Meta:
        model = RPSCAssignment
        fields = ['role', 'level', 'term', 'faculty']


# ---- QMSC: two separate forms -----------------------------------------------

class QMSCChairmanForm(AssignmentFormMixin, StyledModelForm):
    """Adds a QMSC Chairman — no course, no external member."""
    class Meta:
        model = QMSCAssignment
        fields = ['faculty']

    def clean(self):
        cleaned_data = super().clean()
        qs = QMSCAssignment.objects.filter(exam_program=self.exam_program, role='Chairman', is_deleted=False)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A QMSC Chairman is already assigned to this department bill.")
        return cleaned_data


class QMSCMemberForm(AssignmentFormMixin, StyledModelForm):
    """Adds a per-course QMSC row with internal (faculty) and external member."""
    external_member_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'External member name'}),
        label='External Name',
    )
    external_member_designation = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Designation'}),
        label='External Designation',
    )

    class Meta:
        model = QMSCAssignment
        fields = ['course', 'faculty', 'external_member_name', 'external_member_designation']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Faculty is the internal member — not strictly required if only external assigned
        self.fields['faculty'].required = False
        self.fields['faculty'].label = 'Internal Member'


# ---- QPSC -------------------------------------------------------------------

class QPSCMemberForm(AssignmentFormMixin, StyledModelForm):
    """QPSC: simple Name|Designation|Role table."""
    class Meta:
        model = QPSCMember
        fields = ['faculty', 'role', 'question_count']


class ExamLevelTermSummaryForm(StyledModelForm):
    class Meta:
        model = ExamLevelTermSummary
        fields = ['level', 'term', 'total_students']

    def __init__(self, *args, **kwargs):
        self.exam_program = kwargs.pop('exam_program', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        level = cleaned_data.get('level')
        term = cleaned_data.get('term')
        if self.exam_program and level and term:
            qs = ExamLevelTermSummary.objects.filter(
                exam_program=self.exam_program, level=level, term=term
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Level {level} / Term {term} already has a student count entry.")
        return cleaned_data


class QuestionSetterAssignmentForm(AssignmentFormMixin, StyledModelForm):
    class Meta:
        model = QuestionSetterAssignment
        fields = ['faculty', 'course', 'part']


class ScriptExaminerAssignmentForm(AssignmentFormMixin, StyledModelForm):
    class Meta:
        model = ScriptExaminerAssignment
        fields = ['faculty', 'course', 'part']


class ScriptScrutinizerAssignmentForm(AssignmentFormMixin, StyledModelForm):
    class Meta:
        model = ScriptScrutinizerAssignment
        fields = ['faculty', 'course', 'part']
