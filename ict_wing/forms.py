from django import forms
from .models import DeviceRegistration

class DeviceRegistrationForm(forms.ModelForm):
    class Meta:
        model = DeviceRegistration
        fields = [
            'full_name', 'email', 'phone', 'user_type', 'department',
            'designation_or_roll', 'device_type', 'device_name_brand',
            'mac_address', 'reason'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Enter your full name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Enter your email address'}),
            'phone': forms.TextInput(attrs={
                'placeholder': 'e.g. 017XXXXXXXX',
                'pattern': r'^(?:\+?88)?01[3-9]\d{8}$',
                'title': 'Enter a valid Bangladeshi mobile number (e.g. 01712345678)'
            }),
            'department': forms.TextInput(attrs={'placeholder': 'e.g. CSE, EEE, BBA'}),
            'designation_or_roll': forms.TextInput(attrs={'placeholder': 'Student Roll ID or staff designation'}),
            'device_name_brand': forms.TextInput(attrs={'placeholder': 'e.g. Asus Vivobook, iPhone 14'}),
            'mac_address': forms.TextInput(attrs={
                'placeholder': 'e.g. 1A:2B:3C:4D:5E:6F',
                'pattern': r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$',
                'title': 'Enter a valid MAC address in format XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX'
            }),
            'reason': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe why Wi-Fi access is needed'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        # Remove country code +88 or 88 if present to normalize formatting
        if phone.startswith('+88'):
            phone = phone[3:]
        elif phone.startswith('88'):
            phone = phone[2:]
        return phone

