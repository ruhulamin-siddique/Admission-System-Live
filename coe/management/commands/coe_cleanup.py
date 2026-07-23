"""
CoE Management Command — coe_cleanup

Run this daily via cron or task scheduler:
    python manage.py coe_cleanup

Two passes:
  1. Rejected / Cancelled applications older than rejected_purge_days:
     → purge attachment files → soft-delete record
  2. Delivered applications older than delivered_purge_days:
     → purge attachment files (metadata preserved)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Purge attachment files for old rejected/cancelled and delivered CoE applications.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be deleted without actually deleting.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY RUN — no files will be deleted ==='))

        # ── Pass 1: Rejected / Cancelled ──────────────────────────────────────
        from coe.utils import cleanup_rejected_applications, cleanup_delivered_applications, CoeSettings
        from coe.models import DocumentApplication, ApplicationStatus
        import datetime

        cfg = CoeSettings.get_settings()
        cutoff_rejected = timezone.now() - datetime.timedelta(days=cfg.rejected_purge_days)

        rejected_apps = DocumentApplication.all_objects.filter(
            status__in=[ApplicationStatus.REJECTED, ApplicationStatus.CANCELLED],
            updated_at__lt=cutoff_rejected,
            is_deleted=False,
        )

        self.stdout.write(
            f'Pass 1 — Rejected/Cancelled (cutoff {cfg.rejected_purge_days} days): '
            f'{rejected_apps.count()} applications found.'
        )

        if not dry_run:
            result1 = cleanup_rejected_applications()
            self.stdout.write(
                self.style.SUCCESS(
                    f'  Soft-deleted: {result1["soft_deleted"]}, files purged: {result1["purged_files"]}'
                )
            )
        else:
            for app in rejected_apps[:20]:
                self.stdout.write(f'  Would purge: {app.application_number} ({app.status})')

        # ── Pass 2: Delivered ─────────────────────────────────────────────────
        cutoff_delivered = timezone.now() - datetime.timedelta(days=cfg.delivered_purge_days)
        delivered_apps = DocumentApplication.objects.filter(
            status=ApplicationStatus.DELIVERED,
            delivered_at__lt=cutoff_delivered,
            attachments__is_purged=False,
        ).distinct()

        self.stdout.write(
            f'Pass 2 — Delivered (cutoff {cfg.delivered_purge_days} days): '
            f'{delivered_apps.count()} applications found.'
        )

        if not dry_run:
            result2 = cleanup_delivered_applications()
            self.stdout.write(
                self.style.SUCCESS(
                    f'  Files purged: {result2["purged_files"]}'
                )
            )
        else:
            for app in delivered_apps[:20]:
                self.stdout.write(f'  Would purge files for: {app.application_number}')

        self.stdout.write(self.style.SUCCESS('coe_cleanup complete.'))
