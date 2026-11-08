import os

ADD_PATH = r"templates\students\add.html"

with open(ADD_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add CSS to extra_css block before </style>
css_marker = "        border-color: #94a3b8 transparent transparent transparent !important;\n    }\n</style>"
css_marker_crlf = "        border-color: #94a3b8 transparent transparent transparent !important;\r\n    }\r\n</style>"

new_css = """        border-color: #94a3b8 transparent transparent transparent !important;
    }

    /* ─── Fast-Track Sticky Action Dock ─── */
    .content-wrapper {
        padding-bottom: 95px !important;
    }
    .sticky-admission-dock {
        position: fixed;
        bottom: 18px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1025;
        background: linear-gradient(135deg, #0f172a, #1e293b);
        border: 1px solid rgba(56, 189, 248, 0.4);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.45);
        border-radius: 50px;
        padding: 8px 18px;
        display: flex;
        align-items: center;
        gap: 12px;
        max-width: 95vw;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .sticky-dock-status {
        font-size: 0.82rem;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 20px;
        cursor: pointer;
        transition: all 0.2s ease;
        white-space: nowrap;
    }
    .status-ready {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .status-missing {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .dock-btn-next {
        background: linear-gradient(135deg, #0284c7, #0369a1);
        color: #fff !important;
        font-weight: 800;
        border-radius: 30px;
        border: none;
        padding: 7px 18px;
        font-size: 0.85rem;
        box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
        transition: all 0.2s ease;
        white-space: nowrap;
    }
    .dock-btn-next:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(2, 132, 199, 0.5);
    }
    .dock-btn-save {
        background: linear-gradient(135deg, #10b981, #059669);
        color: #fff !important;
        font-weight: 800;
        border-radius: 30px;
        border: none;
        padding: 7px 20px;
        font-size: 0.85rem;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        transition: all 0.2s ease;
        white-space: nowrap;
    }
    .dock-btn-save:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.5);
    }
    .duplicate-alert-pill {
        display: none;
        margin-top: 6px;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 8px;
        background: #fef3c7;
        color: #92400e;
        border-left: 4px solid #f59e0b;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }
    body.dark-mode .duplicate-alert-pill {
        background: #78350f;
        color: #fef3c7;
        border-left-color: #fbbf24;
    }
</style>"""

if css_marker in content:
    content = content.replace(css_marker, new_css, 1)
    print("CSS injected into add.html")
elif css_marker_crlf in content:
    content = content.replace(css_marker_crlf, new_css.replace("\n", "\r\n"), 1)
    print("CSS injected into add.html with CRLF")
else:
    raise ValueError("CSS marker not found in add.html")

# 2. Add Floating Dock HTML right after </form>
dock_marker = "</form>\n\n<!-- Camera Viewfinder Modal -->"
dock_marker_crlf = "</form>\r\n\r\n<!-- Camera Viewfinder Modal -->"

dock_html = """</form>

<!-- ─── Fast-Track Sticky Action Dock ─── -->
<div id="fastTrackDock" class="sticky-admission-dock">
    <div id="dockValidationStatus" class="sticky-dock-status status-ready" onclick="jumpToFirstInvalidField()" title="Click to jump to first missing field">
        <i class="fas fa-check-circle mr-1"></i> <span id="dockStatusText">Required Fields Ready</span>
    </div>
    <div style="width: 1px; height: 22px; background: rgba(255,255,255,0.2);"></div>
    <button type="button" class="dock-btn-next" onclick="submitAndAddNext()" title="Save student and immediately open a fresh admission form (Shortcut: F2)">
        <i class="fas fa-user-plus mr-1"></i> Save &amp; Add Next <span class="badge badge-light ml-1 text-dark" style="font-size: 10px;">F2</span>
    </button>
    <button type="button" class="dock-btn-save" onclick="submitAdmissionForm()" title="Confirm enrollment and save record (Shortcut: Ctrl+Enter)">
        <i class="fas fa-save mr-1"></i> Save Student <span class="badge badge-light ml-1 text-dark" style="font-size: 10px;">Ctrl+Enter</span>
    </button>
</div>

<!-- Camera Viewfinder Modal -->"""

if dock_marker in content:
    content = content.replace(dock_marker, dock_html, 1)
    print("Floating Dock HTML injected into add.html")
elif dock_marker_crlf in content:
    content = content.replace(dock_marker_crlf, dock_html.replace("\n", "\r\n"), 1)
    print("Floating Dock HTML injected into add.html with CRLF")
else:
    raise ValueError("Dock marker not found in add.html")

# 3. Add Fast-Track & Duplicate Shield JS before </script>\n{% endblock %}
js_marker = "    });\n</script>\n{% endblock %}"
js_marker_crlf = "    });\r\n</script>\r\n{% endblock %}"

js_code = """    });

    // ─── Fast-Track Entry Dock & Ambient Duplicate Shield ───
    function submitAdmissionForm() {
        const form = document.getElementById('admissionForm');
        if (form.reportValidity()) {
            form.submit();
        } else {
            jumpToFirstInvalidField();
        }
    }

    function submitAndAddNext() {
        const form = document.getElementById('admissionForm');
        if (form.reportValidity()) {
            sessionStorage.setItem('post_save_action', 'add_next');
            form.submit();
        } else {
            jumpToFirstInvalidField();
        }
    }

    function jumpToFirstInvalidField() {
        const form = document.getElementById('admissionForm');
        const invalidFields = form.querySelectorAll(':invalid');
        if (invalidFields.length > 0) {
            const first = invalidFields[0];
            first.scrollIntoView({ behavior: 'smooth', block: 'center' });
            first.focus();
            $(first).addClass('is-invalid');
            setTimeout(() => { $(first).removeClass('is-invalid'); }, 2500);
        }
    }

    function updateDockValidation() {
        const form = document.getElementById('admissionForm');
        if (!form) return;
        const requiredFields = form.querySelectorAll('[required]');
        let emptyCount = 0;
        requiredFields.forEach(f => {
            if (!f.value || !f.value.trim()) emptyCount++;
        });

        const statusPill = document.getElementById('dockValidationStatus');
        const statusText = document.getElementById('dockStatusText');
        if (statusPill && statusText) {
            if (emptyCount === 0) {
                statusPill.className = 'sticky-dock-status status-ready';
                statusPill.innerHTML = '<i class="fas fa-check-circle mr-1"></i> <span id="dockStatusText">All Required Fields Ready</span>';
            } else {
                statusPill.className = 'sticky-dock-status status-missing';
                statusPill.innerHTML = '<i class="fas fa-exclamation-circle mr-1"></i> <span id="dockStatusText">' + emptyCount + ' Required Field(s) Missing</span>';
            }
        }
    }

    $(document).ready(function() {
        // Form field changes trigger status update
        $('#admissionForm').on('input change', 'input, select, textarea', function() {
            updateDockValidation();
        });
        updateDockValidation();

        // Keyboard Shortcuts: F2 for Save & Next, Ctrl+Enter for Save
        $(document).on('keydown', function(e) {
            if (e.key === 'F2') {
                e.preventDefault();
                submitAndAddNext();
            } else if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                submitAdmissionForm();
            }
        });

        // Hide floating dock when modals open to eliminate z-index conflict
        $('.modal').on('show.bs.modal', function() {
            $('#fastTrackDock').fadeOut(150);
        }).on('hidden.bs.modal', function() {
            $('#fastTrackDock').fadeIn(200);
        });

        // Ambient Duplicate Shield on mobile & NID fields
        function setupDuplicateWatcher(inputSelector, fieldLabel) {
            let timer = null;
            const $input = $(inputSelector);
            if (!$input.length) return;

            const pillId = 'dup_alert_' + ($input.attr('name') || 'field');
            if (!$('#' + pillId).length) {
                $input.after('<div id="' + pillId + '" class="duplicate-alert-pill"><i class="fas fa-info-circle mr-1"></i> <span class="dup-msg"></span></div>');
            }
            const $pill = $('#' + pillId);

            $input.on('blur', function() {
                const val = ($(this).val() || '').trim();
                if (val.length >= 6) {
                    $.ajax({
                        url: "{% url 'api_global_search' %}",
                        data: { search: val },
                        success: function(response) {
                            if (response && response.indexOf('student-name') !== -1) {
                                $pill.find('.dup-msg').html('Note: Existing student records match this ' + fieldLabel + '. Verify to avoid duplicate entry.');
                                $pill.slideDown(200);
                            } else {
                                $pill.slideUp(150);
                            }
                        },
                        error: function() {
                            $pill.slideUp(150);
                        }
                    });
                } else {
                    $pill.slideUp(150);
                }
            });
        }

        setupDuplicateWatcher('[name="student_mobile"]', 'student mobile');
        setupDuplicateWatcher('[name="father_mobile"]', 'father mobile');
        setupDuplicateWatcher('[name="national_id"]', 'NID/Birth Reg');
    });
</script>
{% endblock %}"""

if js_marker in content:
    content = content.replace(js_marker, js_code, 1)
    print("JS injected into add.html")
elif js_marker_crlf in content:
    content = content.replace(js_marker_crlf, js_code.replace("\n", "\r\n"), 1)
    print("JS injected into add.html with CRLF")
else:
    raise ValueError("JS marker not found in add.html")

with open(ADD_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("Add template modernization applied cleanly and atomically.")
