from django import forms

from .models import APIClient


class APIClientForm(forms.ModelForm):
    scopes = forms.MultipleChoiceField(
        choices=APIClient.SCOPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = APIClient
        fields = [
            'name',
            'contact_name',
            'contact_email',
            'scopes',
            'allowed_ips',
            'rate_limit_per_minute',
            'is_active',
            'notes',
        ]
        widgets = {
            'allowed_ips': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_scopes(self):
        return list(self.cleaned_data.get('scopes') or [])

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.scopes = self.cleaned_data.get('scopes', [])
        if commit:
            instance.save()
        return instance
