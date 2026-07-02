import os
import zipfile

def zipdir(path, ziph):
    # Directories to exclude from production zip
    exclude_dirs = {'.git', '__pycache__', 'media', 'brain', 'venv', 'env', '.idea', '.vscode', '.gemini', 'staticfiles'}
    # Files to exclude from production zip
    exclude_files = {'db.sqlite3', '.env', 'zip_project.py', 'board_response_debug.html', 'academic_patch_release.zip'}
    
    for root, dirs, files in os.walk(path):
        # Filter directories in-place to prevent os.walk from entering them
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        
        for file in files:
            if file in exclude_files or file.startswith('.') or file.endswith('.zip'):
                continue
            file_path = os.path.join(root, file)
            # Calculate path relative to target folder for zip entries
            rel_path = os.path.relpath(file_path, path)
            ziph.write(file_path, rel_path)
            print(f"[ADD] Added to bundle: {rel_path}")

if __name__ == '__main__':
    print("--- Packaging admission system for production deploy ---")
    import datetime
    timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    zip_filename = f'Admission_System_Production_{timestamp_str}.zip'
    
    # Overwrite if exists
    if os.path.exists(zip_filename):
        os.remove(zip_filename)
        
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipdir('.', zipf)
        
    print(f"\nSUCCESS: Created production package: {zip_filename}")
