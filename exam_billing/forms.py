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
        exam_program = kwargs.pop('exam_program', None)
        super().__init__(*args, **kwargs)
        if exam_program:
            self.fields['offering_department'].initial = exam_program.program.short_name
            self.fields['offering_department'].widget.attrs['readonly'] = True
            self.fields['offering_department'].widget.attrs['class'] += ' bg-light text-muted'


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
    """QPSC: simple Name|Designation|Role table. question_count kept for billing only."""
    class Meta:
        model = QPSCMember
        fields = ['faculty', 'role']


class ExamLevelTermSummaryForm(StyledModelForm):
    class Meta:
        model = ExamLevelTermSummary
        fields = ['level', 'term', 'total_students']


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
