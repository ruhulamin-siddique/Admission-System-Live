"""
CoE Module — Forms
"""

from django import forms
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from master_data.models import Program
from .models import ApplicationType, ApplicationStatus, CoeSettings


# ──────────────────────────────────────────────────────────────────────────────
# Public — Application Wizard Forms
# ──────────────────────────────────────────────────────────────────────────────

class ApplicationStep1Form(forms.Form):
    application_type = forms.ChoiceField(
        choices=ApplicationType.choices,
        widget=forms.RadioSelect,
        label=_('Application Type'),
    )


class ApplicationStep2Form(forms.Form):
    """
    Dynamic academic info form. Required fields vary by application_type.
    Pass app_type='...' kwarg on instantiation.
    """
    # Always required
    student_name        = forms.CharField(max_length=200, label=_('Full Name (as per SSC Certificate)'))
    student_id          = forms.CharField(max_length=16, label=_('BAUST Student ID'))
    mobile_number       = forms.CharField(max_length=15, label=_('Mobile Number'))
    email               = forms.EmailField(required=False, label=_('Email Address'))
    department_id       = forms.ModelChoiceField(
        queryset=Program.objects.all().order_by('name'),
        label=_('Department / Program'),
        to_field_name='id',
    )
    admission_batch     = forms.CharField(max_length=10, label=_('Admission Batch'))
    session             = forms.CharField(max_length=20, label=_('Session'))
    passing_semester    = forms.CharField(max_length=30, label=_('Passing Semester'))
    cgpa                = forms.DecimalField(
        max_digits=4, decimal_places=2, min_value=0, max_value=4,
        label=_('CGPA'),
    )
    result_date         = forms.DateField(
        required=False, label=_('Result Publication Date'),
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    # Conditional fields (controlled by app_type)
    father_name         = forms.CharField(max_length=200, required=False, label=_("Father's Name"))
    mother_name         = forms.CharField(max_length=200, required=False, label=_("Mother's Name"))
    dob                 = forms.DateField(
        required=False, label=_('Date of Birth'),
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    corrected_name      = forms.CharField(max_length=200, required=False, label=_('Corrected Full Name'))
    corrected_parent_name = forms.CharField(max_length=200, required=False, label=_('Corrected Parent Name'))
    purpose_destination = forms.CharField(
        required=False, label=_('Purpose / Destination'),
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    level_term          = forms.CharField(max_length=30, required=False, label=_('Level / Term'))
    missing_doc_type    = forms.CharField(max_length=100, required=False, label=_('Type of Missing Document'))

    PARENT_FIELDS_REQUIRED = {
        ApplicationType.PROVISIONAL_TRANSCRIPT,
        ApplicationType.INCOMPLETE_TRANSCRIPT,
        ApplicationType.NAME_CORRECTION,
        ApplicationType.PARENT_NAME_CORRECTION,
    }

    def __init__(self, *args, app_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_type = app_type

        if app_type in self.PARENT_FIELDS_REQUIRED:
            self.fields['father_name'].required = True
            self.fields['mother_name'].required = True
            self.fields['dob'].required = True

        if app_type == ApplicationType.NAME_CORRECTION:
            self.fields['corrected_name'].required = True
        elif app_type == ApplicationType.PARENT_NAME_CORRECTION:
            self.fields['corrected_parent_name'].required = True
        elif app_type == ApplicationType.RECOMMENDATION_LETTER:
            self.fields['purpose_destination'].required = True
        elif app_type == ApplicationType.GRADE_SHEET:
            self.fields['level_term'].required = True
        elif app_type == ApplicationType.DUPLICATE_DOCUMENT:
            self.fields['level_term'].required = True
            self.fields['missing_doc_type'].required = True

    def clean_student_id(self):
        sid = self.cleaned_data.get('student_id')
        if sid:
            sid = ''.join(filter(str.isdigit, sid))
            if len(sid) not in (9, 16):
                raise forms.ValidationError("Student ID must be either 9 digits (legacy) or 16 digits (UGC).")
            if len(sid) == 16 and not sid.startswith('080'):
                raise forms.ValidationError("16-digit UGC Student ID must start with 080 (BAUST university code).")
        return sid

    def clean_mobile_number(self):
        mobile = self.cleaned_data.get('mobile_number')
        if mobile:
            mobile = ''.join(filter(str.isdigit, mobile))
            # Normalise country-code prefixes to bare 01XXXXXXXXX format
            if mobile.startswith('880') and len(mobile) == 13:
                mobile = mobile[3:]   # strip '880' → '01XXXXXXXXX'
            elif mobile.startswith('88') and len(mobile) == 12:
                mobile = mobile[2:]   # strip '88' → '01XXXXXXXXX'
            
            valid_prefixes = ['013', '014', '015', '016', '017', '018', '019']
            if not mobile.startswith('01'):
                raise forms.ValidationError("Bangladeshi mobile number must start with 01")
            prefix = mobile[:3]
            if len(mobile) >= 3 and prefix not in valid_prefixes:
                raise forms.ValidationError(f"Invalid Bangladeshi operator prefix ({prefix}). Must start with 013-019.")
            if len(mobile) != 11:
                raise forms.ValidationError("Bangladeshi mobile number must be exactly 11 digits")
        return mobile

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.strip()
            import re
            email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
            if not re.match(email_regex, email):
                raise forms.ValidationError("Please enter a valid email format (e.g. student@baust.edu.bd)")
        return email

    def cleaned_data_serializable(self) -> dict:
        """Return cleaned_data with DateFields, Decimals, and ModelChoices converted for session storage."""
        from decimal import Decimal
        data = {}
        for key, val in self.cleaned_data.items():
            if hasattr(val, 'isoformat'):
                data[key] = val.isoformat()
            elif isinstance(val, Decimal):
                data[key] = str(val)
            elif hasattr(val, 'pk'):
                data[key] = val.pk
                data[f'{key}_name'] = str(val)
            else:
                data[key] = val
        return data


# ──────────────────────────────────────────────────────────────────────────────
# Public — Tracking Lookup
# ──────────────────────────────────────────────────────────────────────────────

class TrackingLookupForm(forms.Form):
    tracking_number = forms.CharField(
        max_length=20,
        label=_('Application Tracking Number'),
        widget=forms.TextInput(attrs={'placeholder': 'APP-2026-0001'}),
    )
    identifier = forms.CharField(
        max_length=30,
        label=_('Mobile Number or Student ID'),
        widget=forms.TextInput(attrs={'placeholder': _('01XXXXXXXXX or BAUST-ID')}),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Staff — Search / Filter
# ──────────────────────────────────────────────────────────────────────────────

class ApplicationSearchForm(forms.Form):
    q = forms.CharField(
        required=False, label=_('Search'),
        widget=forms.TextInput(attrs={'placeholder': _('Name, ID, tracking no…')}),
    )
    status = forms.ChoiceField(
        required=False, label=_('Status'),
        choices=[('', _('All Statuses'))] + list(ApplicationStatus.choices),
    )
    application_type = forms.ChoiceField(
        required=False, label=_('Type'),
        choices=[('', _('All Types'))] + list(ApplicationType.choices),
    )
    department = forms.ModelChoiceField(
        required=False, queryset=Program.objects.all().order_by('name'),
        label=_('Department'), empty_label=_('All Departments'),
    )
    date_from = forms.DateField(
        required=False, label=_('From'),
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False, label=_('To'),
        widget=forms.DateInput(attrs={'type': 'date'}),
    )


# ──────────────────────────────────────────────────────────────────────────────
# HoD Review Form
# ──────────────────────────────────────────────────────────────────────────────

class HodReviewForm(forms.Form):
    ACTION_CHOICES = [
        ('approve', _('Approve & Forward to CoE')),
        ('hold',    _('Place on Hold')),
        ('reject',  _('Reject Application')),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, label=_('Action'))
    note = forms.CharField(
        required=False, label=_('Note / Reason'),
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': _('Optional note or mandatory rejection reason…')}),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Officer Assignment Form
# ──────────────────────────────────────────────────────────────────────────────

class OfficerAssignForm(forms.Form):
    officer = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label=_('Processing Officer'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .utils import get_coe_processing_officers
        self.fields['officer'].queryset = get_coe_processing_officers()


# ──────────────────────────────────────────────────────────────────────────────
# Processing — Board Verification Form
# ──────────────────────────────────────────────────────────────────────────────

class ProcessingBoardForm(forms.Form):
    BOARD_CHOICES = [
        ('dhaka', _('Dhaka Board')),
        ('rajshahi', _('Rajshahi Board')),
        ('chittagong', _('Chittagong Board')),
        ('sylhet', _('Sylhet Board')),
        ('barishal', _('Barishal Board')),
        ('comilla', _('Comilla Board')),
        ('jessore', _('Jessore Board')),
        ('mymensingh', _('Mymensingh Board')),
        ('dinajpur', _('Dinajpur Board')),
        ('technical', _('Technical Board')),
        ('madrasah', _('Madrasah Board')),
    ]
    board_roll         = forms.CharField(max_length=30, label=_('Board Roll Number'))
    board_registration = forms.CharField(max_length=30, label=_('Board Registration Number'))
    board_name         = forms.ChoiceField(choices=BOARD_CHOICES, label=_('Education Board'))
    board_year         = forms.CharField(max_length=10, label=_('Passing Year'))


# ──────────────────────────────────────────────────────────────────────────────
# Re-upload Request Form
# ──────────────────────────────────────────────────────────────────────────────

class ReuploadRequestForm(forms.Form):
    note = forms.CharField(
        label=_('Issue Description (will be sent via SMS)'),
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': _('Describe what the student needs to re-upload and why…'),
        }),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Delivery OTP Form
# ──────────────────────────────────────────────────────────────────────────────

class DeliveryOtpForm(forms.Form):
    otp = forms.CharField(
        max_length=6, min_length=6, label=_('6-Digit OTP'),
        widget=forms.TextInput(attrs={
            'placeholder': '------',
            'class': 'form-control otp-input',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
        }),
    )

    def clean_otp(self):
        otp = self.cleaned_data['otp']
        if not otp.isdigit():
            raise forms.ValidationError(_('OTP must be a 6-digit number.'))
        return otp


# ──────────────────────────────────────────────────────────────────────────────
# CoE Settings Form
# ──────────────────────────────────────────────────────────────────────────────

class CoeSettingsForm(forms.ModelForm):
    class Meta:
        model = CoeSettings
        exclude = ['updated_at']
        widgets = {
            'tracking_id_prefix': forms.TextInput(attrs={'maxlength': 10, 'class': 'form-control'}),
            'attachment_max_mb': forms.NumberInput(attrs={'min': 1, 'max': 20, 'class': 'form-control'}),
            'rejected_purge_days': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
            'delivered_purge_days': forms.NumberInput(attrs={'min': 30, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'custom-control-input'

