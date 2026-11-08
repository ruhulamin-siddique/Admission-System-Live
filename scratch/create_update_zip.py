import zipfile
import os

zip_filename = "ma_elt_merge_update.zip"

files_to_zip = [
    "master_data/migrations/0012_merge_ma_eng_and_elt_to_ma_in_elt.py",
    "students/utils.py",
    "master_data/management/commands/seed_master_data.py",
]

if os.path.exists(zip_filename):
    os.remove(zip_filename)

with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for rel_path in files_to_zip:
        if os.path.exists(rel_path):
            zipf.write(rel_path, rel_path)
            print(f"[ADD] {rel_path}")
        else:
            print(f"[ERR] File not found: {rel_path}")

print(f"\nSuccessfully created {zip_filename}")
