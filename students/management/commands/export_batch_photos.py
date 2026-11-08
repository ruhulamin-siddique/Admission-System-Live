import os
import zipfile
from django.core.management.base import BaseCommand
from django.conf import settings
from students.models import Student
from students.views import _format_photo_filename

class Command(BaseCommand):
    help = 'Export batchwise student photos to a ZIP archive with customizable naming rules.'

    def add_arguments(self, parser):
        parser.add_argument('--batch', type=str, help='Batch number/name to filter (e.g. 60)')
        parser.add_argument('--program', type=str, help='Academic program code to filter (e.g. CSE)')
        parser.add_argument('--naming-rule', type=str, default='id_name',
                            choices=['id_name', 'id_only', 'name_id', 'id_program_name', 'id_batch_name', 'custom'],
                            help='Naming rule preset (default: id_name)')
        parser.add_argument('--custom-pattern', type=str, default='',
                            help='Custom pattern template e.g. "{id}_{program}_{name}"')
        parser.add_argument('--separator', type=str, default='_', choices=['_', '-', ' '],
                            help='Word separator character (default: _)')
        parser.add_argument('--case-format', type=str, default='preserve', choices=['preserve', 'upper', 'lower'],
                            help='Text case format (default: preserve)')
        parser.add_argument('--folder-structure', type=str, default='flat', choices=['flat', 'batch', 'program'],
                            help='ZIP subfolder structure (default: flat)')
        parser.add_argument('--output', type=str, help='Output ZIP file path (e.g. batch_60_photos.zip)')

    def handle(self, *args, **options):
        batch = options.get('batch')
        program = options.get('program')
        naming_rule = options.get('naming_rule')
        custom_pattern = options.get('custom_pattern')
        separator = options.get('separator')
        case_format = options.get('case_format')
        folder_structure = options.get('folder_structure')
        output_path = options.get('output')

        students = Student.objects.exclude(photo_path__isnull=True).exclude(photo_path='')

        if batch:
            students = students.filter(batch=batch)
        if program:
            students = students.filter(program__iexact=program)

        total_count = students.count()
        if total_count == 0:
            self.stdout.write(self.style.WARNING('No student records found with valid photo paths for the given criteria.'))
            return

        if not output_path:
            batch_str = f"batch_{batch}" if batch else "all_batches"
            prog_str = f"_{program}" if program else ""
            output_path = f"{batch_str}{prog_str}_photos.zip"

        self.stdout.write(f"Packaging photos for {total_count} student(s) into '{output_path}' using naming rule '{naming_rule}'...")

        files_added = 0
        missing_files = 0

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for student in students:
                raw_path = str(student.photo_path or '').strip()
                if not raw_path:
                    continue

                if raw_path.startswith(settings.MEDIA_URL):
                    raw_path = raw_path[len(settings.MEDIA_URL):].lstrip('/')
                elif raw_path.startswith('/media/'):
                    raw_path = raw_path[len('/media/'):].lstrip('/')

                full_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, raw_path))

                if os.path.exists(full_path):
                    ext = os.path.splitext(full_path)[1].lower() or '.jpg'
                    zip_filename = _format_photo_filename(
                        student,
                        naming_rule=naming_rule,
                        custom_pattern=custom_pattern,
                        separator=separator,
                        case_format=case_format,
                        folder_structure=folder_structure,
                        ext=ext
                    )
                    zip_file.write(full_path, zip_filename)
                    files_added += 1
                else:
                    missing_files += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully archived {files_added} photos into '{os.path.abspath(output_path)}'."
        ))
        if missing_files > 0:
            self.stdout.write(self.style.WARNING(f"Note: {missing_files} physical photo file(s) were missing on disk."))
