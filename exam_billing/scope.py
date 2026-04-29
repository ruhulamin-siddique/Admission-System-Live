from django.core.exceptions import PermissionDenied
from django.db.models import Q

from master_data.models import Program


def user_can_view_all_departments(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.has_access('exam_billing', 'view_all_departments'))


def get_allowed_programs(user):
    queryset = Program.objects.all().order_by('-sort_order', 'name')
    if user_can_view_all_departments(user):
        return queryset

    profile = getattr(user, 'profile', None)
    scope = (getattr(profile, 'department_scope', '') or '').strip()
    if not scope:
        return Program.objects.none()

    return queryset.filter(Q(short_name__iexact=scope) | Q(name__iexact=scope))


def filter_by_user_scope(queryset, user, program_field='program'):
    if user_can_view_all_departments(user):
        return queryset
    allowed_ids = list(get_allowed_programs(user).values_list('id', flat=True))
    return queryset.filter(**{f'{program_field}__in': allowed_ids})


def require_program_access(user, program):
    if user_can_view_all_departments(user):
        return
    if not get_allowed_programs(user).filter(pk=program.pk).exists():
        raise PermissionDenied('You do not have access to this department/program.')


def require_exam_program_access(user, exam_program):
    require_program_access(user, exam_program.program)

