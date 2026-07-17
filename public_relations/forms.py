"""
public_relations/forms.py
=========================
Bilingual ModelForms and inline formset factories.
All fields use direct file upload only (no external link fields).
"""

from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .models import (
    MediaHouse,
    PublicRelationsArchive,
    MediaCoverage,
    MediaAsset,
)


# ---------------------------------------------------------------------------
# Shared widget helpers
# ---------------------------------------------------------------------------

_TEXT_INPUT   = forms.TextInput(attrs={'class': 'form-control'})
_EMAIL_INPUT  = forms.EmailInput(attrs={'class': 'form-control'})
_URL_INPUT    = forms.URLInput(attrs={'class': 'form-control', 'type': 'url'})
_TEXTAREA     = forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
_SELECT       = forms.Select(attrs={'class': 'form-control'})
_DATE_INPUT   = forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
_NUMBER_INPUT = forms.NumberInput(attrs={'class': 'form-control'})
_FILE_INPUT   = forms.ClearableFileInput(attrs={'class': 'form-control-file'})


# ---------------------------------------------------------------------------
# Form 1: MediaHouseForm
# ---------------------------------------------------------------------------

class MediaHouseForm(forms.ModelForm):
    """Add or edit a media outlet entry."""

    class Meta:
        model  = MediaHouse
        fields = ['name', 'media_type', 'editor', 'email', 'mobile', 'website', 'whatsapp']
        widgets = {
            'name':       _TEXT_INPUT,
            'media_type': _SELECT,
            'editor':     _TEXT_INPUT,
            'email':      _EMAIL_INPUT,
            'mobile':     _TEXT_INPUT,
            'website':    _URL_INPUT,
            'whatsapp':   _TEXT_INPUT,
        }
        labels = {
            'name':       _('Media Name'),
            'media_type': _('Media Type'),
            'editor':     _('Editor'),
            'email':      _('Email'),
            'mobile':     _('Mobile'),
            'website':    _('Website'),
            'whatsapp':   _('WhatsApp'),
        }

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_mobile(self):
        val = self.cleaned_data.get('mobile', '').strip()
        if val.startswith('+88'):
            val = val[3:]
        elif val.startswith('88') and len(val) == 13:
            val = val[2:]
        return val

    def clean_whatsapp(self):
        val = self.cleaned_data.get('whatsapp', '').strip()
        if val.startswith('+88'):
            val = val[3:]
        elif val.startswith('88') and len(val) == 13:
            val = val[2:]
        return val


# ---------------------------------------------------------------------------
# Form 2: PublicRelationsArchiveForm
# ---------------------------------------------------------------------------

class PublicRelationsArchiveForm(forms.ModelForm):
    """Core press-release metadata."""

    class Meta:
        model  = PublicRelationsArchive
        fields = [
            'press_release_no',
            'press_release_date',
            'event_name',
            'department',
            'full_text',
            'press_release_pdf_file',
            'remarks',
        ]
        widgets = {
            'press_release_no':       _TEXT_INPUT,
            'press_release_date':     _DATE_INPUT,
            'event_name':             _TEXT_INPUT,
            'department':             _TEXT_INPUT,
            'full_text':              forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'press_release_pdf_file': _FILE_INPUT,
            'remarks':                _TEXTAREA,
        }
        labels = {
            'press_release_no':       _('Press Release No'),
            'press_release_date':     _('Date'),
            'event_name':             _('Event Title / Headline'),
            'department':             _('Department / Office Related'),
            'full_text':              _('Full Body Text'),
            'press_release_pdf_file': _('Press Release PDF'),
            'remarks':                _('Remarks'),
        }
        help_texts = {
            'press_release_no': _('Unique serial number, e.g. PR/2026/07/01. Leave blank to auto-generate.'),
            'full_text':        _('Type the complete press release body text here.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['press_release_no'].required = False
        if not self.instance.pk:
            import datetime
            today = datetime.date.today()
            self.fields['press_release_date'].initial = today
            self.fields['press_release_no'].initial = self._meta.model.get_next_pr_number(today)

        self.fields['press_release_no'].widget.attrs['class'] = 'form-control pr-number-field'
        self.fields['press_release_no'].widget.attrs['placeholder'] = _('Leave blank to auto-generate')

    def clean_press_release_no(self):
        val = self.cleaned_data['press_release_no'].strip()
        if val:
            import re
            if not re.match(r'^PR/\d{4}/\d{2}/\d{2,}$', val):
                raise forms.ValidationError(_("Invalid format. The PR number must be in the format 'PR/YYYY/MM/NN' (e.g. PR/2026/07/01)."))
            
            queryset = self._meta.model.objects.filter(press_release_no__iexact=val)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError(_("This Press Release No already exists. Please select a unique number."))
        return val

    def clean_event_name(self):
        return self.cleaned_data['event_name'].strip()


# ---------------------------------------------------------------------------
# Form 3: MediaCoverageForm  (used inside inline formset)
# ---------------------------------------------------------------------------

class MediaCoverageForm(forms.ModelForm):
    """One row of media coverage."""

    class Meta:
        model  = MediaCoverage
        fields = [
            'media_house',
            'published_date',
            'newspaper_pdf_file',
            'screenshot_file',
            'online_link',
        ]
        widgets = {
            'media_house':        _SELECT,
            'published_date':     _DATE_INPUT,
            'newspaper_pdf_file': _FILE_INPUT,
            'screenshot_file':    forms.ClearableFileInput(attrs={'class': 'form-control-file', 'accept': 'image/*'}),
            'online_link':        _URL_INPUT,
        }
        labels = {
            'media_house':        _('Media House'),
            'published_date':     _('Published Date'),
            'newspaper_pdf_file': _('News PDF'),
            'screenshot_file':    _('Screenshot'),
            'online_link':        _('Online Link'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            import datetime
            self.fields['published_date'].initial = datetime.date.today()

    def clean(self):
        cleaned = super().clean()
        media_house = cleaned.get('media_house')
        if not media_house and any([
            cleaned.get('published_date'),
            cleaned.get('newspaper_pdf_file'),
            cleaned.get('screenshot_file'),
            cleaned.get('online_link'),
        ]):
            self.add_error('media_house', _('Media house is required for a coverage row.'))
        return cleaned


# ---------------------------------------------------------------------------
# Form 4: MediaAssetForm  (used inside inline formset)
# ---------------------------------------------------------------------------

class MediaAssetForm(forms.ModelForm):
    """One row of a multimedia asset."""

    class Meta:
        model  = MediaAsset
        fields = ['asset_type', 'file_upload', 'link', 'year', 'caption']
        widgets = {
            'asset_type':  _SELECT,
            'file_upload': _FILE_INPUT,
            'link':        _URL_INPUT,
            'year':        _NUMBER_INPUT,
            'caption':     _TEXT_INPUT,
        }
        labels = {
            'asset_type':  _('Asset Type'),
            'file_upload': _('Upload File'),
            'link':        _('External Link (YouTube / Drive / Facebook)'),
            'year':        _('Year'),
            'caption':     _('Caption'),
        }

    def clean(self):
        cleaned    = super().clean()
        asset_type = cleaned.get('asset_type')
        file_upload = cleaned.get('file_upload')
        link_val   = cleaned.get('link', '').strip() if cleaned.get('link') else ''

        # Photo: file upload required
        if asset_type == 'photo' and not file_upload:
            self.add_error('file_upload', _('A photo file upload is required.'))

        # Video: external link required (no direct upload for large video files)
        if asset_type == 'video' and not link_val:
            self.add_error('link', _('An external link is required for video assets.'))

        # Drive / YouTube / Facebook: link required
        if asset_type in ('drive', 'youtube', 'facebook') and not link_val:
            self.add_error('link', _('An external link URL is required for this asset type.'))

        return cleaned


# ---------------------------------------------------------------------------
# Inline formset factories
# ---------------------------------------------------------------------------

MediaCoverageFormSet = inlineformset_factory(
    PublicRelationsArchive,
    MediaCoverage,
    form=MediaCoverageForm,
    extra=1,
    can_delete=True,
    fields=['media_house', 'published_date', 'newspaper_pdf_file', 'screenshot_file', 'online_link'],
)

MediaAssetFormSet = inlineformset_factory(
    PublicRelationsArchive,
    MediaAsset,
    form=MediaAssetForm,
    extra=1,
    can_delete=True,
    fields=['asset_type', 'file_upload', 'link', 'year', 'caption'],
)


# ---------------------------------------------------------------------------
# Form 5: PRSearchForm  (unbound filter engine form)
# ---------------------------------------------------------------------------

class PRSearchForm(forms.Form):
    """Multi-parameter search / filter form for the archive list."""

    keyword    = forms.CharField(
        required=False,
        label=_('Keyword Search'),
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': _('Event title, details body, or serial no.'),
        })
    )
    start_date = forms.DateField(
        required=False,
        label=_('Start Date'),
        widget=_DATE_INPUT,
    )
    end_date = forms.DateField(
        required=False,
        label=_('End Date'),
        widget=_DATE_INPUT,
    )
    media_type = forms.ChoiceField(
        required=False,
        label=_('Media Type'),
        choices=[('', _('--- All Media Types ---'))] + [
            ('national', _('National Newspaper')),
            ('local',    _('Local Newspaper')),
            ('online',   _('Online Portal')),
            ('tv',       _('TV Channel')),
        ],
        widget=_SELECT,
    )
    department = forms.CharField(
        required=False,
        label=_('Department'),
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': _('Enter department name'),
        })
    )

    def clean(self):
        cleaned    = super().clean()
        start_date = cleaned.get('start_date')
        end_date   = cleaned.get('end_date')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', _('End date cannot be earlier than start date.'))
        return cleaned
