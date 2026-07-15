from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages
from core.decorators import require_access
from .forms import DeviceRegistrationForm
from .models import DeviceRegistration

def register_device(request):
    """
    Public MAC address registration form.
    Does not require authentication.
    """
    if request.method == 'POST':
        form = DeviceRegistrationForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            # Standardize MAC address separator and case
            mac = form.cleaned_data['mac_address'].strip().replace('-', ':').upper()
            device.mac_address = mac
            device.status = 'pending'
            device.save()
            return redirect('registration_success', pk=device.pk)
    else:
        form = DeviceRegistrationForm()
        
    return render(request, 'ict_wing/register.html', {'form': form})

def registration_success(request, pk):
    """Shows success confirmation page."""
    device = get_object_or_404(DeviceRegistration, pk=pk)
    return render(request, 'ict_wing/success.html', {'device': device})

@require_access('ict_wing', 'view_devices')
def manage_devices(request):
    """
    ICT Wing dashboard to browse and filter device registrations.
    Visible only to users with 'view_devices' task permission in RBAC.
    """
    # Fetch filters from request
    status = request.GET.get('status', '')
    user_type = request.GET.get('user_type', '')
    dept = request.GET.get('department', '')
    search = request.GET.get('search', '').strip()

    # Base Queryset
    devices = DeviceRegistration.objects.all()

    # Apply Filters
    if status:
        devices = devices.filter(status=status)
    if user_type:
        devices = devices.filter(user_type=user_type)
    if dept:
        devices = devices.filter(department__iexact=dept)
    if search:
        devices = devices.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search) |
            Q(mac_address__icontains=search) |
            Q(designation_or_roll__icontains=search)
        )

    # Get unique departments list for filter dropdown
    departments = DeviceRegistration.objects.values_list('department', flat=True).distinct().order_by('department')
    
    # Check if user is allowed to edit/approve devices for UI control
    can_manage = False
    if request.user.is_superuser:
        can_manage = True
    elif hasattr(request.user, 'profile') and request.user.profile.has_access('ict_wing', 'manage_devices'):
        can_manage = True

    # Count multiple registrations per phone number
    phone_counts = {}
    for p in DeviceRegistration.objects.values_list('phone', flat=True):
        phone_counts[p] = phone_counts.get(p, 0) + 1
        
    for dev in devices:
        dev.phone_device_count = phone_counts.get(dev.phone, 1)


    context = {
        'devices': devices,
        'departments': departments,
        'selected_status': status,
        'selected_user_type': user_type,
        'selected_dept': dept,
        'search_query': search,
        'can_manage': can_manage,
    }
    return render(request, 'ict_wing/manage.html', context)

@require_access('ict_wing', 'manage_devices')
def approve_device(request, pk):
    """
    POST View to approve a device and bind it in the network.
    """
    if request.method == 'POST':
        device = get_object_or_404(DeviceRegistration, pk=pk)
        assigned_ip = request.POST.get('assigned_ip', '').strip()
        admin_notes = request.POST.get('admin_notes', '').strip()

        device.status = 'approved'
        if assigned_ip:
            device.assigned_ip = assigned_ip
        if admin_notes:
            device.admin_notes = admin_notes
        device.save()

        messages.success(request, f"Device for {device.full_name} has been approved and binded.")
    return redirect('manage_devices')

@require_access('ict_wing', 'manage_devices')
def reject_device(request, pk):
    """
    POST View to reject a device.
    """
    if request.method == 'POST':
        device = get_object_or_404(DeviceRegistration, pk=pk)
        admin_notes = request.POST.get('admin_notes', '').strip()

        device.status = 'rejected'
        if admin_notes:
            device.admin_notes = admin_notes
        device.save()

        messages.warning(request, f"Device for {device.full_name} has been rejected.")
    return redirect('manage_devices')

def check_device_status(request):
    """
    Public device status checking portal.
    Allows searching by Reference ID (e.g. 1 or DR-00001), MAC Address, or Phone Number.
    """
    query = request.GET.get('query', '').strip()
    devices = None
    searched = False
    error = None

    if query:
        searched = True
        ref_id = None
        # Try parsing reference ID e.g. 1, 00001, DR-00001, or DR-1 (but avoid phone number matching)
        if query.isdigit() and len(query) < 10:
            ref_id = int(query)
        elif query.upper().startswith('DR-'):
            try:
                ref_id = int(query.upper().split('DR-')[-1])
            except ValueError:
                pass
        
        # Clean query for phone checking: strip +88 or 88
        cleaned_phone = query
        if cleaned_phone.startswith('+88'):
            cleaned_phone = cleaned_phone[3:]
        elif cleaned_phone.startswith('88'):
            cleaned_phone = cleaned_phone[2:]
        
        filters = Q(mac_address__iexact=query.replace('-', ':').upper())
        if ref_id is not None:
            filters |= Q(pk=ref_id)
        if cleaned_phone.isdigit() and len(cleaned_phone) == 11 and cleaned_phone.startswith('01'):
            filters |= Q(phone=cleaned_phone)
            
        try:
            devices = DeviceRegistration.objects.filter(filters)
            if not devices.exists():
                error = "No registration records found for this query. Double-check your Reference ID, MAC Address, or Mobile Number."
        except Exception:
            error = "An error occurred while processing your search."
            
    return render(request, 'ict_wing/status.html', {
        'query': query,
        'devices': devices,
        'searched': searched,
        'error': error
    })
