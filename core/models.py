from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out

class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permissions')
    module = models.CharField(max_length=50) # e.g., 'students', 'finance'
    task = models.CharField(max_length=100)  # e.g., 'view_directory', 'add_student'

    class Meta:
        unique_together = ('role', 'module', 'task')

    def __str__(self):
        return f"{self.role.name}: {self.module}.{self.task}"

class UserProfile(models.Model):
    REGISTRATION_STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('DISAPPROVED', 'Disapproved'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    
    # University Verification Fields
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    designation = models.CharField(max_length=100, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    
    department_scope = models.CharField(
        max_length=100, 
        null=True, 
        blank=True, 
        help_text="If set, restricts access to only this Program/Department's data."
    )
    is_active = models.BooleanField(default=True)
    registration_status = models.CharField(
        max_length=20, 
        choices=REGISTRATION_STATUS_CHOICES, 
        default='APPROVED'  # Existing users are assumed approved
    )
    theme_mode = models.CharField(
        max_length=10, 
        default='light', 
        choices=[('light', 'Light'), ('dark', 'Dark')]
    )
    navbar_fixed = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='staff_photos/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.role.name if self.role else 'No Role'}"

    def has_access(self, module, task):
        if self.user.is_superuser:
            return True
        if not self.role:
            return False
        return self.role.permissions.filter(module=module, task=task).exists()

class SystemSettings(models.Model):
    institution_name = models.CharField(max_length=255, default="Bangladesh Army University of Science and Technology")
    institution_logo_url = models.URLField(max_length=500, blank=True, null=True)
    institution_logo = models.ImageField(upload_to='branding/', blank=True, null=True)
    institution_favicon = models.ImageField(upload_to='branding/', blank=True, null=True)
    theme_color = models.CharField(max_length=50, default="#1e40af")
    
    # SMS API Configuration
    sms_api_key = models.CharField(max_length=255, blank=True, null=True)
    sms_sender_id = models.CharField(max_length=100, blank=True, null=True)
    sms_api_url = models.URLField(max_length=500, blank=True, null=True, help_text="The endpoint for the SMS gateway (e.g. BulkSMSBD, GreenWeb)")
    sms_is_active = models.BooleanField(default=False)

    ID_MODE_CHOICES = [
        ('auto',      'Auto — System generates full 16-digit ID automatically'),
        ('semi_auto', 'Semi-Auto — System generates prefix; staff enters last 3 serial digits'),
        ('manual',    'Manual — Staff types the complete 16-digit UGC ID'),
    ]
    id_mode = models.CharField(
        max_length=10,
        choices=ID_MODE_CHOICES,
        default='semi_auto',
        help_text="Controls how the Student ID is generated on the admission form.",
    )

    @property
    def auto_id_generation(self):
        """Backward-compatible property — True only in full-auto mode."""
        return self.id_mode == 'auto'

    @auto_id_generation.setter
    def auto_id_generation(self, value):
        """Backward-compatible setter — maps boolean to id_mode."""
        if value:
            self.id_mode = 'auto'
        else:
            # If someone explicitly disables auto, we go to manual
            if self.id_mode == 'auto':
                self.id_mode = 'manual'


    @property
    def logo_url(self):
        if self.institution_logo:
            return self.institution_logo.url
        return self.institution_logo_url

    @property
    def favicon_url(self):
        if self.institution_favicon:
            return self.institution_favicon.url
        return None

    def __str__(self):
        return "System Settings"

    class Meta:
        verbose_name_plural = "System Settings"

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('LOGIN', 'Logged In'),
        ('LOGOUT', 'Logged Out'),
        ('PERMISSION', 'Permission Change'),
        ('SECURITY', 'Security Setting Change'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    module = models.CharField(max_length=50) # e.g. 'students', 'security'
    scope = models.CharField(max_length=100, null=True, blank=True, help_text="e.g. Department name for scoped notifications")
    object_id = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField()
    is_system_alert = models.BooleanField(default=False, help_text="If true, visible to all authorized staff regardless of scope")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        user_str = self.user.username if self.user else "System"
        return f"{user_str} - {self.action_type} on {self.module} ({self.timestamp})"

# Signal to ensure UserProfile exists for every User
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
    else:
        # Handle case where user existed before RBAC was added
        if not hasattr(instance, 'profile'):
            UserProfile.objects.get_or_create(user=instance)
    
    try:
        instance.profile.save()
    except Exception:
        pass

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    from .utils import log_activity
    log_activity(request, 'LOGIN', 'security', f'User {user.username} logged in successfully')

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        from .utils import log_activity
        log_activity(request, 'LOGOUT', 'security', f'User {user.username} logged out')
