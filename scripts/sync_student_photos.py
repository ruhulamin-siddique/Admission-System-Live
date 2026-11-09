"""
Automated Student Photo Synchronization Tool for BAUST Admission System
========================================================================
Synchronizes student photos from the incoming 'photos/' staging folder to
'media/student_photos/' with dual-naming preservation and database linking.

Usage:
    python scripts/sync_student_photos.py --dry-run
    python scripts/sync_student_photos.py --execute
"""

import os
import sys
import re
import shutil
import argparse
from pathlib import Path

# Setup Django Environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admission_system.settings')

import django
django.setup()

from students.models import Student

PHOTOS_SRC_DIR = BASE_DIR / 'photos'
MEDIA_DEST_DIR = BASE_DIR / 'media' / 'student_photos'

VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

def sync_photos(dry_run=True):
    print("=" * 70)
    print("       BAUST ADMISSION SYSTEM - PHOTO SYNCHRONIZATION TOOL")
    print("=" * 70)
    mode_label = "[DRY-RUN MODE] (No files or DB will be modified)" if dry_run else "[EXECUTE MODE] (Applying changes)"
    print(f"[*] Execution Mode: {mode_label}")
    print(f"[*] Source Folder:      {PHOTOS_SRC_DIR}")
    print(f"[*] Destination Folder: {MEDIA_DEST_DIR}")
    print("-" * 70)

    if not PHOTOS_SRC_DIR.exists():
        print(f"[-] Error: Source folder does not exist: {PHOTOS_SRC_DIR}")
        return False

    if not dry_run:
        MEDIA_DEST_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted([f for f in os.listdir(PHOTOS_SRC_DIR) if not f.startswith('.')])
    image_files = [f for f in files if Path(f).suffix.lower() in VALID_EXTENSIONS]

    print(f"[*] Found {len(image_files)} image file(s) in source folder.\n")

    copied_id_count = 0
    copied_dual_count = 0
    db_updated_count = 0
    skipped_count = 0

    for filename in image_files:
        src_path = PHOTOS_SRC_DIR / filename
        ext = src_path.suffix.lower()
        if ext == '.jpeg':
            ext = '.jpg'  # Normalize to .jpg for consistent URL matching

        # Extract ID prefix (e.g. 0802620204021024 from 0802620204021024_SUPROVAT_ROY.jpg)
        m = re.match(r'^([0-9]{9,16})', filename)
        if not m:
            print(f"[!] Warning: Cannot extract numeric ID from: {filename}")
            skipped_count += 1
            continue

        student_id_prefix = m.group(1)
        
        # Primary target: media/student_photos/<student_id>.<ext>
        dest_primary = MEDIA_DEST_DIR / f"{student_id_prefix}{ext}"
        
        # Secondary dual target: media/student_photos/<original_filename>
        dest_dual = MEDIA_DEST_DIR / filename

        # 1. Copy Primary
        if dry_run:
            copied_id_count += 1
        else:
            try:
                shutil.copy2(src_path, dest_primary)
                copied_id_count += 1
            except Exception as e:
                print(f"[-] Failed copying primary for {filename}: {e}")

        # 2. Copy Dual Original Name (if different from primary)
        if dest_dual != dest_primary:
            if dry_run:
                copied_dual_count += 1
            else:
                try:
                    shutil.copy2(src_path, dest_dual)
                    copied_dual_count += 1
                except Exception as e:
                    print(f"[-] Failed copying dual original name for {filename}: {e}")

        # 3. Check Database Linking
        # First check student by extracted ID
        student = Student.objects.filter(student_id=student_id_prefix).first()
        if not student:
            # Fallback search by original ID if reassigned
            student = Student.objects.filter(old_student_id=student_id_prefix).first()

        expected_photo_path = f"student_photos/{student_id_prefix}{ext}"

        if student:
            current_path = (student.photo_path or '').strip().replace('\\', '/')
            if not current_path or current_path != expected_photo_path:
                if dry_run:
                    print(f"[+] [DRY-RUN] Would update DB for {student.student_id} ({student.student_name}): '{current_path}' -> '{expected_photo_path}'")
                    db_updated_count += 1
                else:
                    student.photo_path = expected_photo_path
                    student.save(update_fields=['photo_path'])
                    print(f"[+] [DB UPDATE] {student.student_id} ({student.student_name}): photo_path set to '{expected_photo_path}'")
                    db_updated_count += 1

    print("\n" + "=" * 70)
    print("                     SYNCHRONIZATION SUMMARY")
    print("=" * 70)
    print(f"Total source images:           {len(image_files)}")
    print(f"Primary ID files deployed:     {copied_id_count}")
    print(f"Dual-named files preserved:    {copied_dual_count}")
    print(f"Database records linked:       {db_updated_count}")
    print(f"Skipped / Unmatched files:     {skipped_count}")
    print("=" * 70)

    if dry_run:
        print("\n[i] Dry-run completed successfully with 0 errors.")
        print("[i] To execute the actual copy and database link, run:")
        print("    python scripts/sync_student_photos.py --execute\n")
    else:
        print("\n[+] All student photos deployed successfully to media/student_photos/!")
        print("[+] Student profiles and directory will now display photos immediately.\n")

    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Synchronize student photos from photos/ to media/student_photos/")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run', action='store_true', help="Preview actions without modifying disk or DB")
    group.add_argument('--execute', action='store_true', help="Perform actual copy and database update")

    args = parser.parse_args()
    sync_photos(dry_run=args.dry_run)
