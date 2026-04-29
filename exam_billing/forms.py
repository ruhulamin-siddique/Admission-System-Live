from django import forms

from master_data.models import Program

from .models import (
    BillingExam,
    BillingRateTemplate,
    CECCAssignment,
    ECMember,
    ExamCourse,
    ExamFaculty,
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


class FacultyProfileForm(StyledModelForm):
    class Meta:
        model = FacultyProfile
        fields = ['name', 'designation', 'employee_id', 'program', 'is_active']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['program'].queryset = get_allowed_programs(user) if user else Program.objects.all()


class ExamCourseForm(StyledModelForm):
    class Meta:
        model = ExamCourse
        fields = ['level', 'term', 'course_code', 'offering_department', 'no_of_scripts', 'syllabus', 'course_title', 'total_students', 'is_engineering']


class ExamFacultyForm(StyledModelForm):
    class Meta:
        model = ExamFaculty
        fields = ['faculty']

    def __init__(self, *args, **kwargs):
        exam_program = kwargs.pop('exam_program')
        super().__init__(*args, **kwargs)
        self.fields['faculty'].queryset = FacultyProfile.objects.filter(program=exam_program.program, is_active=True)


class AssignmentFormMixin:
    def __init__(self, *args, **kwargs):
        exam_program = kwargs.pop('exam_program')
        super().__init__(*args, **kwargs)
        self.exam_program = exam_program
        if 'faculty' in self.fields:
            self.fields['faculty'].queryset = FacultyProfile.objects.filter(program=exam_program.program, is_active=True)
        if 'course' in self.fields:
            self.fields['course'].queryset = ExamCourse.objects.filter(exam_program=exam_program)


class CECCAssignmentForm(AssignmentFormMixin, StyledModelForm):
    class Meta:
        model = CECCAssignment
        fields = ['faculty', 'role']


class ECMemberForm(AssignmentFormMixin, StyledModelForm):
    class Meta:
        model = ECMember
        fields = ['faculty', 'role', 'level', 'term']


class RPSCAssignmentForm(AssignmentFormMixin, StyledModelForm):
    class Meta:
        model = RPSCAssignment
        fields = ['faculty', 'role', 'level', 'term', 'total_students']


class QMSCAssignmentForm(AssignmentFormMixin, StyledModelForm):
    class Meta:
        model = QMSCAssignment
        fields = ['faculty', 'course', 'role', 'is_external']


class QPSCMemberForm(AssignmentFormMixin, StyledModelForm):
    class Meta:
        model = QPSCMember
        fields = ['faculty', 'role', 'question_count']


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
