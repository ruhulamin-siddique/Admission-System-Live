import os
import zipfile
import datetime

def main():
    # Workspace root directory
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Generate timestamped filename
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    zip_filename = f'todays_update_{timestamp}.zip'
    zip_path = os.path.join(root_dir, zip_filename)
    
    files_to_zip = [
        'admission_system/settings.py',
        'public_relations/forms.py',
        'public_relations/models.py',
        'public_relations/views.py',
        'public_relations/urls.py',
        'templates/public_relations/archive_form.html',
        'templates/public_relations/archive_detail.html',
        'templates/public_relations/pr_print.html',
        'templates/public_relations/media_house_list.html',
        'templates/public_relations/widgets/premium_clearable_file.html',
        'public_relations/migrations/0009_alter_publicrelationsarchive_press_release_no.py',
        'public_relations/migrations/0010_auto_20260718_0328.py',
        'public_relations/migrations/0011_alter_mediacoverage_online_link.py',
    ]
    
    print(f"Creating zip file at: {zip_path}")
    
    # Overwrite if exists
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for rel_path in files_to_zip:
            full_path = os.path.join(root_dir, rel_path)
            if os.path.exists(full_path):
                zip_file.write(full_path, rel_path)
                print(f"Added: {rel_path}")
            else:
                print(f"Warning: file not found: {rel_path}")

    print(f"\nZip file created successfully at: {zip_path}")
    print(f"File size: {os.path.getsize(zip_path) / 1024:.2f} KB")

if __name__ == '__main__':
    main()
