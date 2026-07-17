"""
public_relations/models.py
==========================
Bilingual schema using Django's gettext_lazy translation functions.
Media files (PDFs, screenshots, assets) are stored as direct file uploads.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
import datetime


# ---------------------------------------------------------------------------
# Choices (Translated at runtime)
# ---------------------------------------------------------------------------

MEDIA_TYPE_CHOICES = [
    ('national', _('National Newspaper')),
    ('local',    _('Local Newspaper')),
    ('online',   _('Online Portal')),
    ('tv',       _('TV Channel')),
]

ASSET_TYPE_CHOICES = [
    ('photo',    _('Photo')),
    ('video',    _('Video')),
    ('drive',    _('Google Drive')),
    ('youtube',  _('YouTube')),
    ('facebook', _('Facebook')),
]

CURRENT_YEAR = datetime.date.today().year


# ---------------------------------------------------------------------------
# Model 1: MediaHouse
# ---------------------------------------------------------------------------

class MediaHouse(models.Model):
    """Directory record for a print, local, or online media outlet."""

    phone_validator = RegexValidator(
        regex=r'^(?:\+?88)?01[3-9]\d{8}$',
        message=_("Enter a valid Bangladeshi mobile number (e.g. 01712345678)")
    )

    name       = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("Media Name"),
        help_text=_("Full name of the media house or portal")
    )
    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPE_CHOICES,
        verbose_name=_("Media Type")
    )
    editor     = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Editor"),
        help_text=_("Name of the Chief Editor")
    )
    email      = models.EmailField(blank=True, verbose_name=_("Email"))
    mobile     = models.CharField(
        max_length=20,
        blank=True,
        validators=[phone_validator],
        verbose_name=_("Mobile")
    )
    website    = models.URLField(blank=True, verbose_name=_("Website"))
    whatsapp   = models.CharField(
        max_length=20,
        blank=True,
        validators=[phone_validator],
        verbose_name=_("WhatsApp")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("Media House")
        verbose_name_plural = _("Media Houses")
        ordering            = ['media_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_media_type_display()})"


# ---------------------------------------------------------------------------
# Model 2: PublicRelationsArchive
# ---------------------------------------------------------------------------

class PublicRelationsArchive(models.Model):
    """Master record for a single press-release / PR event."""

    press_release_no   = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Press Release No"),
        help_text=_("Unique identifier, e.g. PRO-2024-001")
    )
    press_release_date = models.DateField(
        verbose_name=_("Press Release Date")
    )
    event_name         = models.CharField(
        max_length=500,
        verbose_name=_("Event Title / Headline")
    )
    department         = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Department / Faculty"),
        help_text=_("Associated department or program")
    )
    full_text          = models.TextField(
        blank=True,
        verbose_name=_("Press Release Full Body"),
        help_text=_("The complete text of the press release")
    )
    press_release_pdf_file = models.FileField(
        upload_to='pr/pdfs/',
        blank=True,
        null=True,
        verbose_name=_("Press Release PDF File")
    )
    remarks            = models.TextField(
        blank=True,
        verbose_name=_("Remarks / Notes")
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pr_archives',
        verbose_name=_("Created By")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("Press Release Archive")
        verbose_name_plural = _("Press Release Archives")
        ordering            = ['-press_release_date', '-created_at']

    def __str__(self):
        return f"[{self.press_release_no}] {self.event_name}"

    def save(self, *args, **kwargs):
        if not self.press_release_no:
            year = self.press_release_date.year if self.press_release_date else datetime.date.today().year
            prefix = f"PRO-{year}-"
            latest = PublicRelationsArchive.objects.filter(
                press_release_no__startswith=prefix
            ).order_by('-press_release_no').first()

            if latest:
                try:
                    last_num = int(latest.press_release_no.split('-')[-1])
                    next_num = last_num + 1
                except ValueError:
                    next_num = 1
            else:
                next_num = 1

            self.press_release_no = f"{prefix}{next_num:04d}"
        super().save(*args, **kwargs)

    @property
    def pdf_url(self):
        if self.press_release_pdf_file:
            return self.press_release_pdf_file.url
        return ''

    @property
    def coverage_count(self):
        return self.coverages.count()

    @property
    def national_count(self):
        return self.coverages.filter(media_house__media_type='national').count()

    @property
    def local_count(self):
        return self.coverages.filter(media_house__media_type='local').count()

    @property
    def online_count(self):
        return self.coverages.filter(media_house__media_type='online').count()

    @property
    def tv_count(self):
        return self.coverages.filter(media_house__media_type='tv').count()


# ---------------------------------------------------------------------------
# Model 3: MediaCoverage
# ---------------------------------------------------------------------------

class MediaCoverage(models.Model):
    """Junction record linking a PublicRelationsArchive entry to a MediaHouse."""

    archive_entry  = models.ForeignKey(
        PublicRelationsArchive,
        on_delete=models.CASCADE,
        related_name='coverages',
        verbose_name=_("Archive Entry")
    )
    media_house    = models.ForeignKey(
        MediaHouse,
        on_delete=models.PROTECT,
        related_name='coverages',
        verbose_name=_("Media House")
    )
    published_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Published Date")
    )
    newspaper_pdf_file = models.FileField(
        upload_to='coverage/pdfs/',
        blank=True,
        null=True,
        verbose_name=_("Published News PDF File")
    )
    screenshot_file = models.ImageField(
        upload_to='coverage/screenshots/',
        blank=True,
        null=True,
        verbose_name=_("Published News Screenshot")
    )
    online_link    = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name=_("Online News Link")
    )

    class Meta:
        verbose_name        = _("Media Coverage")
        verbose_name_plural = _("Media Coverages")
        ordering            = ['-published_date']
        unique_together     = ('archive_entry', 'media_house')

    def __str__(self):
        return f"{self.media_house.name} → {self.archive_entry.press_release_no}"


# ---------------------------------------------------------------------------
# Model 4: MediaAsset
# ---------------------------------------------------------------------------

class MediaAsset(models.Model):
    """Supporting multimedia assets attached to a PublicRelationsArchive entry."""

    archive_entry = models.ForeignKey(
        PublicRelationsArchive,
        on_delete=models.CASCADE,
        related_name='assets',
        verbose_name=_("Archive Entry")
    )
    asset_type    = models.CharField(
        max_length=10,
        choices=ASSET_TYPE_CHOICES,
        verbose_name=_("Asset Type")
    )
    file_upload = models.FileField(
        upload_to='assets/',
        blank=True,
        null=True,
        verbose_name=_("Asset File Upload")
    )
    link          = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name=_("External Link (YouTube/Drive/Facebook)")
    )
    year          = models.PositiveIntegerField(
        default=CURRENT_YEAR,
        validators=[
            MinValueValidator(2000),
            MaxValueValidator(2100),
        ],
        verbose_name=_("Year"),
        help_text=_("The year this asset belongs to")
    )
    caption       = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Caption / Description")
    )

    class Meta:
        verbose_name        = _("Media Asset")
        verbose_name_plural = _("Media Assets")
        ordering            = ['-year', 'asset_type']

    def __str__(self):
        return f"{self.get_asset_type_display()} — {self.archive_entry.press_release_no}"

    @property
    def file_url(self):
        if self.file_upload:
            return self.file_upload.url
        return self.link or ''

    @property
    def is_file_asset(self):
        return self.asset_type in ('photo', 'video')

    @property
    def is_link_asset(self):
        return self.asset_type in ('drive', 'youtube', 'facebook')
