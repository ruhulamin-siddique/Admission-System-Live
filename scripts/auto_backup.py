"""
Automated Zero-Lock Hot Backup Tool for BAUST Admission System
==============================================================
Uses SQLite's native online backup API (sqlite3.Connection.backup)
to create consistent snapshots while the web server is actively running.
Automatically manages 14-day rolling retention.
"""

import os
import sys
import sqlite3
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / 'db.sqlite3'
BACKUP_DIR = BASE_DIR / 'backups' / 'daily'
RETENTION_DAYS = 14

def run_hot_backup():
    if not DB_PATH.exists():
        print(f"[-] Error: Database file not found at: {DB_PATH}")
        sys.exit(1)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    backup_file = BACKUP_DIR / f"db_backup_{timestamp}.sqlite3"
    
    print(f"[*] Starting live zero-lock backup of: {DB_PATH.name} ({DB_PATH.stat().st_size / (1024*1024):.2f} MB)...")
    
    try:
        # Connect to source in URI read-only mode to prevent write contention
        source_conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        dest_conn = sqlite3.connect(backup_file)
        
        # Use SQLite Online Backup API
        with dest_conn:
            source_conn.backup(dest_conn, pages=100, sleep=0.01)
            
        dest_conn.close()
        source_conn.close()
        
        backup_size_mb = backup_file.stat().st_size / (1024 * 1024)
        print(f"[+] SUCCESS: Snapshot created: {backup_file.name} ({backup_size_mb:.2f} MB)")
        
    except Exception as e:
        print(f"[-] Backup failed: {e}")
        if backup_file.exists():
            backup_file.unlink()
        sys.exit(1)

    # Clean up backups older than retention policy
    cutoff_time = datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)
    deleted_count = 0
    
    for f in BACKUP_DIR.glob("db_backup_*.sqlite3"):
        if f.is_file():
            file_mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            if file_mtime < cutoff_time:
                try:
                    f.unlink()
                    deleted_count += 1
                except Exception:
                    pass
                    
    if deleted_count > 0:
        print(f"[*] Retention Policy: Purged {deleted_count} backup(s) older than {RETENTION_DAYS} days.")

if __name__ == '__main__':
    run_hot_backup()

