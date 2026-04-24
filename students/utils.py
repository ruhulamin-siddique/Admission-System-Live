import pandas as pd
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone
from .models import Student, ProgramChangeHistory, SMSHistory

from master_data.models import Cluster, Program, Hall, Semester, AdmissionYear

# UGC Defaults (Fallback)
UNIVERSITY_CODE = "080"

def decompose_ugc_id(s_id):
    """
    Breaks down a 16-character UGC ID into its descriptive components.
    Structure: UUU YY S HH CcssP SSS
    """
    if not s_id or len(s_id) != 16:
        return None
    
    # Get semester name
    sem_val = s_id[5:6]
    sem_name = "Spring/Winter" if sem_val == "1" else "Fall/Summer"
    
    # Get Hall name
    hall = Hall.objects.filter(code=s_id[6:8]).first()
    hall_name = hall.name if hall else "Unknown"
    
    return {
        "university": s_id[0:3],      # 080
        "year": s_id[3:5],            # 26
        "semester": sem_val,          # 1/2
        "semester_name": sem_name,
        "hall": s_id[6:8],            # 00/01/02/04
        "hall_name": hall_name,
        "cluster": s_id[8:10],        # 05/04/02
        "subject": s_id[10:12],       # 01/02...
        "level": s_id[12:13],         # 1/3
        "serial": s_id[13:16],        # 001
    }

def generate_next_ugc_id(admission_year, semester_name, hall_name, program_name, cluster_name, program_level="Bachelor", subject_code=None, mba_credits=None):
    """
    Dynamic Automated UGC ID Generator using Master Data.
    Structure: UUU YY S HH CcssP SSS
    """
    year_code = str(admission_year)[-2:]
    
    # 1. Get Semester Code from DB
    sem = Semester.objects.filter(name__icontains=semester_name).first()
    semester_code = sem.code if sem else "1"
            
    # 2. Get Hall Code from DB
    hall = Hall.objects.filter(name__icontains=hall_name).first()
    hall_code = hall.code if hall else "00"
    
    # 3. Get Cluster & Subject Codes from DB
    # We look for the Program specifically to get its UGC code and Cluster code
    prog = Program.objects.filter(name__icontains=program_name).first()
    if prog:
        cluster_code = prog.cluster.code
        s_code = prog.ugc_code
        level_code = prog.level_code
    else:
        # Fallback to old behavior if program not found in master data
        cluster_code = "05"
        s_code = "01"
        level_code = "1"
    
    # Construct prefixes
    prefix_part1 = f"{UNIVERSITY_CODE}{year_code}{semester_code}" # UUU YY S (6 chars)
    prefix_part2 = f"{cluster_code}{s_code}{level_code}"           # CcssP (5 chars)
    
    # Full ID prefix (including hall)
    full_prefix = f"{prefix_part1}{hall_code}{prefix_part2}"      # 13 chars total
    
    # Serial Logic
    serial_start = 1
    if program_name == "MBA":
        if mba_credits == 48:
            serial_start = 301
        elif mba_credits == 60:
            serial_start = 601

    last_student = Student.objects.filter(
        student_id__regex=rf'^{prefix_part1}..{prefix_part2}'
    ).order_by('-student_id').first()

    if last_student:
        last_serial = int(last_student.student_id[-3:])
        new_serial = last_serial + 1
    else:
        new_serial = serial_start

    return f"{full_prefix}{str(new_serial).zfill(3)}"

def validate_ugc_id(s_id):
    """
    Validates a student ID against the UGC format.
    Structure: UUU YY S HH CcssP SSS (Total 16 chars)
    """
    if not s_id or len(s_id) != 16:
        return False, "ID must be exactly 16 characters."
    
    if not s_id.startswith(UNIVERSITY_CODE):
        return False, f"ID must start with university code {UNIVERSITY_CODE}."
    
    if not s_id.isdigit():
        return False, "ID must contain only numbers."
    
    # Semester check (1 or 2) at index 5
    if s_id[5] not in ['1', '2']:
        return False, "Invalid semester code."
        
    return True, ""

def import_students_from_excel(file_obj, update_existing=False):
    """
    Enhanced Bulk Excel Import Logic with Update and Validation support.
    """
    try:
        df = pd.read_excel(file_obj)
        # Standardize column names (lowercase and snake_case)
        df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
        
        # Get list of valid model fields
        valid_fields = [f.name for f in Student._meta.get_fields()]
        # Exclude internal/meta fields from update
        exclude_from_update = {'student_id', 'created_at', 'last_updated'}
        update_fields = [f for f in valid_fields if f in df.columns and f not in exclude_from_update]

        records_to_process = []
        errors = []
        existing_ids = set(Student.objects.values_list('student_id', flat=True)) if not update_existing else set()
        processed_ids = set()
        
        for index, row in df.iterrows():
            student_data = {}
            # Map Excel columns to model fields
            for col in df.columns:
                if col in valid_fields:
                    val = row[col]
                    if pd.isna(val):
                        val = None
                    student_data[col] = val
            
            # 1. Extract and Clean ID
            s_id = str(student_data.get('student_id', '')).strip()
            if not s_id or s_id == 'nan':
                errors.append(f"Row {index+2}: Student ID is missing.")
                continue
                
            # ID Correction (legacy logic)
            if len(s_id) == 15 and s_id.startswith('80'):
                s_id = '0' + s_id
            student_data['student_id'] = s_id
            
            # 2. UGC Validation
            is_valid, v_msg = validate_ugc_id(s_id)
            if not is_valid:
                errors.append(f"Row {index+2}: {v_msg} ({s_id})")
                continue

            # 3. Duplicate checks
            if s_id in processed_ids:
                errors.append(f"Row {index+2}: Duplicate ID in file ({s_id}).")
                continue
            
            if not update_existing and s_id in existing_ids:
                errors.append(f"Row {index+2}: ID already exists in database ({s_id}).")
                continue
            
            # Name sanitization
            for name_field in ['student_name', 'father_name', 'mother_name']:
                if student_data.get(name_field):
                    student_data[name_field] = str(student_data[name_field]).upper()
            
            records_to_process.append(Student(**student_data))
            processed_ids.add(s_id)

        # Atomic Bulk Operation
        with transaction.atomic():
            if update_existing:
                # Use bulk_create with update_conflicts for high performance on Postgres
                Student.objects.bulk_create(
                    records_to_process,
                    update_conflicts=True,
                    unique_fields=['student_id'],
                    update_fields=update_fields
                )
            else:
                Student.objects.bulk_create(records_to_process)
            
        return {
            'success': True,
            'count': len(records_to_process),
            'errors': errors[:20], # Show more errors for convenience
            'total_errors': len(errors)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def bulk_import_program_change(records):
    """Specialized bulk logic for program changes if ever needed."""
    pass

def execute_program_change_web(student, new_program, new_cluster, new_year, new_semester, hall_name, notes="Web-based program change"):
    """
    Handles the complexity of changing a student's program and generating a new ID.
    Now includes automated SMS notifications and persistent history tracking.
    """
    try:
        with transaction.atomic():
            old_id = student.student_id
            old_program = student.program
            
            # 1. Generate new ID using the automated logic
            new_id = generate_next_ugc_id(
                admission_year=new_year,
                semester_name=new_semester,
                hall_name=hall_name,
                program_name=new_program,
                cluster_name=new_cluster,
                program_level=student.program_type,
                mba_credits=student.mba_credits
            )
            
            # 2. Record history in the dedicated audit table
            ProgramChangeHistory.objects.create(
                old_student_id=old_id,
                new_student_id=new_id,
                old_program=old_program,
                new_program=new_program,
                notes=notes
            )
            
            # 3. Migrate Student Data to New ID (Cloning Strategy)
            student.old_student_id = old_id # Persist immediate previous ID
            student.student_id = new_id
            student.program = new_program
            student.cluster = new_cluster
            student.admission_year = new_year
            student.semester_name = new_semester
            student.hall_attached = hall_name
            
            # Save creates a new row because PK (student_id) changed
            student.save()
            
            # Delete old row after successful clone
            Student.objects.filter(student_id=old_id).delete()
            
            # 4. Synchronize related soft-linked records
            SMSHistory.objects.filter(student_id=old_id).update(student_id=new_id)
            
            # 5. Trigger Automated SMS Notification
            if student.student_mobile:
                msg_body = (
                    f"Dear {student.student_name}, your department has been changed to {new_program}. "
                    f"Your new official ID is {new_id}. Please use this for all future academic records. - BAUST"
                )
                
                # Trigger Actual SMS Delivery
                from core.utils import send_sms
                success, response_text = send_sms(student.student_mobile, msg_body)
                
                # Log the SMS in History with API Response
                SMSHistory.objects.create(
                    recipient_name=student.student_name,
                    student_id=new_id,
                    recipient_contact=student.student_mobile,
                    sms_delivery_type="Transaction",
                    message_type="SMS",
                    message_body=msg_body,
                    status="Delivered" if success else "Failed",
                    api_response=response_text,
                    api_profile_name="ProgramChangeSystem"
                )
            
            return {'success': True, 'new_id': new_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}
