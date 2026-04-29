import hashlib
import secrets

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class APIClient(models.Model):
    SCOPE_CHOICES = [
        ('students:read', 'Read student academic data'),
        ('students:pii', 'Read student personal/contact data'),
        ('reports:read', 'Read aggregate report summaries'),
    ]

    name = models.CharField(max_length=150, unique=True)
    contact_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    key_prefix = models.CharField(max_length=12, unique=True, editable=False)
    key_hash = models.CharField(max_length=128, editable=False)
    scopes = models.JSONField(default=list, blank=True)
    allowed_ips = models.TextField(
        blank=True,
        help_text="Optional comma/newline separated IP allowlist. Leave blank to allow any IP.",
    )
    is_active = models.BooleanField(default=True)
    rate_limit_per_minute = models.PositiveIntegerField(default=120)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_api_clients')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @staticmethod
    def hash_key(raw_key):
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    @classmethod
    def issue_key(cls):
        token = f"adm_{secrets.token_urlsafe(32)}"
        return token, token[:12], cls.hash_key(token)

    def set_new_key(self):
        raw_key, prefix, digest = self.issue_key()
        self.key_prefix = prefix
        self.key_hash = digest
        return raw_key

    def has_scope(self, scope):
        return scope in (self.scopes or [])

    def allowed_ip_list(self):
        raw_items = self.allowed_ips.replace('\n', ',').split(',') if self.allowed_ips else []
        return [item.strip() for item in raw_items if item.strip()]

    def is_ip_allowed(self, ip_address):
        allowed = self.allowed_ip_list()
        return not allowed or ip_address in allowed

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=['is_active', 'revoked_at', 'updated_at'])


class APIRequestLog(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('DENIED', 'Denied'),
        ('ERROR', 'Error'),
        ('RATE_LIMITED', 'Rate Limited'),
    ]

    client = models.ForeignKey(APIClient, on_delete=models.SET_NULL, null=True, blank=True, related_name='request_logs')
    key_prefix = models.CharField(max_length=12, blank=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    query_string = models.TextField(blank=True)
    status_code = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    response_ms = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['client', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        client = self.client.name if self.client else self.key_prefix or 'unknown'
        return f"{client} {self.method} {self.path} [{self.status_code}]"
