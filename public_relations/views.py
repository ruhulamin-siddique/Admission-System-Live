"""
public_relations/views.py
=========================
Bilingual view functions using Django's i18n support.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils.translation import gettext as _

from core.decorators import require_access
from core.utils import log_activity

from .models import (
    MediaHouse,
    PublicRelationsArchive,
    MediaCoverage,
    MediaAsset,
)
from .forms import (
    MediaHouseForm,
    PublicRelationsArchiveForm,
    MediaCoverageFormSet,
    MediaAssetFormSet,
    PRSearchForm,
)
from .utils import export_archive_to_excel, render_archive_pdf


# ============================================================================
# Dashboard
# ============================================================================

@require_access('public_relations', 'view_dashboard')
def dashboard(request):
    total_releases     = PublicRelationsArchive.objects.count()
    total_coverage     = MediaCoverage.objects.count()
    national_count     = MediaCoverage.objects.filter(media_house__media_type='national').count()
    local_count        = MediaCoverage.objects.filter(media_house__media_type='local').count()
    online_count       = MediaCoverage.objects.filter(media_house__media_type='online').count()
    tv_count           = MediaCoverage.objects.filter(media_house__media_type='tv').count()
    total_media_houses = MediaHouse.objects.count()

    recent_entries = (
        PublicRelationsArchive.objects
        .select_related('created_by')
        .prefetch_related('coverages')
        .order_by('-press_release_date', '-created_at')[:10]
    )

    media_houses_by_type = {
        'national': MediaHouse.objects.filter(media_type='national').count(),
        'local':    MediaHouse.objects.filter(media_type='local').count(),
        'online':   MediaHouse.objects.filter(media_type='online').count(),
        'tv':       MediaHouse.objects.filter(media_type='tv').count(),
    }

    import datetime
    from django.db.models.functions import ExtractMonth
    from django.db.models import Count

    current_year = datetime.date.today().year
    monthly_data = (
        PublicRelationsArchive.objects
        .filter(press_release_date__year=current_year)
        .annotate(month=ExtractMonth('press_release_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    
    monthly_counts = [0] * 12
    for item in monthly_data:
        if item['month']:
            monthly_counts[item['month'] - 1] = item['count']

    context = {
        'page_title':          _('PR Dashboard'),
        'total_releases':      total_releases,
        'total_coverage':      total_coverage,
        'national_count':      national_count,
        'local_count':         local_count,
        'online_count':        online_count,
        'tv_count':            tv_count,
        'total_media_houses':  total_media_houses,
        'recent_entries':      recent_entries,
        'media_houses_by_type': media_houses_by_type,
        'monthly_counts':      monthly_counts,
        'current_year':        current_year,
    }
    return render(request, 'public_relations/dashboard.html', context)


# ============================================================================
# Archive List + Multi-Parameter Search Engine
# ============================================================================

@require_access('public_relations', 'view_archive')
def archive_list(request):
    search_form = PRSearchForm(request.GET or None)
    queryset    = (
        PublicRelationsArchive.objects
        .select_related('created_by')
        .prefetch_related('coverages__media_house')
        .order_by('-press_release_date', '-created_at')
    )

    applied = False

    if search_form.is_valid():
        keyword    = search_form.cleaned_data.get('keyword', '').strip()
        start_date = search_form.cleaned_data.get('start_date')
        end_date   = search_form.cleaned_data.get('end_date')
        media_type = search_form.cleaned_data.get('media_type', '')
        department = search_form.cleaned_data.get('department', '').strip()

        if keyword:
            applied = True
            queryset = queryset.filter(
                Q(press_release_no__icontains=keyword) |
                Q(event_name__icontains=keyword)       |
                Q(full_text__icontains=keyword)        |
                Q(department__icontains=keyword)       |
                Q(coverages__media_house__name__icontains=keyword)
            ).distinct()

        if start_date:
            applied = True
            queryset = queryset.filter(press_release_date__gte=start_date)
        if end_date:
            applied = True
            queryset = queryset.filter(press_release_date__lte=end_date)

        if media_type:
            applied = True
            queryset = queryset.filter(
                coverages__media_house__media_type=media_type
            ).distinct()

        if department:
            applied = True
            queryset = queryset.filter(department__icontains=department)

    # Pagination
    paginator   = Paginator(queryset, 20)
    page_number = request.GET.get('page', 1)
    page_obj    = paginator.get_page(page_number)

    can_add    = _has_perm(request, 'add_archive')
    can_edit   = _has_perm(request, 'edit_archive')
    can_delete = _has_perm(request, 'delete_archive')
    can_export = _has_perm(request, 'export_data')

    context = {
        'page_title':   _('Press Release Archive'),
        'search_form':  search_form,
        'page_obj':     page_obj,
        'applied':      applied,
        'total_count':  queryset.count(),
        'can_add':      can_add,
        'can_edit':     can_edit,
        'can_delete':   can_delete,
        'can_export':   can_export,
        'get_params':   _get_params_without_page(request),
    }
    return render(request, 'public_relations/archive_list.html', context)


# ============================================================================
# Archive Create (Unified formset view, atomic transaction)
# ============================================================================

@require_access('public_relations', 'add_archive')
def archive_create(request):
    if request.method == 'POST':
        archive_form    = PublicRelationsArchiveForm(request.POST, request.FILES)
        coverage_formset = MediaCoverageFormSet(request.POST, request.FILES, prefix='coverages')
        asset_formset    = MediaAssetFormSet(request.POST, request.FILES, prefix='assets')

        all_valid = (
            archive_form.is_valid() and
            coverage_formset.is_valid() and
            asset_formset.is_valid()
        )

        if all_valid:
            try:
                with transaction.atomic():
                    archive = archive_form.save(commit=False)
                    archive.created_by = request.user
                    archive.save()

                    coverage_formset.instance = archive
                    coverage_formset.save()

                    asset_formset.instance = archive
                    asset_formset.save()

                log_activity(
                    request, 'CREATE', 'public_relations',
                    f'Press Release created: {archive.press_release_no} — {archive.event_name}',
                    object_id=str(archive.pk),
                    is_system_alert=True,
                )
                messages.success(
                    request,
                    _('Press Release "%(no)s" successfully saved.') % {'no': archive.press_release_no}
                )
                return redirect('pr_archive_detail', pk=archive.pk)

            except Exception as exc:
                messages.error(request, _('Error while saving: %(err)s') % {'err': str(exc)})
        else:
            messages.error(request, _('There are errors in the form. Please check details below.'))

    else:
        archive_form     = PublicRelationsArchiveForm()
        coverage_formset = MediaCoverageFormSet(prefix='coverages')
        asset_formset    = MediaAssetFormSet(prefix='assets')

    context = {
        'page_title':        _('Create Press Release'),
        'archive_form':      archive_form,
        'coverage_formset':  coverage_formset,
        'asset_formset':     asset_formset,
        'is_edit':           False,
    }
    return render(request, 'public_relations/archive_form.html', context)


# ============================================================================
# Archive Detail
# ============================================================================

@require_access('public_relations', 'view_archive')
def archive_detail(request, pk):
    entry = get_object_or_404(
        PublicRelationsArchive.objects
        .select_related('created_by')
        .prefetch_related('coverages__media_house', 'assets'),
        pk=pk
    )

    can_edit   = _has_perm(request, 'edit_archive')
    can_delete = _has_perm(request, 'delete_archive')
    can_export = _has_perm(request, 'export_data')

    context = {
        'page_title': _('Press Release: %(no)s') % {'no': entry.press_release_no},
        'entry':      entry,
        'coverages':  entry.coverages.select_related('media_house').all(),
        'assets':     entry.assets.all(),
        'can_edit':   can_edit,
        'can_delete': can_delete,
        'can_export': can_export,
    }
    return render(request, 'public_relations/archive_detail.html', context)


# ============================================================================
# Archive Edit
# ============================================================================

@require_access('public_relations', 'edit_archive')
def archive_edit(request, pk):
    archive = get_object_or_404(PublicRelationsArchive, pk=pk)

    if request.method == 'POST':
        archive_form     = PublicRelationsArchiveForm(request.POST, request.FILES, instance=archive)
        coverage_formset = MediaCoverageFormSet(
            request.POST, request.FILES, instance=archive, prefix='coverages'
        )
        asset_formset = MediaAssetFormSet(
            request.POST, request.FILES, instance=archive, prefix='assets'
        )

        all_valid = (
            archive_form.is_valid() and
            coverage_formset.is_valid() and
            asset_formset.is_valid()
        )

        if all_valid:
            try:
                with transaction.atomic():
                    archive_form.save()
                    coverage_formset.save()
                    asset_formset.save()

                log_activity(
                    request, 'UPDATE', 'public_relations',
                    f'Press Release updated: {archive.press_release_no}',
                    object_id=str(archive.pk),
                )
                messages.success(
                    request,
                    _('Press Release "%(no)s" successfully updated.') % {'no': archive.press_release_no}
                )
                return redirect('pr_archive_detail', pk=archive.pk)

            except Exception as exc:
                messages.error(request, _('Error while updating: %(err)s') % {'err': str(exc)})
        else:
            messages.error(request, _('There are errors in the form.'))

    else:
        archive_form     = PublicRelationsArchiveForm(instance=archive)
        coverage_formset = MediaCoverageFormSet(instance=archive, prefix='coverages')
        asset_formset    = MediaAssetFormSet(instance=archive, prefix='assets')

    context = {
        'page_title':       _('Edit: %(no)s') % {'no': archive.press_release_no},
        'archive_form':     archive_form,
        'coverage_formset': coverage_formset,
        'asset_formset':    asset_formset,
        'archive':          archive,
        'is_edit':          True,
    }
    return render(request, 'public_relations/archive_form.html', context)


# ============================================================================
# Archive Delete
# ============================================================================

@require_access('public_relations', 'delete_archive')
def archive_delete(request, pk):
    archive = get_object_or_404(PublicRelationsArchive, pk=pk)

    if request.method == 'POST':
        pr_no = archive.press_release_no
        archive.delete()
        log_activity(
            request, 'DELETE', 'public_relations',
            f'Press Release deleted: {pr_no}',
            object_id=str(pk),
            is_system_alert=True,
        )
        messages.warning(request, _('Press Release "%(no)s" has been deleted.') % {'no': pr_no})
        return redirect('pr_archive_list')

    return redirect('pr_archive_detail', pk=pk)


# ============================================================================
# Media House List
# ============================================================================

@require_access('public_relations', 'view_dashboard')
def media_house_list(request):
    media_type = request.GET.get('media_type', '')
    search     = request.GET.get('search', '').strip()

    houses = MediaHouse.objects.all()

    if media_type:
        houses = houses.filter(media_type=media_type)
    if search:
        houses = houses.filter(
            Q(name__icontains=search)   |
            Q(editor__icontains=search) |
            Q(mobile__icontains=search)
        )

    paginator   = Paginator(houses, 25)
    page_number = request.GET.get('page', 1)
    page_obj    = paginator.get_page(page_number)

    can_manage = _has_perm(request, 'manage_media_houses')

    context = {
        'page_title':          _('Media House Directory'),
        'page_obj':            page_obj,
        'selected_media_type': media_type,
        'search_query':        search,
        'can_manage':          can_manage,
        'national_count':      MediaHouse.objects.filter(media_type='national').count(),
        'local_count':         MediaHouse.objects.filter(media_type='local').count(),
        'online_count':        MediaHouse.objects.filter(media_type='online').count(),
        'tv_count':            MediaHouse.objects.filter(media_type='tv').count(),
    }
    return render(request, 'public_relations/media_house_list.html', context)


# ============================================================================
# Media House Create
# ============================================================================

@require_access('public_relations', 'manage_media_houses')
def media_house_create(request):
    if request.method == 'POST':
        form = MediaHouseForm(request.POST)
        if form.is_valid():
            house = form.save()
            log_activity(
                request, 'CREATE', 'public_relations',
                f'Media house added: {house.name}',
                object_id=str(house.pk),
            )
            messages.success(request, _('"%(name)s" successfully added.') % {'name': house.name})
            return redirect('pr_media_houses')
    else:
        form = MediaHouseForm()

    return render(request, 'public_relations/media_house_form.html', {
        'page_title': _('New Media House'),
        'form':       form,
        'is_edit':    False,
    })


# ============================================================================
# Media House Edit
# ============================================================================

@require_access('public_relations', 'manage_media_houses')
def media_house_edit(request, pk):
    house = get_object_or_404(MediaHouse, pk=pk)

    if request.method == 'POST':
        form = MediaHouseForm(request.POST, instance=house)
        if form.is_valid():
            form.save()
            log_activity(
                request, 'UPDATE', 'public_relations',
                f'Media house updated: {house.name}',
                object_id=str(house.pk),
            )
            messages.success(request, _('"%(name)s" updated.') % {'name': house.name})
            return redirect('pr_media_houses')
    else:
        form = MediaHouseForm(instance=house)

    return render(request, 'public_relations/media_house_form.html', {
        'page_title': _('Edit: %(name)s') % {'name': house.name},
        'form':       form,
        'house':      house,
        'is_edit':    True,
    })


# ============================================================================
# Media House Delete
# ============================================================================

@require_access('public_relations', 'manage_media_houses')
def media_house_delete(request, pk):
    house = get_object_or_404(MediaHouse, pk=pk)

    if request.method == 'POST':
        coverage_count = house.coverages.count()
        if coverage_count > 0:
            messages.error(
                request,
                _('"%(name)s" cannot be deleted because it has %(count)s linked coverage record(s). '
                  'Remove those coverage rows first.') % {
                      'name': house.name,
                      'count': coverage_count,
                  }
            )
        else:
            name = house.name
            house.delete()
            log_activity(
                request, 'DELETE', 'public_relations',
                f'Media house deleted: {name}',
                object_id=str(pk),
            )
            messages.success(request, _('"%(name)s" has been deleted.') % {'name': name})
        return redirect('pr_media_houses')

    # GET — not used (delete is done via inline modal POST), but guard it
    return redirect('pr_media_houses')




# ============================================================================
# Excel Export
# ============================================================================

@require_access('public_relations', 'export_data')
def export_excel(request):
    queryset = PublicRelationsArchive.objects.order_by('-press_release_date', '-created_at')

    keyword    = request.GET.get('keyword', '').strip()
    start_date = request.GET.get('start_date', '')
    end_date   = request.GET.get('end_date', '')
    media_type = request.GET.get('media_type', '')
    department = request.GET.get('department', '').strip()

    if keyword:
        queryset = queryset.filter(
            Q(press_release_no__icontains=keyword) |
            Q(event_name__icontains=keyword)       |
            Q(full_text__icontains=keyword)        |
            Q(department__icontains=keyword)
        ).distinct()
    if start_date:
        queryset = queryset.filter(press_release_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(press_release_date__lte=end_date)
    if media_type:
        queryset = queryset.filter(
            coverages__media_house__media_type=media_type
        ).distinct()
    if department:
        queryset = queryset.filter(department__icontains=department)

    return export_archive_to_excel(queryset)


# ============================================================================
# PDF Export (single entry)
# ============================================================================

@require_access('public_relations', 'export_data')
def export_pdf(request, pk):
    return render_archive_pdf(request, pk)


# ============================================================================
# Private helpers
# ============================================================================

def _has_perm(request, task):
    if request.user.is_superuser:
        return True
    return (
        hasattr(request.user, 'profile') and
        request.user.profile.has_access('public_relations', task)
    )


def _get_params_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


# ============================================================================
# Press Release Showcase / Portal View
# ============================================================================

@require_access('public_relations', 'view_archive')
def pr_portal(request):
    search_query = request.GET.get('q', '').strip()
    queryset = (
        PublicRelationsArchive.objects
        .select_related('created_by')
        .prefetch_related('coverages__media_house', 'assets')
        .order_by('-press_release_date', '-created_at')
    )

    if search_query:
        queryset = queryset.filter(
            Q(press_release_no__icontains=search_query) |
            Q(event_name__icontains=search_query)       |
            Q(full_text__icontains=search_query)        |
            Q(department__icontains=search_query)
        ).distinct()

    paginator = Paginator(queryset, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': _('PR Showcase'),
        'page_obj': page_obj,
        'search_query': search_query,
    }
    return render(request, 'public_relations/portal.html', context)


# ============================================================================
# API Endpoint: Next PR Number
# ============================================================================

@require_access('public_relations', 'view_archive')
def get_next_pr_number(request):
    from django.http import JsonResponse
    import datetime
    
    date_str = request.GET.get('date', '').strip()
    if not date_str:
        return JsonResponse({'error': 'Date parameter is required'}, status=400)
        
    try:
        date_val = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        
    next_no = PublicRelationsArchive.get_next_pr_number(date_val)
    return JsonResponse({'pr_number': next_no})


# ============================================================================
# API Endpoint: Check PR Number Duplicate
# ============================================================================

@require_access('public_relations', 'view_archive')
def check_pr_duplicate(request):
    from django.http import JsonResponse
    pr_number = request.GET.get('pr_number', '').strip()
    exclude_id = request.GET.get('exclude_id', '').strip()
    
    if not pr_number:
        return JsonResponse({'exists': False})
        
    queryset = PublicRelationsArchive.objects.filter(press_release_no__iexact=pr_number)
    if exclude_id and exclude_id.isdigit():
        queryset = queryset.exclude(pk=int(exclude_id))
        
    exists = queryset.exists()
    return JsonResponse({'exists': exists})

