from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import Cluster, Program, Hall, AdmissionYear, Semester, Batch
from core.decorators import require_access

@login_required
@require_access('security', 'manage_users') # Reusing security permission for settings
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
@require_access('security', 'manage_users')
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
@require_access('security', 'manage_users')
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
@require_access('security', 'manage_users')
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
            obj.name = request.POST.get('name')
            obj.code = request.POST.get('code')
        elif model_name == 'program':
            obj.name = request.POST.get('name')
            obj.short_name = request.POST.get('short_name')
            obj.ugc_code = request.POST.get('ugc_code')
            obj.cluster = get_object_or_404(Cluster, id=request.POST.get('cluster'))
            obj.level_code = request.POST.get('level_code')
            obj.sort_order = request.POST.get('sort_order', 0)
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
            obj.name = request.POST.get('name')
            obj.admission_year = get_object_or_404(AdmissionYear, id=request.POST.get('year'))
            obj.sort_order = request.POST.get('sort_order', 0)
        
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
