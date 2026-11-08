from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class CounselingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'counseling'
    verbose_name = _('Psychological Counseling & Student Wellbeing')
