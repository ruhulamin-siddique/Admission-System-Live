import os

PROFILE_PATH = r"templates\students\profile.html"

with open(PROFILE_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add CSS before </style>\n{% endblock %}
css_marker = "    .text-xs { font-size: 0.75rem; letter-spacing: 0.5px; }\n</style>"
new_css = """    .text-xs { font-size: 0.75rem; letter-spacing: 0.5px; }

    /* ─── Modern Student 360 Milestone Stepper & Hero ─── */
    .milestone-hero-card {
        background: #ffffff;
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.06);
        overflow: hidden;
        transition: all 0.25s ease;
    }
    body.dark-mode .milestone-hero-card {
        background: #1e293b;
        border-color: #334155;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.3);
    }
    .milestone-stepper-wrap {
        display: flex;
        align-items: center;
        justify-content: space-between;
        position: relative;
        padding: 16px 20px;
        background: #f8fafc;
        border-top: 1px solid #e2e8f0;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        gap: 8px;
    }
    body.dark-mode .milestone-stepper-wrap {
        background: #0f172a;
        border-top-color: #334155;
    }
    .milestone-step-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        position: relative;
        flex: 1 1 0;
        min-width: 110px;
        cursor: pointer;
        transition: transform 0.2s ease;
        padding: 6px 4px;
        border-radius: 10px;
    }
    .milestone-step-item:hover {
        transform: translateY(-2px);
        background: rgba(2, 132, 199, 0.08);
    }
    .milestone-step-node {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 15px;
        margin-bottom: 6px;
        box-shadow: 0 3px 8px rgba(0,0,0,0.1);
        transition: all 0.25s ease;
        z-index: 2;
    }
    .node-complete {
        background: linear-gradient(135deg, #10b981, #059669);
        color: #ffffff;
    }
    .node-partial {
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: #ffffff;
    }
    .node-pending {
        background: #e2e8f0;
        color: #64748b;
    }
    body.dark-mode .node-pending {
        background: #334155;
        color: #94a3b8;
    }
    .node-exempt {
        background: linear-gradient(135deg, #0284c7, #0369a1);
        color: #ffffff;
    }
    .node-muted {
        background: #64748b;
        color: #ffffff;
    }
    .milestone-step-title {
        font-size: 0.82rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 2px;
        white-space: nowrap;
    }
    body.dark-mode .milestone-step-title {
        color: #f1f5f9;
    }
    .milestone-step-badge {
        font-size: 0.7rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 20px;
        white-space: nowrap;
    }
    .copy-chip-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 10px;
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        color: #334155;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .copy-chip-btn:hover {
        background: #e2e8f0;
        color: #0f172a;
        transform: translateY(-1px);
    }
    body.dark-mode .copy-chip-btn {
        background: #334155;
        border-color: #475569;
        color: #e2e8f0;
    }
    body.dark-mode .copy-chip-btn:hover {
        background: #475569;
        color: #ffffff;
    }
    .copy-chip-btn.copied {
        background: #10b981 !important;
        border-color: #059669 !important;
        color: #ffffff !important;
    }
</style>"""

if css_marker in content:
    content = content.replace(css_marker, new_css, 1)
    print("CSS injected successfully.")
else:
    # Try normalized CRLF
    css_marker_crlf = css_marker.replace("\n", "\r\n")
    new_css_crlf = new_css.replace("\n", "\r\n")
    if css_marker_crlf in content:
        content = content.replace(css_marker_crlf, new_css_crlf, 1)
        print("CSS injected successfully with CRLF.")
    else:
        raise ValueError("CSS marker not found in profile.html")

# 2. Add Hero & Stepper HTML directly above `<div class="col-md-3">\n        <!-- Profile Image -->`
hero_marker = '    <div class="col-md-3">\n        <!-- Profile Image -->'
hero_marker_crlf = '    <div class="col-md-3">\r\n        <!-- Profile Image -->'

stepper_html = """    <!-- ─── Student 360 Progression Hero & Stepper ─── -->
    <div class="col-12 mb-4">
        <div class="milestone-hero-card">
            <!-- Hero Summary Strip -->
            <div class="p-3 d-flex flex-wrap justify-content-between align-items-center" style="gap: 12px;">
                <div class="d-flex align-items-center flex-wrap" style="gap: 12px;">
                    <div class="d-flex align-items-center">
                        <span class="font-weight-black text-uppercase text-dark h5 mb-0 mr-2">{{ student.student_name }}</span>
                        <span class="badge {% if student.admission_status == 'Active' %}badge-success{% else %}badge-secondary{% endif %} px-2.5 py-1 rounded-pill" style="font-size: 0.78rem;">
                            {{ student.admission_status }}
                        </span>
                    </div>
                    <div class="d-flex align-items-center" style="gap: 8px;">
                        <button type="button" class="copy-chip-btn" data-copy="{{ student.student_id }}" title="Click to Copy Student ID">
                            <i class="fas fa-id-badge text-primary"></i>
                            <code>{{ student.student_id }}</code>
                            <i class="far fa-copy text-muted ml-1 copy-icon"></i>
                        </button>
                        {% if student.student_mobile and student.student_mobile != '-' %}
                        <button type="button" class="copy-chip-btn" data-copy="{{ student.student_mobile }}" title="Click to Copy Mobile">
                            <i class="fas fa-phone-alt text-success"></i>
                            <span>{{ student.student_mobile }}</span>
                            <i class="far fa-copy text-muted ml-1 copy-icon"></i>
                        </button>
                        {% endif %}
                    </div>
                </div>
                <div class="text-muted small">
                    <span class="font-weight-bold text-dark">{{ student.program|default:"Unspecified Dept" }}</span>
                    <span class="mx-1.5">•</span>
                    <span>Batch {{ student.batch }}</span>
                    {% if student.semester_name %}
                    <span class="mx-1.5">•</span>
                    <span>{{ student.semester_name }}</span>
                    {% endif %}
                </div>
            </div>

            <!-- 6-Stage Milestone Stepper -->
            <div class="milestone-stepper-wrap">
                <!-- 1. Form Submitted -->
                <div class="milestone-step-item" onclick="jumpToTab('#details')" title="Click to view bio details">
                    <div class="milestone-step-node node-complete">
                        <i class="fas fa-file-check"></i>
                    </div>
                    <div class="milestone-step-title">1. Form &amp; Bio</div>
                    <span class="milestone-step-badge badge badge-success">Enrolled</span>
                </div>

                <!-- 2. Board Verified -->
                <div class="milestone-step-item" onclick="jumpToTab('#academic')" title="Click to view board verification logs">
                    {% if student.ssc_verified and student.hsc_verified %}
                        <div class="milestone-step-node node-complete"><i class="fas fa-check-double"></i></div>
                        <div class="milestone-step-title">2. Board Verif</div>
                        <span class="milestone-step-badge badge badge-success">Both Verified</span>
                    {% elif student.bteb_verified %}
                        <div class="milestone-step-node node-complete"><i class="fas fa-award"></i></div>
                        <div class="milestone-step-title">2. Board Verif</div>
                        <span class="milestone-step-badge badge badge-success">BTEB Verified</span>
                    {% elif student.ssc_verified or student.hsc_verified %}
                        <div class="milestone-step-node node-partial"><i class="fas fa-check"></i></div>
                        <div class="milestone-step-title">2. Board Verif</div>
                        <span class="milestone-step-badge badge badge-warning text-dark">Partial Verified</span>
                    {% else %}
                        <div class="milestone-step-node node-pending"><i class="fas fa-shield-alt"></i></div>
                        <div class="milestone-step-title">2. Board Verif</div>
                        <span class="milestone-step-badge badge badge-light border">Unverified</span>
                    {% endif %}
                </div>

                <!-- 3. Admission Fees -->
                <div class="milestone-step-item" onclick="jumpToTab('#financial')" title="Click to view payment details">
                    {% if student.admission_payment and student.admission_payment > 0 or student.waiver and student.waiver >= 100 or student.admission_status == 'Active' %}
                        <div class="milestone-step-node node-complete"><i class="fas fa-receipt"></i></div>
                        <div class="milestone-step-title">3. Admission Fee</div>
                        <span class="milestone-step-badge badge badge-success">Paid / Active</span>
                    {% else %}
                        <div class="milestone-step-node node-partial"><i class="fas fa-clock"></i></div>
                        <div class="milestone-step-title">3. Admission Fee</div>
                        <span class="milestone-step-badge badge badge-warning text-dark">Pending</span>
                    {% endif %}
                </div>

                <!-- 4. UGC ID Finalized -->
                <div class="milestone-step-item" onclick="jumpToTab('#details')" title="Click to view ID structure">
                    {% if student.student_id|length == 16 %}
                        <div class="milestone-step-node node-complete"><i class="fas fa-fingerprint"></i></div>
                        <div class="milestone-step-title">4. UGC ID</div>
                        <span class="milestone-step-badge badge badge-success">16-Digit Valid</span>
                    {% elif student.is_legacy_student %}
                        <div class="milestone-step-node node-exempt"><i class="fas fa-history"></i></div>
                        <div class="milestone-step-title">4. System ID</div>
                        <span class="milestone-step-badge badge badge-info">Legacy Valid</span>
                    {% else %}
                        <div class="milestone-step-node node-partial"><i class="fas fa-exclamation-circle"></i></div>
                        <div class="milestone-step-title">4. System ID</div>
                        <span class="milestone-step-badge badge badge-warning text-dark">Standard</span>
                    {% endif %}
                </div>

                <!-- 5. Hall Residency -->
                <div class="milestone-step-item" onclick="jumpToTab('#details')" title="Click to view residency and attachment">
                    {% if student.is_non_residential %}
                        <div class="milestone-step-node node-exempt"><i class="fas fa-house-user"></i></div>
                        <div class="milestone-step-title">5. Hall Seat</div>
                        <span class="milestone-step-badge badge badge-secondary">Non-Residential</span>
                    {% elif student.hall_residential %}
                        <div class="milestone-step-node node-complete"><i class="fas fa-hotel"></i></div>
                        <div class="milestone-step-title">5. Hall Seat</div>
                        <span class="milestone-step-badge badge badge-success">{{ student.hall_residential.short_name|default:"Allocated" }}</span>
                    {% elif student.hall_attached %}
                        <div class="milestone-step-node node-partial"><i class="fas fa-building"></i></div>
                        <div class="milestone-step-title">5. Hall Seat</div>
                        <span class="milestone-step-badge badge badge-warning text-dark">{{ student.hall_attached }}</span>
                    {% else %}
                        <div class="milestone-step-node node-pending"><i class="fas fa-bed"></i></div>
                        <div class="milestone-step-title">5. Hall Seat</div>
                        <span class="milestone-step-badge badge badge-light border">Unallocated</span>
                    {% endif %}
                </div>

                <!-- 6. Uniform & Additional Fees -->
                <div class="milestone-step-item" onclick="jumpToTab('#financial')" title="Click to view uniform package status">
                    {% if student.uniform_status == 'PAID' %}
                        <div class="milestone-step-node node-complete"><i class="fas fa-user-tie"></i></div>
                        <div class="milestone-step-title">6. Uniform</div>
                        <span class="milestone-step-badge badge badge-success">Paid</span>
                    {% elif student.uniform_status == 'OPTED_OUT' %}
                        <div class="milestone-step-node node-muted"><i class="fas fa-ban"></i></div>
                        <div class="milestone-step-title">6. Uniform</div>
                        <span class="milestone-step-badge badge badge-secondary">Opted Out</span>
                    {% elif student.uniform_status == 'PARTIAL' %}
                        <div class="milestone-step-node node-partial"><i class="fas fa-adjust"></i></div>
                        <div class="milestone-step-title">6. Uniform</div>
                        <span class="milestone-step-badge badge badge-warning text-dark">Partial</span>
                    {% else %}
                        <div class="milestone-step-node node-pending"><i class="fas fa-clock"></i></div>
                        <div class="milestone-step-title">6. Uniform</div>
                        <span class="milestone-step-badge badge badge-light border">Due / Pending</span>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>\n"""

if hero_marker in content:
    content = content.replace(hero_marker, stepper_html + hero_marker, 1)
    print("Hero & Stepper injected successfully.")
elif hero_marker_crlf in content:
    content = content.replace(hero_marker_crlf, stepper_html.replace("\n", "\r\n") + hero_marker_crlf, 1)
    print("Hero & Stepper injected successfully with CRLF.")
else:
    raise ValueError("Hero marker not found in profile.html")

# 3. Add JavaScript helper functions before </script>\n{% endblock %}
js_marker = "    }\n</script>\n{% endblock %}"
js_marker_crlf = "    }\r\n</script>\r\n{% endblock %}"

js_addition = """    }

    // ─── Jump To Tab Helper (Safely activates tab & scrolls) ───
    window.jumpToTab = function(tabHash) {
        if (!tabHash) return;
        let tabLink = document.querySelector('.nav-pills a[href="' + tabHash + '"]');
        if (!tabLink && tabHash === '#academic') {
            tabLink = document.querySelector('.nav-pills a[href="#academic-records"]') || document.querySelector('.nav-pills a[href="#academic"]');
        }
        if (tabLink) {
            $(tabLink).tab('show');
            const targetPane = document.querySelector(tabHash);
            if (targetPane) {
                targetPane.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    };

    // ─── Interactive Copy Chip with Tooltip Reset ───
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('.copy-chip-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const textToCopy = this.getAttribute('data-copy');
                if (!textToCopy) return;

                const self = this;
                const icon = self.querySelector('.copy-icon');
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(textToCopy).then(function() {
                        self.classList.add('copied');
                        if (icon) icon.className = 'fas fa-check text-white ml-1 copy-icon';
                        setTimeout(function() {
                            self.classList.remove('copied');
                            if (icon) icon.className = 'far fa-copy text-muted ml-1 copy-icon';
                        }, 1800);
                    }).catch(function() {
                        fallbackCopy(self, textToCopy, icon);
                    });
                } else {
                    fallbackCopy(self, textToCopy, icon);
                }
            });
        });

        function fallbackCopy(elem, text, icon) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                elem.classList.add('copied');
                if (icon) icon.className = 'fas fa-check text-white ml-1 copy-icon';
                setTimeout(function() {
                    elem.classList.remove('copied');
                    if (icon) icon.className = 'far fa-copy text-muted ml-1 copy-icon';
                }, 1800);
            } catch (err) {}
            document.body.removeChild(textarea);
        }
    });
</script>
{% endblock %}"""

if js_marker in content:
    content = content.replace(js_marker, js_addition, 1)
    print("JS helpers injected successfully.")
elif js_marker_crlf in content:
    content = content.replace(js_marker_crlf, js_addition.replace("\n", "\r\n"), 1)
    print("JS helpers injected successfully with CRLF.")
else:
    raise ValueError("JS marker not found in profile.html")

with open(PROFILE_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("Profile template modernization applied cleanly and atomically.")

