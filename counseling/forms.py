"""
counseling/forms.py
===================
Forms for Case Intake, Appointment Scheduling, SOAP Records, Emergency Triage,
and Public Student Booking.
"""

from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import (
    CounselingCase,
    CounselingAppointment,
    SessionRecord,
    EmergencyIntervention,
    WellbeingWorkshop,
    CounselingSettings,
    CounselorProfile,
    CaseCategory,
    RiskLevel,
    CaseStatus,
    AppointmentMode,
    ReferralSource,
    AppointmentStatus
)
from students.models import Student


class CounselingCaseIntakeForm(forms.ModelForm):
    student_id_input = forms.CharField(
        max_length=50,
        required=True,
        label=_("Student ID (UGC ID)"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter 16-digit or Legacy Student ID...'),
            'id': 'id_student_lookup_input',
            'autocomplete': 'off'
        })
    )

    class Meta:
        model = CounselingCase
        fields = [
            'alias_code',
            'category',
            'risk_level',
            'status',
            'assigned_counselor',
            'intake_date',
            'presenting_complaints',
            'sleep_appetite_notes',
            'family_social_notes',
            'medication_history',
        ]
        widgets = {
            'alias_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Optional pseudonym e.g. Client-A')}),
            'category': forms.Select(attrs={'class': 'form-control select2'}),
            'risk_level': forms.Select(attrs={'class': 'form-control select2'}),
            'status': forms.Select(attrs={'class': 'form-control select2'}),
            'assigned_counselor': forms.Select(attrs={'class': 'form-control select2'}),
            'intake_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'presenting_complaints': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': _('Describe main issues, triggers, timeline...')}),
            'sleep_appetite_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Hours of sleep, insomnia, appetite changes...')}),
            'family_social_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Family dynamics, parental support, roommate conflict...')}),
            'medication_history': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Current prescriptions, past psychiatrist visits...')}),
        }

    def clean_student_id_input(self):
        sid = self.cleaned_data.get('student_id_input', '').strip()
        student = Student.objects.filter(student_id=sid).first()
        if not student:
            # Try searching old_student_id
            student = Student.objects.filter(old_student_id=sid).first()
        if not student:
            raise forms.ValidationError(_(f"No student record found with ID: '{sid}'. Please check the student directory."))
        self.cleaned_student = student
        return sid


class CounselingAppointmentForm(forms.ModelForm):
    class Meta:
        model = CounselingAppointment
        fields = [
            'case',
            'counselor',
            'appointment_date',
            'time_slot',
            'session_mode',
            'referral_source',
            'status',
            'student_notes',
        ]
        widgets = {
            'case': forms.Select(attrs={'class': 'form-control select2'}),
            'counselor': forms.Select(attrs={'class': 'form-control select2', 'id': 'id_counselor_select'}),
            'appointment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'id_appointment_date'}),
            'time_slot': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_time_slot_input', 'placeholder': 'e.g. 10:00 AM - 10:50 AM'}),
            'session_mode': forms.Select(attrs={'class': 'form-control'}),
            'referral_source': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'student_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Any special requests or pre-session notes...')}),
        }

    def clean(self):
        cleaned_data = super().clean()
        counselor = cleaned_data.get('counselor')
        appt_date = cleaned_data.get('appointment_date')
        time_slot = cleaned_data.get('time_slot')
        status = cleaned_data.get('status')

        if counselor and appt_date and time_slot and status not in [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]:
            conflict = CounselingAppointment.objects.filter(
                counselor=counselor,
                appointment_date=appt_date,
                time_slot=time_slot,
                status__in=[AppointmentStatus.CONFIRMED, AppointmentStatus.REQUESTED]
            )
            if self.instance and self.instance.pk:
                conflict = conflict.exclude(pk=self.instance.pk)
            if conflict.exists():
                self.add_error('time_slot', _(f"This time slot ({time_slot}) is already booked for this counselor on {appt_date}."))
        return cleaned_data


class SessionRecordForm(forms.ModelForm):
    class Meta:
        model = SessionRecord
        fields = [
            'session_number',
            'session_date',
            'subjective_notes',
            'objective_notes',
            'assessment',
            'plan',
            'next_session_date',
        ]
        widgets = {
            'session_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'session_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'subjective_notes': forms.Textarea(attrs={'class': 'form-control soap-field', 'id': 'id_subjective', 'rows': 5, 'placeholder': _("Student's self-reported feelings, thoughts, and recent life events...")}),
            'objective_notes': forms.Textarea(attrs={'class': 'form-control soap-field', 'id': 'id_objective', 'rows': 5, 'placeholder': _("Therapist's observations: Appearance, affect, eye contact, speech, psychomotor state...")}),
            'assessment': forms.Textarea(attrs={'class': 'form-control soap-field', 'id': 'id_assessment', 'rows': 5, 'placeholder': _("Diagnostic impressions, formulation of progress, symptom change analysis...")}),
            'plan': forms.Textarea(attrs={'class': 'form-control soap-field', 'id': 'id_plan', 'rows': 5, 'placeholder': _("Interventions used (CBT/Mindfulness), homework assigned, safety plan, next appointment...")}),
            'next_session_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class EmergencyInterventionForm(forms.ModelForm):
    class Meta:
        model = EmergencyIntervention
        fields = [
            'incident_type',
            'actions_taken',
            'medical_referral_made',
            'hospital_name',
            'authorities_notified',
            'safety_contract_signed',
            'resolved',
            'resolution_notes',
        ]
        widgets = {
            'incident_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Suicidal Ideation / Panic Attack / Self-Harm Risk')}),
            'actions_taken': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': _('Immediate steps taken in chamber / hall...')}),
            'medical_referral_made': forms.CheckboxInput(attrs={'class': 'custom-control-input', 'id': 'id_med_referral'}),
            'hospital_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Combined Military Hospital (CMH) Saidpur')}),
            'authorities_notified': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Provost contacted, Chief Medical Officer, Parents/Guardian phone log...')}),
            'safety_contract_signed': forms.CheckboxInput(attrs={'class': 'custom-control-input', 'id': 'id_safety_contract'}),
            'resolved': forms.CheckboxInput(attrs={'class': 'custom-control-input', 'id': 'id_resolved'}),
            'resolution_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Follow-up schedule and resolution summary...')}),
        }


class WellbeingWorkshopForm(forms.ModelForm):
    class Meta:
        model = WellbeingWorkshop
        fields = [
            'title',
            'speaker',
            'venue',
            'event_date',
            'start_time',
            'target_audience',
            'description',
            'capacity',
            'is_cancelled',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Overcoming Exam Anxiety & Burnout')}),
            'speaker': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Guest Psychologist / Facilitator')}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Central Auditorium / Hall-1')}),
            'event_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'target_audience': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Level 1 Students, All Residential Students')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Topics covered, workshop format...')}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 10}),
            'is_cancelled': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
        }


class CounselingSettingsForm(forms.ModelForm):
    class Meta:
        model = CounselingSettings
        fields = [
            'enable_sms_notifications',
            'sms_template_appointment_confirm',
            'sms_template_crisis_alert',
            'session_lock_hours',
            'crisis_sla_hours',
            'default_slot_duration_minutes',
            'counselor_room_default',
        ]
        widgets = {
            'enable_sms_notifications': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'sms_template_appointment_confirm': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'sms_template_crisis_alert': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'session_lock_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'crisis_sla_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'default_slot_duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 15}),
            'counselor_room_default': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CounselorProfileForm(forms.ModelForm):
    class Meta:
        model = CounselorProfile
        fields = [
            'designation',
            'license_number',
            'room_number',
            'contact_number',
            'is_active_counselor',
            'weekly_slots_json',
            'bio',
        ]
        widgets = {
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active_counselor': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'weekly_slots_json': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': '{\n  "Sunday": ["09:00 AM - 09:50 AM", "10:00 AM - 10:50 AM"],\n  "Monday": ["09:00 AM - 09:50 AM", "10:00 AM - 10:50 AM"]\n}'
            }),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# ============================================================================
# Public Student Booking Portal Form (Self-Service)
# ============================================================================

class PublicStudentBookingForm(forms.Form):
    student_id = forms.CharField(
        max_length=50,
        required=True,
        label=_("Student ID"),
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': _('e.g. 202401040012 or 9-digit ID'),
            'id': 'public_student_id'
        })
    )
    student_mobile = forms.CharField(
        max_length=20,
        required=True,
        label=_("Active Mobile Number / সক্রিয় মোবাইল নম্বর"),
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': _('e.g. 017XXXXXXXX or 018XXXXXXXX'),
            'id': 'public_mobile'
        })
    )
    category = forms.ChoiceField(
        choices=[
            ('academic_stress', _('একাডেমিক চাপ ও পড়াশোনায় মনোযোগ (Academic Stress)')),
            ('exam_anxiety', _('পরীক্ষার ভয় ও অতিরিক্ত দুশ্চিন্তা (Exam & Test Anxiety)')),
            ('hall_homesick', _('হল জীবন ও বাড়ির জন্য মন খারাপ (Hall Life & Homesickness)')),
            ('family_relations', _('পারিবারিক ও ব্যক্তিগত সম্পর্ক (Family & Relationships)')),
            ('grief_trauma', _('মানসিক ট্রমা, হতাশা ও শোক (Grief, Loss & Trauma)')),
            ('substance', _('অভ্যাস ও আসক্তি নিয়ন্ত্রণ (Habit & Substance Support)')),
            ('career_esteem', _('ভবিষ্যৎ ক্যারিয়ার ও আত্মবিশ্বাস (Career & Self-Esteem)')),
            ('other', _('অন্যান্য ব্যক্তিগত সমস্যা (Other Concerns)')),
        ],
        required=True,
        label=_("পরামর্শের মূল বিষয় / উদ্বেগের কারণ"),
        widget=forms.Select(attrs={'class': 'form-control form-control-lg', 'id': 'public_category_select'})
    )
    urgency = forms.ChoiceField(
        choices=[
            ('routine', _('🟢 রুটিন কাউন্সেলিং (Routine Check-in)')),
            ('priority', _('🟡 অগ্রাধিকার সহায়তা (Priority Support)')),
            ('crisis', _('🔴 জরুরি সংকটকালীন সহায়তা (Urgent Crisis Care)')),
        ],
        initial='routine',
        required=True,
        label=_("সহায়তার প্রয়োজনীয়তার মাত্রা"),
        widget=forms.RadioSelect()
    )
    session_mode = forms.ChoiceField(
        choices=AppointmentMode.choices,
        initial=AppointmentMode.IN_PERSON,
        required=True,
        label=_("পরামর্শ গ্রহণের মাধ্যম"),
        widget=forms.RadioSelect()
    )
    appointment_date = forms.DateField(
        required=True,
        label=_("পছন্দের তারিখ"),
        widget=forms.DateInput(attrs={'class': 'form-control form-control-lg', 'type': 'date', 'id': 'public_date_input'})
    )
    time_slot = forms.CharField(
        max_length=50,
        required=True,
        label=_("পছন্দের সময়সূচি"),
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Select slot e.g. 10:00 AM - 10:50 AM', 'id': 'public_time_slot'})
    )
    brief_notes = forms.CharField(
        required=False,
        label=_("সংক্ষিপ্ত বিবরণ / আপনার মনের কথা (ঐচ্ছিক ও সম্পূর্ণ গোপনীয়)"),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'id': 'public_brief_notes',
            'placeholder': _('কাউন্সেলরকে আপনার সমস্যাটি সহজে বুঝতে সাহায্য করতে সংক্ষেপে কিছু লিখতে পারেন...')
        })
    )
    consent_agreed = forms.BooleanField(
        required=True,
        label=_("আমি কাউন্সেলিং সহায়তার জন্য সম্মত এবং অবগত আছি যে আমার আলোচনা সম্পূর্ণ গোপন থাকবে।"),
        widget=forms.CheckboxInput(attrs={'class': 'consent-checkbox-input', 'id': 'public_consent'})
    )

    def clean(self):
        import re
        cleaned_data = super().clean()
        sid = cleaned_data.get('student_id', '').strip()
        mobile = cleaned_data.get('student_mobile', '').strip()

        # 1. Validate student existence in database
        student = Student.objects.filter(student_id=sid).first() or Student.objects.filter(old_student_id=sid).first()
        if not student:
            self.add_error('student_id', _("শিক্ষার্থী আইডিটি সিস্টেমে পাওয়া যায়নি। অনুগ্রহ করে ১৬ বা ৯ ডিজিটের সঠিক আইডি লিখুন। (No student profile found for this ID)."))
            return cleaned_data

        # 2. Validate Bangladeshi Mobile Number Format (Flexible for any student SIM)
        cleaned_mobile = ''.join(filter(str.isdigit, str(mobile or '')))
        if cleaned_mobile.startswith('880'):
            cleaned_mobile = cleaned_mobile[2:]
        elif cleaned_mobile.startswith('+880'):
            cleaned_mobile = cleaned_mobile[3:]

        if not re.match(r'^01[3-9]\d{8}$', cleaned_mobile):
            self.add_error('student_mobile', _("অনুগ্রহ করে একটি সঠিক ১১ ডিজিটের বাংলাদেশি মোবাইল নম্বর লিখুন (যেমন: 017XXXXXXXX)। Please enter a valid 11-digit Bangladeshi mobile number."))
        else:
            cleaned_data['cleaned_mobile'] = cleaned_mobile

        # 3. Validate appointment date
        appt_date = cleaned_data.get('appointment_date')
        time_slot = cleaned_data.get('time_slot')
        if appt_date and appt_date < timezone.localdate():
            self.add_error('appointment_date', _("অনুগ্রহ করে আজকের বা ভবিষ্যতের একটি তারিখ নির্বাচন করুন। (Past dates cannot be selected)."))

        # 4. Validate slot availability with active counselor
        if appt_date and time_slot:
            active_counselor = CounselorProfile.objects.filter(is_active_counselor=True).first()
            if active_counselor:
                is_taken = CounselingAppointment.objects.filter(
                    counselor=active_counselor,
                    appointment_date=appt_date,
                    time_slot=time_slot,
                    status__in=[AppointmentStatus.CONFIRMED, AppointmentStatus.REQUESTED]
                ).exists()
                if is_taken:
                    self.add_error('time_slot', _("দুঃখিত, এই সময়সূচিটি ইতিমধ্যেই অন্য কারো জন্য নির্ধারিত হয়েছে। অনুগ্রহ করে অন্য সময় বেছে নিন। (This slot is already booked)."))

        cleaned_data['student_obj'] = student
        return cleaned_data


class PublicAppointmentStatusLookupForm(forms.Form):
    lookup_query = forms.CharField(
        max_length=60,
        required=True,
        label=_("Secret Tracking Token or Student ID"),
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': _('e.g. CARE-2026-XXXX or Student ID'),
            'id': 'status_lookup_input',
            'autocomplete': 'off'
        })
    )
