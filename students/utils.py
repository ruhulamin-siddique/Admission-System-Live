import pandas as pd
from django.db import models, transaction
from django.db.models import Max, Q
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
    hall_name = (hall.full_name or hall.short_name) if hall else "Unknown"
    
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

def get_canonical_program_name(raw_name):
    """
    Shared resolver: given any full or short program name, returns the canonical
    stored value. Optimized with a static cache to prevent redundant DB loops.
    """
    if not raw_name:
        return raw_name
    
    # Static cache to avoid fetching Programs multiple times
    if not hasattr(get_canonical_program_name, '_cache'):
        from master_data.models import Program
        progs = list(Program.objects.all())
        get_canonical_program_name._cache = {
            p.name.upper(): (p.short_name if p.short_name else p.name)
            for p in progs
        }
        for p in progs:
            if p.short_name:
                get_canonical_program_name._cache[p.short_name.upper()] = (p.short_name if p.short_name else p.name)

    key = str(raw_name).strip().upper()
    return get_canonical_program_name._cache.get(key, raw_name)


def generate_ugc_prefix(admission_year, semester_name, hall_name, program_name, cluster_name, program_level="Bachelor"):
    """
    Returns only the first 13-digit UGC prefix (no serial).
    Structure: UUU YY S HH CcssP  (13 chars)
    Used by the semi-auto admission form so the user can supply the last 3 serial digits.
    """
    from django.db.models import Q
    year_code = str(admission_year)[-2:]

    sem = Semester.objects.filter(Q(name__icontains=semester_name)).first()
    semester_code = sem.code if sem else "1"

    hall = Hall.objects.filter(
        Q(short_name__icontains=hall_name) | Q(full_name__icontains=hall_name)
    ).first()
    hall_code = str(hall.code if hall else "00").zfill(2)

    prog = Program.objects.filter(
        Q(name__iexact=program_name) | Q(short_name__iexact=program_name)
    ).first()
    if prog:
        cluster_code = str(prog.cluster.code).zfill(2)
        s_code       = str(prog.ugc_code).zfill(2)
        level_code   = prog.level_code
    else:
        cluster_code = "05"
        s_code       = "01"
        level_code   = "1"

    prefix = f"{UNIVERSITY_CODE}{year_code}{semester_code}{hall_code}{cluster_code}{s_code}{level_code}"
    return prefix  # 13 characters


def generate_next_ugc_id(admission_year, semester_name, hall_name, program_name, cluster_name, program_level="Bachelor", subject_code=None, mba_credits=None):
    """
    Dynamic Automated UGC ID Generator using Master Data.
    Structure: UUU YY S HH CcssP SSS
    """
    year_code = str(admission_year)[-2:]
    
    # 1. Get Semester Code from DB
    sem = None
    if semester_name:
        sem = Semester.objects.filter(Q(name__icontains=semester_name)).first()
    semester_code = sem.code if sem else "1"
            
    # 2. Get Hall Code from DB
    hall = None
    if hall_name:
        hall = Hall.objects.filter(
            Q(short_name__icontains=hall_name) | 
            Q(full_name__icontains=hall_name)
        ).first()
    hall_code = hall.code if hall else "00"
    
    # 3. Get Cluster & Subject Codes from DB
    # We look for the Program specifically to get its UGC code and Cluster code
    prog = None
    if program_name:
        prog = Program.objects.filter(
            Q(name__iexact=program_name) | 
            Q(short_name__iexact=program_name)
        ).first()
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
    
    # Ensure all codes are correctly padded
    hall_code = str(hall_code).zfill(2)
    cluster_code = str(cluster_code).zfill(2)
    s_code = str(s_code).zfill(2)
    
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
        
        # Get mapping of valid model fields to their instances
        valid_fields = {f.name: f for f in Student._meta.get_fields()}
        # Exclude internal/meta fields from update
        exclude_from_update = {'student_id', 'created_at', 'last_updated'}
        update_fields = [f for f in valid_fields.keys() if f in df.columns and f not in exclude_from_update]

        records_to_process = []
        errors = []
        existing_ids = set(Student.objects.values_list('student_id', flat=True))
        # Keep track of what we will update vs insert
        inserted_list = []
        updated_list = []
        processed_ids = set()
        
        # PRE-FETCH: Build lookup tables for high-performance normalization
        from master_data.models import Program
        all_programs = list(Program.objects.select_related('cluster').all())
        
        # Build mapping: (full_name/short_name) -> {canonical, cluster, type}
        prog_lookup = {}
        for p in all_programs:
            canonical = p.short_name if p.short_name else p.name
            p_data = {
                'canonical': canonical,
                'cluster': p.cluster.name,
                'type': p.get_level_code_display()
            }
            prog_lookup[p.name.upper()] = p_data
            if p.short_name:
                prog_lookup[p.short_name.upper()] = p_data

        for index, row in df.iterrows():
            student_data = {}
            # Map Excel columns to model fields
            for col in df.columns:
                if col in valid_fields:
                    val = row[col]
                    field = valid_fields[col]
                    
                    if pd.isna(val):
                        val = None
                        
                    if isinstance(field, models.BooleanField):
                        if val is None:
                            val = False
                        else:
                            val = str(val).strip().lower() in ['true', '1', 'yes', 'y', 't']
                    elif isinstance(field, models.DateField) and val is not None:
                        try:
                            val = pd.to_datetime(val).date()
                        except Exception:
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
            
            # Automatically detect legacy student status (batch 1-12 or short ID)
            is_legacy = False
            if student_data.get('is_legacy_student'):
                is_legacy = True
            if s_id and len(s_id) < 16:
                is_legacy = True
            if student_data.get('batch'):
                import re
                nums = re.findall(r'\d+', str(student_data['batch']))
                if nums:
                    batch_num = int(nums[0])
                    if 1 <= batch_num <= 12:
                        is_legacy = True
            if is_legacy:
                student_data['is_legacy_student'] = True
            
            # 2. UGC Validation
            if not student_data.get('is_legacy_student', False):
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
                    
            # 4. Program & Cluster normalization — use pre-fetched lookup
            if student_data.get('program'):
                raw_prog = str(student_data['program']).strip().upper()
                if raw_prog in prog_lookup:
                    match = prog_lookup[raw_prog]
                    student_data['program'] = match['canonical']
                    student_data['cluster'] = match['cluster']
                    student_data['program_type'] = match['type']
                else:
                    # Fallback if not found in master data
                    student_data['program'] = get_canonical_program_name(student_data['program'])
                
            # Status standardization
            if student_data.get('admission_status'):
                stat = str(student_data['admission_status']).strip().title()
                if stat in ['Active', 'Admitted', 'Current', 'Running']:
                    stat = 'Active'
                elif stat in ['Canceled', 'Cancel', 'Cancelled']:
                    stat = 'Cancelled'
                elif stat in ['Graduated', 'Alumni']:
                    stat = 'Graduated'
                elif stat not in ['Pending', 'Active', 'Cancelled', 'Graduated']:
                    stat = 'Pending' # Fallback
                student_data['admission_status'] = stat
            
            # Default Admission Date if missing
            if not student_data.get('admission_date'):
                student_data['admission_date'] = timezone.now().date()

            # Default Current Batch / Current Semester if missing (essential since bulk_create bypasses save())
            if not student_data.get('current_batch') and student_data.get('batch'):
                student_data['current_batch'] = student_data['batch']
            if not student_data.get('current_semester'):
                student_data['current_semester'] = 'Level 1 Term I'

            records_to_process.append(Student(**student_data))
            processed_ids.add(s_id)
            
            if s_id in existing_ids:
                updated_list.append(s_id)
            else:
                inserted_list.append(s_id)

        # Atomic Bulk Operation
        with transaction.atomic():
            if update_existing:
                # Use bulk_create with update_conflicts for high performance on Postgres
                Student.objects.bulk_create(
                    records_to_process,
                    update_conflicts=True,
                    update_fields=update_fields
                )
            else:
                Student.objects.bulk_create(records_to_process)
            
        return {
            'success': True,
            'count': len(records_to_process),
            'inserted_count': len(inserted_list),
            'updated_count': len(updated_list),
            'inserted_list': inserted_list,      # Full list
            'updated_list': updated_list,        # Full list
            'errors': errors,                    # Full list
            'total_errors': len(errors)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def bulk_import_program_change(records):
    """Specialized bulk logic for program changes if ever needed."""
    pass

def execute_program_change_web(student, new_program, new_cluster, new_year, new_semester, hall_name, notes="Web-based program change", custom_id=None):
    """
    Handles the complexity of changing a student's program and generating a new ID.
    Now includes automated SMS notifications and persistent history tracking.
    """
    try:
        with transaction.atomic():
            old_id = student.student_id
            old_program = student.program
            
            if get_canonical_program_name(old_program) == get_canonical_program_name(new_program):
                return {'success': False, 'error': "Target program must be different from the current program."}
            
            # 1. Generate new ID using the automated logic
            if custom_id:
                new_id = custom_id
            else:
                new_id = generate_next_ugc_id(
                    admission_year=new_year,
                    semester_name=new_semester,
                    hall_name=hall_name,
                    program_name=new_program,
                    cluster_name=new_cluster,
                    program_level=student.program_type,
                    mba_credits=student.mba_credits
                )
            
            if not new_id or len(new_id) != 16 or not new_id.isdigit():
                return {'success': False, 'error': "Invalid student ID format. Must be exactly 16 digits."}
            
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


# ──────────────────────────────────────────────────────────────────────────────
# Academic Data Patch Utility
# ──────────────────────────────────────────────────────────────────────────────

SSC_FIELDS = [
    'ssc_school', 'ssc_year', 'ssc_board', 'ssc_roll',
    'ssc_reg', 'ssc_gpa', 'ssc_physics', 'ssc_chemistry', 'ssc_math',
]
HSC_FIELDS = [
    'hsc_college', 'hsc_year', 'hsc_board', 'hsc_roll',
    'hsc_reg', 'hsc_gpa', 'hsc_physics', 'hsc_chemistry', 'hsc_math',
]
FLOAT_FIELDS = {'ssc_gpa', 'ssc_physics', 'ssc_chemistry', 'ssc_math',
                'hsc_gpa', 'hsc_physics', 'hsc_chemistry', 'hsc_math'}

ALL_ACADEMIC_FIELDS = SSC_FIELDS + HSC_FIELDS

# Friendly labels for each field (used in templates)
FIELD_LABELS = {
    'ssc_school':    'SSC School',
    'ssc_year':      'SSC Year',
    'ssc_board':     'SSC Board',
    'ssc_roll':      'SSC Roll',
    'ssc_reg':       'SSC Registration',
    'ssc_gpa':       'SSC GPA',
    'ssc_physics':   'SSC Physics',
    'ssc_chemistry': 'SSC Chemistry',
    'ssc_math':      'SSC Math',
    'hsc_college':   'HSC College',
    'hsc_year':      'HSC Year',
    'hsc_board':     'HSC Board',
    'hsc_roll':      'HSC Roll',
    'hsc_reg':       'HSC Registration',
    'hsc_gpa':       'HSC GPA',
    'hsc_physics':   'HSC Physics',
    'hsc_chemistry': 'HSC Chemistry',
    'hsc_math':      'HSC Math',
}

# Quick-select presets: (label, icon, field list)
FIELD_PRESETS = [
    (
        'ssc_ids',
        'SSC Board IDs',
        'fa-id-card',
        ['ssc_board', 'ssc_year', 'ssc_roll', 'ssc_reg'],
    ),
    (
        'hsc_ids',
        'HSC Board IDs',
        'fa-id-badge',
        ['hsc_board', 'hsc_year', 'hsc_roll', 'hsc_reg'],
    ),
    (
        'both_ids',
        'Both Board IDs',
        'fa-layer-group',
        ['ssc_board', 'ssc_year', 'ssc_roll', 'ssc_reg',
         'hsc_board', 'hsc_year', 'hsc_roll', 'hsc_reg'],
    ),
    (
        'ssc_all',
        'All SSC Fields',
        'fa-list-ul',
        SSC_FIELDS,
    ),
    (
        'hsc_all',
        'All HSC Fields',
        'fa-list-ol',
        HSC_FIELDS,
    ),
    (
        'both_all',
        'All Academic Fields',
        'fa-th-list',
        ALL_ACADEMIC_FIELDS,
    ),
]


def get_academic_patch_fields(field_group):
    """Backward-compat helper: returns field list for a field_group string."""
    if field_group == 'ssc':
        return list(SSC_FIELDS)
    elif field_group == 'hsc':
        return list(HSC_FIELDS)
    else:  # 'both'
        return list(ALL_ACADEMIC_FIELDS)


def derive_field_groups(selected_fields):
    """
    Given an arbitrary list of field names, returns which verification groups
    are affected: {'ssc': bool, 'hsc': bool}.
    Used to decide which *_verified flags to reset.
    """
    ssc_set = set(SSC_FIELDS)
    hsc_set = set(HSC_FIELDS)
    fields_set = set(selected_fields)
    return {
        'ssc': bool(fields_set & ssc_set),
        'hsc': bool(fields_set & hsc_set),
    }


def patch_academic_data_from_excel(file_obj, selected_fields, scope_queryset, dry_run=False, changed_by_user=None):
    """
    Targeted Excel patch for SSC/HSC academic fields.

    Args:
        file_obj        : The uploaded Excel file object.
        selected_fields : List of model field names to patch (e.g. ['ssc_board', 'ssc_year', 'ssc_roll', 'ssc_reg']).
                          Only columns present in BOTH this list AND the Excel file are processed.
        scope_queryset  : A pre-filtered Django queryset of eligible Student objects.
        dry_run         : If True, compute diffs but do NOT commit to the database.
        changed_by_user : The User performing the action (for history logging).

    Returns a dict:
        success         : bool
        preview_rows    : list of dicts (for diff display)
        updated_count   : number of students actually updated
        skipped_blank   : rows skipped because all target fields were blank
        not_in_scope    : IDs found in Excel but not in scope_queryset
        not_found       : IDs in Excel that don't exist at all in the database
        errors          : list of error strings
        error           : top-level error string (only when success=False)
    """
    # Validate selected_fields against known academic fields
    valid_selected = [f for f in selected_fields if f in ALL_ACADEMIC_FIELDS]
    if not valid_selected:
        return {'success': False, 'error': "No valid academic fields selected."}

    try:
        df = pd.read_excel(file_obj)
        df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

        if 'student_id' not in df.columns:
            return {'success': False, 'error': "Excel file must contain a 'student_id' column."}

        # Intersect: only process fields that are both selected AND present in the file
        fields_in_file = [f for f in valid_selected if f in df.columns]
        if not fields_in_file:
            field_list = ', '.join(valid_selected)
            return {
                'success': False,
                'error': f"None of the selected columns were found in the file. Expected: {field_list}"
            }

        # Build scope lookup: student_id → Student instance
        scope_map = {s.student_id: s for s in scope_queryset}
        all_ids_in_db = set(Student.objects.values_list('student_id', flat=True))

        preview_rows = []
        students_to_update = []

        not_in_scope = []
        not_found = []
        skipped_blank = []
        errors = []

        for idx, row in df.iterrows():
            raw_id = str(row.get('student_id', '')).strip()
            # Clean float representation (e.g. "12345.0")
            if raw_id.endswith('.0'):
                raw_id = raw_id[:-2]
            if not raw_id or raw_id == 'nan':
                errors.append(f"Row {idx + 2}: Missing student_id.")
                continue

            # Check existence
            if raw_id not in all_ids_in_db:
                not_found.append(raw_id)
                continue

            # Check scope
            if raw_id not in scope_map:
                not_in_scope.append(raw_id)
                continue

            student = scope_map[raw_id]
            row_diffs = []
            has_any_value = False

            for field in fields_in_file:
                raw_val = row.get(field)
                if pd.isna(raw_val) or raw_val == '':
                    new_val = None
                else:
                    if field in FLOAT_FIELDS:
                        try:
                            new_val = float(raw_val)
                        except (ValueError, TypeError):
                            errors.append(f"Row {idx + 2} ({raw_id}): Invalid numeric for '{field}': {raw_val}")
                            new_val = None
                    else:
                        new_val = str(raw_val).strip()
                        if new_val.endswith('.0'):
                            new_val = new_val[:-2]
                        if new_val == 'nan':
                            new_val = None

                if new_val is not None:
                    has_any_value = True

                old_val = getattr(student, field, None)
                old_display = str(old_val) if old_val is not None else '—'
                new_display = str(new_val) if new_val is not None else '—'

                row_diffs.append({
                    'field': field,
                    'label': FIELD_LABELS.get(field, field),
                    'old': old_display,
                    'new': new_display,
                    'changed': (str(old_val) if old_val is not None else '') != (str(new_val) if new_val is not None else ''),
                })
                setattr(student, field, new_val)

            if not has_any_value:
                skipped_blank.append(raw_id)
                continue

            preview_rows.append({
                'student_id': raw_id,
                'student_name': student.student_name,
                'diffs': row_diffs,
            })
            students_to_update.append(student)

        # Determine which verification flags need to be reset
        groups = derive_field_groups(fields_in_file)
        bulk_update_fields = list(fields_in_file)

        if groups['ssc'] and students_to_update:
            bulk_update_fields.append('ssc_verified')
            for s in students_to_update:
                s.ssc_verified = False
        if groups['hsc'] and students_to_update:
            bulk_update_fields.append('hsc_verified')
            for s in students_to_update:
                s.hsc_verified = False

        if not dry_run and students_to_update:
            with transaction.atomic():
                Student.objects.bulk_update(students_to_update, bulk_update_fields, batch_size=200)

                # Manual StudentFieldHistory creation (bulk_update bypasses save())
                if changed_by_user:
                    from .models import StudentFieldHistory
                    history_records = []
                    for preview in preview_rows:
                        sid = preview['student_id']
                        student = scope_map[sid]
                        for diff in preview['diffs']:
                            if diff['changed']:
                                history_records.append(StudentFieldHistory(
                                    student=student,
                                    field_name=diff['field'],
                                    old_value=diff['old'] if diff['old'] != '—' else None,
                                    new_value=diff['new'] if diff['new'] != '—' else None,
                                    changed_by=changed_by_user,
                                ))
                    if history_records:
                        StudentFieldHistory.objects.bulk_create(history_records, batch_size=500)

        return {
            'success': True,
            'preview_rows': preview_rows,
            'updated_count': len(students_to_update) if not dry_run else 0,
            'preview_count': len(students_to_update),
            'fields_patched': fields_in_file,
            'groups_affected': groups,
            'skipped_blank': skipped_blank,
            'not_in_scope': not_in_scope,
            'not_found': not_found,
            'errors': errors,
        }

    except Exception as e:
        import traceback
        return {'success': False, 'error': str(e), 'traceback': traceback.format_exc()}



