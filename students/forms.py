from django import forms
from .models import Student
from datetime import datetime

BOARD_CHOICES = [
    ('', 'Select Board'),
    ('Dhaka', 'Dhaka'),
    ('Rajshahi', 'Rajshahi'),
    ('Comilla', 'Comilla'),
    ('Jessore', 'Jessore'),
    ('Chittagong', 'Chittagong'),
    ('Barisal', 'Barisal'),
    ('Sylhet', 'Sylhet'),
    ('Dinajpur', 'Dinajpur'),
    ('Mymensingh', 'Mymensingh'),
    ('Madrasah', 'Madrasah'),
    ('Technical', 'Technical'),
    ('Other', 'Other'),
]

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        exclude = ['created_at', 'last_updated', 'photo_path']
        labels = {
            'program_type': 'Program Type',
            'admission_year': 'Admission Year',
            'semester_name': 'Admitted Semester',
            'hall_attached': 'Hall Attachment',
        }
        widgets = {
            'student_id': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'placeholder': 'Generated upon selection...'}),
            'student_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'old_student_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Previous ID (if any)'}),
            'program': forms.Select(attrs={'class': 'form-control select2'}),
            'cluster': forms.Select(attrs={'class': 'form-control'}),
            'batch': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 25th'}),
            'semester_name': forms.Select(attrs={'class': 'form-control'}),
            'program_type': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('Bachelor', 'Bachelor'),
                ('Masters', 'Masters'),
            ]),
            'admission_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'admission_status': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('Active', 'Active'),
                ('Inactive', 'Inactive'),
            ]),
            'gender': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('Male', 'Male'),
                ('Female', 'Female'),
                ('Other', 'Other'),
            ]),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'blood_group': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('A+', 'A+'), ('A-', 'A-'),
                ('B+', 'B+'), ('B-', 'B-'),
                ('O+', 'O+'), ('O-', 'O-'),
                ('AB+', 'AB+'), ('AB-', 'AB-'),
            ]),
            'religion': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('Islam', 'Islam'),
                ('Hinduism', 'Hinduism'),
                ('Buddhism', 'Buddhism'),
                ('Christianity', 'Christianity'),
                ('Other', 'Other'),
            ]),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
            'father_occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'student_mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '01XXXXXXXXX'}),
            'father_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'student_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'present_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'permanent_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'ssc_school': forms.TextInput(attrs={'class': 'form-control', 'list': 'school_list', 'placeholder': 'Start typing school name...'}),
            'ssc_year': forms.TextInput(attrs={'class': 'form-control', 'list': 'year_list'}),
            'ssc_board': forms.Select(attrs={'class': 'form-control'}, choices=BOARD_CHOICES),
            'ssc_roll': forms.TextInput(attrs={'class': 'form-control'}),
            'ssc_reg': forms.TextInput(attrs={'class': 'form-control'}),
            'ssc_gpa': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hsc_college': forms.TextInput(attrs={'class': 'form-control', 'list': 'college_list', 'placeholder': 'Start typing college name...'}),
            'hsc_year': forms.TextInput(attrs={'class': 'form-control', 'list': 'year_list'}),
            'hsc_board': forms.Select(attrs={'class': 'form-control'}, choices=BOARD_CHOICES),
            'hsc_roll': forms.TextInput(attrs={'class': 'form-control'}),
            'hsc_reg': forms.TextInput(attrs={'class': 'form-control'}),
            'hsc_gpa': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hall_attached': forms.Select(attrs={'class': 'form-control'}),
            'admission_payment': forms.NumberInput(attrs={'class': 'form-control'}),
            'second_installment': forms.NumberInput(attrs={'class': 'form-control'}),
            'waiver': forms.NumberInput(attrs={'class': 'form-control'}),
            'others': forms.NumberInput(attrs={'class': 'form-control'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'mba_credits': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_non_residential': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'is_freedom_fighter_child': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'is_armed_forces_child': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'is_july_joddha_2024': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'is_credit_transfer': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'is_temp_admission_cancel': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            
            # Structured Addresses
            'present_division': forms.Select(attrs={'class': 'form-control'}),
            'present_district': forms.Select(attrs={'class': 'form-control'}),
            'present_upazila': forms.Select(attrs={'class': 'form-control'}),
            'present_village': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Village/Area/House'}),
            
            'permanent_division': forms.Select(attrs={'class': 'form-control'}),
            'permanent_district': forms.Select(attrs={'class': 'form-control'}),
            'permanent_upazila': forms.Select(attrs={'class': 'form-control'}),
            'permanent_village': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Village/Area/House'}),
            
            # Subject Marks
            'ssc_physics': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'title': 'Enter SSC Physics Grade Point or Marks'}),
            'ssc_chemistry': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'title': 'Enter SSC Chemistry Grade Point or Marks'}),
            'ssc_math': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'title': 'Enter SSC Math Grade Point or Marks'}),
            
            'hsc_physics': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'title': 'Enter HSC Physics Grade Point or Marks'}),
            'hsc_chemistry': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'title': 'Enter HSC Chemistry Grade Point or Marks'}),
            'hsc_math': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'title': 'Enter HSC Math Grade Point or Marks'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from master_data.models import Program, Cluster, Hall, AdmissionYear, Semester, Batch
        
        # Populate dynamic choices
        self.fields['program'].widget.choices = [('', 'Select Program')] + [
            (p.name, p.name) for p in Program.objects.all().order_by('name')
        ]
        self.fields['cluster'].widget.choices = [('', 'Select Cluster')] + [
            (c.name, c.name) for c in Cluster.objects.all().order_by('name')
        ]
        self.fields['hall_attached'].widget.choices = [('', 'Select Hall')] + [
            (h.name, h.name) for h in Hall.objects.all().order_by('name')
        ]
        self.fields['semester_name'].widget.choices = [('', 'Select Semester')] + [
            (s.name, s.name) for s in Semester.objects.all().order_by('name')
        ]
        
        # Batch needs to be a Select instead of TextInput now
        self.fields['batch'].widget = forms.Select(attrs={'class': 'form-control'})
        self.fields['batch'].widget.choices = [('', 'Select Batch')] + [
            (b.name, b.name) for b in Batch.objects.all().order_by('-sort_order', 'name')
        ]
        
        active_years = AdmissionYear.objects.filter(is_active=True).order_by('-year')
        if active_years.exists():
             self.fields['admission_year'].widget = forms.Select(
                 attrs={'class': 'form-control'},
                 choices=[(y.year, y.year) for y in active_years]
             )

        # Mandatory Contact Fields
        self.fields['student_mobile'].required = True
        self.fields['father_mobile'].required = True
        self.fields['mother_mobile'].required = True
        
        # Optional/Removed Mandatory Fields
        self.fields['student_email'].required = False
        self.fields['blood_group'].required = False
        
        # Mandatory Biographical Fields
        self.fields['gender'].required = True
        self.fields['dob'].required = True
        self.fields['religion'].required = True
        
        # Mandatory Family Fields
        self.fields['father_name'].required = True
        self.fields['mother_name'].required = True
        
        # Mandatory Academic Fields (UGC Requirements)
        self.fields['program'].required = True
        self.fields['cluster'].required = True
        self.fields['admission_year'].required = True
        self.fields['semester_name'].required = True
        self.fields['hall_attached'].required = True
        self.fields['program_type'].required = True
        self.fields['batch'].required = True
        
        # Mandatory SSC/Equivalent Fields
        self.fields['ssc_school'].required = True
        self.fields['ssc_board'].required = True
        self.fields['ssc_roll'].required = True
        self.fields['ssc_gpa'].required = True
        
        # Initialize Address Choices
        from .geo_data import BANGLADESH_GEO
        divisions = [('', 'Select Division')] + [(d, d) for d in BANGLADESH_GEO.keys()]
        self.fields['present_division'].widget.choices = divisions
        self.fields['permanent_division'].widget.choices = divisions
        
        # Districts and Upazilas will be populated via AJAX/JS, 
        # but we need to ensure the posted values are valid during form validation.
        # We'll allow any choice for now and handle specific validation if needed.
        self.fields['present_district'].widget.choices = [('', 'Select District')]
        self.fields['present_upazila'].widget.choices = [('', 'Select Upazila')]
        self.fields['permanent_district'].widget.choices = [('', 'Select District')]
        self.fields['permanent_upazila'].widget.choices = [('', 'Select Upazila')]

        # If instance exists (Edit mode), populate the current choices to avoid validation errors
        if self.instance.pk:
            if self.instance.present_division:
                districts = BANGLADESH_GEO.get(self.instance.present_division, {})
                self.fields['present_district'].widget.choices = [('', 'Select District')] + [(d, d) for d in districts.keys()]
                if self.instance.present_district:
                    upazilas = districts.get(self.instance.present_district, [])
                    self.fields['present_upazila'].widget.choices = [('', 'Select Upazila')] + [(u, u) for u in upazilas]
            
            if self.instance.permanent_division:
                districts = BANGLADESH_GEO.get(self.instance.permanent_division, {})
                self.fields['permanent_district'].widget.choices = [('', 'Select District')] + [(d, d) for d in districts.keys()]
                if self.instance.permanent_district:
                    upazilas = districts.get(self.instance.permanent_district, [])
                    self.fields['permanent_upazila'].widget.choices = [('', 'Select Upazila')] + [(u, u) for u in upazilas]

    def clean_national_id(self):
        nid = self.cleaned_data.get('national_id')
        if nid:
            # Strip any non-digit characters
            nid = ''.join(filter(str.isdigit, nid))
            valid_lengths = [10, 13, 17]
            if len(nid) not in valid_lengths:
                raise forms.ValidationError("NID must be 10, 13, or 17 digits long")
        return nid

    def clean_student_mobile(self):
        mobile = self.cleaned_data.get('student_mobile')
        if mobile:
            # Strip any non-digit characters
            mobile = ''.join(filter(str.isdigit, mobile))
            if not mobile.startswith('01'):
                raise forms.ValidationError("Mobile number must start with 01")
            if len(mobile) != 11:
                raise forms.ValidationError("Mobile number must be exactly 11 digits")
        return mobile

    def clean_father_mobile(self):
        return self._clean_mobile(self.cleaned_data.get('father_mobile'))

    def clean_mother_mobile(self):
        return self._clean_mobile(self.cleaned_data.get('mother_mobile'))

    def _clean_mobile(self, mobile):
        if mobile:
            # Strip any non-digit characters
            mobile = ''.join(filter(str.isdigit, mobile))
            if not mobile.startswith('01'):
                raise forms.ValidationError("Mobile number must start with 01")
            if len(mobile) != 11:
                raise forms.ValidationError("Mobile number must be exactly 11 digits")
        return mobile
