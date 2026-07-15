from django.db import models
from django.core.validators import RegexValidator

class DeviceRegistration(models.Model):
    USER_TYPE_CHOICES = [
        ('student', 'Student'),
        ('faculty', 'Faculty Member'),
        ('officer', 'Officer'),
        ('staff', 'Staff Member'),
        ('other', 'Other'),
    ]

    DEVICE_TYPE_CHOICES = [
        ('laptop', 'Laptop'),
        ('mobile', 'Mobile / Tablet'),
        ('desktop', 'Desktop PC'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    mac_validator = RegexValidator(
        regex=r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$',
        message="Enter a valid MAC address in format XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX"
    )

    phone_validator = RegexValidator(
        regex=r'^(?:\+?88)?01[3-9]\d{8}$',
        message="Enter a valid Bangladeshi mobile number (e.g. 01712345678 or +8801712345678)"
    )

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, validators=[phone_validator])
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='student')
    department = models.CharField(max_length=150, help_text="e.g. CSE, EEE, ME, CE, BBA")
    designation_or_roll = models.CharField(
        max_length=100, 
        help_text="Designation (for staff/faculty) or Roll/ID Number (for students)"
    )
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES, default='laptop')
    device_name_brand = models.CharField(max_length=150, help_text="e.g. Asus ROG, iPhone 14, Dell Inspiron")
    mac_address = models.CharField(
        max_length=17, 
        validators=[mac_validator],
        help_text="Physical address of your network card (Wi-Fi/Ethernet)"
    )
    reason = models.TextField(blank=True, help_text="Why do you require Wi-Fi/network access?")
    
    # ICT Administration Fields
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    assigned_ip = models.GenericIPAddressField(blank=True, null=True, help_text="Assigned IP address (Admin only)")
    admin_notes = models.TextField(blank=True, help_text="ICT administrator notes")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} - {self.device_name_brand} ({self.mac_address})"

    class Meta:
        verbose_name = "Device Registration"
        verbose_name_plural = "Device Registrations"
        ordering = ['-created_at']
