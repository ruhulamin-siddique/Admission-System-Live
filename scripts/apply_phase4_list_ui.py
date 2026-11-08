import os

LIST_PATH = r"templates\students\list.html"

with open(LIST_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update z-index from 99999 to 1025 on #bulk-action-bar and add Export Selected Excel button
old_bar = """<div id="bulk-action-bar" style="position: fixed; bottom: -120px; left: 50%; transform: translateX(-50%); z-index: 99999; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); background: linear-gradient(135deg, #0f172a, #1e293b); padding: 12px 24px; border-radius: 50px; display: flex; align-items: center; gap: 12px; max-width: 95vw; width: max-content; border: 1px solid rgba(56, 189, 248, 0.4); box-shadow: 0 20px 40px rgba(0,0,0,0.5); visibility: hidden; opacity: 0;">"""
old_bar_crlf = old_bar.replace("\n", "\r\n")

new_bar = """<div id="bulk-action-bar" style="position: fixed; bottom: -120px; left: 50%; transform: translateX(-50%); z-index: 1025; transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); background: linear-gradient(135deg, #0f172a, #1e293b); padding: 10px 22px; border-radius: 50px; display: flex; align-items: center; gap: 10px; max-width: 95vw; width: max-content; border: 1px solid rgba(56, 189, 248, 0.4); box-shadow: 0 15px 35px rgba(0,0,0,0.45); visibility: hidden; opacity: 0;">"""

if old_bar in content:
    content = content.replace(old_bar, new_bar, 1)
    print("Fixed #bulk-action-bar z-index to 1025")
elif old_bar_crlf in content:
    content = content.replace(old_bar_crlf, new_bar.replace("\n", "\r\n"), 1)
    print("Fixed #bulk-action-bar z-index with CRLF")
else:
    raise ValueError("bulk-action-bar marker not found")

# Add Export to Excel button inside #bulk-action-bar before Clear Selection button
old_clear_btn = """    <button class="btn btn-outline-light border-0 rounded-circle ml-1" style="width: 32px; height: 32px; padding: 0; line-height: 32px; background: rgba(255,255,255,0.1);" onclick="clearSelection()" title="Clear Selection">"""
old_clear_btn_crlf = old_clear_btn.replace("\n", "\r\n")

excel_btn = """    {% has_access 'students' 'export_excel' as can_export_sel %}
    {% if can_export_sel %}
    <button class="btn btn-primary font-weight-black rounded-pill px-3 px-md-4 shadow-sm" onclick="exportSelectedExcel()" title="Export Selected to Excel">
        <i class="fas fa-file-excel mr-1"></i> <span class="d-none d-md-inline">Export Excel</span>
    </button>
    {% endif %}

    <button class="btn btn-outline-light border-0 rounded-circle ml-1" style="width: 32px; height: 32px; padding: 0; line-height: 32px; background: rgba(255,255,255,0.1);" onclick="clearSelection()" title="Clear Selection">"""

if old_clear_btn in content:
    content = content.replace(old_clear_btn, excel_btn, 1)
    print("Export Selected button added to #bulk-action-bar")
elif old_clear_btn_crlf in content:
    content = content.replace(old_clear_btn_crlf, excel_btn.replace("\n", "\r\n"), 1)
    print("Export Selected button added to #bulk-action-bar with CRLF")
else:
    raise ValueError("Clear selection button marker not found")

# 2. Add Filter Chips bar right above <div id="directory-results">
results_marker = '    <div id="directory-results">'
results_marker_crlf = '    <div id="directory-results">'

chips_html = """    <!-- ─── Active Filter Chips Bar ─── -->
    {% if selected_year or selected_dept or selected_program or selected_batch or selected_gender or selected_status %}
    <div id="active-filter-chips-bar" class="px-3 py-2 bg-light border-bottom d-flex align-items-center flex-wrap" style="gap: 8px; font-size: 0.8rem;">
        <span class="font-weight-bold text-muted mr-1"><i class="fas fa-filter text-primary mr-1"></i>Active:</span>
        {% if selected_year %}
        <span class="badge badge-primary px-2.5 py-1.5 rounded-pill font-weight-bold">
            Year: {{ selected_year }} <a href="javascript:void(0)" onclick="removeDirectoryFilter('year')" class="text-white ml-1 font-weight-bold">✕</a>
        </span>
        {% endif %}
        {% if selected_dept %}
        <span class="badge badge-info px-2.5 py-1.5 rounded-pill font-weight-bold">
            Cluster: {{ selected_dept }} <a href="javascript:void(0)" onclick="removeDirectoryFilter('dept')" class="text-white ml-1 font-weight-bold">✕</a>
        </span>
        {% endif %}
        {% if selected_program %}
        <span class="badge badge-success px-2.5 py-1.5 rounded-pill font-weight-bold">
            Program: {{ selected_program }} <a href="javascript:void(0)" onclick="removeDirectoryFilter('program')" class="text-white ml-1 font-weight-bold">✕</a>
        </span>
        {% endif %}
        {% if selected_batch %}
        <span class="badge badge-warning text-dark px-2.5 py-1.5 rounded-pill font-weight-bold">
            Batch: {{ selected_batch }} <a href="javascript:void(0)" onclick="removeDirectoryFilter('batch')" class="text-dark ml-1 font-weight-bold">✕</a>
        </span>
        {% endif %}
        {% if selected_gender %}
        <span class="badge badge-secondary px-2.5 py-1.5 rounded-pill font-weight-bold">
            Gender: {{ selected_gender }} <a href="javascript:void(0)" onclick="removeDirectoryFilter('gender')" class="text-white ml-1 font-weight-bold">✕</a>
        </span>
        {% endif %}
        {% if selected_status %}
        <span class="badge badge-dark px-2.5 py-1.5 rounded-pill font-weight-bold">
            Status: {{ selected_status }} <a href="javascript:void(0)" onclick="removeDirectoryFilter('status')" class="text-white ml-1 font-weight-bold">✕</a>
        </span>
        {% endif %}
        <a href="javascript:void(0)" onclick="clearDirectoryFilters()" class="text-danger font-weight-bold ml-auto small">Clear All <i class="fas fa-undo ml-1"></i></a>
    </div>
    {% endif %}

    <div id="directory-results">"""

if results_marker in content:
    content = content.replace(results_marker, chips_html, 1)
    print("Filter chips bar injected into list.html")
elif results_marker_crlf in content:
    content = content.replace(results_marker_crlf, chips_html.replace("\n", "\r\n"), 1)
    print("Filter chips bar injected into list.html with CRLF")
else:
    raise ValueError("directory-results marker not found")

# 3. Add JS functions to end of scripts before </script>
end_marker = "}\n</script>\n\n{% include 'students/modals/photo_export_modal.html' %}\n{% endblock %}"
end_marker_crlf = "}\r\n</script>\r\n\r\n{% include 'students/modals/photo_export_modal.html' %}\r\n{% endblock %}"

new_js = """}

    // ─── Phase 4: Directory Filter Chips & Bulk Action Enhancements ───
    function removeDirectoryFilter(fieldName) {
        const form = document.getElementById('directory-filter-form');
        if (!form) return;
        const field = form.querySelector('[name="' + fieldName + '"]');
        if (field) {
            field.value = '';
            $(field).trigger('change');
            if (typeof htmx !== 'undefined') {
                htmx.trigger(form, 'submit');
            } else {
                form.submit();
            }
        }
    }

    function exportSelectedExcel() {
        const selected = Array.from(selectedStudentIds);
        if (selected.length === 0) {
            if (typeof Swal !== 'undefined') {
                Swal.fire({ icon: 'info', title: 'No Students Selected', text: 'Please check at least one student in the table.' });
            } else {
                alert('Please select at least one student.');
            }
            return;
        }
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = "{% url 'export_students' %}";
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]') ? document.querySelector('[name=csrfmiddlewaretoken]').value : '{{ csrf_token }}';
        form.innerHTML = '<input type="hidden" name="csrfmiddlewaretoken" value="' + csrfToken + '">' +
                         '<input type="hidden" name="selected_ids" value="' + selected.join(',') + '">';
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
    }

    // Modal safety: hide bulk bar when modal opens
    $('.modal').on('show.bs.modal', function() {
        $('#bulk-action-bar').css('visibility', 'hidden');
    }).on('hidden.bs.modal', function() {
        if (typeof updateBulkBarVisibility === 'function') {
            updateBulkBarVisibility();
        }
    });

    // Handle "Save & Add Next" redirect handoff
    $(document).ready(function() {
        if (sessionStorage.getItem('post_save_action') === 'add_next') {
            sessionStorage.removeItem('post_save_action');
            window.location.href = "{% url 'add_student' %}";
        }
    });

    // Re-sync after HTMX swaps
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if (evt.detail.target && evt.detail.target.id === 'directory-results') {
            if (typeof updateBulkBarVisibility === 'function') {
                updateBulkBarVisibility();
            }
        }
    });
</script>

{% include 'students/modals/photo_export_modal.html' %}
{% endblock %}"""

if end_marker in content:
    content = content.replace(end_marker, new_js, 1)
    print("JS helpers injected into list.html")
elif end_marker_crlf in content:
    content = content.replace(end_marker_crlf, new_js.replace("\n", "\r\n"), 1)
    print("JS helpers injected into list.html with CRLF")
else:
    raise ValueError("End script marker not found in list.html")

with open(LIST_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("List template modernization applied cleanly and atomically.")
