from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .access_registry import ACCESS_REGISTRY
from .decorators import require_access
from .forms import (
    RoleForm,
    StaffUserCreateForm,
    UserAccessForm,
    UserSelfProfileForm,
    get_department_scope_choices,
    get_department_scope_label,
)
from .models import Role, RolePermission, SystemSettings, UserProfile
from django.http import JsonResponse
import json

@login_required
def toggle_theme(request):
    """AJAX view to persist theme mode preference."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            mode = data.get('mode')
            if mode in ['light', 'dark']:
                profile = request.user.profile
                profile.theme_mode = mode
                profile.save(update_fields=['theme_mode'])
                return JsonResponse({'status': 'success'})
        except Exception:
            pass
    return JsonResponse({'status': 'error'}, status=400)


def _ensure_missing_user_profiles():
    missing_users = list(User.objects.filter(profile__isnull=True))
    if missing_users:
        UserProfile.objects.bulk_create(
            [UserProfile(user=user) for user in missing_users],
            ignore_conflicts=True,
        )


def _add_form_errors(request, form, prefix):
    error_messages = []
    for field_name, field_errors in form.errors.items():
        label = form.fields[field_name].label if field_name in form.fields else 'Error'
        for error in field_errors:
            error_messages.append(f'{label}: {error}')

    if not error_messages:
        messages.error(request, prefix)
        return

    for error_message in error_messages[:3]:
        messages.error(request, f'{prefix} {error_message}')


def _build_access_summary(user):
    if user.is_superuser:
        allowed_permissions = {
            (module_key, task_key)
            for module_key, module in ACCESS_REGISTRY.items()
            for task_key in module['tasks']
        }
    else:
        profile = getattr(user, 'profile', None)
        if not profile or not profile.role:
            return []
        allowed_permissions = {
            (permission.module, permission.task)
            for permission in profile.role.permissions.all()
        }

    sections = []
    for module_key, module in ACCESS_REGISTRY.items():
        visible_tasks = []
        for task_key, task_info in module['tasks'].items():
            if (module_key, task_key) in allowed_permissions:
                visible_tasks.append({
                    'label': task_info[0],
                    'description': task_info[1],
                })

        if visible_tasks:
            sections.append({
                'display': module['display'],
                'icon': module['icon'],
                'tasks': visible_tasks,
            })

    return sections


@require_access('security', 'manage_roles')
def role_management(request):
    """Enhanced view to manage roles, descriptions, and granular task permissions with usage stats."""
    role_form = RoleForm()

    if request.method == "POST":
        action = request.POST.get('action', 'update_permissions')

        if action == 'create_role':
            role_form = RoleForm(request.POST)
            if role_form.is_valid():
                role = role_form.save()
                messages.success(request, f'Role "{role.name}" created successfully.')
                from .utils import log_activity
                log_activity(request, 'CREATE', 'security', f'Created security role: {role.name}', object_id=str(role.id))
                return redirect('role_management')
            _add_form_errors(request, role_form, 'Could not create the role.')
            
        elif action == 'edit_role':
            role_id = request.POST.get('role_id')
            role = get_object_or_404(Role, id=role_id)
            form = RoleForm(request.POST, instance=role)
            if form.is_valid():
                form.save()
                messages.success(request, f'Role "{role.name}" updated successfully.')
                from .utils import log_activity
                log_activity(request, 'UPDATE', 'security', f'Updated identity for role: {role.name}', object_id=str(role.id))
            else:
                _add_form_errors(request, form, 'Could not update the role.')
            return redirect('role_management')

        elif action == 'delete_role':
            role_id = request.POST.get('role_id')
            role = get_object_or_404(Role, id=role_id)
            usage = UserProfile.objects.filter(role=role).count()
            if usage > 0:
                messages.error(request, f'Cannot delete role "{role.name}" because it is currently assigned to {usage} staff members.')
            else:
                role_name = role.name
                role.delete()
                messages.success(request, f'Role "{role_name}" has been removed.')
                from .utils import log_activity
                log_activity(request, 'DELETE', 'security', f'Permanently deleted role: {role_name}', object_id=role_id)
            return redirect('role_management')

        else:
            role_id = request.POST.get('role_id')
            role = get_object_or_404(Role, id=role_id)
            valid_permission_keys = {
                f'{module_key}:{task_key}'
                for module_key, module in ACCESS_REGISTRY.items()
                for task_key in module['tasks']
            }

            selected_permissions = []
            for key in request.POST:
                if key in valid_permission_keys:
                    module, task = key.split(':', 1)
                    selected_permissions.append(RolePermission(role=role, module=module, task=task))

            role.permissions.all().delete()
            RolePermission.objects.bulk_create(selected_permissions)
            messages.success(request, f'Permissions updated for role: {role.name}')
            from .utils import log_activity
            log_activity(request, 'PERMISSION', 'security', f'Reconfigured permission matrix for role: {role.name}', object_id=str(role.id))
            return redirect('role_management')

    roles = Role.objects.all().prefetch_related('permissions').order_by('name')
    from django.db.models import Count
    roles = roles.annotate(user_count=Count('userprofile'))
    
    for role in roles:
        role.permission_total = role.permissions.count()

    task_count = sum(len(module['tasks']) for module in ACCESS_REGISTRY.values())
    return render(request, 'core/role_management.html', {
        'roles': roles,
        'registry': ACCESS_REGISTRY,
        'role_form': role_form,
        'role_count': roles.count(),
        'module_count': len(ACCESS_REGISTRY),
        'task_count': task_count,
    })


@require_access('security', 'manage_users')
def user_management(request):
    """Professional staff directory with search, filtering, and access controls."""
    _ensure_missing_user_profiles()

    if request.method == "POST":
        action = request.POST.get('action')
        if action == 'update_user':
            user = get_object_or_404(User, id=request.POST.get('user_id'))
            if user.is_superuser and not request.user.is_superuser:
                messages.error(request, 'Only a superuser can modify another superuser account.')
                return redirect('user_management')

            form = UserAccessForm(request.POST, user=user)
            if form.is_valid():
                form.save()
                messages.success(request, f'Account details updated for {user.username}.')
            else:
                _add_form_errors(request, form, f'Could not update {user.username}.')

            return redirect('user_management')

    roles = Role.objects.all().order_by('name')
    scope_choices = get_department_scope_choices(include_blank=False)

    query = request.GET.get('q', '').strip()
    selected_role = request.GET.get('role', '').strip()
    selected_status = request.GET.get('status', '').strip()
    selected_scope = request.GET.get('scope', '').strip()

    users = User.objects.all().select_related('profile', 'profile__role').order_by('username')

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    if selected_role:
        users = users.filter(profile__role_id=selected_role)

    if selected_status == 'active':
        users = users.filter(is_active=True)
    elif selected_status == 'inactive':
        users = users.filter(is_active=False)
    elif selected_status == 'unassigned':
        users = users.filter(profile__role__isnull=True)
    elif selected_status == 'scoped':
        users = users.exclude(profile__department_scope__isnull=True).exclude(profile__department_scope='')

    if selected_scope:
        users = users.filter(profile__department_scope=selected_scope)

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    scoped_users = User.objects.exclude(profile__department_scope__isnull=True).exclude(profile__department_scope='').count()
    unassigned_users = User.objects.filter(profile__role__isnull=True).count()
    filtered_count = users.count()

    users = list(users)
    for managed_user in users:
        profile = getattr(managed_user, 'profile', None)
        managed_user.scope_label = get_department_scope_label(
            getattr(profile, 'department_scope', ''),
        )
        managed_user.display_name = managed_user.get_full_name() or managed_user.username

    return render(request, 'core/user_management.html', {
        'users': users,
        'roles': roles,
        'scope_choices': scope_choices,
        'query': query,
        'selected_role': selected_role,
        'selected_status': selected_status,
        'selected_scope': selected_scope,
        'total_users': total_users,
        'active_users': active_users,
        'scoped_users': scoped_users,
        'unassigned_users': unassigned_users,
        'filtered_count': filtered_count,
    })


@require_access('security', 'manage_users')
def user_create(request):
    """Creates a new staff account with validated role and scope assignment."""
    if request.method != "POST":
        return redirect('user_management')

    form = StaffUserCreateForm(request.POST)
    if form.is_valid():
        user = form.save()
        messages.success(request, f'User {user.username} successfully onboarded to the suite.')
        from .utils import log_activity
        log_activity(request, 'CREATE', 'security', f'Onboarded new staff member: {user.username}', object_id=str(user.id))
    else:
        _add_form_errors(request, form, 'Could not create the account.')

    return redirect('user_management')


@require_access('security', 'manage_users')
def user_toggle_status(request, user_id):
    """Activates or deactivates a staff member account."""
    if request.method != "POST":
        messages.error(request, 'Status changes must be submitted from the management page.')
        return redirect('user_management')

    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account from the staff directory.')
    elif user.is_superuser:
        messages.error(request, 'Superuser accounts cannot be deactivated here.')
    else:
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        status = "activated" if user.is_active else "deactivated"
        messages.success(request, f'User {user.username} has been {status}.')

    return redirect('user_management')


@require_access('security', 'manage_users')
def user_reset_password(request, user_id):
    """Sets a validated temporary password for a staff member."""
    if request.method != "POST":
        messages.error(request, 'Password resets must be submitted from the management page.')
        return redirect('user_management')

    user = get_object_or_404(User, id=user_id)
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'Only a superuser can reset another superuser password.')
        return redirect('user_management')

    form = SetPasswordForm(user, request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, f'Password for {user.username} has been reset.')
    else:
        _add_form_errors(request, form, f'Could not reset the password for {user.username}.')

    return redirect('user_management')


@login_required
def user_profile(request):
    """Self-service profile page for every authenticated user."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        profile_form = UserSelfProfileForm(request.POST, user=request.user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('user_profile')
        _add_form_errors(request, profile_form, 'Could not update your profile.')
    else:
        profile_form = UserSelfProfileForm(user=request.user)

    return render(request, 'core/profile.html', {
        'profile_form': profile_form,
        'scope_label': get_department_scope_label(profile.department_scope),
        'access_summary': _build_access_summary(request.user),
    })


@require_access('security', 'manage_roles') # Use same permission as roles for now
def audit_logs(request):
    """View to browse and filter system-wide activity logs."""
    from .models import ActivityLog
    
    query = request.GET.get('q', '').strip()
    action_filter = request.GET.get('action', '')
    module_filter = request.GET.get('module', '')
    user_filter = request.GET.get('user', '')
    
    logs = ActivityLog.objects.select_related('user').all()
    
    if query:
        logs = logs.filter(description__icontains=query)
    if action_filter:
        logs = logs.filter(action_type=action_filter)
    if module_filter:
        logs = logs.filter(module=module_filter)
    if user_filter:
        logs = logs.filter(user_id=user_filter)
        
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Context data for filters
    users = User.objects.filter(is_staff=True).order_by('username')
    modules = ActivityLog.objects.values_list('module', flat=True).distinct()
    actions = ActivityLog.ACTION_CHOICES
    
    return render(request, 'core/audit_logs.html', {
        'page_obj': page_obj,
        'users': users,
        'modules': modules,
        'actions': actions,
        'query': query,
        'action_filter': action_filter,
        'module_filter': module_filter,
        'user_filter': user_filter,
    })

@require_access('security', 'manage_settings')
def system_settings(request):
    """View to manage institutional branding and system-wide settings."""
    settings, _ = SystemSettings.objects.get_or_create(id=1)
    if request.method == "POST":
        settings.institution_name = request.POST.get('institution_name')
        settings.institution_logo_url = request.POST.get('institution_logo_url')
        settings.theme_color = request.POST.get('theme_color')
        
        # SMS Settings
        settings.sms_api_key = request.POST.get('sms_api_key')
        settings.sms_sender_id = request.POST.get('sms_sender_id')
        settings.sms_api_url = request.POST.get('sms_api_url')
        settings.sms_is_active = request.POST.get('sms_is_active') == 'on'

        if request.FILES.get('institution_logo'):
            settings.institution_logo = request.FILES.get('institution_logo')
        if request.FILES.get('institution_favicon'):
            settings.institution_favicon = request.FILES.get('institution_favicon')

        settings.save()
        
        from .utils import log_activity
        log_activity(request, 'SECURITY', 'security', 'Updated institutional branding and SMS configuration')
        
        messages.success(request, "Institutional branding and SMS configuration updated.")
        return redirect('system_settings')
    return render(request, 'core/system_settings.html', {'settings': settings})
