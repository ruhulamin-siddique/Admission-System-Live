"""
Live Database Sync Tool for Local Development
=============================================
Usage:
    python sync_live_db.py
    python sync_live_db.py path/to/backup.json

This script:
1. Finds the latest db_backup_*.json in the current folder (or uses the passed file).
2. Creates a safety backup of your existing db.sqlite3.
3. Builds fresh schema tables using Django migrations.
4. Truncates pre-seeded rows generated during migrations to eliminate UNIQUE constraint conflicts.
5. Loads all objects from the live JSON dump into your local SQLite database.
6. Runs Django system check to verify integrity.
"""

import os
import sys
import glob
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import django
from django.core.management import call_command
from django.db import connection
from django.utils import timezone


def get_backup_file():
    # 1. Direct command line argument
    if len(sys.argv) > 1:
        chosen = Path(sys.argv[1])
        if chosen.exists():
            return chosen
        print(f"[-] Error: Specified file not found: {chosen}")
        sys.exit(1)

    # 2. Check candidate folders: project root & user Downloads folder
    candidate_folders = [
        BASE_DIR,
        Path.home() / "Downloads"
    ]

    candidates = []
    for folder in candidate_folders:
        if folder.exists():
            # Matches standard Django live dump naming: db_backup_*.json
            matches = list(folder.glob("db_backup_*.json"))
            candidates.extend(matches)

    # If no db_backup_*.json found, search for any .json in project root (excluding package.json)
    if not candidates:
        candidates = [
            f for f in BASE_DIR.glob("*.json") 
            if f.name not in ("package.json", "tsconfig.json")
        ]

    if not candidates:
        print("[-] Error: No JSON backup file found in project root or Downloads folder.")
        print("    Please specify the file path directly:")
        print("    python sync_live_db.py <path_to_backup.json>")
        sys.exit(1)

    # Pick the newest file by modification timestamp (os.path.getmtime)
    latest_file = max(candidates, key=lambda f: f.stat().st_mtime)
    return latest_file



def sync():
    backup_file = get_backup_file()
    print(f"[*] Target live backup: {backup_file.name} ({backup_file.stat().st_size / (1024*1024):.2f} MB)")

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admission_system.settings')
    django.setup()

    db_path = BASE_DIR / 'db.sqlite3'
    backups_dir = BASE_DIR / 'backups'
    backups_dir.mkdir(exist_ok=True)

    # 1. Backup existing db.sqlite3
    if db_path.exists():
        timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
        safety_backup = backups_dir / f"db_local_backup_{timestamp}.sqlite3"
        print(f"[*] Creating safety backup: {safety_backup.name}...")
        shutil.copy2(db_path, safety_backup)
        try:
            os.remove(db_path)
        except Exception as e:
            print(f"[-] Notice: Could not remove old db.sqlite3 ({e}), proceeding with schema overwrite.")

    # 2. Run migrations
    print("[*] Running migrations to build fresh schema...")
    call_command('migrate', interactive=False, verbosity=0)

    # 3. Clean pre-seeded rows to prevent unique/duplicate collisions
    print("[*] Truncating migration-seeded rows for a clean sync slate...")
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA foreign_keys = OFF;')
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'django_migrations';")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(f'DELETE FROM "{table}";')
        cursor.execute('PRAGMA foreign_keys = ON;')

    # 4. Load live data
    print(f"[*] Loading live data from {backup_file.name} (this may take 1-3 minutes)...")
    call_command('loaddata', str(backup_file), verbosity=1)

    # 5. System check
    print("[*] Running Django system check...")
    call_command('check')

    print("\n" + "="*65)
    print(f"[+] SUCCESS: Local database successfully synced with live data!")
    print("="*65)


if __name__ == '__main__':
    sync()
