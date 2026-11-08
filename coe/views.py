"""
CoE Module — Views

Covers all phases:
  Phase 3 — Public Submission (submit wizard + track)
  Phase 4 — Staff Backend    (dashboard, list, detail)
  Phase 5 — HoD Interface    (hod_dashboard, review, bulk)
  Phase 6 — Kanban           (kanban_board, assign)
  Phase 7 — Processing       (workstation, API fetch, reupload, mark_ready)
  Phase 8 — Delivery Desk    (delivery_dashboard, verify_otp, mark_delivered)
  Phase 9 — Utilities        (export_excel, settings, AJAX)
"""

import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.decorators import require_access
from master_data.models import Program

from .forms import (
    ApplicationSearchForm, ApplicationStep1Form, ApplicationStep2Form,
    CoeSettingsForm, DeliveryOtpForm,
    HodReviewForm, OfficerAssignForm, ProcessingBoardForm,
    TrackingLookupForm, ReuploadRequestForm,
)
from .models import (
    ApplicationAttachment, ApplicationStatus, ApplicationStatusLog,
    ApplicationType, CoeSettings, DocumentApplication, ProcessingVerification,
)
from .utils import (
    compute_sha256, generate_delivery_otp, generate_pin,
    generate_tracking_number, purge_attachments, send_coe_sms, transition_status,
    generate_qr_code_base64, render_to_pdf_bytes, send_coe_email,
)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — PUBLIC VIEWS  (no login required)
# ═══════════════════════════════════════════════════════════════════════════════

def submit_application(request):
    """
    Public 4-step application submission wizard.
    Session-backed; HTMX steps swap in partial content.
    """
    if request.method == 'POST' and request.POST.get('action') == 'reset':
        request.session.pop('coe_wizard', None)
        return redirect('coe_submit')

    wizard = request.session.get('coe_wizard', {'step': 1, 'data': {}})
    step = wizard.get('step', 1)
    app_type = wizard.get('data', {}).get('application_type')

    form = None
    cfg = CoeSettings.get_settings()
    required_attachments = []
    files_meta = []

    if step == 2:
        form = ApplicationStep2Form(initial=wizard.get('data', {}), app_type=app_type)
    elif step == 3:
        required_attachments = _get_required_attachments(app_type)
    elif step == 4:
        files_meta = wizard.get('data', {}).get('files_meta', [])

    context = {
        'step': step,
        'application_types': ApplicationType.choices,
        'application_type': app_type,
        'programs': Program.objects.all().order_by('name'),
        'wizard_data': wizard.get('data', {}),
        'form': form,
        'max_mb': cfg.attachment_max_mb,
        'required_attachments': required_attachments,
        'files_meta': files_meta,
        'step_labels': [
            (1, _('Application Type')),
            (2, _('Student Info')),
            (3, _('Documents')),
            (4, _('Review & Submit')),
        ],
    }
    return render(request, 'coe/submit_wizard.html', context)


def submit_step(request, step: int):
    """
    HTMX partial handler for each wizard step.
    step 1 = type selector, 2 = academic info, 3 = attachments, 4 = review+submit
    """
    wizard = request.session.get('coe_wizard', {'step': 1, 'data': {}})

    if request.method == 'POST':
        if step == 1:
            app_type = request.POST.get('application_type')
            if app_type and app_type in dict(ApplicationType.choices):
                wizard['data']['application_type'] = app_type
                wizard['step'] = 2
                request.session['coe_wizard'] = wizard
                if not request.headers.get('HX-Request'):
                    return redirect('coe_submit')
                programs = Program.objects.all().order_by('name')
                form = ApplicationStep2Form(initial=wizard['data'], app_type=app_type)
                return render(request, 'coe/partials/step2.html', {
                    'step': 2,
                    'form': form,
                    'application_type': app_type,
                    'programs': programs,
                    'wizard_data': wizard['data'],
                })
            else:
                return render(request, 'coe/partials/step1.html', {
                    'step': 1,
                    'application_types': ApplicationType.choices,
                    'error': _('Please select an application type.'),
                })

        elif step == 2:
            form = ApplicationStep2Form(request.POST, app_type=wizard['data'].get('application_type'))
            if form.is_valid():
                wizard['data'].update(form.cleaned_data_serializable())
                wizard['step'] = 3
                request.session['coe_wizard'] = wizard
                if not request.headers.get('HX-Request'):
                    return redirect('coe_submit')
                cfg = CoeSettings.get_settings()
                return render(request, 'coe/partials/step3.html', {
                    'step': 3,
                    'wizard_data': wizard['data'],
                    'max_mb': cfg.attachment_max_mb,
                    'required_attachments': _get_required_attachments(wizard['data'].get('application_type')),
                })
            else:
                programs = Program.objects.all().order_by('name')
                return render(request, 'coe/partials/step2.html', {
                    'step': 2,
                    'form': form,
                    'application_type': wizard['data'].get('application_type'),
                    'programs': programs,
                    'wizard_data': wizard['data'],
                })

        elif step == 3:
            # Handle file uploads — store files in temp storage and session metadata for review
            import uuid
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile

            cfg = CoeSettings.get_settings()
            errors = []
            req_atts = _get_required_attachments(wizard['data'].get('application_type'))
            req_keys = {att['key']: att['label'] for att in req_atts}

            existing_pending = request.session.get('coe_pending_files', {})
            new_pending = {}

            if not request.FILES and not existing_pending:
                errors.append(_('Please attach the required document(s) before proceeding.'))
            else:
                for key, f in request.FILES.items():
                    ok, err = _validate_attachment(f, cfg.attachment_max_mb)
                    if not ok:
                        errors.append(f"{f.name}: {err}")
                    else:
                        temp_filename = f"coe_temp/{uuid.uuid4().hex}_{f.name}"
                        saved_path = default_storage.save(temp_filename, ContentFile(f.read()))

                        new_pending[key] = {
                            'temp_path': saved_path,
                            'field_name': key,
                            'original_name': f.name,
                            'size_kb': f.size // 1024,
                            'label': str(req_keys.get(key, f.name)),
                        }

                if not errors and new_pending:
                    existing_pending.update(new_pending)
                    request.session['coe_pending_files'] = existing_pending
                    if hasattr(request.session, 'modified'):
                        request.session.modified = True

            # BUG-6 FIX: Validate every required attachment key is covered
            if not errors:
                combined = request.session.get('coe_pending_files', {})
                missing_atts = [att for att in req_atts if att['key'] not in combined]
                if missing_atts:
                    for att in missing_atts:
                        errors.append(_('Missing required document: %(label)s') % {'label': att['label']})

            files_meta = list(request.session.get('coe_pending_files', {}).values())

            if errors:
                if not request.headers.get('HX-Request'):
                    messages.error(request, errors[0])
                    return redirect('coe_submit')
                return render(request, 'coe/partials/step3.html', {
                    'step': 3,
                    'wizard_data': wizard['data'],
                    'max_mb': cfg.attachment_max_mb,
                    'required_attachments': req_atts,
                    'errors': errors,
                })

            wizard['step'] = 4
            request.session['coe_wizard'] = wizard
            if hasattr(request.session, 'modified'):
                request.session.modified = True

            if not request.headers.get('HX-Request'):
                return redirect('coe_submit')

            return render(request, 'coe/partials/step4.html', {
                'step': 4,
                'wizard_data': wizard['data'],
                'files_meta': files_meta,
            })

        elif step == 4:
            # Final submission
            data = wizard.get('data', {})
            pending_files = request.session.get('coe_pending_files', {})

            if not data.get('application_type'):
                messages.error(request, _('Session expired. Please restart your application.'))
                request.session.pop('coe_wizard', None)
                request.session.pop('coe_pending_files', None)
                return redirect('coe_submit')

            if not pending_files:
                wizard['step'] = 3
                request.session['coe_wizard'] = wizard
                if hasattr(request.session, 'modified'):
                    request.session.modified = True
                messages.error(request, _('Please attach the required document(s) before submitting.'))
                if not request.headers.get('HX-Request'):
                    return redirect('coe_submit')
                cfg = CoeSettings.get_settings()
                return render(request, 'coe/partials/step3.html', {
                    'step': 3,
                    'wizard_data': data,
                    'max_mb': cfg.attachment_max_mb,
                    'required_attachments': _get_required_attachments(data.get('application_type')),
                    'errors': [_('Please attach the required document(s) before submitting.')],
                })

            # Create the application
            try:
                dept_id = data.get('department_id') or data.get('department_id_id')
                dept = Program.objects.get(pk=dept_id)
            except (Program.DoesNotExist, KeyError, ValueError):
                return render(request, 'coe/partials/step4.html', {
                    'step': 4,
                    'wizard_data': data,
                    'files_meta': list(pending_files.values()),
                    'error': _('Invalid department selection. Please go back and reselect.'),
                })

            tracking_number = generate_tracking_number()
            pin = generate_pin()

            app = DocumentApplication.objects.create(
                application_number=tracking_number,
                tracking_pin=pin,
                application_type=data['application_type'],
                status=ApplicationStatus.UNDER_HOD_REVIEW,
                student_name=data.get('student_name', ''),
                student_id=data.get('student_id', ''),
                mobile_number=data.get('mobile_number', ''),
                email=data.get('email', ''),
                session=data.get('session', ''),
                department=dept,
                admission_batch=data.get('admission_batch', ''),
                father_name=data.get('father_name', ''),
                mother_name=data.get('mother_name', ''),
                dob=data.get('dob') or None,
                passing_semester=data.get('passing_semester', ''),
                cgpa=data.get('cgpa', 0),
                result_date=data.get('result_date') or None,
                corrected_name=data.get('corrected_name', ''),
                corrected_parent_name=data.get('corrected_parent_name', ''),
                purpose_destination=data.get('purpose_destination', ''),
                level_term=data.get('level_term', ''),
                missing_doc_type=data.get('missing_doc_type', ''),
                submitted_by=request.user if request.user.is_authenticated else None,
            )

            # Save attachments from temp files
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile

            valid_att_types = dict(ApplicationAttachment.attachment_type.field.choices)
            for key, meta in pending_files.items():
                temp_path = meta['temp_path']
                if default_storage.exists(temp_path):
                    with default_storage.open(temp_path, 'rb') as f:
                        file_bytes = f.read()
                        sha = compute_sha256(ContentFile(file_bytes))
                        att_type = key if key in valid_att_types else 'other'

                        att = ApplicationAttachment(
                            application=app,
                            attachment_type=att_type,
                            sha256_hash=sha,
                            original_filename=meta['original_name'],
                            file_size_kb=meta['size_kb'],
                        )
                        att.file.save(meta['original_name'], ContentFile(file_bytes), save=True)

                    # Delete temp file
                    try:
                        default_storage.delete(temp_path)
                    except Exception:
                        pass

            # Initial status log
            ApplicationStatusLog.objects.create(
                application=app,
                old_status='',
                new_status=ApplicationStatus.UNDER_HOD_REVIEW,
                changed_by=request.user if request.user.is_authenticated else None,
                note=_('Application submitted via public portal.'),
            )

            # Send confirmation SMS
            cfg = CoeSettings.get_settings()
            if cfg.sms_notify_submit:
                send_coe_sms(app.mobile_number, 'submit', {
                    'tracking_number': tracking_number,
                    'pin': pin,
                })

            # Clear wizard session
            request.session.pop('coe_wizard', None)
            request.session.pop('coe_pending_files', None)

            # Store result for success page
            request.session['coe_submit_result'] = {
                'pk': app.pk,
                'tracking_number': tracking_number,
                'pin': pin,
                'student_name': app.student_name,
                'app_type': app.get_application_type_display(),
            }
            if request.headers.get('HX-Request'):
                from django.http import HttpResponse
                response = HttpResponse()
                response['HX-Redirect'] = reverse('coe_submit_success')
                return response
            return redirect('coe_submit_success')

    # GET — render current step partial based on wizard state.
    # BUG-12 FIX: When back=1 use the URL-path step (not wizard.step) so that
    # step3-back→step2 and step4-back→step3 work correctly.
    back = request.GET.get('back') == '1'
    render_step = step if back else wizard.get('step', 1)

    # Sync wizard state backwards so re-renders stay consistent
    if back and step < wizard.get('step', 1):
        wizard['step'] = step
        request.session['coe_wizard'] = wizard

    if render_step == 1:
        return render(request, 'coe/partials/step1.html', {
            'application_types': ApplicationType.choices,
            'wizard_data': wizard.get('data', {}),
        })
    elif render_step == 2:
        programs = Program.objects.all().order_by('name')
        app_type = wizard.get('data', {}).get('application_type')
        form = ApplicationStep2Form(initial=wizard.get('data', {}), app_type=app_type)
        return render(request, 'coe/partials/step2.html', {
            'step': 2,
            'form': form,
            'application_type': app_type,
            'programs': programs,
            'wizard_data': wizard.get('data', {}),
        })
    elif render_step == 3:
        cfg = CoeSettings.get_settings()
        return render(request, 'coe/partials/step3.html', {
            'wizard_data': wizard.get('data', {}),
            'max_mb': cfg.attachment_max_mb,
            'required_attachments': _get_required_attachments(wizard['data'].get('application_type')),
        })
    elif render_step == 4:
        return render(request, 'coe/partials/step4.html', {
            'wizard_data': wizard.get('data', {}),
            'files_meta': list(request.session.get('coe_pending_files', {}).values()),
        })

    return redirect('coe_submit')


def submit_success(request):
    """Display tracking number and PIN after successful submission."""
    result = request.session.pop('coe_submit_result', None)
    if not result:
        return redirect('coe_submit')
    return render(request, 'coe/submit_success.html', {'result': result})


def track_application(request):
    """
    Public tracking portal. Looks up application by tracking number +
    mobile number or student ID.
    """
    form = TrackingLookupForm(request.GET or None)
    application = None
    error = None

    if request.GET and form.is_valid():
        tracking_number = form.cleaned_data['tracking_number'].strip()
        identifier = form.cleaned_data['identifier'].strip()  # mobile or student_id

        digits = ''.join(filter(str.isdigit, identifier))
        if digits.startswith('880') and len(digits) == 13:
            mobile_clean = digits[3:]
        elif digits.startswith('88') and len(digits) == 12:
            mobile_clean = digits[2:]
        else:
            mobile_clean = digits

        qs = DocumentApplication.all_objects.filter(
            application_number__iexact=tracking_number
        ).filter(
            Q(mobile_number=identifier) | Q(mobile_number=mobile_clean) | Q(student_id__iexact=identifier)
        )
        application = qs.first()
        if not application:
            error = _('No application found. Please check your Tracking ID and Mobile Number / Student ID.')

    # Status steps for progress bar
    status_steps = [
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.UNDER_HOD_REVIEW,
        ApplicationStatus.PENDING_COE_ASSIGNMENT,
        ApplicationStatus.IN_PROCESSING,
        ApplicationStatus.ACTION_REQUIRED,
        ApplicationStatus.READY_FOR_DELIVERY,
        ApplicationStatus.DELIVERED,
    ]

    steps_data = []
    progress_width = 0
    contacts = []
    stage_title = ""
    stage_note = ""
    
    if application:
        status_order = {
            ApplicationStatus.SUBMITTED: 1,
            ApplicationStatus.UNDER_HOD_REVIEW: 2,
            ApplicationStatus.PENDING_COE_ASSIGNMENT: 3,
            ApplicationStatus.IN_PROCESSING: 4,
            ApplicationStatus.DISPATCHED_TO_DELIVERY: 4,
            ApplicationStatus.RECEIVED_BY_CLERK: 4,
            ApplicationStatus.ACTION_REQUIRED: 5,
            ApplicationStatus.READY_FOR_DELIVERY: 6,
            ApplicationStatus.DELIVERED: 7,
        }
        
        current_val = status_order.get(application.status, 7)
        for step_key in status_steps:
            step_val = status_order.get(step_key, 7)
            
            if step_key == ApplicationStatus.IN_PROCESSING and application.status in [ApplicationStatus.IN_PROCESSING, ApplicationStatus.DISPATCHED_TO_DELIVERY, ApplicationStatus.RECEIVED_BY_CLERK]:
                css_class = 'active'
            elif application.status == step_key:
                css_class = 'active'
            elif current_val > step_val:
                css_class = 'completed'
            else:
                css_class = ''
                
            steps_data.append({
                'key': step_key,
                'class': css_class
            })
            
        width_map = {
            ApplicationStatus.SUBMITTED: 15,
            ApplicationStatus.UNDER_HOD_REVIEW: 30,
            ApplicationStatus.PENDING_COE_ASSIGNMENT: 45,
            ApplicationStatus.IN_PROCESSING: 60,
            ApplicationStatus.DISPATCHED_TO_DELIVERY: 68,
            ApplicationStatus.RECEIVED_BY_CLERK: 76,
            ApplicationStatus.ACTION_REQUIRED: 84,
            ApplicationStatus.READY_FOR_DELIVERY: 92,
            ApplicationStatus.DELIVERED: 100,
        }
        progress_width = width_map.get(application.status, 100)

        status = application.status
        from django.contrib.auth.models import User
        
        def clean_str(val):
            if not val:
                return ''
            val = val.lower().replace('&', 'and')
            return ''.join(c for c in val if c.isalnum())
            
        # Default values — prevent UnboundLocalError if status falls through
        contacts = []
        stage_title = _("Processing")
        stage_note = _("Your application is being processed.")

        if status == ApplicationStatus.SUBMITTED:
            stage_title = _("Submission Received")
            stage_note = _("Your application has been received and is queued for verification.")
            
        elif status == ApplicationStatus.UNDER_HOD_REVIEW:
            stage_title = _("Department Head Review (HoD)")
            stage_note = _("The application is pending review and sign-off by your Department Head.")
            dept = application.department
            hods = User.objects.filter(
                profile__role__name__icontains="Department Head",
                is_active=True
            ).select_related('profile')
            
            matched_hods = []
            if dept:
                c_short = clean_str(dept.short_name)
                c_full = clean_str(dept.name)
                for u in hods:
                    u_scope = clean_str(u.profile.department_scope)
                    u_dept = clean_str(u.profile.department)
                    
                    is_match = False
                    if u_scope and (u_scope == c_short or u_scope == c_full):
                        is_match = True
                    elif u_dept and (c_short in u_dept or c_full in u_dept or u_dept in c_full):
                        is_match = True
                        
                    if is_match:
                        matched_hods.append(u)
            
            if not matched_hods:
                matched_hods = list(hods)
                
            for u in matched_hods:
                contacts.append({
                    'name': u.get_full_name() or u.username,
                    'designation': u.profile.designation or _("Head of Department"),
                    'mobile': u.profile.phone_number or _("N/A"),
                    'email': u.email or _("N/A"),
                })
                
        elif status == ApplicationStatus.PENDING_COE_ASSIGNMENT:
            stage_title = _("Pending CoE Office Assignment")
            stage_note = _("The application is pending processing queue allocation by the Deputy Controller.")
            dcoes = User.objects.filter(
                profile__role__name__icontains="Deputy Controller",
                is_active=True
            ).select_related('profile')
            for u in dcoes:
                contacts.append({
                    'name': u.get_full_name() or u.username,
                    'designation': u.profile.designation or _("Deputy Controller of Examinations"),
                    'mobile': u.profile.phone_number or _("N/A"),
                    'email': u.email or _("N/A"),
                })
                
        elif status == ApplicationStatus.IN_PROCESSING:
            stage_title = _("Academic Document Processing")
            stage_note = _("Your document is currently being verified and prepared by the assigned officer.")
            u = application.assigned_to
            if u:
                contacts.append({
                    'name': u.get_full_name() or u.username,
                    'designation': u.profile.designation or _("Processing Officer"),
                    'mobile': u.profile.phone_number or _("N/A"),
                    'email': u.email or _("N/A"),
                })
                
        elif status in [ApplicationStatus.DISPATCHED_TO_DELIVERY, ApplicationStatus.RECEIVED_BY_CLERK]:
            stage_title = _("Delivery Desk (Sorting & Packaging)")
            stage_note = _("Verification is complete. The physical copy is being packaged and sorted at the delivery desk.")
            clerks = User.objects.filter(
                profile__role__name__icontains="Delivery Desk",
                is_active=True
            ).select_related('profile')
            for u in clerks:
                contacts.append({
                    'name': u.get_full_name() or u.username,
                    'designation': u.profile.designation or _("Delivery Desk Clerk"),
                    'mobile': u.profile.phone_number or _("N/A"),
                    'email': u.email or _("N/A"),
                })
                
        elif status == ApplicationStatus.READY_FOR_DELIVERY:
            stage_title = _("Ready for Delivery / Collection")
            stage_note = _("Document is ready for pickup! Please visit the Delivery Desk with your verification OTP code.")
            clerks = User.objects.filter(
                profile__role__name__icontains="Delivery Desk",
                is_active=True
            ).select_related('profile')
            for u in clerks:
                contacts.append({
                    'name': u.get_full_name() or u.username,
                    'designation': u.profile.designation or _("Delivery Desk Clerk"),
                    'mobile': u.profile.phone_number or _("N/A"),
                    'email': u.email or _("N/A"),
                })
                
        elif status == ApplicationStatus.ACTION_REQUIRED:
            stage_title = _("Action Required (Student correction)")
            stage_note = _("One or more uploaded attachments did not pass inspection. Please log in to the correction portal and re-upload.")
            
        elif status == ApplicationStatus.DELIVERED:
            stage_title = _("Document Delivered")
            stage_note = _("Your document has been physically delivered. Thank you!")
            
        elif status in [ApplicationStatus.REJECTED, ApplicationStatus.CANCELLED]:
            stage_title = _("Application Closed")
            stage_note = _("This request has been cancelled or rejected by administration.")

        if not contacts:
            contacts.append({
                'name': _("CoE Help Desk"),
                'designation': _("General Support Desk"),
                'mobile': _("01780780780"),
                'email': _("coe.support@baust.edu.bd"),
            })

    return render(request, 'coe/track_application.html', {
        'form': form,
        'application': application,
        'error': error,
        'steps_data': steps_data,
        'progress_width': progress_width,
        'contacts': contacts,
        'stage_title': stage_title,
        'stage_note': stage_note,
    })


def ajax_type_fields(request):
    """HTMX: return the dynamic field list for a given application type."""
    app_type = request.GET.get('type', '')
    required = _get_required_attachments(app_type)
    type_fields = _get_type_specific_fields(app_type)
    return render(request, 'coe/partials/type_fields.html', {
        'required_attachments': required,
        'type_fields': type_fields,
        'application_type': app_type,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — STAFF BACKEND
# ═══════════════════════════════════════════════════════════════════════════════

@require_access('coe', 'view_all_applications')
def dashboard(request):
    """Master KPI dashboard with bottleneck alerts and submission chart data."""
    today = timezone.localdate()
    now = timezone.now()

    # KPI counts
    qs_all = DocumentApplication.objects.all()
    kpi = {
        'today_submitted': qs_all.filter(submitted_at__date=today).count(),
        'pending_hod': qs_all.filter(status=ApplicationStatus.UNDER_HOD_REVIEW).count(),
        'pending_assignment': qs_all.filter(status=ApplicationStatus.PENDING_COE_ASSIGNMENT).count(),
        'in_processing': qs_all.filter(status=ApplicationStatus.IN_PROCESSING).count(),
        'action_required': qs_all.filter(status=ApplicationStatus.ACTION_REQUIRED).count(),
        'ready_delivery': qs_all.filter(status=ApplicationStatus.READY_FOR_DELIVERY).count(),
        'delivered_today': qs_all.filter(status=ApplicationStatus.DELIVERED, delivered_at__date=today).count(),
        'total': qs_all.count(),
    }

    # Bottleneck — stalled > 48 hours in non-terminal states
    import datetime
    cutoff_48h = now - datetime.timedelta(hours=48)
    active_statuses = [
        ApplicationStatus.UNDER_HOD_REVIEW,
        ApplicationStatus.PENDING_COE_ASSIGNMENT,
        ApplicationStatus.IN_PROCESSING,
        ApplicationStatus.ACTION_REQUIRED,
        ApplicationStatus.DISPATCHED_TO_DELIVERY,
        ApplicationStatus.RECEIVED_BY_CLERK,
    ]
    stalled = qs_all.filter(status__in=active_statuses, updated_at__lt=cutoff_48h)

    # Recent 10 applications
    recent = qs_all.order_by('-submitted_at')[:10]

    # Chart data — submissions per type
    type_chart = list(
        qs_all.values('application_type')
              .annotate(count=Count('id'))
              .order_by('-count')
    )

    return render(request, 'coe/dashboard.html', {
        'kpi': kpi,
        'stalled': stalled[:5],
        'stalled_count': stalled.count(),
        'recent': recent,
        'type_chart': json.dumps(type_chart),
        'ApplicationStatus': ApplicationStatus,
    })


@require_access('coe', 'view_all_applications')
def application_list(request):
    """Full filterable & searchable list of all applications."""
    form = ApplicationSearchForm(request.GET or None)
    qs = DocumentApplication.objects.select_related('department', 'assigned_to').all()

    if form.is_valid():
        q = form.cleaned_data.get('q')
        status = form.cleaned_data.get('status')
        app_type = form.cleaned_data.get('application_type')
        dept = form.cleaned_data.get('department')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')

        if q:
            qs = qs.filter(
                Q(application_number__icontains=q)
                | Q(student_name__icontains=q)
                | Q(student_id__icontains=q)
                | Q(mobile_number__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if app_type:
            qs = qs.filter(application_type=app_type)
        if dept:
            qs = qs.filter(department=dept)
        if date_from:
            qs = qs.filter(submitted_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(submitted_at__date__lte=date_to)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'coe/application_list.html', {
        'form': form,
        'page_obj': page_obj,
        'total': qs.count(),
        'ApplicationStatus': ApplicationStatus,
    })


@require_access('coe', 'view_all_applications')
def application_detail(request, pk):
    """Full detail view with timeline, attachments, and audit log."""
    app = get_object_or_404(DocumentApplication, pk=pk)
    logs = app.status_logs.order_by('changed_at')
    attachments = app.attachments.all()
    verification = getattr(app, 'verification', None)

    return render(request, 'coe/application_detail.html', {
        'app': app,
        'logs': logs,
        'attachments': attachments,
        'verification': verification,
        'ApplicationStatus': ApplicationStatus,
    })


@login_required
def ajax_attachments(request, pk):
    """AJAX: Return attachment list for an application as JSON."""
    app = get_object_or_404(DocumentApplication, pk=pk)
    data = [
        {
            'id': att.id,
            'type': att.get_attachment_type_display(),
            'filename': att.original_filename,
            'size_kb': att.file_size_kb,
            'url': att.file.url if not att.is_purged else '',
            'is_purged': att.is_purged,
        }
        for att in app.attachments.all()
    ]
    return JsonResponse({'attachments': data})


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — HoD INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

@require_access('coe', 'dept_head_review')
def hod_dashboard(request):
    """
    Department-scoped application table for Head of Department.
    Filtered to the HoD's department_scope if set.
    """
    user_dept = getattr(request.user, 'profile', None)
    dept_scope = getattr(user_dept, 'department_scope', None) if user_dept else None

    qs = DocumentApplication.objects.filter(
        status=ApplicationStatus.UNDER_HOD_REVIEW
    ).select_related('department')

    # Check explicitly assigned HoD departments in CoE Settings
    from .models import CoeUserRoleAssignment, CoeRoleType
    hod_depts = CoeUserRoleAssignment.objects.filter(role_type=CoeRoleType.HOD, user=request.user).values_list('department_id', flat=True)
    if hod_depts and not request.user.is_superuser:
        qs = qs.filter(department_id__in=hod_depts)
    elif dept_scope and not request.user.is_superuser:
        qs = qs.filter(
            Q(department__short_name__iexact=dept_scope)
            | Q(department__code__iexact=dept_scope)
            | Q(department__name__icontains=dept_scope)
        )

    q = request.GET.get('q', '').strip()
    app_type = request.GET.get('application_type', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if q:
        qs = qs.filter(
            Q(application_number__icontains=q)
            | Q(student_name__icontains=q)
            | Q(student_id__icontains=q)
        )
    if app_type:
        qs = qs.filter(application_type=app_type)
    if date_from:
        qs = qs.filter(submitted_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(submitted_at__date__lte=date_to)

    from master_data.models import Program
    assigned_hod_dept_ids = CoeUserRoleAssignment.objects.filter(
        role_type=CoeRoleType.HOD, user__is_active=True
    ).values_list('department_id', flat=True)
    unassigned_hod_depts = Program.objects.exclude(id__in=assigned_hod_dept_ids)

    from .models import ApplicationType
    paginator = Paginator(qs.order_by('-submitted_at'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'coe/hod_dashboard.html', {
        'page_obj': page_obj,
        'total': qs.count(),
        'dept_scope': dept_scope,
        'ApplicationType': ApplicationType,
        'query': q,
        'app_type': app_type,
        'date_from': date_from,
        'date_to': date_to,
        'unassigned_hod_depts': unassigned_hod_depts,
    })


@require_access('coe', 'dept_head_review')
def hod_review(request, pk):
    """HTMX modal — Approve / Hold / Reject a single application."""
    app = get_object_or_404(DocumentApplication, pk=pk, status=ApplicationStatus.UNDER_HOD_REVIEW)

    # Department scope enforcement
    user_dept = getattr(request.user, 'profile', None)
    dept_scope = getattr(user_dept, 'department_scope', None) if user_dept else None
    if dept_scope and not request.user.is_superuser:
        dept_match = (
            (app.department.short_name and app.department.short_name.lower() == dept_scope.lower()) or
            (app.department.code and app.department.code.lower() == dept_scope.lower()) or
            (app.department.name and dept_scope.lower() in app.department.name.lower())
        )
        if not dept_match:
            messages.error(request, _('Access denied: This application belongs to another department.'))
            return redirect('coe_hod_dashboard')

    if request.method == 'POST':
        form = HodReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            note = form.cleaned_data.get('note', '')

            if action == 'approve':
                app.dept_head_note = note
                app.save(update_fields=['dept_head_note'])  # BUG-7 FIX: explicit save before transition
                transition_status(
                    app, ApplicationStatus.PENDING_COE_ASSIGNMENT,
                    changed_by=request.user,
                    note=note or _('HoD approved and forwarded to CoE.'),
                    send_sms_key='hod_approved',
                    sms_context={'tracking_number': app.application_number},
                )
                if request.headers.get('HX-Request'):
                    return HttpResponse(
                        f'<div class="alert alert-success">{_("Application approved and forwarded to CoE.")}</div>'
                        '<script>setTimeout(()=>location.reload(),1200);</script>'
                    )
                messages.success(request, _('Application approved and forwarded to CoE.'))
            elif action == 'hold':
                app.dept_head_note = note
                app.save(update_fields=['dept_head_note'])
                ApplicationStatusLog.objects.create(
                    application=app, old_status=app.status, new_status=app.status,
                    changed_by=request.user, note=f"[HOLD] {note}"
                )
                if request.headers.get('HX-Request'):
                    return HttpResponse(
                        f'<div class="alert alert-warning">{_("Application placed on hold.")}</div>'
                        '<script>setTimeout(()=>location.reload(),1200);</script>'
                    )
                messages.warning(request, _('Application placed on hold.'))
            elif action == 'reject':
                if not note:
                    form.add_error('note', _('Rejection reason is required.'))
                else:
                    app.rejection_reason = note
                    app.save(update_fields=['rejection_reason'])  # BUG-7 FIX: explicit save before transition
                    transition_status(
                        app, ApplicationStatus.REJECTED,
                        changed_by=request.user,
                        note=note,
                    )
                    if request.headers.get('HX-Request'):
                        return HttpResponse(
                            f'<div class="alert alert-danger">{_("Application rejected.")}</div>'
                            '<script>setTimeout(()=>location.reload(),1200);</script>'
                        )
                    messages.error(request, _('Application rejected.'))

            return redirect('coe_hod_dashboard')
    else:
        form = HodReviewForm()

    attachments = app.attachments.all()
    template = 'coe/partials/hod_review_modal.html' if request.headers.get('HX-Request') else 'coe/hod_review.html'
    return render(request, template, {'app': app, 'form': form, 'attachments': attachments})


@require_access('coe', 'dept_head_review')
@require_POST
def hod_bulk_action(request):
    """Bulk approve or reject multiple applications."""
    app_ids = request.POST.getlist('app_ids')
    action = request.POST.get('bulk_action')
    note = request.POST.get('note', '')

    if not app_ids:
        messages.warning(request, _('No applications selected.'))
        return redirect('coe_hod_dashboard')

    apps = DocumentApplication.objects.filter(
        pk__in=app_ids, status=ApplicationStatus.UNDER_HOD_REVIEW
    )

    count = 0
    for app in apps:
        if action == 'approve':
            transition_status(
                app, ApplicationStatus.PENDING_COE_ASSIGNMENT,
                changed_by=request.user,
                note=note or _('Bulk approved by HoD.'),
                send_sms_key='hod_approved',
                sms_context={'tracking_number': app.application_number},
            )
            count += 1
        elif action == 'reject' and note:
            app.rejection_reason = note
            app.save(update_fields=['rejection_reason'])
            transition_status(
                app, ApplicationStatus.REJECTED,
                changed_by=request.user, note=note,
            )
            count += 1

    messages.success(request, _(f'{count} applications processed.'))
    return redirect('coe_hod_dashboard')


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — CoE KANBAN / ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

@require_access('coe', 'coe_desk_assign')
def kanban_board(request):
    """CoE Desk Kanban — three-column assignment board."""
    import datetime
    cutoff_48h = timezone.now() - datetime.timedelta(hours=48)

    pending = DocumentApplication.objects.filter(
        status=ApplicationStatus.PENDING_COE_ASSIGNMENT
    ).select_related('department').prefetch_related('status_logs', 'status_logs__changed_by').order_by('-submitted_at')

    in_processing = DocumentApplication.objects.filter(
        status=ApplicationStatus.IN_PROCESSING
    ).select_related('department', 'assigned_to').prefetch_related('status_logs', 'status_logs__changed_by').order_by('-updated_at')

    action_required = DocumentApplication.objects.filter(
        status=ApplicationStatus.ACTION_REQUIRED
    ).select_related('department', 'assigned_to').prefetch_related('status_logs', 'status_logs__changed_by').order_by('-updated_at')

    ready = DocumentApplication.objects.filter(
        status=ApplicationStatus.READY_FOR_DELIVERY
    ).select_related('department', 'assigned_to').prefetch_related('status_logs', 'status_logs__changed_by').order_by('-updated_at')

    # Officers specifically designated for CoE processing
    from .utils import get_coe_processing_officers
    officers = get_coe_processing_officers()

    # Pre-calculate workload per officer for active states
    officer_workloads = []
    for officer in officers:
        assigned_apps = DocumentApplication.objects.filter(
            assigned_to=officer,
            status__in=[
                ApplicationStatus.IN_PROCESSING,
                ApplicationStatus.ACTION_REQUIRED,
                ApplicationStatus.READY_FOR_DELIVERY
            ]
        ).select_related('department').order_by('status', '-updated_at')
        
        officer_workloads.append({
            'officer': officer,
            'applications': assigned_apps,
            'count': assigned_apps.count(),
            'in_processing_count': assigned_apps.filter(status=ApplicationStatus.IN_PROCESSING).count(),
            'action_required_count': assigned_apps.filter(status=ApplicationStatus.ACTION_REQUIRED).count(),
            'ready_count': assigned_apps.filter(status=ApplicationStatus.READY_FOR_DELIVERY).count(),
        })

    return render(request, 'coe/kanban_board.html', {
        'pending': pending,
        'in_processing': in_processing,
        'action_required': action_required,
        'ready': ready,
        'officers': officers,
        'officer_workloads': officer_workloads,
        'cutoff_48h': cutoff_48h,
    })


@require_access('coe', 'coe_desk_assign')
def assign_officer(request, pk):
    """HTMX modal — assign or re-assign a processing officer to an application."""
    app = get_object_or_404(
        DocumentApplication, pk=pk,
        status__in=[
            ApplicationStatus.PENDING_COE_ASSIGNMENT,
            ApplicationStatus.IN_PROCESSING,
            ApplicationStatus.ACTION_REQUIRED,
            ApplicationStatus.READY_FOR_DELIVERY
        ]
    )

    if request.method == 'POST':
        form = OfficerAssignForm(request.POST)
        if form.is_valid():
            officer = form.cleaned_data['officer']
            old_officer = app.assigned_to
            app.assigned_to = officer
            
            if app.status == ApplicationStatus.PENDING_COE_ASSIGNMENT:
                transition_status(
                    app, ApplicationStatus.IN_PROCESSING,
                    changed_by=request.user,
                    note=_(f'Assigned to {officer.get_full_name() or officer.username} for processing.'),
                )
            else:
                # Re-assignment: just save the new officer and log it
                app.save(update_fields=['assigned_to'])  # BUG-8 FIX: auto_now field must not be in update_fields
                ApplicationStatusLog.objects.create(
                    application=app,
                    old_status=app.status,
                    new_status=app.status,
                    changed_by=request.user,
                    note=_(f'Reassigned from {old_officer.get_full_name() or old_officer.username if old_officer else "None"} to {officer.get_full_name() or officer.username}.'),
                )
                
            if request.headers.get('HX-Request'):
                return HttpResponse(
                    f'<div class="alert alert-success">'
                    f'{_("Assigned to")} {officer.get_full_name() or officer.username}.'
                    f'</div><script>setTimeout(()=>location.reload(),1000);</script>'
                )
            messages.success(request, _(f'Application assigned to {officer.get_full_name() or officer.username}.'))
            return redirect('coe_kanban')
    else:
        form = OfficerAssignForm(initial={'officer': app.assigned_to})

    template = 'coe/partials/assign_modal.html' if request.headers.get('HX-Request') else 'coe/assign_officer.html'
    return render(request, template, {'app': app, 'form': form})


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7 — PROCESSING WORKSTATION
# ═══════════════════════════════════════════════════════════════════════════════

@require_access('coe', 'processing_officer')
def processing_workstation(request, pk):
    """Split-screen processing workstation for the assigned officer."""
    app = get_object_or_404(DocumentApplication, pk=pk)

    # Ensure officer only sees their own assignments (unless superuser)
    if not request.user.is_superuser and app.assigned_to != request.user:
        if not (hasattr(request.user, 'profile') and request.user.profile.has_access('coe', 'view_all_applications')):
            messages.error(request, _('This application is not assigned to you.'))
            return redirect('coe_kanban')

    verification, _ = ProcessingVerification.objects.get_or_create(application=app)
    attachments = app.attachments.all()
    logs = app.status_logs.order_by('changed_at')

    return render(request, 'coe/processing_workstation.html', {
        'app': app,
        'verification': verification,
        'attachments': attachments,
        'logs': logs,
        'ApplicationStatus': ApplicationStatus,
    })


@require_access('coe', 'processing_officer')
@require_POST
def fetch_admission_api(request, pk):
    """
    Fetch student record from the internal student database.
    Caches result in ProcessingVerification.
    """
    app = get_object_or_404(DocumentApplication, pk=pk)
    verification, _ = ProcessingVerification.objects.get_or_create(application=app)

    from students.models import Student  # local import to avoid circular
    try:
        student = Student.objects.filter(
            Q(student_id__iexact=app.student_id) | Q(old_student_id__iexact=app.student_id)
        ).first()
        if student:
            data = {
                'student_id': student.student_id,
                'name': student.student_name,
                'program': str(student.program or ''),
                'session': str(student.semester_name or student.admission_year or ''),
                'status': student.admission_status,
            }
            verification.admission_api_fetched = True
            verification.admission_api_data = data
            verification.verified_by = request.user
            verification.verified_at = timezone.now()
            verification.save()
            return JsonResponse({'success': True, 'data': data})
        else:
            return JsonResponse({'success': False, 'error': _('Student not found in admission database.')})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)})


@require_access('coe', 'processing_officer')
@require_POST
def fetch_board_api(request, pk):
    """
    Fetch SSC/HSC board record via BoardVerificationEngine / BTEBVerificationEngine in students module.
    Caches result in ProcessingVerification.
    """
    app = get_object_or_404(DocumentApplication, pk=pk)
    form = ProcessingBoardForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors})

    verification, _ = ProcessingVerification.objects.get_or_create(application=app)

    # Save the board search params
    verification.board_roll = form.cleaned_data.get('board_roll', '')
    verification.board_registration = form.cleaned_data.get('board_registration', '')
    verification.board_name = form.cleaned_data.get('board_name', '')
    verification.board_year = form.cleaned_data.get('board_year', '')

    try:
        from students.utils_board import BoardVerificationEngine, BTEBVerificationEngine, is_technical_board
        if is_technical_board(verification.board_name):
            engine = BTEBVerificationEngine()
            result = engine.verify(
                roll=verification.board_roll,
                reg=verification.board_registration,
                year=verification.board_year,
            )
        else:
            engine = BoardVerificationEngine()
            result = engine.get_result(
                board=verification.board_name,
                roll=verification.board_roll,
                reg=verification.board_registration,
                year=verification.board_year,
            )
        verification.board_api_fetched = True
        verification.board_api_data = result
        verification.verified_by = request.user
        verification.verified_at = timezone.now()
        verification.save()
        return JsonResponse({'success': True, 'data': result})
    except Exception as exc:
        verification.save(update_fields=['board_roll', 'board_registration', 'board_name', 'board_year'])
        return JsonResponse({'success': False, 'error': str(exc)})


@require_access('coe', 'processing_officer')
@require_POST
def request_reupload(request, pk):
    """Set status to ACTION_REQUIRED and send SMS requesting re-upload."""
    app = get_object_or_404(DocumentApplication, pk=pk, status=ApplicationStatus.IN_PROCESSING)
    form = ReuploadRequestForm(request.POST)
    if form.is_valid():
        note = form.cleaned_data['note']
        transition_status(
            app, ApplicationStatus.ACTION_REQUIRED,
            changed_by=request.user, note=note,
            send_sms_key='action_required',
            sms_context={'note': note},
        )
        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="alert alert-warning">{_("Action Required SMS sent to student.")}</div>'
                '<script>setTimeout(()=>location.reload(),1200);</script>'
            )
        messages.warning(request, _('Student notified to re-upload documents.'))
    else:
        messages.error(request, _('Please provide a reason for re-upload request.'))
    return redirect('coe_process', pk=pk)


@require_access('coe', 'processing_officer')
@require_POST
def dispatch_to_delivery(request, pk):
    """Mark application as dispatched to delivery desk clerk."""
    app = get_object_or_404(DocumentApplication, pk=pk, status=ApplicationStatus.IN_PROCESSING)
    transition_status(
        app, ApplicationStatus.DISPATCHED_TO_DELIVERY,
        changed_by=request.user,
        note=_('Verification complete. Dispatched to Delivery Desk clerk.'),
    )
    messages.success(request, _('Application sent to the Delivery Desk queue.'))
    return redirect('coe_process', pk=pk)


@require_access('coe', 'delivery_desk')
@require_POST
def clerk_receive(request, pk):
    """Mark application as physically received by clerk at delivery desk."""
    app = get_object_or_404(DocumentApplication, pk=pk, status=ApplicationStatus.DISPATCHED_TO_DELIVERY)
    transition_status(
        app, ApplicationStatus.RECEIVED_BY_CLERK,
        changed_by=request.user,
        note=_(f'Document physically received by clerk {request.user.get_full_name() or request.user.username} for packaging.'),
    )
    messages.success(request, _('Document marked as received. Start sorting & packaging.'))
    return redirect('coe_delivery_dashboard')


@require_access('coe', 'delivery_desk')
@require_POST
def clerk_mark_ready(request, pk):
    """Generate OTP and mark application as Ready for Delivery (sending SMS notifications)."""
    app = get_object_or_404(DocumentApplication, pk=pk, status=ApplicationStatus.RECEIVED_BY_CLERK)
    otp = generate_delivery_otp()
    app.delivery_otp = otp
    app.save(update_fields=['delivery_otp'])

    transition_status(
        app, ApplicationStatus.READY_FOR_DELIVERY,
        changed_by=request.user,
        note=_('Processing complete. OTP generated and dispatched.'),
        send_sms_key='ready_for_delivery',
        sms_context={'doc_type': app.get_application_type_display()},
    )

    # Also dispatch OTP SMS
    cfg = CoeSettings.get_settings()
    if cfg.sms_delivery_otp:
        send_coe_sms(app.mobile_number, 'delivery_otp', {'otp': otp})

    messages.success(request, _(f'Application marked as ready. OTP sent to student ({app.mobile_number}).'))
    return redirect('coe_delivery_dashboard')


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8 — DELIVERY DESK
# ═══════════════════════════════════════════════════════════════════════════════

@require_access('coe', 'delivery_desk')
def delivery_dashboard(request):
    """Delivery clerk queue — search + list applications at delivery desk stages."""
    query = request.GET.get('q', '').strip()
    app_type = request.GET.get('application_type', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    target_statuses = [
        ApplicationStatus.DISPATCHED_TO_DELIVERY,
        ApplicationStatus.RECEIVED_BY_CLERK,
        ApplicationStatus.READY_FOR_DELIVERY,
    ]
    
    qs = DocumentApplication.objects.filter(
        status__in=target_statuses
    ).select_related('department').prefetch_related('status_logs', 'status_logs__changed_by').order_by('-updated_at')

    if query:
        qs = qs.filter(
            Q(application_number__icontains=query)
            | Q(student_name__icontains=query)
            | Q(student_id__icontains=query)
        )
    if app_type:
        qs = qs.filter(application_type=app_type)
    if date_from:
        qs = qs.filter(updated_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(updated_at__date__lte=date_to)

    pending_receipt = qs.filter(status=ApplicationStatus.DISPATCHED_TO_DELIVERY)
    received_sorting = qs.filter(status=ApplicationStatus.RECEIVED_BY_CLERK)
    ready_delivery = qs.filter(status=ApplicationStatus.READY_FOR_DELIVERY)

    from .models import ApplicationType, CoeUserRoleAssignment, CoeRoleType
    has_delivery_clerks = CoeUserRoleAssignment.objects.filter(
        role_type=CoeRoleType.DELIVERY_CLERK, user__is_active=True
    ).exists()

    return render(request, 'coe/delivery_dashboard.html', {
        'query': query,
        'app_type': app_type,
        'date_from': date_from,
        'date_to': date_to,
        'ApplicationType': ApplicationType,
        'pending_receipt': pending_receipt,
        'received_sorting': received_sorting,
        'ready_delivery': ready_delivery,
        'has_delivery_clerks': has_delivery_clerks,
        
        'count_receipt': pending_receipt.count(),
        'count_sorting': received_sorting.count(),
        'count_ready': ready_delivery.count(),
        'total_count': qs.count(),
    })


@require_access('coe', 'delivery_desk')
def verify_otp(request, pk):
    """OTP entry modal with identity verification prompt."""
    app = get_object_or_404(DocumentApplication, pk=pk, status=ApplicationStatus.READY_FOR_DELIVERY)

    if request.method == 'POST':
        form = DeliveryOtpForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data['otp']
            if entered_otp == app.delivery_otp:
                app.delivery_otp_verified = True
                app.save(update_fields=['delivery_otp_verified'])
                if request.headers.get('HX-Request'):
                    return render(request, 'coe/partials/otp_verified.html', {'app': app})
                messages.success(request, _('OTP verified successfully. You may now deliver the document.'))
                return redirect('coe_mark_delivered', pk=pk)
            else:
                form.add_error('otp', _('Incorrect OTP. Please try again.'))
    else:
        form = DeliveryOtpForm()

    template = 'coe/partials/delivery_otp_modal.html' if request.headers.get('HX-Request') else 'coe/verify_otp.html'
    return render(request, template, {'app': app, 'form': form})


@require_access('coe', 'delivery_desk')
@require_POST
def mark_delivered(request, pk):
    """Mark application as delivered after OTP verification."""
    app = get_object_or_404(DocumentApplication, pk=pk, status=ApplicationStatus.READY_FOR_DELIVERY)

    if not app.delivery_otp_verified:
        messages.error(request, _('OTP must be verified before marking as delivered.'))
        return redirect('coe_delivery_dashboard')

    identity_note = request.POST.get('identity_note', '').strip()
    app.delivered_at = timezone.now()
    app.delivered_by = request.user
    app.save(update_fields=['delivered_at', 'delivered_by'])

    transition_status(
        app, ApplicationStatus.DELIVERED,
        changed_by=request.user,
        note=identity_note or _('Document delivered. OTP verified.'),
    )

    messages.success(request, _(f'Document delivered successfully to {app.student_name}.'))
    return redirect('coe_delivery_dashboard')


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 9 — EXPORT & SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

@require_access('coe', 'export_data')
def export_excel(request):
    """Export filtered application data to .xlsx using openpyxl."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    form = ApplicationSearchForm(request.GET or None)
    qs = DocumentApplication.objects.select_related('department', 'assigned_to').all()

    if form.is_valid():
        q = form.cleaned_data.get('q')
        status = form.cleaned_data.get('status')
        app_type = form.cleaned_data.get('application_type')
        dept = form.cleaned_data.get('department')
        date_from = form.cleaned_data.get('date_from')   # MINOR-3 FIX
        date_to = form.cleaned_data.get('date_to')       # MINOR-3 FIX

        if q:
            qs = qs.filter(
                Q(application_number__icontains=q) | Q(student_name__icontains=q)
                | Q(student_id__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if app_type:
            qs = qs.filter(application_type=app_type)
        if dept:
            qs = qs.filter(department=dept)
        if date_from:                                     # MINOR-3 FIX
            qs = qs.filter(submitted_at__date__gte=date_from)
        if date_to:                                       # MINOR-3 FIX
            qs = qs.filter(submitted_at__date__lte=date_to)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'CoE Applications'

    header_fill = PatternFill('solid', fgColor='1F4E79')
    header_font = Font(color='FFFFFF', bold=True, size=11)
    headers = [
        'Application #', 'Type', 'Status', 'Student Name', 'Student ID',
        'Mobile', 'Department', 'Session', 'Batch', 'CGPA',
        'Assigned To', 'Submitted At', 'Updated At',
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    for row, app in enumerate(qs, 2):
        ws.append([
            app.application_number,
            app.get_application_type_display(),
            app.get_status_display(),
            app.student_name,
            app.student_id,
            app.mobile_number,
            str(app.department),
            app.session,
            app.admission_batch,
            str(app.cgpa),
            app.assigned_to.get_full_name() if app.assigned_to else '',
            app.submitted_at.strftime('%Y-%m-%d %H:%M') if app.submitted_at else '',
            app.updated_at.strftime('%Y-%m-%d %H:%M') if app.updated_at else '',
        ])

    for col in ws.columns:
        max_len = max((len(str(cell.value or '')) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="coe_applications.xlsx"'
    wb.save(response)
    return response


@require_access('coe', 'manage_settings')
def coe_settings_view(request):
    """CoE module configuration — singleton settings & role designations."""
    from master_data.models import Program
    from .models import CoeAssignmentRule, ApplicationType, CoeUserRoleAssignment, CoeRoleType
    from .utils import get_coe_processing_officers, get_coe_module_candidate_users
    
    settings_obj = CoeSettings.get_settings()
    candidate_users = get_coe_module_candidate_users()
    officers = get_coe_processing_officers()
    departments = Program.objects.all().order_by('short_name')

    if request.method == 'POST':
        form = CoeSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            
            # 1. Process Auto-Assignment Type Rules
            for app_type_code, app_label in ApplicationType.choices:
                officer_id = request.POST.get(f'rule_{app_type_code}')
                if officer_id:
                   CoeAssignmentRule.objects.update_or_create(
                       application_type=app_type_code,
                       defaults={'officer_id': officer_id}
                   )
                else:
                   CoeAssignmentRule.objects.filter(application_type=app_type_code).delete()

            # 2. Process Multi-Account Role Assignments
            # Global Roles: Controller, DCoE, Officer, Clerk
            global_roles = [
                (CoeRoleType.CONTROLLER, 'role_controller'),
                (CoeRoleType.DEPUTY_CONTROLLER, 'role_dcoe'),
                (CoeRoleType.PROCESSING_OFFICER, 'role_officer'),
                (CoeRoleType.DELIVERY_CLERK, 'role_clerk'),
            ]
            for role_type, post_param in global_roles:
                selected_ids = [int(uid) for uid in request.POST.getlist(post_param) if uid.isdigit()]
                # Sync: Delete existing assignments for role and re-create
                CoeUserRoleAssignment.objects.filter(role_type=role_type, department__isnull=True).delete()
                for uid in selected_ids:
                    CoeUserRoleAssignment.objects.create(role_type=role_type, user_id=uid)

            # Department HoD Roles
            for dept in departments:
                param_name = f'role_hod_{dept.id}'
                selected_ids = [int(uid) for uid in request.POST.getlist(param_name) if uid.isdigit()]
                CoeUserRoleAssignment.objects.filter(role_type=CoeRoleType.HOD, department=dept).delete()
                for uid in selected_ids:
                    CoeUserRoleAssignment.objects.create(role_type=CoeRoleType.HOD, user_id=uid, department=dept)
            
            messages.success(request, _('CoE settings & role assignments updated successfully.'))
            return redirect('coe_settings')
    else:
        form = CoeSettingsForm(instance=settings_obj)

    # Context Data Building
    current_rules = {rule.application_type: rule.officer_id for rule in CoeAssignmentRule.objects.all()}
    app_type_rules = []
    for code, label in ApplicationType.choices:
        app_type_rules.append({
            'code': code,
            'label': label,
            'assigned_officer_id': current_rules.get(code),
        })

    # Group Current Role Assignments
    role_assignments = {
        'controller': set(CoeUserRoleAssignment.objects.filter(role_type=CoeRoleType.CONTROLLER).values_list('user_id', flat=True)),
        'dcoe':       set(CoeUserRoleAssignment.objects.filter(role_type=CoeRoleType.DEPUTY_CONTROLLER).values_list('user_id', flat=True)),
        'officer':    set(CoeUserRoleAssignment.objects.filter(role_type=CoeRoleType.PROCESSING_OFFICER).values_list('user_id', flat=True)),
        'clerk':      set(CoeUserRoleAssignment.objects.filter(role_type=CoeRoleType.DELIVERY_CLERK).values_list('user_id', flat=True)),
    }

    dept_hod_map = {}
    for dept in departments:
        assigned_ids = set(CoeUserRoleAssignment.objects.filter(role_type=CoeRoleType.HOD, department=dept).values_list('user_id', flat=True))
        dept.assigned_hod_ids = assigned_ids
        dept_hod_map[dept.id] = assigned_ids

    return render(request, 'coe/settings.html', {
        'form': form, 
        'settings_obj': settings_obj,
        'officers': officers,
        'candidate_users': candidate_users,
        'departments': departments,
        'app_type_rules': app_type_rules,
        'role_assignments': role_assignments,
        'dept_hod_map': dept_hod_map,
    })


@require_access('coe', 'manage_settings')
def test_coe_email(request):
    """AJAX endpoint to test dynamic SMTP email dispatch."""
    if request.method == 'POST':
        import json
        from django.http import JsonResponse
        try:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                data = request.POST
            recipient = data.get('email', '').strip()
            if not recipient:
                return JsonResponse({'success': False, 'message': _('Recipient email address is required.')}, status=400)

            from .utils import send_coe_email
            success = send_coe_email(
                recipient_email=recipient,
                subject="[BAUST CoE] Test Email Gateway Verification",
                template_name='coe/emails/status_update_email.html',
                context={
                    'app': {
                        'student_name': 'Test Recipient',
                        'application_number': 'COED-TEST-2026',
                        'student_id': '20260001',
                        'department': 'Controller of Examinations',
                        'get_application_type_display': 'SMTP Gateway Test Verification',
                        'get_status_display': 'SMTP Connection Verified Successfully',
                    },
                    'event': 'submit',
                    'custom_message': 'This test notification email confirms that your BAUST Controller of Examinations SMTP server settings are correctly configured and working!',
                }
            )
            if success:
                return JsonResponse({'success': True, 'message': _('Test email dispatched successfully to ') + recipient})
            else:
                return JsonResponse({'success': False, 'message': _('SMTP Error: Could not connect to mail server. Please verify your SMTP Host, Port, Username, and Password in settings.')}, status=500)
        except Exception as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)


# ═══════════════════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_required_attachments(app_type: str) -> list[dict]:
    """Return the list of required attachment dicts (with key and label) for a given application type."""
    fc = {'key': 'final_clearance', 'label': _('Final Clearance')}
    ps = {'key': 'payment_slip', 'label': _('Payment Slip')}
    ssc = {'key': 'ssc_cert', 'label': _('SSC/HSC Certificate OR NID Photocopy')}
    ol = {'key': 'offer_letter', 'label': _('Offer Letter (Printed Copy)')}
    bmc = {'key': 'baust_mc', 'label': _('BAUST Originals (MCE, MoI, MC, TS)')}
    c_ssc = {'key': 'ssc_cert', 'label': _('Corrected SSC/HSC Certificate / Online Copy')}
    md = {'key': 'missing_doc_copy', 'label': _('Missing Document Copy')}
    gd = {'key': 'gd_copy', 'label': _('General Diary (GD) Copy')}

    mapping = {
        ApplicationType.MAIN_CERTIFICATE:       [fc, ps, ol],
        ApplicationType.PROVISIONAL_TRANSCRIPT: [fc, ps, ssc],
        ApplicationType.INCOMPLETE_TRANSCRIPT:  [fc, ps, ssc],
        ApplicationType.NAME_CORRECTION:         [fc, c_ssc, bmc],
        ApplicationType.PARENT_NAME_CORRECTION:  [fc, c_ssc, bmc],
        ApplicationType.RECOMMENDATION_LETTER:  [fc, ps],
        ApplicationType.GRADE_SHEET:            [fc, ps],
        ApplicationType.DUPLICATE_DOCUMENT:     [md, gd, ps],
    }
    return mapping.get(app_type, [fc, ps])


def _get_type_specific_fields(app_type: str) -> list[dict]:
    """Return the list of extra field descriptors for a given application type."""
    common = [
        {'name': 'session', 'label': 'Session', 'type': 'text', 'required': True},
        {'name': 'passing_semester', 'label': 'Passing Semester', 'type': 'text', 'required': True},
        {'name': 'cgpa', 'label': 'CGPA', 'type': 'number', 'required': True, 'step': '0.01', 'min': '0', 'max': '4'},
        {'name': 'result_date', 'label': 'Result Publication Date', 'type': 'date', 'required': False},
    ]
    parent_fields = [
        {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
        {'name': 'mother_name', 'label': "Mother's Name", 'type': 'text', 'required': True},
        {'name': 'dob', 'label': 'Date of Birth', 'type': 'date', 'required': True},
    ]
    mapping = {
        ApplicationType.MAIN_CERTIFICATE:       common,
        ApplicationType.PROVISIONAL_TRANSCRIPT: parent_fields + common,
        ApplicationType.INCOMPLETE_TRANSCRIPT:  parent_fields + common,
        ApplicationType.NAME_CORRECTION: common + [
            {'name': 'corrected_name', 'label': 'Corrected Full Name', 'type': 'text', 'required': True},
            {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
            {'name': 'mother_name', 'label': "Mother's Name", 'type': 'text', 'required': True},
        ],
        ApplicationType.PARENT_NAME_CORRECTION: common + [
            {'name': 'corrected_parent_name', 'label': 'Corrected Parent Name', 'type': 'text', 'required': True},
            {'name': 'father_name', 'label': "Father's Name", 'type': 'text', 'required': True},
            {'name': 'mother_name', 'label': "Mother's Name", 'type': 'text', 'required': True},
        ],
        ApplicationType.RECOMMENDATION_LETTER: common + [
            {'name': 'purpose_destination', 'label': 'Purpose / Destination', 'type': 'textarea', 'required': True},
        ],
        ApplicationType.GRADE_SHEET: common + [
            {'name': 'level_term', 'label': 'Level / Term', 'type': 'text', 'required': True},
        ],
        ApplicationType.DUPLICATE_DOCUMENT: common + [
            {'name': 'level_term', 'label': 'Level / Term', 'type': 'text', 'required': True},
            {'name': 'missing_doc_type', 'label': 'Type of Missing Document', 'type': 'text', 'required': True},
        ],
    }
    return mapping.get(app_type, common)


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 1–5 — ENHANCED ENGINES (Public QR Verify, PDF Exports, Re-Upload, Register)
# ═══════════════════════════════════════════════════════════════════════════════

def verify_document_public(request, tracking_number):
    """
    Public QR Verification Portal.
    Non-authenticated. Anyone scanning the QR code or visiting URL
    verifies the official authenticity of a delivered BAUST academic document.
    """
    app = DocumentApplication.all_objects.filter(application_number__iexact=tracking_number).first()
    qr_url = request.build_absolute_uri()
    qr_base64 = generate_qr_code_base64(qr_url)

    return render(request, 'coe/verify_public.html', {
        'app': app,
        'tracking_number': tracking_number,
        'qr_base64': qr_base64,
        'verify_url': qr_url,
    })


def student_reupload_portal(request):
    """
    Public portal for students in ACTION_REQUIRED status to re-upload missing documents.
    Authenticates via Tracking ID + PIN.
    """
    app = None
    error = None
    success_msg = None

    if request.method == 'POST':
        action = request.POST.get('action')
        tracking_number = request.POST.get('tracking_number', '').strip()
        pin = request.POST.get('pin', '').strip()

        if action == 'auth' or action == 'reupload':
            app = DocumentApplication.all_objects.filter(
                application_number__iexact=tracking_number,
                tracking_pin=pin,
            ).first()

            if not app:
                error = _('Invalid Tracking Number or PIN. Please check your credentials.')
            elif app.status not in [ApplicationStatus.ACTION_REQUIRED, ApplicationStatus.IN_PROCESSING]:
                error = _(f'Application is currently in status "{app.get_status_display()}". Re-upload is only allowed for applications in "Action Required" or "In Processing" status.')

        if action == 'reupload' and app and not error:
            if not request.FILES:
                error = _('Please select at least one file to re-upload.')
            else:
                cfg = CoeSettings.get_settings()
                valid_types = dict(ApplicationAttachment.attachment_type.field.choices)
                count = 0
                for field_name, f in request.FILES.items():
                    ok, err_msg = _validate_attachment(f, cfg.attachment_max_mb)
                    if not ok:
                        error = f"{f.name}: {err_msg}"
                        break
                    sha = compute_sha256(f)
                    att_type = field_name if field_name in valid_types else 'other'
                    ApplicationAttachment.objects.create(
                        application=app,
                        attachment_type=att_type,
                        file=f,
                        sha256_hash=sha,
                        original_filename=f.name,
                        file_size_kb=f.size // 1024,
                    )
                    count += 1

                if not error:
                    officer_str = app.assigned_to.get_full_name() or app.assigned_to.username if app.assigned_to else ''
                    note_msg = _(f'Student re-uploaded corrected document(s) via public portal. Assigned officer: {officer_str}') if officer_str else _('Student re-uploaded corrected document(s) via public portal.')
                    transition_status(
                        app, ApplicationStatus.IN_PROCESSING,
                        note=note_msg,
                        send_sms_key='reupload_complete',
                        sms_context={'tracking_number': app.application_number},
                    )
                    success_msg = _(f'Successfully uploaded {count} file(s). Your application is back in processing.')
                    app = None  # reset app view after success

    cfg = CoeSettings.get_settings()
    return render(request, 'coe/reupload_portal.html', {
        'app': app,
        'error': error,
        'success_msg': success_msg,
        'max_mb': cfg.attachment_max_mb,
    })


def download_receipt_pdf(request, pk):
    """Generate and serve student submission receipt PDF with embedded QR code.

    BUG-4 FIX: Access control —
      - Authenticated staff: always allowed.
      - Unauthenticated (student self-service): must supply ?pin=XXXX matching tracking_pin.
    """
    app = get_object_or_404(DocumentApplication, pk=pk)

    if not request.user.is_authenticated:
        supplied_pin = request.GET.get('pin', '').strip()
        if not supplied_pin or supplied_pin != app.tracking_pin:
            from django.http import Http404
            raise Http404
    verify_url = request.build_absolute_uri(f"/coe/verify/{app.application_number}/")
    qr_base64 = generate_qr_code_base64(verify_url)

    pdf_bytes = render_to_pdf_bytes('coe/pdf/student_receipt.html', {
        'app': app,
        'qr_base64': qr_base64,
        'verify_url': verify_url,
        'now': timezone.now(),
    })

    if not pdf_bytes:
        return HttpResponse('Failed to generate PDF receipt', status=500)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="receipt_{app.application_number}.pdf"'
    return response


@require_access('coe', 'processing_officer')
def download_routing_slip_pdf(request, pk):
    """Generate CoE staff internal routing slip PDF for physical document processing folders."""
    app = get_object_or_404(DocumentApplication, pk=pk)
    verify_url = request.build_absolute_uri(f"/coe/verify/{app.application_number}/")
    qr_base64 = generate_qr_code_base64(verify_url)

    pdf_bytes = render_to_pdf_bytes('coe/pdf/staff_routing_slip.html', {
        'app': app,
        'qr_base64': qr_base64,
        'attachments': app.attachments.all(),
        'logs': app.status_logs.order_by('changed_at'),
        'verification': getattr(app, 'verification', None),
        'now': timezone.now(),
    })

    if not pdf_bytes:
        return HttpResponse('Failed to generate routing slip PDF', status=500)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="routing_slip_{app.application_number}.pdf"'
    return response


@require_access('coe', 'delivery_desk')
def delivery_handover_register(request):
    """Printable daily delivery register with physical student signature column."""
    date_str = request.GET.get('date')
    if date_str:
        try:
            from datetime import datetime as _dt
            target_date = _dt.strptime(date_str, '%Y-%m-%d').date()  # MINOR-4 FIX: timezone has no .datetime
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    applications = DocumentApplication.objects.filter(
        status=ApplicationStatus.DELIVERED,
        delivered_at__date=target_date,
    ).select_related('department', 'delivered_by').order_by('delivered_at')

    return render(request, 'coe/delivery_handover_register.html', {
        'applications': applications,
        'target_date': target_date,
        'count': applications.count(),
    })


@require_access('coe', 'view_all_applications')
def reports_dashboard(request):
    """
    Renders the CoE reports and analytics dashboard.
    Calculates overview KPIs, SLA metrics, officer throughput, funnel conversion, and department stats.
    """
    import datetime
    from django.db.models import Avg, Count, Q, F, ExpressionWrapper, DurationField
    from django.utils.dateparse import parse_date
    from django.contrib.auth.models import User
    from master_data.models import Program

    # 1. Fetch available filter choices
    departments = Program.objects.all().order_by('name')
    officers = User.objects.filter(is_active=True, is_staff=True).order_by('first_name', 'last_name')
    if not officers.exists():
        officers = User.objects.filter(is_active=True).order_by('username')
        
    app_types = ApplicationType.choices

    # 2. Get query parameters
    q_date_from = request.GET.get('date_from')
    q_date_to = request.GET.get('date_to')
    q_dept = request.GET.get('department')
    q_type = request.GET.get('application_type')
    q_officer = request.GET.get('assigned_to')
    preset = request.GET.get('preset', '')

    # Handle presets
    today = timezone.localdate()
    if preset == 'today':
        q_date_from = today.strftime('%Y-%m-%d')
        q_date_to = today.strftime('%Y-%m-%d')
    elif preset == '7days':
        q_date_from = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        q_date_to = today.strftime('%Y-%m-%d')
    elif preset == '30days':
        q_date_from = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        q_date_to = today.strftime('%Y-%m-%d')
    elif preset == 'this_month':
        q_date_from = today.replace(day=1).strftime('%Y-%m-%d')
        q_date_to = today.strftime('%Y-%m-%d')

    # Build filters
    filters = Q()
    if q_date_from:
        parsed_from = parse_date(q_date_from)
        if parsed_from:
            dt_from = timezone.make_aware(datetime.datetime.combine(parsed_from, datetime.time.min))
            filters &= Q(submitted_at__gte=dt_from)
    if q_date_to:
        parsed_to = parse_date(q_date_to)
        if parsed_to:
            dt_to = timezone.make_aware(datetime.datetime.combine(parsed_to, datetime.time.max))
            filters &= Q(submitted_at__lte=dt_to)
    if q_dept:
        filters &= Q(department_id=q_dept)
    if q_type:
        filters &= Q(application_type=q_type)
    if q_officer:
        filters &= Q(assigned_to_id=q_officer)

    # 3. Base Querysets
    qs_all = DocumentApplication.objects.filter(filters)
    
    # 4. KPI Calcs
    total_apps = qs_all.count()
    completed_apps_qs = qs_all.filter(status__in=[ApplicationStatus.READY_FOR_DELIVERY, ApplicationStatus.DELIVERED])
    completed_count = completed_apps_qs.count()
    
    # Average Resolution Time (TAT)
    avg_tat_str = "N/A"
    completed_with_dates = completed_apps_qs.filter(delivered_at__isnull=False)
    if completed_with_dates.exists():
        tat_agg = completed_with_dates.annotate(
            tat=ExpressionWrapper(F('delivered_at') - F('submitted_at'), output_field=DurationField())
        ).aggregate(Avg('tat'))
        avg_delta = tat_agg['tat__avg']
        if avg_delta:
            days = avg_delta.days
            hours, remainder = divmod(avg_delta.seconds, 3600)
            if days > 0:
                avg_tat_str = f"{days}d {hours}h"
            else:
                avg_tat_str = f"{hours}h"
    
    # SLA Compliance rate (Target <= 72 hours)
    sla_hours = 72
    sla_compliant_count = 0
    sla_compliance_rate = 0.0
    if completed_with_dates.exists():
        all_completed = list(completed_with_dates.only('submitted_at', 'delivered_at'))
        for app in all_completed:
            delta = app.delivered_at - app.submitted_at
            if delta.total_seconds() <= (sla_hours * 3600):
                sla_compliant_count += 1
        if len(all_completed) > 0:
            sla_compliance_rate = round((sla_compliant_count / len(all_completed)) * 100, 1)

    # Stalled applications (> 48 hours in active states)
    active_statuses = [
        ApplicationStatus.UNDER_HOD_REVIEW,
        ApplicationStatus.PENDING_COE_ASSIGNMENT,
        ApplicationStatus.IN_PROCESSING,
        ApplicationStatus.ACTION_REQUIRED,
        ApplicationStatus.DISPATCHED_TO_DELIVERY,
        ApplicationStatus.RECEIVED_BY_CLERK,
    ]
    cutoff_stalled = timezone.now() - datetime.timedelta(hours=48)
    stalled_qs = qs_all.filter(status__in=active_statuses, updated_at__lt=cutoff_stalled)
    stalled_count = stalled_qs.count()

    # 5. Report 1: Processing Time by Application Type
    type_tat_data = []
    type_completed_list = completed_with_dates.only('application_type', 'submitted_at', 'delivered_at')
    type_times = {}
    for app in type_completed_list:
        delta = app.delivered_at - app.submitted_at
        if app.application_type not in type_times:
            type_times[app.application_type] = []
        type_times[app.application_type].append(delta.total_seconds() / 3600.0) # in hours
    
    for t_val, t_lbl in ApplicationType.choices:
        t_hours = type_times.get(t_val, [])
        avg_h = round(sum(t_hours) / len(t_hours), 1) if t_hours else 0.0
        type_tat_data.append({
            'type_val': t_val,
            'type_display': str(t_lbl),
            'avg_hours': avg_h
        })
    type_tat_data = sorted(type_tat_data, key=lambda x: x['avg_hours'], reverse=True)

    # Report 3: Departmental Request Share
    dept_chart = list(
        qs_all.values('department__name', 'department__short_name')
              .annotate(count=Count('id'))
              .order_by('-count')
    )
    dept_chart_formatted = []
    for item in dept_chart:
        name = item['department__short_name'] or item['department__name'] or 'Unknown'
        dept_chart_formatted.append({
            'label': name,
            'count': item['count']
        })

    # Report 4: Funnel & Stalled list
    f_total = total_apps
    f_approved = qs_all.exclude(status=ApplicationStatus.SUBMITTED).count()
    f_assigned = qs_all.exclude(status__in=[ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_HOD_REVIEW, ApplicationStatus.PENDING_COE_ASSIGNMENT]).count()
    f_ready = qs_all.filter(status__in=[ApplicationStatus.READY_FOR_DELIVERY, ApplicationStatus.DELIVERED]).count()
    f_delivered = qs_all.filter(status=ApplicationStatus.DELIVERED).count()

    funnel_stages = [
        {'stage': 'Submitted', 'count': f_total},
        {'stage': 'HOD Approved', 'count': f_approved},
        {'stage': 'Assigned', 'count': f_assigned},
        {'stage': 'Ready for Delivery', 'count': f_ready},
        {'stage': 'Delivered', 'count': f_delivered},
    ]

    stalled_list = []
    for app in stalled_qs.select_related('department', 'assigned_to').order_by('updated_at')[:10]:
        last_log = app.status_logs.order_by('-changed_at').first()
        start_time = last_log.changed_at if last_log else app.submitted_at
        delta = timezone.now() - start_time
        stalled_list.append({
            'app': app,
            'days': delta.days,
            'hours': int(delta.seconds / 3600) % 24,
        })

    # Report 2: Officer Workload & Speed Leaderboard
    assigned_officers_ids = DocumentApplication.objects.values_list('assigned_to_id', flat=True).distinct()
    assigned_users = User.objects.filter(id__in=assigned_officers_ids, is_active=True)
    
    officer_leaderboard = []
    for user in assigned_users:
        user_fullname = user.get_full_name() or user.username
        
        active_queue = qs_all.filter(
            assigned_to=user,
            status__in=[ApplicationStatus.IN_PROCESSING, ApplicationStatus.ACTION_REQUIRED]
        ).count()
        
        completed_count_user = qs_all.filter(
            assigned_to=user,
            status__in=[ApplicationStatus.READY_FOR_DELIVERY, ApplicationStatus.DELIVERED]
        ).count()
        
        completed_apps_user = qs_all.filter(
            assigned_to=user,
            status__in=[ApplicationStatus.READY_FOR_DELIVERY, ApplicationStatus.DELIVERED]
        )
        
        tot_seconds = 0
        valid_apps = 0
        for app in completed_apps_user:
            log_assigned = app.status_logs.filter(new_status=ApplicationStatus.IN_PROCESSING).first()
            start_t = log_assigned.changed_at if log_assigned else app.submitted_at
            end_t = app.delivered_at if app.delivered_at else app.updated_at
            
            if end_t and start_t:
                tot_seconds += (end_t - start_t).total_seconds()
                valid_apps += 1
                
        avg_speed_days = round((tot_seconds / valid_apps) / 86400.0, 1) if valid_apps > 0 else 0.0
        
        reuploads_requested = ApplicationStatusLog.objects.filter(
            application__assigned_to=user,
            new_status=ApplicationStatus.ACTION_REQUIRED
        ).values('application_id').distinct().count()
        
        total_worked_on = qs_all.filter(assigned_to=user).count()
        return_rate = round((reuploads_requested / total_worked_on) * 100, 1) if total_worked_on > 0 else 0.0

        officer_leaderboard.append({
            'name': user_fullname,
            'active_queue': active_queue,
            'completed': completed_count_user,
            'avg_speed': avg_speed_days,
            'return_rate': return_rate
        })
    
    officer_leaderboard = sorted(officer_leaderboard, key=lambda x: (x['completed'], -x['avg_speed']), reverse=True)

    # Report 5: Live Feed & Daily Throughput
    today_submitted = DocumentApplication.objects.filter(submitted_at__date=today).count()
    today_delivered = DocumentApplication.objects.filter(status=ApplicationStatus.DELIVERED, delivered_at__date=today).count()
    today_ready = DocumentApplication.objects.filter(status=ApplicationStatus.READY_FOR_DELIVERY, updated_at__date=today).count()
    today_outflow = today_delivered + today_ready

    recent_logs = ApplicationStatusLog.objects.select_related('application', 'changed_by').order_by('-changed_at')[:10]

    # Area chart: Inflow vs Outflow over past 7 days
    trend_labels = []
    trend_submissions = []
    trend_completions = []
    
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        trend_labels.append(d.strftime('%b %d'))
        sub_c = DocumentApplication.objects.filter(submitted_at__date=d).count()
        trend_submissions.append(sub_c)
        
        comp_c = DocumentApplication.objects.filter(
            Q(status=ApplicationStatus.DELIVERED, delivered_at__date=d) |
            Q(status=ApplicationStatus.READY_FOR_DELIVERY, updated_at__date=d)
        ).count()
        trend_completions.append(comp_c)

    return render(request, 'coe/reports.html', {
        'departments': departments,
        'officers': officers,
        'app_types': app_types,
        'q_date_from': q_date_from or '',
        'q_date_to': q_date_to or '',
        'q_dept': q_dept or '',
        'q_type': q_type or '',
        'q_officer': q_officer or '',
        'preset': preset,
        
        'total_apps': total_apps,
        'completed_count': completed_count,
        'avg_tat_str': avg_tat_str,
        'sla_compliance_rate': sla_compliance_rate,
        'stalled_count': stalled_count,
        
        'officer_leaderboard': officer_leaderboard,
        'stalled_list': stalled_list,
        'recent_logs': recent_logs,
        
        'type_tat_json': json.dumps(type_tat_data),
        'dept_chart_json': json.dumps(dept_chart_formatted),
        'funnel_json': json.dumps(funnel_stages),
        'trend_json': json.dumps({
            'labels': trend_labels,
            'submissions': trend_submissions,
            'completions': trend_completions
        }),
        'today_submitted': today_submitted,
        'today_outflow': today_outflow,
        'ApplicationStatus': ApplicationStatus,
    })


def _validate_attachment(file_obj, max_mb: int) -> tuple[bool, str]:
    """Validate file extension and size."""
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
    import os
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in allowed_extensions:
        return False, f"File type '{ext}' is not allowed. Accepted: PDF, JPG, PNG, WEBP."
    max_bytes = max_mb * 1024 * 1024
    if file_obj.size > max_bytes:
        return False, f"File size {file_obj.size // 1024} KB exceeds {max_mb} MB limit."
    return True, ''
