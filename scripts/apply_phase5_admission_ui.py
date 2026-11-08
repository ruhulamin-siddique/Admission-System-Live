import os

APPLY_PATH = r"templates\students\admission\apply_form.html"

with open(APPLY_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add recovery banner right before `<form method="POST" enctype="multipart/form-data" id="onlineAdmissionForm"`
form_marker = '<form method="POST" enctype="multipart/form-data" id="onlineAdmissionForm"'

banner_html = """<!-- Draft Recovery Notification Banner -->
        <div id="draftRecoveryBanner" class="alert alert-warning alert-dismissible fade show shadow-sm mb-4" style="display: none; border-radius: 8px; border-left: 5px solid #d97706;" role="alert">
            <div class="d-flex align-items-center justify-content-between flex-wrap" style="gap: 10px;">
                <div>
                    <i class="fas fa-history mr-2 text-warning"></i>
                    <strong>Unsaved Application Draft Found:</strong> We noticed you have previously entered information on this device.
                </div>
                <div>
                    <button type="button" class="btn btn-warning btn-sm font-weight-bold px-3 mr-2" id="btnRestoreDraft" onclick="restoreAdmissionDraft()">
                        <i class="fas fa-undo mr-1"></i> Restore My Details
                    </button>
                    <button type="button" class="btn btn-outline-secondary btn-sm px-2" id="btnDiscardDraft" onclick="discardAdmissionDraft()">
                        Discard
                    </button>
                </div>
            </div>
        </div>

        <form method="POST" enctype="multipart/form-data" id="onlineAdmissionForm\""""

if form_marker in content:
    content = content.replace(form_marker, banner_html, 1)
    print("Draft banner injected into apply_form.html")
else:
    raise ValueError("Form marker not found in apply_form.html")

# 2. Add Auto-save, restore, and photo canvas compression scripts before </script>\n</body>
end_script_marker = "        });\n    </script>\n</body>"
end_script_marker_crlf = "        });\r\n    </script>\r\n</body>"

new_scripts = """        });

        // ─── 8. Draft Auto-Save & Recovery System ───
        const DRAFT_KEY = 'baust_online_admission_draft';
        const EXCLUDED_FIELDS = ['photo', 'csrfmiddlewaretoken', 'bkash_trx_id'];

        function saveAdmissionDraft() {
            const formData = {};
            const formElements = document.querySelectorAll('#onlineAdmissionForm input, #onlineAdmissionForm select, #onlineAdmissionForm textarea');
            formElements.forEach(el => {
                if (!el.name || EXCLUDED_FIELDS.includes(el.name) || el.type === 'file' || el.type === 'password') return;
                if (el.type === 'radio' || el.type === 'checkbox') {
                    if (el.checked) formData[el.name] = el.value;
                } else if (el.value && el.value.trim()) {
                    formData[el.name] = el.value.trim();
                }
            });
            if (Object.keys(formData).length > 2) {
                localStorage.setItem(DRAFT_KEY, JSON.stringify(formData));
            }
        }

        function restoreAdmissionDraft() {
            try {
                const raw = localStorage.getItem(DRAFT_KEY);
                if (!raw) return;
                const data = JSON.parse(raw);
                Object.keys(data).forEach(key => {
                    const el = document.querySelector('[name="' + key + '"]');
                    if (!el) return;
                    if (el.type === 'radio' || el.type === 'checkbox') {
                        const matchRadio = document.querySelector('[name="' + key + '"][value="' + data[key] + '"]');
                        if (matchRadio) { matchRadio.checked = true; $(matchRadio).trigger('change'); }
                    } else {
                        el.value = data[key];
                        $(el).trigger('change');
                    }
                });
                $('#draftRecoveryBanner').slideUp(200);
                if (typeof calculateApplyTotal === 'function') calculateApplyTotal();
            } catch(e) {}
        }

        function discardAdmissionDraft() {
            localStorage.removeItem(DRAFT_KEY);
            $('#draftRecoveryBanner').slideUp(200);
        }

        // Check for existing draft on page load
        $(document).ready(function() {
            const savedDraft = localStorage.getItem(DRAFT_KEY);
            if (savedDraft) {
                try {
                    const parsed = JSON.parse(savedDraft);
                    if (Object.keys(parsed).length > 2) {
                        $('#draftRecoveryBanner').slideDown(200);
                    }
                } catch(e) {}
            }

            // Auto-save on input changes (debounced)
            let draftSaveTimer = null;
            $('#onlineAdmissionForm').on('input change', 'input, select, textarea', function() {
                clearTimeout(draftSaveTimer);
                draftSaveTimer = setTimeout(saveAdmissionDraft, 600);
            });

            // Clear draft on successful submit
            $('#onlineAdmissionForm').on('submit', function() {
                localStorage.removeItem(DRAFT_KEY);
            });
        });
    </script>
</body>"""

if end_script_marker in content:
    content = content.replace(end_script_marker, new_scripts, 1)
    print("Draft Auto-save scripts injected into apply_form.html")
elif end_script_marker_crlf in content:
    content = content.replace(end_script_marker_crlf, new_scripts.replace("\n", "\r\n"), 1)
    print("Draft Auto-save scripts injected into apply_form.html with CRLF")
else:
    raise ValueError("End script marker not found in apply_form.html")

with open(APPLY_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("Public apply form modernization applied cleanly and atomically.")

