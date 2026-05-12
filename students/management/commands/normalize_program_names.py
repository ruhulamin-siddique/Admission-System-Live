"""
Management command: normalize_program_names
===========================================
Fixes the department name mismatch between old imported data (full names like
"Computer Science and Engineering") and new imports (short names like "CSE").

Usage:
    python manage.py normalize_program_names           # dry-run (preview only)
    python manage.py normalize_program_names --apply   # write changes to DB

The canonical name is determined by get_canonical_program_name() — the same
function used by the bulk importer, so both systems are guaranteed to agree.
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Normalizes student.program values to canonical short names."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually write changes to the database. Without this flag, runs in dry-run mode.',
        )

    def handle(self, *args, **options):
        from students.models import Student
        from students.utils import get_canonical_program_name

        apply = options['apply']
        mode_label = "APPLY" if apply else "DRY-RUN"
        self.stdout.write(self.style.WARNING(f"\n[{mode_label}] Scanning student program names...\n"))

        # Build snapshot of all unique program values currently in DB
        all_programs = (
            Student.objects
            .exclude(program__isnull=True)
            .exclude(program='')
            .values_list('program', flat=True)
            .distinct()
            .order_by('program')
        )

        # Map each current value to its canonical form
        change_map = {}   # { current_value: canonical_value }
        no_match = []     # values that had no match in master_data

        for prog in all_programs:
            canonical = get_canonical_program_name(prog)
            if canonical != prog:
                change_map[prog] = canonical
            elif canonical == prog:
                # Try to confirm it matched something in master_data
                from master_data.models import Program
                matched = Program.objects.filter(
                    name__iexact=prog
                ).exists() or Program.objects.filter(
                    short_name__iexact=prog
                ).exists()
                if not matched:
                    no_match.append(prog)

        if not change_map:
            self.stdout.write(self.style.SUCCESS("OK All program names are already canonical. Nothing to change.\n"))
        else:
            self.stdout.write(f"{'OLD VALUE':<45} {'→':^3} {'CANONICAL VALUE':<45} {'STUDENTS':>8}")
            self.stdout.write("-" * 105)

            total_students = 0
            with transaction.atomic():
                for old_val, new_val in sorted(change_map.items()):
                    count = Student.objects.filter(program=old_val).count()
                    total_students += count
                    self.stdout.write(
                        f"{old_val:<45} {'→':^3} {new_val:<45} {count:>8}"
                    )
                    if apply:
                        Student.objects.filter(program=old_val).update(program=new_val)

                if not apply:
                    transaction.set_rollback(True)

            self.stdout.write("-" * 105)
            action = "Updated" if apply else "Would update"
            self.stdout.write(self.style.SUCCESS(
                f"\nOK {action} {total_students} student records across "
                f"{len(change_map)} program name(s).\n"
            ))

        if no_match:
            self.stdout.write(self.style.WARNING(
                f"\nWARN {len(no_match)} unrecognised program value(s) "
                f"(not in master_data — left unchanged):"
            ))
            for v in no_match:
                count = Student.objects.filter(program=v).count()
                self.stdout.write(f"  * {v!r}  ({count} students)")
            self.stdout.write("")

        if not apply:
            self.stdout.write(self.style.WARNING(
                "This was a DRY-RUN. Run with --apply to save changes.\n"
            ))
