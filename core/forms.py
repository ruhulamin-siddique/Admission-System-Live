from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from master_data.models import Program

from .models import Role


def get_department_scope_choices(include_blank=True, current_value=None):
    choices = []
    seen_values = set()

    if include_blank:
        choices.append(('', 'Global Access'))

    programs = Program.objects.select_related('cluster').order_by('cluster__name', 'name')
    for program in programs:
        value = (program.short_name or program.name or '').strip()
        if not value or value in seen_values:
            continue

        label = program.name
        if program.short_name:
            label = f'{program.short_name} - {program.name}'

        choices.append((value, label))
        seen_values.add(value)

    current_value = (current_value or '').strip()
    if current_value and current_value not in seen_values:
        choices.append((current_value, current_value))

    return choices


def get_department_scope_label(value):
    scope_value = (value or '').strip()
    if not scope_value:
        return 'Global Access'

    for choice_value, choice_label in get_department_scope_choices(include_blank=False, current_value=scope_value):
        if choice_value == scope_value:
            return choice_label

    return scope_value


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ('name', 'description')

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        qs = Role.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise forms.ValidationError('A role with this name already exists.')
        return name


class StaffUserCreateForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)
    role = forms.ModelChoiceField(queryset=Role.objects.none(), required=False)
    department_scope = forms.ChoiceField(choices=(), required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].queryset = Role.objects.order_by('name')
        self.fields['department_scope'].choices = get_department_scope_choices()

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email address is already used by another account.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name'].strip()
        user.last_name = self.cleaned_data['last_name'].strip()
        user.email = self.cleaned_data['email']
        user.is_staff = True

        if commit:
            user.save()
            profile = user.profile
            profile.role = self.cleaned_data['role']
            profile.department_scope = self.cleaned_data['department_scope']
            profile.save()

        return user


class UserAccessForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    employee_id = forms.CharField(max_length=50, required=False)
    designation = forms.CharField(max_length=100, required=False)
    department = forms.CharField(max_length=100, required=False)
    phone_number = forms.CharField(max_length=15, required=False)
    role = forms.ModelChoiceField(queryset=Role.objects.none(), required=False)
    department_scope = forms.ChoiceField(choices=(), required=False)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['role'].queryset = Role.objects.order_by('name')
        self.fields['department_scope'].choices = get_department_scope_choices(
            current_value=getattr(getattr(user, 'profile', None), 'department_scope', ''),
        )

        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['role'].initial = getattr(user.profile, 'role', None)
            self.fields['department_scope'].initial = getattr(user.profile, 'department_scope', '')
            
            profile = user.profile
            self.fields['employee_id'].initial = profile.employee_id
            self.fields['designation'].initial = profile.designation
            self.fields['department'].initial = profile.department
            self.fields['phone_number'].initial = profile.phone_number

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('This email address is already used by another account.')
        return email

    def save(self):
        self.user.first_name = self.cleaned_data['first_name'].strip()
        self.user.last_name = self.cleaned_data['last_name'].strip()
        self.user.email = self.cleaned_data['email']
        self.user.save(update_fields=['first_name', 'last_name', 'email'])

        profile = self.user.profile
        profile.role = self.cleaned_data['role']
        profile.department_scope = self.cleaned_data['department_scope']
        
        profile.employee_id = self.cleaned_data['employee_id']
        profile.designation = self.cleaned_data['designation']
        profile.department = self.cleaned_data['department']
        profile.phone_number = self.cleaned_data['phone_number']
        
        profile.save()
        return self.user


class UserSelfProfileForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    photo = forms.ImageField(required=False)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('This email address is already used by another account.')
        return email

    def save(self):
        self.user.first_name = self.cleaned_data['first_name'].strip()
        self.user.last_name = self.cleaned_data['last_name'].strip()
        self.user.email = self.cleaned_data['email']
        self.user.save(update_fields=['first_name', 'last_name', 'email'])
        
        profile = self.user.profile
        if self.cleaned_data.get('photo'):
            profile.photo = self.cleaned_data['photo']
            profile.save(update_fields=['photo'])
        return self.user


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'University Email'}))
    employee_id = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'placeholder': 'Employee ID'}))
    designation = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'placeholder': 'Designation'}))
    department = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'placeholder': 'Department'}))
    phone_number = forms.CharField(max_length=11, required=True, widget=forms.TextInput(attrs={'placeholder': 'Phone (01XXXXXXXXX)'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if not email.endswith('@baust.edu.bd'):
            raise forms.ValidationError("Please use your verified university edumail.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '')
        import re
        if not re.match(r'^01[3-9]\d{8}$', phone):
            raise forms.ValidationError("Please enter a valid 11-digit Bangladeshi phone number.")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name'].strip()
        user.last_name = self.cleaned_data['last_name'].strip()
        user.is_active = False
        user.is_staff = True
        
        if commit:
            user.save()
            profile = user.profile
            profile.registration_status = 'PENDING'
            profile.is_active = False
            
            # Map university fields
            profile.employee_id = self.cleaned_data['employee_id']
            profile.designation = self.cleaned_data['designation']
            profile.department = self.cleaned_data['department']
            profile.phone_number = self.cleaned_data['phone_number']
            
            profile.save()
        return user
