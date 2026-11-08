"""
counseling/views.py
===================
Views for Counselor Command Center, Case Dossiers, SOAP Notes, Psychometric Tests,
Emergency Protocol, Public Self-Booking Portal, and De-Identified Analytics.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext as _
from django.utils import timezone
import datetime
import json

from core.decorators import require_access
from core.utils import log_activity, send_sms
from students.models import Student
from master_data.models import Program, Hall

from .models import (
    CounselingCase,
    CounselingAppointment,
    SessionRecord,
    MentalHealthAssessment,
    EmergencyIntervention,
    WellbeingWorkshop,
    WellbeingWorkshopParticipant,
    CounselingSettings,
    CounselorProfile,
    CaseStatusLog,
    CaseCategory,
    RiskLevel,
    CaseStatus,
    AppointmentMode,
    AppointmentStatus,
    ReferralSource,
    AssessmentType,
)
from .forms import (
    CounselingCaseIntakeForm,
    CounselingAppointmentForm,
    SessionRecordForm,
    EmergencyInterventionForm,
    WellbeingWorkshopForm,
    CounselingSettingsForm,
    CounselorProfileForm,
    PublicStudentBookingForm,
)
from .utils import (
    PHQ9_QUESTIONS,
    PHQ9_OPTIONS,
    GAD7_QUESTIONS,
    GAD7_OPTIONS,
    DASS21_QUESTIONS,
    DASS21_OPTIONS,
    CLINICAL_SNIPPETS,
    calculate_phq9_score,
    calculate_gad7_score,
    calculate_dass21_score,
    send_counseling_notification_sms,
)


# ============================================================================
# 1. Public Student Self-Booking Portal (No Staff Login Required)
# ============================================================================

def public_book_appointment(request):
    """
    Public student booking page (/counseling/book/).
    Allows students to submit a confidential appointment request with their Student ID.
    """
    from django.contrib.auth.models import User
    settings = CounselingSettings.get_settings()
    active_counselors = CounselorProfile.objects.filter(is_active_counselor=True)

    if not active_counselors.exists():
        # Auto-provision or retrieve default counselor profile
        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()
        if admin_user:
            profile, created = CounselorProfile.objects.get_or_create(
                user=admin_user,
                defaults={
                    'designation': 'Clinical Psychologist & Student Counselor',
                    'room_number': settings.counselor_room_default or 'Room 204',
                    'is_active_counselor': True,
                }
            )
            if not profile.is_active_counselor:
                profile.is_active_counselor = True
                profile.save(update_fields=['is_active_counselor'])
            active_counselors = CounselorProfile.objects.filter(is_active_counselor=True)

    if not active_counselors.exists():
        return render(request, 'counseling/public_booking_closed.html', {
            'settings': settings,
        })

    if request.method == 'POST':
        form = PublicStudentBookingForm(request.POST)
        if form.is_valid():
            student = form.cleaned_data['student_obj']
            category = form.cleaned_data['category']
            urgency = form.cleaned_data['urgency']
            session_mode = form.cleaned_data['session_mode']
            appt_date = form.cleaned_data['appointment_date']
            time_slot = form.cleaned_data['time_slot']
            brief_notes = form.cleaned_data.get('brief_notes', '')

            # Risk mapping
            risk = RiskLevel.LOW
            if urgency == 'priority':
                risk = RiskLevel.MODERATE
            elif urgency == 'crisis':
                risk = RiskLevel.CRITICAL

            # Find or create active CounselingCase for this student
            case = CounselingCase.objects.filter(student=student, status__in=[CaseStatus.OPEN, CaseStatus.IN_THERAPY]).first()
            if not case:
                counselor = active_counselors.first()
                case = CounselingCase.objects.create(
                    student=student,
                    category=category,
                    risk_level=risk,
                    status=CaseStatus.OPEN,
                    assigned_counselor=counselor,
                    intake_date=appt_date,
                    presenting_complaints=brief_notes or _("Submitted via Public Booking Portal.")
                )
                CaseStatusLog.objects.create(
                    case=case,
                    old_status="",
                    new_status=CaseStatus.OPEN,
                    note=_("Case opened via student self-booking portal.")
                )

            # Assign counselor
            counselor = case.assigned_counselor or active_counselors.first()

            # Create or update appointment
            contact_mobile = form.cleaned_data.get('cleaned_mobile', '')
            try:
                with transaction.atomic():
                    appt = CounselingAppointment.objects.create(
                        case=case,
                        counselor=counselor,
                        appointment_date=appt_date,
                        time_slot=time_slot,
                        session_mode=session_mode,
                        referral_source=ReferralSource.SELF,
                        status=AppointmentStatus.CONFIRMED if urgency != 'crisis' else AppointmentStatus.REQUESTED,
                        student_notes=brief_notes,
                        contact_mobile=contact_mobile
                    )
            except Exception:
                form.add_error('time_slot', _("দুঃখিত, এই সময়সূচিটি ইতিমধ্যেই অন্য কারো জন্য নির্ধারিত হয়েছে। অনুগ্রহ করে অন্য সময় বেছে নিন। (Slot already booked)."))
                return render(request, 'counseling/public_book.html', {
                    'form': form,
                    'settings': settings,
                    'active_counselors': active_counselors,
                })

            # Dispatch discreet confirmation SMS
            sms_sent = False
            try:
                sms_success, sms_err = send_counseling_notification_sms(
                    student=student,
                    message_type="appointment_confirm",
                    context={
                        'date': appt_date.strftime('%d-%b-%Y'),
                        'time': time_slot,
                        'room': counselor.room_number if counselor else settings.counselor_room_default,
                        'case_number': case.case_number,
                        'secret_token': appt.secret_token,
                    }
                )
                sms_sent = bool(sms_success)
            except Exception:
                sms_sent = False

            # Store in session for success screen
            request.session['counseling_public_token'] = {
                'case_number': case.case_number,
                'secret_token': appt.secret_token,
                'student_name': student.student_name,
                'date': appt_date.strftime('%A, %d %B %Y'),
                'time': time_slot,
                'room': counselor.room_number if counselor else settings.counselor_room_default,
                'urgency': urgency,
                'sms_sent': sms_sent,
                'contact_mobile': contact_mobile,
            }
            return redirect('counseling_public_success')
    else:
        # Pre-fill date with tomorrow if weekday
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        if tomorrow.weekday() == 4: # Friday
            tomorrow += datetime.timedelta(days=2) # Sunday in BD
        form = PublicStudentBookingForm(initial={'appointment_date': tomorrow})

    return render(request, 'counseling/public_book.html', {
        'form': form,
        'settings': settings,
        'active_counselors': active_counselors,
    })


def public_book_success(request):
    """Public confirmation receipt after successful booking."""
    token_data = request.session.get('counseling_public_token', None)
    if not token_data:
        return redirect('counseling_public_book')
    return render(request, 'counseling/public_success.html', {'token': token_data})


def api_verify_student_id(request):
    """
    Real-time HTMX endpoint to verify Student ID.
    Returns safe, non-sensitive verification status badge (Program & Batch).
    """
    sid = request.GET.get('student_id', '').strip()
    if not sid:
        return HttpResponse("")
    
    student = Student.objects.filter(student_id=sid).first() or Student.objects.filter(old_student_id=sid).first()
    if student:
        prog = student.program or _("Undergraduate Program")
        batch = f"Batch {student.batch}" if student.batch else ""
        return render(request, 'counseling/partials/student_verify_success.html', {
            'student': student,
            'prog': prog,
            'batch': batch,
        })
    else:
        return render(request, 'counseling/partials/student_verify_error.html', {
            'sid': sid,
        })


def api_check_appointment_status(request):
    """
    HTMX endpoint for anonymous appointment status lookup by Secret Token or Student ID.
    """
    query = (request.POST.get('lookup_query') or request.GET.get('lookup_query') or '').strip()
    if not query:
        return render(request, 'counseling/partials/status_lookup_result.html', {
            'searched': False,
        })
    
    # 1. Lookup by Secret Token
    appt = CounselingAppointment.objects.filter(secret_token__iexact=query).select_related('case__student', 'counselor').first()
    
    # 2. If not found, lookup by Student ID (retrieve latest active/requested appointment)
    if not appt:
        student = Student.objects.filter(student_id=query).first() or Student.objects.filter(old_student_id=query).first()
        if student:
            appt = CounselingAppointment.objects.filter(case__student=student).select_related('case__student', 'counselor').order_by('-appointment_date', '-id').first()
    
    settings = CounselingSettings.get_settings()
    return render(request, 'counseling/partials/status_lookup_result.html', {
        'searched': True,
        'appointment': appt,
        'query': query,
        'settings': settings,
    })


@require_POST
def api_cancel_public_appointment(request):
    """
    Allows a student to cancel their upcoming appointment using their secret tracking token.
    """
    token = request.POST.get('secret_token', '').strip()
    appt = CounselingAppointment.objects.filter(secret_token=token).first()
    if appt and appt.status in [AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED]:
        appt.status = AppointmentStatus.CANCELLED
        appt.save(update_fields=['status'])
        settings = CounselingSettings.get_settings()
        return render(request, 'counseling/partials/status_lookup_result.html', {
            'searched': True,
            'appointment': appt,
            'query': token,
            'settings': settings,
            'cancel_success': True,
        })
    return HttpResponseBadRequest(_("Invalid request or appointment cannot be cancelled."))


# ============================================================================
# 2. Psychologist Command Center & Dashboard
# ============================================================================

@require_access('counseling', 'view_dashboard')
def dashboard(request):
    """
    Main Clinical Command Center for University Psychologist.
    """
    today = timezone.localdate()

    # KPI Statistics
    total_cases = CounselingCase.objects.count()
    active_cases = CounselingCase.objects.filter(status__in=[CaseStatus.OPEN, CaseStatus.IN_THERAPY]).count()
    critical_cases = CounselingCase.objects.filter(risk_level=RiskLevel.CRITICAL, status__in=[CaseStatus.OPEN, CaseStatus.IN_THERAPY]).count()
    high_risk_cases = CounselingCase.objects.filter(risk_level=RiskLevel.HIGH, status__in=[CaseStatus.OPEN, CaseStatus.IN_THERAPY]).count()
    
    today_appointments = (
        CounselingAppointment.objects
        .filter(appointment_date=today)
        .select_related('case__student', 'counselor')
        .order_by('time_slot')
    )

    upcoming_appointments = (
        CounselingAppointment.objects
        .filter(appointment_date__gt=today, status__in=[AppointmentStatus.CONFIRMED, AppointmentStatus.REQUESTED])
        .select_related('case__student', 'counselor')
        .order_by('appointment_date', 'time_slot')[:8]
    )

    urgent_cases = (
        CounselingCase.objects
        .filter(risk_level__in=[RiskLevel.HIGH, RiskLevel.CRITICAL], status__in=[CaseStatus.OPEN, CaseStatus.IN_THERAPY])
        .select_related('student', 'assigned_counselor')
        .order_by('-risk_level', '-intake_date')[:6]
    )

    recent_sessions = (
        SessionRecord.objects
        .select_related('case__student', 'recorded_by')
        .order_by('-session_date', '-created_at')[:5]
    )

    # Category Breakdown for Charts
    category_counts = (
        CounselingCase.objects
        .values('category')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    category_labels = [str(dict(CaseCategory.choices).get(c['category'], c['category'])) for c in category_counts]
    category_data = [c['total'] for c in category_counts]

    context = {
        'kpi': {
            'total_cases': total_cases,
            'active_cases': active_cases,
            'critical_cases': critical_cases,
            'high_risk_cases': high_risk_cases,
            'today_appts_count': today_appointments.count(),
        },
        'today_appointments': today_appointments,
        'upcoming_appointments': upcoming_appointments,
        'urgent_cases': urgent_cases,
        'recent_sessions': recent_sessions,
        'category_labels_json': json.dumps(category_labels, cls=DjangoJSONEncoder),
        'category_data_json': json.dumps(category_data, cls=DjangoJSONEncoder),
        'today': today,
    }
    return render(request, 'counseling/dashboard.html', context)


# ============================================================================
# 3. Case Directory & Intake Management
# ============================================================================

@require_access('counseling', 'manage_cases')
def case_list(request):
    """Filterable directory of counseling cases."""
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    risk_filter = request.GET.get('risk', '').strip()
    category_filter = request.GET.get('category', '').strip()
    dept_filter = request.GET.get('department', '').strip()

    cases = CounselingCase.objects.select_related('student', 'assigned_counselor').all()

    if query:
        cases = cases.filter(
            Q(case_number__icontains=query) |
            Q(alias_code__icontains=query) |
            Q(student__student_id__icontains=query) |
            Q(student__student_name__icontains=query) |
            Q(student__student_mobile__icontains=query)
        )

    if status_filter:
        cases = cases.filter(status=status_filter)
    if risk_filter:
        cases = cases.filter(risk_level=risk_filter)
    if category_filter:
        cases = cases.filter(category=category_filter)
    if dept_filter:
        cases = cases.filter(student__program__icontains=dept_filter)

    paginator = Paginator(cases, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    programs = Program.objects.all()

    return render(request, 'counseling/case_list.html', {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'risk_filter': risk_filter,
        'category_filter': category_filter,
        'dept_filter': dept_filter,
        'programs': programs,
        'categories': CaseCategory.choices,
        'risk_levels': RiskLevel.choices,
        'statuses': CaseStatus.choices,
    })


@require_access('counseling', 'manage_cases')
def case_create(request):
    """Clinical intake form to open a new case."""
    if request.method == 'POST':
        form = CounselingCaseIntakeForm(request.POST)
        if form.is_valid():
            case = form.save(commit=False)
            case.student = form.cleaned_student
            case.created_by = request.user
            case.save()

            CaseStatusLog.objects.create(
                case=case,
                old_status="",
                new_status=case.status,
                changed_by=request.user,
                note=_("Initial intake record created.")
            )

            log_activity(request, 'CREATE', 'counseling', f"Opened case {case.case_number} for {case.student.student_id}")
            messages.success(request, _(f"Case {case.case_number} successfully registered for {case.student.student_name}."))
            return redirect('counseling_case_detail', pk=case.pk)
    else:
        # Pre-fill student if passed via GET parameter (e.g. ?student_id=...)
        initial_data = {}
        sid = request.GET.get('student_id')
        if sid:
            initial_data['student_id_input'] = sid
        form = CounselingCaseIntakeForm(initial=initial_data)

    return render(request, 'counseling/case_form.html', {
        'form': form,
        'is_edit': False,
    })


@require_access('counseling', 'manage_cases')
def case_detail(request, pk):
    """
    Comprehensive student clinical dossier with full academic context,
    longitudinal symptom graph, session records, and assessments.
    """
    case = get_object_or_404(CounselingCase.all_objects.select_related('student', 'assigned_counselor__user'), pk=pk)

    sessions = case.session_records.select_related('recorded_by').order_by('-session_date', '-session_number')
    appointments = case.appointments.select_related('counselor').order_by('-appointment_date')
    assessments = case.assessments.order_by('assessed_date')
    emergencies = case.emergency_interventions.order_by('-incident_date')
    status_logs = case.status_logs.select_related('changed_by').order_by('-changed_at')

    # Prepare aligned longitudinal chart data for PHQ-9 & GAD-7
    date_map = {}
    for a in assessments:
        if a.assessment_type in [AssessmentType.PHQ9, AssessmentType.GAD7]:
            d_key = a.assessed_date
            if d_key not in date_map:
                date_map[d_key] = {'phq9': None, 'gad7': None, 'label': a.assessed_date.strftime('%d %b')}
            if a.assessment_type == AssessmentType.PHQ9:
                date_map[d_key]['phq9'] = a.total_score
            elif a.assessment_type == AssessmentType.GAD7:
                date_map[d_key]['gad7'] = a.total_score

    sorted_dates = sorted(date_map.keys())
    chart_dates = [date_map[d]['label'] for d in sorted_dates]
    phq9_scores = [date_map[d]['phq9'] for d in sorted_dates]
    gad7_scores = [date_map[d]['gad7'] for d in sorted_dates]

    return render(request, 'counseling/case_detail.html', {
        'case': case,
        'student': case.student,
        'sessions': sessions,
        'appointments': appointments,
        'assessments': assessments,
        'emergencies': emergencies,
        'status_logs': status_logs,
        'chart_dates_json': json.dumps(chart_dates, cls=DjangoJSONEncoder),
        'phq9_scores_json': json.dumps(phq9_scores, cls=DjangoJSONEncoder),
        'gad7_scores_json': json.dumps(gad7_scores, cls=DjangoJSONEncoder),
    })


@require_access('counseling', 'manage_cases')
def case_edit(request, pk):
    """Edit case details."""
    case = get_object_or_404(CounselingCase, pk=pk)
    if request.method == 'POST':
        form = CounselingCaseIntakeForm(request.POST, instance=case)
        if form.is_valid():
            old_status = case.status
            new_case = form.save(commit=False)
            new_case.student = form.cleaned_student
            new_case.save()

            if old_status != new_case.status:
                CaseStatusLog.objects.create(
                    case=new_case,
                    old_status=old_status,
                    new_status=new_case.status,
                    changed_by=request.user,
                    note=_("Status modified in case editor.")
                )

            log_activity(request, 'UPDATE', 'counseling', f"Updated case {case.case_number}")
            messages.success(request, _(f"Case {case.case_number} updated successfully."))
            return redirect('counseling_case_detail', pk=case.pk)
    else:
        form = CounselingCaseIntakeForm(instance=case, initial={'student_id_input': case.student.student_id})

    return render(request, 'counseling/case_form.html', {
        'form': form,
        'case': case,
        'is_edit': True,
    })


@require_access('counseling', 'manage_cases')
def case_delete(request, pk):
    """Soft delete a case."""
    case = get_object_or_404(CounselingCase, pk=pk)
    if request.method == 'POST':
        case.is_deleted = True
        case.save()
        log_activity(request, 'DELETE', 'counseling', f"Soft-deleted case {case.case_number}")
        messages.warning(request, _(f"Case {case.case_number} has been soft-deleted."))
        return redirect('counseling_case_list')
    return render(request, 'counseling/case_confirm_delete.html', {'case': case})


# ============================================================================
# 4. Appointment Scheduling
# ============================================================================

@require_access('counseling', 'manage_appointments')
def appointment_list(request):
    """Schedule management and calendar view."""
    date_query = request.GET.get('date', timezone.localdate().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.datetime.strptime(date_query, '%Y-%m-%d').date()
    except ValueError:
        selected_date = timezone.localdate()

    appointments = (
        CounselingAppointment.objects
        .filter(appointment_date=selected_date)
        .select_related('case__student', 'counselor')
        .order_by('time_slot')
    )

    all_upcoming = (
        CounselingAppointment.objects
        .filter(appointment_date__gte=timezone.localdate())
        .select_related('case__student', 'counselor')
        .order_by('appointment_date', 'time_slot')[:20]
    )

    return render(request, 'counseling/appointment_list.html', {
        'appointments': appointments,
        'all_upcoming': all_upcoming,
        'selected_date': selected_date,
    })


@require_access('counseling', 'manage_appointments')
def appointment_create(request):
    """Book a new appointment."""
    case_id = request.GET.get('case_id')
    initial = {}
    if case_id:
        case = get_object_or_404(CounselingCase, pk=case_id)
        initial['case'] = case
        if case.assigned_counselor:
            initial['counselor'] = case.assigned_counselor

    if request.method == 'POST':
        form = CounselingAppointmentForm(request.POST)
        if form.is_valid():
            try:
                appt = form.save()
                log_activity(request, 'CREATE', 'counseling', f"Booked appointment for case {appt.case.case_number} on {appt.appointment_date}")
                
                # Send SMS
                send_counseling_notification_sms(
                    student=appt.case.student,
                    message_type="appointment_confirm",
                    context={
                        'date': appt.appointment_date.strftime('%d-%b-%Y'),
                        'time': appt.time_slot,
                        'room': appt.counselor.room_number if appt.counselor else 'Room 204'
                    }
                )
                messages.success(request, _(f"Appointment booked for {appt.appointment_date} ({appt.time_slot}). Confirmation SMS queued."))
                return redirect('counseling_case_detail', pk=appt.case.pk)
            except Exception as e:
                messages.error(request, _(f"Error booking slot: This counselor already has a booking at {form.cleaned_data.get('time_slot')} on {form.cleaned_data.get('appointment_date')}."))
    else:
        form = CounselingAppointmentForm(initial=initial)

    return render(request, 'counseling/appointment_form.html', {'form': form})


@require_access('counseling', 'manage_appointments')
def appointment_status_update(request, pk, new_status):
    """Quick update appointment status (Completed, Cancelled, No-Show)."""
    appt = get_object_or_404(CounselingAppointment, pk=pk)
    if new_status in dict(AppointmentStatus.choices):
        appt.status = new_status
        appt.save()
        messages.success(request, _(f"Appointment marked as {appt.get_status_display()}."))
    return redirect(request.META.get('HTTP_REFERER', 'counseling_appointments'))


# ============================================================================
# 5. Clinical Session Records (SOAP Notes)
# ============================================================================

@require_access('counseling', 'manage_sessions')
def record_session(request, case_id):
    """Create or update 4-Quadrant SOAP clinical record."""
    case = get_object_or_404(CounselingCase, pk=case_id)
    settings = CounselingSettings.get_settings()
    session_pk = request.GET.get('session_id')
    instance = None

    if session_pk:
        instance = get_object_or_404(SessionRecord, pk=session_pk, case=case)
        # Automatic time-based lock enforcement (session_lock_hours window)
        if not instance.is_locked and instance.created_at:
            elapsed_hours = (timezone.now() - instance.created_at).total_seconds() / 3600.0
            if elapsed_hours > settings.session_lock_hours:
                instance.is_locked = True
                instance.locked_at = timezone.now()
                instance.save(update_fields=['is_locked', 'locked_at'])

        if instance.is_locked:
            messages.error(request, _(f"This clinical session record is locked (exceeded {settings.session_lock_hours}h edit window) and cannot be modified."))
            return redirect('counseling_case_detail', pk=case.pk)

    if request.method == 'POST':
        form = SessionRecordForm(request.POST, instance=instance)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.case = case
            if not rec.recorded_by:
                rec.recorded_by = request.user
            
            # Check if psychologist clicked "Save and Lock"
            if 'lock_record' in request.POST:
                rec.is_locked = True
                rec.locked_at = timezone.now()

            rec.save()

            # Transition case status to In-Therapy if Open
            if case.status == CaseStatus.OPEN:
                case.status = CaseStatus.IN_THERAPY
                case.save()
                CaseStatusLog.objects.create(
                    case=case,
                    old_status=CaseStatus.OPEN,
                    new_status=CaseStatus.IN_THERAPY,
                    changed_by=request.user,
                    note=_("Transitioned to Active Therapy after recording Session #") + str(rec.session_number)
                )

            log_activity(request, 'CREATE' if not instance else 'UPDATE', 'counseling', f"Recorded Session #{rec.session_number} for {case.case_number}")
            messages.success(request, _(f"Session #{rec.session_number} clinical record saved successfully."))
            return redirect('counseling_case_detail', pk=case.pk)
    else:
        initial = {}
        if not instance:
            next_num = case.session_records.count() + 1
            initial['session_number'] = next_num
            initial['session_date'] = timezone.localdate()
        form = SessionRecordForm(instance=instance, initial=initial)

    return render(request, 'counseling/session_record_form.html', {
        'form': form,
        'case': case,
        'instance': instance,
        'snippets': CLINICAL_SNIPPETS,
        'lock_hours': settings.session_lock_hours,
    })


# ============================================================================
# 6. Interactive Psychological Assessment Engine (PHQ-9, GAD-7, DASS-21)
# ============================================================================

@require_access('counseling', 'conduct_assessments')
def conduct_assessment(request, case_id, scale_type):
    """
    Interactive clinical screening form with real-time score calculation.
    """
    case = get_object_or_404(CounselingCase, pk=case_id)
    scale_type_upper = scale_type.upper()

    if scale_type_upper == 'PHQ9':
        questions = PHQ9_QUESTIONS
        options = PHQ9_OPTIONS
        title = "PHQ-9 Depression Assessment"
    elif scale_type_upper == 'GAD7':
        questions = GAD7_QUESTIONS
        options = GAD7_OPTIONS
        title = "GAD-7 Generalized Anxiety Scale"
    elif scale_type_upper == 'DASS21':
        questions = DASS21_QUESTIONS
        options = DASS21_OPTIONS
        title = "DASS-21 Multi-Scale (Depression, Anxiety, Stress)"
    else:
        messages.error(request, _("Unknown psychological assessment scale."))
        return redirect('counseling_case_detail', pk=case.pk)

    if request.method == 'POST':
        # Extract answers
        responses = {}
        for q in questions:
            qid = q["id"]
            try:
                responses[qid] = int(request.POST.get(qid, 0) or 0)
            except (ValueError, TypeError):
                responses[qid] = 0

        notes = request.POST.get('clinical_notes', '')

        # Calculate scores
        if scale_type_upper == 'PHQ9':
            result = calculate_phq9_score(responses)
        elif scale_type_upper == 'GAD7':
            result = calculate_gad7_score(responses)
        else:
            result = calculate_dass21_score(responses)

        assessment = MentalHealthAssessment.objects.create(
            case=case,
            assessment_type=scale_type_upper,
            item_responses=responses,
            total_score=result['total_score'],
            sub_scores=result.get('sub_scores', {}),
            severity_tier=result['severity_tier'],
            assessed_date=timezone.localdate(),
            administered_by=request.user,
            notes=notes
        )

        # If high suicidal risk flagged in PHQ-9 Q9, escalate case risk to CRITICAL
        if scale_type_upper == 'PHQ9' and result.get('has_suicidal_flag'):
            case.risk_level = RiskLevel.CRITICAL
            case.save(update_fields=['risk_level', 'updated_at'])
            messages.warning(request, _("⚠️ Critical suicidal ideation response detected (Item 9). Case risk level elevated to CRITICAL. Follow emergency protocol if needed."))

        log_activity(request, 'CREATE', 'counseling', f"Administered {scale_type_upper} to {case.case_number}: Score {result['total_score']} ({result['severity_tier']})")
        messages.success(request, _(f"{title} successfully completed. Score: {result['total_score']} ({result['severity_tier']})."))
        return redirect('counseling_case_detail', pk=case.pk)

    return render(request, 'counseling/assessment_form.html', {
        'case': case,
        'scale_type': scale_type_upper,
        'title': title,
        'questions': questions,
        'options': options,
    })


# ============================================================================
# 7. Emergency Crisis Triage & Safety Escalation
# ============================================================================

@require_access('counseling', 'emergency_protocol')
def emergency_escalation(request, case_id):
    """Log an acute psychiatric / self-harm crisis intervention."""
    case = get_object_or_404(CounselingCase, pk=case_id)

    if request.method == 'POST':
        form = EmergencyInterventionForm(request.POST)
        if form.is_valid():
            em = form.save(commit=False)
            em.case = case
            em.logged_by = request.user
            em.save()

            # Elevate case risk
            if not em.resolved:
                case.risk_level = RiskLevel.CRITICAL
                case.save()

            log_activity(request, 'SECURITY', 'counseling', f"EMERGENCY INTERVENTION logged for {case.case_number}: {em.incident_type}")
            messages.error(request, _(f"🚨 Emergency protocol logged for {case.case_number}. Authorities informed."))
            return redirect('counseling_case_detail', pk=case.pk)
    else:
        initial = {
            'incident_type': 'Suicidal Ideation / Severe Distress',
            'authorities_notified': f"Hall: {case.student.hall_attached or 'Non-Resident'}, Guardian: {case.student.father_mobile or case.student.emergency_contact}"
        }
        form = EmergencyInterventionForm(initial=initial)

    return render(request, 'counseling/emergency_triage.html', {
        'form': form,
        'case': case,
        'student': case.student,
    })


# ============================================================================
# 8. Campus Mental Health Workshops & Campaigns
# ============================================================================

@require_access('counseling', 'manage_workshops')
def workshop_list(request):
    """List of campus wellbeing workshops."""
    workshops = WellbeingWorkshop.objects.prefetch_related('participants').order_by('-event_date')
    today = timezone.localdate()
    return render(request, 'counseling/workshops.html', {'workshops': workshops, 'today': today})


@require_access('counseling', 'manage_workshops')
def workshop_create(request):
    """Create a new wellness event."""
    if request.method == 'POST':
        form = WellbeingWorkshopForm(request.POST)
        if form.is_valid():
            w = form.save()
            log_activity(request, 'CREATE', 'counseling', f"Created workshop '{w.title}'")
            messages.success(request, _(f"Workshop '{w.title}' scheduled for {w.event_date}."))
            return redirect('counseling_workshops')
    else:
        form = WellbeingWorkshopForm(initial={'event_date': timezone.localdate() + datetime.timedelta(days=7)})

    return render(request, 'counseling/workshop_form.html', {'form': form})


@require_access('counseling', 'manage_workshops')
def workshop_register(request, pk):
    """Register student participant for a workshop."""
    workshop = get_object_or_404(WellbeingWorkshop, pk=pk)
    if request.method == 'POST':
        if workshop.registered_count >= workshop.capacity:
            messages.error(request, _("This workshop has reached maximum capacity and cannot accept additional registrations."))
            return redirect('counseling_workshops')

        student_id = request.POST.get('student_id', '').strip()
        student = Student.objects.filter(student_id=student_id).first() or Student.objects.filter(old_student_id=student_id).first()
        if student:
            p, created = WellbeingWorkshopParticipant.objects.get_or_create(workshop=workshop, student=student)
            if created:
                messages.success(request, _(f"Student {student.student_name} registered for workshop."))
            else:
                messages.info(request, _(f"Student is already registered."))
        else:
            messages.error(request, _("No matching student ID found."))
    return redirect('counseling_workshops')


# ============================================================================
# 9. De-Identified Macro Wellbeing Analytics
# ============================================================================

@require_access('counseling', 'view_analytics')
def macro_analytics(request):
    """
    High-level institutional mental health intelligence for university leadership.
    STRICT PRIVACY GUARD: No student PII (names, phone numbers, IDs) is returned.
    """
    total_cases = CounselingCase.objects.count()
    
    # Category Distribution
    category_data = (
        CounselingCase.objects
        .values('category')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    cat_chart_labels = [str(dict(CaseCategory.choices).get(c['category'], c['category'])) for c in category_data]
    cat_chart_values = [c['count'] for c in category_data]

    # Department Breakdown
    dept_data = (
        CounselingCase.objects
        .values('student__program')
        .annotate(total=Count('id'), critical=Count('id', filter=Q(risk_level=RiskLevel.CRITICAL)))
        .order_by('-total')[:10]
    )

    # Residential vs Non-Residential Stats
    residential_count = CounselingCase.objects.filter(student__is_non_residential=False).count()
    non_residential_count = CounselingCase.objects.filter(student__is_non_residential=True).count()

    # Risk Stratification Breakdown
    risk_data = (
        CounselingCase.objects
        .values('risk_level')
        .annotate(count=Count('id'))
    )
    risk_dict = {r['risk_level']: r['count'] for r in risk_data}

    # Average PHQ-9 and GAD-7 Scores
    avg_phq9 = MentalHealthAssessment.objects.filter(assessment_type=AssessmentType.PHQ9).aggregate(Avg('total_score'))['total_score__avg'] or 0
    avg_gad7 = MentalHealthAssessment.objects.filter(assessment_type=AssessmentType.GAD7).aggregate(Avg('total_score'))['total_score__avg'] or 0

    return render(request, 'counseling/macro_analytics.html', {
        'total_cases': total_cases,
        'cat_chart_labels_json': json.dumps(cat_chart_labels, cls=DjangoJSONEncoder),
        'cat_chart_values_json': json.dumps(cat_chart_values, cls=DjangoJSONEncoder),
        'dept_data': dept_data,
        'residential_count': residential_count,
        'non_residential_count': non_residential_count,
        'risk_dict': risk_dict,
        'avg_phq9': round(avg_phq9, 1),
        'avg_gad7': round(avg_gad7, 1),
    })


# ============================================================================
# 10. Counseling Settings & Psychologist Profile
# ============================================================================

@require_access('counseling', 'manage_settings')
def counseling_settings_view(request):
    """Configure system-wide counseling rules and SMS templates."""
    settings = CounselingSettings.get_settings()
    if request.method == 'POST':
        form = CounselingSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            log_activity(request, 'UPDATE', 'counseling', "Updated counseling system settings")
            messages.success(request, _("Counseling settings updated successfully."))
            return redirect('counseling_settings')
    else:
        form = CounselingSettingsForm(instance=settings)

    return render(request, 'counseling/settings.html', {'form': form})


@require_access('counseling', 'manage_cases')
def counselor_profile_view(request):
    """Psychologist personal schedule & office configuration."""
    profile, _ = CounselorProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = CounselorProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, _("Counselor profile updated."))
            return redirect('counseling_counselor_profile')
    else:
        form = CounselorProfileForm(instance=profile)

    return render(request, 'counseling/counselor_profile.html', {'form': form, 'profile': profile})


# ============================================================================
# 11. Async APIs (Autocomplete & Slots)
# ============================================================================

@login_required
def api_student_search(request):
    """Async autocomplete for Student ID lookup."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    students = Student.objects.filter(
        Q(student_id__icontains=q) |
        Q(student_name__icontains=q) |
        Q(old_student_id__icontains=q)
    )[:10]

    results = [{
        'id': s.student_id,
        'name': s.student_name,
        'program': s.program,
        'batch': s.batch,
        'hall': s.hall_attached or 'Non-Resident',
        'photo': s.photo_url,
    } for s in students]

    return JsonResponse({'results': results})


@login_required
def api_available_slots(request):
    """Returns available time slots for a given counselor and date."""
    counselor_id = request.GET.get('counselor_id')
    date_str = request.GET.get('date')

    if not date_str:
        return JsonResponse({'slots': []})

    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'slots': []})

    counselor = CounselorProfile.objects.filter(pk=counselor_id).first() if counselor_id else CounselorProfile.objects.filter(is_active_counselor=True).first()
    if not counselor:
        return JsonResponse({'slots': []})

    weekday_name = date_obj.strftime('%A')
    slots_dict = counselor.get_default_slots()
    all_slots = slots_dict.get(weekday_name, [])

    # Find booked slots
    booked = CounselingAppointment.objects.filter(
        counselor=counselor,
        appointment_date=date_obj,
        status__in=[AppointmentStatus.CONFIRMED, AppointmentStatus.REQUESTED]
    ).values_list('time_slot', flat=True)

    available = [{'slot': s, 'is_available': s not in booked} for s in all_slots]

    return JsonResponse({'slots': available, 'counselor_name': str(counselor)})
