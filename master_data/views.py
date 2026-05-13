from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import Cluster, Program, Hall, AdmissionYear, Semester, Batch
from core.decorators import require_access

@login_required
@require_access('security', 'manage_academic_settings')
def academic_settings(request):
    context = {
        'clusters': Cluster.objects.all().order_by('name'),
        'programs': Program.objects.all().order_by('name'),
        'halls': Hall.objects.all().order_by('full_name', 'short_name'),
        'years': AdmissionYear.objects.all().order_by('-year'),
        'semesters': Semester.objects.all().order_by('name'),
        'batches': Batch.objects.all().order_by('-admission_year', 'name'),
    }
    return render(request, 'master_data/academic_settings.html', context)

@login_required
@require_access('security', 'manage_academic_settings')
def add_master_data(request, model_name):
    if request.method == 'POST':
        if model_name == 'cluster':
            Cluster.objects.create(name=request.POST.get('name'), code=request.POST.get('code'))
        elif model_name == 'program':
            cluster = get_object_or_404(Cluster, id=request.POST.get('cluster'))
            Program.objects.create(
                name=request.POST.get('name'), 
                short_name=request.POST.get('short_name'),
                ugc_code=request.POST.get('ugc_code'),
                cluster=cluster,
                level_code=request.POST.get('level_code'),
                sort_order=request.POST.get('sort_order', 0)
            )
        elif model_name == 'hall':
            Hall.objects.create(
                full_name=request.POST.get('full_name'),
                short_name=request.POST.get('short_name'),
                code=request.POST.get('code')
            )
        elif model_name == 'year':
            AdmissionYear.objects.create(year=request.POST.get('year'))
        elif model_name == 'semester':
            Semester.objects.create(name=request.POST.get('name'), code=request.POST.get('code'))
        elif model_name == 'batch':
            year = get_object_or_404(AdmissionYear, id=request.POST.get('year'))
            order = request.POST.get('sort_order', 0)
            Batch.objects.create(name=request.POST.get('name'), admission_year=year, sort_order=order)
            
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
        obj.delete()
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
            obj.name = request.POST.get('name')
            obj.short_name = request.POST.get('short_name')
            obj.ugc_code = request.POST.get('ugc_code')
            obj.cluster = get_object_or_404(Cluster, id=request.POST.get('cluster'))
            obj.level_code = request.POST.get('level_code')
            obj.sort_order = request.POST.get('sort_order', 0)
            new_canonical = obj.short_name if obj.short_name else obj.name
            if old_canonical != new_canonical:
                from students.models import Student
                Student.objects.filter(program=old_canonical).update(program=new_canonical)
        elif model_name == 'hall':
            obj.full_name = request.POST.get('full_name')
            obj.short_name = request.POST.get('short_name')
            obj.code = request.POST.get('code')
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
