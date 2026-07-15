import os
import zipfile

def main():
    # Workspace root directory
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(root_dir, 'deployment_update.zip')
    
    # Files and folders to include
    include_paths = [
        # Settings & Core URLs
        'admission_system/settings.py',
        'admission_system/urls.py',
        
        # Core App files modified
        'core/access_registry.py',
        'core/models.py',
        'core/views.py',
        'core/urls.py',
        'core/middleware.py',
        'core/migrations/0016_userprofile_language.py',
        
        # New Public Relations App
        'public_relations',
        
        # Templates & Locales
        'templates/base.html',
        'templates/public_relations',
        'templates/core/role_management.html',
        'locale',
        
        # Custom helper tools
        'scratch/compile_po.py',
    ]

    print(f"Creating deployment update archive at: {zip_path}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for path in include_paths:
            full_path = os.path.join(root_dir, path)
            if not os.path.exists(full_path):
                print(f"Skipping (not found): {path}")
                continue
                
            if os.path.isdir(full_path):
                # Recursively add all files in directory
                for dirpath, _, filenames in os.walk(full_path):
                    for filename in filenames:
                        file_full_path = os.path.join(dirpath, filename)
                        arcname = os.path.relpath(file_full_path, root_dir)
                        # Skip pyc and system generated logs
                        if '__pycache__' in arcname or '.mo' in arcname:
                            continue
                        zip_file.write(file_full_path, arcname)
                        print(f"Added folder file: {arcname}")
            else:
                arcname = os.path.relpath(full_path, root_dir)
                zip_file.write(full_path, arcname)
                print(f"Added file: {arcname}")

    print("\nUpdate package built successfully!")
    print(f"File size: {os.path.getsize(zip_path) / 1024:.2f} KB")

if __name__ == '__main__':
    main()
