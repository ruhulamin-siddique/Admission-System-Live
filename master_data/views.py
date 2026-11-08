from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from .models import Cluster, Program, Hall, AdmissionYear, Semester, Batch
from core.decorators import require_access

@login_required
@require_access('security', 'manage_academic_settings')
def academic_settings(request):
    from django.db.models import Count, Q
    from collections import Counter
    
    halls_annotated = Hall.objects.annotate(
        occupied_count=Count('residents', filter=Q(residents__is_non_residential=False))
    ).order_by('full_name', 'short_name')
    
    clusters = list(Cluster.objects.all().order_by('name'))
    programs = list(Program.objects.all().order_by('name'))
    halls = list(halls_annotated)
    years = list(AdmissionYear.objects.all().order_by('-year'))
    semesters = list(Semester.objects.all().order_by('name'))
    batches = list(Batch.objects.all().order_by('-admission_year', 'name'))
    
    # Detect duplicate 5-digit UGC codes in Programs
    program_ugc_counts = Counter(p.full_ugc_code for p in programs)
    for p in programs:
        p.is_duplicate = (program_ugc_counts[p.full_ugc_code] > 1)

    # Detect duplicate codes in Halls
    hall_code_counts = Counter(h.code for h in halls if h.code)
    for h in halls:
        h.is_duplicate = (hall_code_counts[h.code] > 1)

    # Detect duplicate codes in Clusters
    cluster_code_counts = Counter(c.code for c in clusters if c.code)
    for c in clusters:
        c.is_duplicate = (cluster_code_counts[c.code] > 1)

    # Detect duplicate codes in Semesters
    semester_code_counts = Counter(s.code for s in semesters if s.code)
    for s in semesters:
        s.is_duplicate = (semester_code_counts[s.code] > 1)

    # Detect duplicate batch names in the same admission year
    batch_counts = Counter((b.name, b.admission_year_id) for b in batches)
    for b in batches:
        b.is_duplicate = (batch_counts[(b.name, b.admission_year_id)] > 1)

    context = {
        'clusters': clusters,
        'programs': programs,
        'halls': halls,
        'years': years,
        'semesters': semesters,
        'batches': batches,
        'has_duplicate_programs': any(p.is_duplicate for p in programs),
        'has_duplicate_halls': any(h.is_duplicate for h in halls),
        'has_duplicate_clusters': any(c.is_duplicate for c in clusters),
        'has_duplicate_semesters': any(s.is_duplicate for s in semesters),
        'has_duplicate_batches': any(b.is_duplicate for b in batches),
    }
    return render(request, 'master_data/academic_settings.html', context)

@login_required
@require_access('security', 'manage_academic_settings')
def add_master_data(request, model_name):
    if request.method == 'POST':
        duplicate_warning = False
        try:
            with transaction.atomic():
                if model_name == 'cluster':
                    Cluster.objects.create(name=request.POST.get('name'), code=request.POST.get('code'))
                elif model_name == 'program':
                    cluster = get_object_or_404(Cluster, id=request.POST.get('cluster'))
                    ugc_code = request.POST.get('ugc_code')
                    level_code = request.POST.get('level_code')
                    if Program.objects.filter(cluster=cluster, ugc_code=ugc_code, level_code=level_code).exists():
                        duplicate_warning = True
                        messages.warning(request, f"Notice: A program with the same Cluster, UGC Code '{ugc_code}', and Level already exists. The program was successfully added, and duplicates are highlighted in the UI.")
                    Program.objects.create(
                        name=request.POST.get('name'), 
                        short_name=request.POST.get('short_name'),
                        ugc_code=ugc_code,
                        cluster=cluster,
                        level_code=level_code,
                        sort_order=request.POST.get('sort_order', 0)
                    )
                elif model_name == 'hall':
                    code = request.POST.get('code')
                    if Hall.objects.filter(code=code).exists():
                        duplicate_warning = True
                        messages.warning(request, f"Warning: A duplicate Hall code '{code}' has been detected. The hall was successfully added, but duplicate codes may impact standard UGC ID assignments.")
                    Hall.objects.create(
                        full_name=request.POST.get('full_name'),
                        short_name=request.POST.get('short_name'),
                        code=code,
                        capacity=int(request.POST.get('capacity', 0) or 0)
                    )
                elif model_name == 'year':
                    AdmissionYear.objects.create(year=request.POST.get('year'))
                elif model_name == 'semester':
                    Semester.objects.create(name=request.POST.get('name'), code=request.POST.get('code'))
                elif model_name == 'batch':
                    year = get_object_or_404(AdmissionYear, id=request.POST.get('year'))
                    order = request.POST.get('sort_order', 0)
                    Batch.objects.create(name=request.POST.get('name'), admission_year=year, sort_order=order)

            if not duplicate_warning:
                messages.success(request, f"{model_name.capitalize()} added successfully.")
        except IntegrityError:
            if model_name == 'program':
                messages.error(request, "Unable to add Program: A program with this Name or Short Name already exists.")
            elif model_name == 'cluster':
                messages.error(request, "Unable to add Cluster: A cluster with this Name or UGC Code already exists.")
            elif model_name == 'hall':
                messages.error(request, "Unable to add Hall: A hall with this Name or Short Name already exists.")
            elif model_name == 'year':
                messages.error(request, "Unable to add Admission Year: This year already exists.")
            elif model_name == 'semester':
                messages.error(request, "Unable to add Semester: A semester with this Name already exists.")
            elif model_name == 'batch':
                messages.error(request, "Unable to add Batch: A batch with this Name already exists for the selected admission year.")
            else:
                messages.error(request, f"Unable to add {model_name}: A duplicate entry already exists.")
        except Exception as e:
            messages.error(request, f"Failed to add {model_name}: {str(e)}")
            
    tab_map = {'cluster': 'clusters', 'program': 'programs', 'hall': 'halls', 'year': 'years', 'semester': 'semesters', 'batch': 'batches'}
    tab = tab_map.get(model_name, '')
    return redirect(f"{reverse('academic_settings')}#{tab}")

@login_required
@require_access('security', 'manage_academic_settings')
def delete_master_data(request, model_name, pk):
    model_map = {
        'cluster': Cluster,
        'program': Program,
        'hall': Hall,
        'year': AdmissionYear,
        'semester': Semester,
        'batch': Batch,
    }
    model = model_map.get(model_name)
    if model:
        obj = get_object_or_404(model, pk=pk)
        try:
            obj.delete()
            messages.success(request, f"{model_name.capitalize()} deleted successfully.")
        except (ProtectedError, IntegrityError):
            messages.error(request, f"Cannot delete {model_name}: It is currently linked to existing records (e.g. programs or students) in the system.")
        except Exception as e:
            messages.error(request, f"Failed to delete {model_name}: {str(e)}")
    tab_map = {'cluster': 'clusters', 'program': 'programs', 'hall': 'halls', 'year': 'years', 'semester': 'semesters', 'batch': 'batches'}
    tab = tab_map.get(model_name, '')
    return redirect(f"{reverse('academic_settings')}#{tab}")

@login_required
@require_access('security', 'manage_academic_settings')
def edit_master_data(request, model_name, pk):
    """View to handle editing existing master data records."""
    model_map = {
        'cluster': Cluster,
        'program': Program,
        'hall': Hall,
        'year': AdmissionYear,
        'semester': Semester,
        'batch': Batch,
    }
    model = model_map.get(model_name)
    obj = get_object_or_404(model, pk=pk)
    
    if request.method == 'POST':
        duplicate_warning = False
        try:
            with transaction.atomic():
                if model_name == 'cluster':
                    old_name = obj.name
                    new_name = request.POST.get('name')
                    obj.name = new_name
                    obj.code = request.POST.get('code')
                    if old_name != new_name:
                        from students.models import Student
                        Student.objects.filter(cluster=old_name).update(cluster=new_name)
                elif model_name == 'program':
                    old_canonical = obj.short_name if obj.short_name else obj.name
                    cluster = get_object_or_404(Cluster, id=request.POST.get('cluster'))
                    ugc_code = request.POST.get('ugc_code')
                    level_code = request.POST.get('level_code')
                    if Program.objects.filter(cluster=cluster, ugc_code=ugc_code, level_code=level_code).exclude(pk=obj.pk).exists():
                        duplicate_warning = True
                        messages.warning(request, f"Notice: Another program under this Cluster already uses UGC Code '{ugc_code}' with Level '{level_code}'. The program was updated and duplicates are highlighted in the UI.")
                    obj.name = request.POST.get('name')
                    obj.short_name = request.POST.get('short_name')
                    obj.ugc_code = ugc_code
                    obj.cluster = cluster
                    obj.level_code = level_code
                    obj.sort_order = request.POST.get('sort_order', 0)
                    new_canonical = obj.short_name if obj.short_name else obj.name
                    if old_canonical != new_canonical:
                        from students.models import Student
                        Student.objects.filter(program=old_canonical).update(program=new_canonical)
                elif model_name == 'hall':
                    new_code = request.POST.get('code')
                    obj.full_name = request.POST.get('full_name')
                    obj.short_name = request.POST.get('short_name')
                    obj.capacity = int(request.POST.get('capacity', 0) or 0)
                    if Hall.objects.filter(code=new_code).exclude(pk=obj.pk).exists():
                        duplicate_warning = True
                        messages.warning(request, f"Warning: A duplicate Hall code '{new_code}' has been detected. The hall was successfully updated, but duplicate codes may impact standard UGC ID assignments.")
                    obj.code = new_code
                elif model_name == 'year':
                    obj.year = request.POST.get('year')
                    obj.is_active = request.POST.get('is_active') == 'on'
                elif model_name == 'semester':
                    obj.name = request.POST.get('name')
                    obj.code = request.POST.get('code')
                elif model_name == 'batch':
                    old_name = obj.name
                    new_name = request.POST.get('name')
                    obj.name = new_name
                    obj.admission_year = get_object_or_404(AdmissionYear, id=request.POST.get('year'))
                    obj.sort_order = request.POST.get('sort_order', 0)
                    
                    # If name changed, propagate to students (Since it's a CharField, not a FK)
                    if old_name != new_name:
                        from students.models import Student
                        import re
                        nums = re.findall(r'\d+', new_name)
                        new_batch_num = int(nums[0]) if nums else 0
                        Student.objects.filter(batch=old_name).update(batch=new_name, batch_number=new_batch_num)
                
                obj.save()

            if not duplicate_warning:
                messages.success(request, f"{model_name.capitalize()} updated successfully.")
        except IntegrityError:
            if model_name == 'program':
                messages.error(request, "Unable to update Program: Another program with this Name or Short Name already exists.")
            elif model_name == 'cluster':
                messages.error(request, "Unable to update Cluster: Another cluster with this Name or UGC Code already exists.")
            elif model_name == 'hall':
                messages.error(request, "Unable to update Hall: Another hall with this Name or Short Name already exists.")
            elif model_name == 'year':
                messages.error(request, "Unable to update Admission Year: This year already exists.")
            elif model_name == 'semester':
                messages.error(request, "Unable to update Semester: Another semester with this Name already exists.")
            elif model_name == 'batch':
                messages.error(request, "Unable to update Batch: Another batch with this Name already exists for the selected admission year.")
            else:
                messages.error(request, f"Unable to update {model_name}: A duplicate entry already exists.")
        except Exception as e:
            messages.error(request, f"Failed to update {model_name}: {str(e)}")

        tab_map = {
            'cluster': 'clusters',
            'program': 'programs',
            'hall': 'halls',
            'year': 'years',
            'semester': 'semesters',
            'batch': 'batches',
        }
        tab = tab_map.get(model_name, '')
        return redirect(f"{reverse('academic_settings')}#{tab}")
    
    return redirect('academic_settings')
    
@login_required
@require_access('security', 'manage_academic_settings')
def harmonize_batch_assignment(request):
    """
    Bulk assigns a batch to students based on Program, Year, and Semester filters.
    This is the 'Master Data Harmonizer' requested by the user.
    """
    from django.db import transaction
    if request.method == 'POST':
        batch_id = request.POST.get('batch_id')
        program_name = request.POST.get('program')
        year = request.POST.get('year')
        semester = request.POST.get('semester')
        
        from .models import Batch
        from students.models import Student
        import re
        
        batch = get_object_or_404(Batch, id=batch_id)
        nums = re.findall(r'\d+', batch.name)
        batch_num = int(nums[0]) if nums else 0
        
        # Build filter
        filters = {}
        if program_name: filters['program'] = program_name
        if year: filters['admission_year'] = year
        if semester: filters['semester_name'] = semester
        
        if not filters:
            from django.contrib import messages
            messages.warning(request, "Please select at least one filter to avoid accidental global updates.")
            return redirect(f"{reverse('academic_settings')}#batches")
            
        try:
            with transaction.atomic():
                students = Student.objects.filter(**filters)
                count = students.count()
                students.update(batch=batch.name, batch_number=batch_num)
                
            from django.contrib import messages
            messages.success(request, f"Harmonization Complete: Assigned '{batch.name}' to {count} students matching your criteria.")
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f"Harmonization failed: {str(e)}")
    
    return redirect(f"{reverse('academic_settings')}#batches")

@login_required
@require_access('security', 'manage_academic_settings')
def generate_programs_pdf(request):
    """Generates a PDF document for all academic programs."""
    from core.models import SystemSettings
    from django.utils import timezone
    from django.conf import settings
    import os
    from students.views import render_to_pdf
    
    sys_settings = SystemSettings.objects.get_or_create(id=1)[0]
    logo = None
    if sys_settings.institution_logo:
        logo = os.path.join(settings.MEDIA_ROOT, str(sys_settings.institution_logo))
        if not os.path.exists(logo):
            logo = None
            
    programs = Program.objects.all().order_by('-sort_order', 'name')
    
    context = {
        'programs': programs,
        'sys_settings': {
            'logo_url': logo,
        },
        'current_time': timezone.now()
    }
    
    pdf_response = render_to_pdf('master_data/pdf/programs_pdf.html', context)
    if pdf_response:
        pdf_response['Content-Disposition'] = 'inline; filename="BAUST_Academic_Programs_Registry.pdf"'
        return pdf_response
    return HttpResponse("Error generating programs PDF.", status=500)
