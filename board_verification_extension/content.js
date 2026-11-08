(function () {
    'use strict';

    function isExtensionValid() {
        return (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.id);
    }

    var currentHost = window.location.hostname;

    // 1. If running on Admission System, record active server origin & sync batch queue automatically
    if (!currentHost.includes('eboardresults.com') && !currentHost.includes('bteb.gov.bd')) {
        if (window.location.origin && window.location.origin.startsWith('http')) {
            if (isExtensionValid()) {
                try { chrome.storage.sync.set({ server_url: window.location.origin }); } catch (e) { }
            }
        }

        var _syncIntervalId = null;
        function _startSyncInterval() {
            if (_syncIntervalId) return;
            _syncIntervalId = setInterval(function () {
                if (!isExtensionValid()) return;
                try {
                    var rawQueue = sessionStorage.getItem('batch_queue');
                    if (!rawQueue) {
                        clearInterval(_syncIntervalId);
                        _syncIntervalId = null;
                        return;
                    }
                    chrome.storage.local.set({
                        batch_queue: rawQueue,
                        batch_index: sessionStorage.getItem('batch_index') || '0'
                    });
                } catch (e) { }
            }, 2000);
        }
        if (sessionStorage.getItem('batch_queue')) _startSyncInterval();
        return;
    }

    // Helper to safely set React-controlled input/select values
    function setNativeInputValue(element, value) {
        if (!element || value === undefined || value === null) return;
        try {
            var valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            var prototype = Object.getPrototypeOf(element);
            var prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value');
            if (prototypeValueSetter && prototypeValueSetter.set && valueSetter && valueSetter.set !== prototypeValueSetter.set) {
                prototypeValueSetter.set.call(element, value);
            } else if (valueSetter && valueSetter.set) {
                valueSetter.set.call(element, value);
            } else {
                element.value = value;
            }
        } catch (e) {
            element.value = value;
        }
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function setNativeSelectValue(element, value) {
        if (!element || value === undefined || value === null) return;
        try {
            var valueSetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value');
            var prototype = Object.getPrototypeOf(element);
            var prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value');
            if (prototypeValueSetter && prototypeValueSetter.set && valueSetter && valueSetter.set !== prototypeValueSetter.set) {
                prototypeValueSetter.set.call(element, value);
            } else if (valueSetter && valueSetter.set) {
                valueSetter.set.call(element, value);
            } else {
                element.value = value;
            }
        } catch (e) {
            element.value = value;
        }
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // 2. Inject Next-Gen Glassmorphic Floating Widget
    function injectWidget() {
        if (document.getElementById('baust_verif_widget')) return;

        var widget = document.createElement('div');
        widget.id = 'baust_verif_widget';
        widget.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999999;
            background: rgba(15, 23, 42, 0.88);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            color: #ffffff;
            padding: 18px 22px;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(56, 189, 248, 0.3);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 13px;
            width: 320px;
            animation: baustSlideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        `;

        if (!document.getElementById('baust_widget_styles')) {
            var styleEl = document.createElement('style');
            styleEl.id = 'baust_widget_styles';
            styleEl.innerHTML = `
                @keyframes baustSlideIn {
                    from { opacity: 0; transform: translateY(-20px) scale(0.95); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }
                @keyframes baustPulse {
                    0% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.7); }
                    70% { box-shadow: 0 0 0 10px rgba(56, 189, 248, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
                }
                .baust-pulse { animation: baustPulse 2s infinite; }
            `;
            document.head.appendChild(styleEl);
        }

        chrome.storage.local.get(['batch_queue', 'batch_index'], function (items) {
            var bqData = null;
            try {
                var rawQueue = items.batch_queue || sessionStorage.getItem('batch_queue');
                if (rawQueue) bqData = JSON.parse(rawQueue);
            } catch (e) { }

            var bqIndex = parseInt(items.batch_index || sessionStorage.getItem('batch_index') || '0', 10);
            var bqHtml = '';

            if (bqData && Array.isArray(bqData) && bqData.length > 0) {
                var currentTask = bqData[bqIndex] || bqData[0];
                var nextTask = bqData[bqIndex + 1];
                var totalCount = bqData.length;
                var currentNum = Math.min(bqIndex + 1, totalCount);

                bqHtml = `
                    <div id="baust_bq_banner" style="background:rgba(30,41,59,0.85); border:1px solid rgba(56,189,248,0.4); border-radius:14px; padding:10px 12px; margin-bottom:12px; font-size:12px; text-align:left;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <span style="font-weight:800; color:#38bdf8; font-size:11px; text-transform:uppercase;">🎯 QUEUE (${currentNum} of ${totalCount})</span>
                            <div style="display:flex; gap:8px;">
                                <button id="btn_bq_skip" style="background:none; border:none; color:#cbd5e1; font-weight:bold; font-size:10px; cursor:pointer; padding:0; text-decoration:underline;">⏭️ Skip</button>
                                <button id="btn_bq_clear" style="background:#f43f5e; color:#ffffff; border:none; padding:3px 8px; border-radius:6px; font-weight:bold; font-size:10px; cursor:pointer;" title="Stop Batch Queue &amp; Switch to Single Student Mode">⛔ Stop Queue</button>
                            </div>
                        </div>
                        
                        <div style="font-weight:800; color:#f8fafc; font-size:13px; line-height:1.2; margin-bottom:2px;">${currentTask.name || 'Student ID: ' + currentTask.student_id}</div>
                        <div style="font-size:11px; color:#94a3b8; font-weight:600;">ID: <strong style="color:#e2e8f0;">${currentTask.student_id}</strong> | Exam: <strong style="color:#38bdf8;">${currentTask.exam || 'SSC'} (${currentTask.board || 'BOARD'})</strong></div>
                        <div style="font-size:11px; color:#cbd5e1; margin-top:2px;">Roll: <strong style="color:#f43f5e;">${currentTask.roll || 'N/A'}</strong> | Reg: <strong style="color:#f43f5e;">${currentTask.reg || 'N/A'}</strong></div>

                        ${nextTask ? '<div style="border-top:1px dashed rgba(255,255,255,0.15); margin:6px 0 0 0; padding-top:4px; font-size:10px; color:#94a3b8;"><span style="color:#64748b;">Next:</span> <strong style="color:#cbd5e1;">' + nextTask.student_id + ' (' + (nextTask.exam || 'SSC') + ')</strong></div>' : ''}
                    </div>
                `;
            }

            var isBtebHost = currentHost.includes('bteb.gov.bd');
            var defaultBoardTag = isBtebHost ? 'Board: BTEB Technical' : 'Board: General / E-Board';

            widget.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:8px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <div class="baust-pulse" style="width:9px; height:9px; background:#38bdf8; border-radius:50%;"></div>
                    <strong style="color:#38bdf8; font-size:14px; letter-spacing:-0.3px;">Admission Verifier <span style="font-size:10px; background:rgba(56,189,248,0.2); padding:2px 6px; border-radius:10px; color:#38bdf8;">v2.5.1</span></strong>
                </div>
                <span id="baust_status_badge" style="background:rgba(2,132,199,0.3); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); padding:2px 8px; border-radius:10px; font-size:10px; font-weight:bold;">READY</span>
            </div>

            ${bqHtml}

            <div id="baust_alert_banner" style="display:none; background:rgba(225,29,72,0.2); border:1px solid #f43f5e; color:#fecdd3; padding:10px 12px; border-radius:12px; margin-bottom:12px; font-size:12px; text-align:left;">
                <strong style="color:#fb7185;"><i class="fas fa-exclamation-triangle"></i> Discrepancy Warning:</strong>
                <ul id="baust_mismatch_list" style="margin:4px 0 0 16px; padding:0;"></ul>
            </div>

            <button id="btn_baust_autofill" style="width:100%; background:linear-gradient(135deg,#0284c7,#0369a1); color:#fff; border:none; padding:10px 11px; border-radius:12px; font-weight:bold; cursor:pointer; margin-bottom:8px; font-size:12.5px; box-shadow:0 4px 15px rgba(2,132,199,0.4); transition:all 0.2s ease;">
                ⚡ 1. Auto-Fill &amp; Solve Captcha
            </button>

            <button id="btn_baust_copy" style="width:100%; background:linear-gradient(135deg,#d97706,#b45309); color:#fff; border:none; padding:10px 11px; border-radius:12px; font-weight:bold; cursor:pointer; margin-bottom:8px; font-size:12.5px; box-shadow:0 4px 15px rgba(217,119,6,0.4); transition:all 0.2s ease;" title="Copy Result to Clipboard for Add/Edit Student Form">
                📋 2. Copy Result for Form
            </button>

            <button id="btn_baust_sync" style="width:100%; background:linear-gradient(135deg,#16a34a,#15803d); color:#fff; border:none; padding:10px 11px; border-radius:12px; font-weight:bold; cursor:pointer; margin-bottom:8px; font-size:12.5px; box-shadow:0 4px 15px rgba(22,163,74,0.4); transition:all 0.2s ease;">
                🚀 3. Direct Sync to System
            </button>

            <div style="display:flex; justify-content:space-between; font-size:11px; color:#94a3b8; margin-top:2px;">
                <span id="baust_board_tag">${defaultBoardTag}</span>
                <span id="baust_server_label">Server: Auto</span>
            </div>
        `;

            document.body.appendChild(widget);

            document.getElementById('btn_baust_autofill').addEventListener('click', function () {
                if (bqData && bqData[bqIndex]) {
                    autoFillFromBatchQueue(bqData, bqIndex);
                } else {
                    autoFillForm();
                }
            });

            document.getElementById('btn_baust_copy').addEventListener('click', function () {
                copyResultToClipboard();
            });

            document.getElementById('btn_baust_sync').addEventListener('click', function () {
                syncResult();
                if (bqData && bqData.length > 0) {
                    var nextIdx = bqIndex + 1;
                    if (nextIdx >= bqData.length) {
                        sessionStorage.removeItem('batch_queue');
                        sessionStorage.removeItem('batch_index');
                        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                            chrome.storage.local.remove(['batch_queue', 'batch_index']);
                        }
                    } else {
                        sessionStorage.setItem('batch_index', nextIdx.toString());
                        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                            chrome.storage.local.set({ batch_index: nextIdx.toString() });
                        }
                    }
                }
            });

            var bqSkipBtn = document.getElementById('btn_bq_skip');
            if (bqSkipBtn) {
                bqSkipBtn.addEventListener('click', function () {
                    var nextIdx = bqIndex + 1;
                    if (bqData && nextIdx >= bqData.length) {
                        sessionStorage.removeItem('batch_queue');
                        sessionStorage.removeItem('batch_index');
                        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                            chrome.storage.local.remove(['batch_queue', 'batch_index']);
                        }
                    } else {
                        sessionStorage.setItem('batch_index', nextIdx.toString());
                        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                            chrome.storage.local.set({ batch_index: nextIdx.toString() });
                        }
                    }
                    location.reload();
                });
            }

            var bqClearBtn = document.getElementById('btn_bq_clear');
            if (bqClearBtn) {
                bqClearBtn.addEventListener('click', function () {
                    sessionStorage.removeItem('batch_queue');
                    sessionStorage.removeItem('batch_index');
                    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                        chrome.storage.local.remove(['batch_queue', 'batch_index']);
                    }
                    location.reload();
                });
            }

            // Fetch stored server URL (defaults to live portal or local fallback)
            chrome.storage.sync.get(['server_url'], function (items) {
                var sUrl = items.server_url || 'https://portal.baust.edu.bd';
                var lbl = document.getElementById('baust_server_label');
                if (lbl) lbl.innerText = 'Server: ' + sUrl.replace(/^https?:\/\//, '');
            });

            // AUTO-FILL ON PAGE LOAD
            setTimeout(function () {
                if (bqData && bqData[bqIndex]) {
                    autoFillFromBatchQueue(bqData, bqIndex);
                } else if (navigator.clipboard && navigator.clipboard.readText) {
                    navigator.clipboard.readText().then(function (txt) {
                        if (txt && (txt.includes('StudentID:') || txt.includes('ServerURL:') || txt.includes('Roll:'))) {
                            autoFillForm(txt);
                        }
                    }).catch(function () { });
                }
            }, 600);
        });
    }

    function triggerChange(el) {
        if (!el) return;
        var ev = document.createEvent('HTMLEvents');
        ev.initEvent('change', true, false);
        el.dispatchEvent(ev);
    }

    // Solve BTEB math security check (e.g., "14 + 7 = ?" or "15 + 4")
    function solveBtebMathCaptcha() {
        var sumEl = document.querySelector('.prs-captcha-sum') || document.querySelector('[class*="captcha-sum"]');
        var capInp = document.getElementById('prs-captcha') || document.querySelector('input.prs-captcha-answer') || document.querySelector('input[placeholder*="Answer"]');
        if (sumEl && capInp) {
            var txt = sumEl.innerText.trim();
            var m = txt.match(/(\d+)\s*([\+\-\*])\s*(\d+)/);
            if (m) {
                var n1 = parseInt(m[1], 10);
                var op = m[2];
                var n2 = parseInt(m[3], 10);
                var ans = (op === '+') ? (n1 + n2) : (op === '-') ? (n1 - n2) : (n1 * n2);
                setNativeInputValue(capInp, ans.toString());
                return true;
            }
        }
        return false;
    }

    function executeBtebAutofill(data) {
        var exam = (data.exam || 'SSC').toUpperCase();
        var roll = data.roll || '';
        var reg = data.reg || '';
        var year = data.year || '';
        var curriculum = data.curriculum || '';
        var semester = data.semester || '2';

        if (!curriculum) {
            curriculum = (exam.includes('HSC') || exam.includes('BM')) ? '26' : '27';
        }

        // 1. Examination select if present
        var selects = document.querySelectorAll('select.prs-select, select');
        var examSel = selects[0];
        if (examSel) {
            for (var i = 0; i < examSel.options.length; i++) {
                var optText = examSel.options[i].text.toLowerCase();
                var optVal = examSel.options[i].value.toLowerCase();
                if ((exam === 'SSC' && (optText.includes('ssc') || optVal.includes('ssc') || optText.includes('vocational'))) ||
                    (exam === 'HSC' && (optText.includes('hsc') || optVal.includes('hsc') || optText.includes('bm') || optText.includes('business'))) ||
                    (exam.includes('DIPLOMA') && optText.includes('diploma'))) {
                    setNativeSelectValue(examSel, examSel.options[i].value);
                    break;
                }
            }
        }

        // 2. Curriculum & Semester selection with staged retries to allow React state updates
        setTimeout(function () {
            var allSelects = document.querySelectorAll('select.prs-select, select');
            allSelects.forEach(function (sel) {
                var curTarget = curriculum.trim().toLowerCase();
                for (var j = 0; j < sel.options.length; j++) {
                    var oVal = sel.options[j].value.toLowerCase();
                    var oText = sel.options[j].text.toLowerCase();
                    if (oVal === curTarget || oText.startsWith(curTarget + ' ') || oText.startsWith(curTarget + '-') || (curTarget === '27' && oText.includes('ssc')) || (curTarget === '26' && oText.includes('hsc'))) {
                        setNativeSelectValue(sel, sel.options[j].value);
                        break;
                    }
                }
            });

            setTimeout(function () {
                var semSelects = document.querySelectorAll('select.prs-select, select');
                semSelects.forEach(function (sel) {
                    var semTarget = semester.trim();
                    for (var k = 0; k < sel.options.length; k++) {
                        var sVal = sel.options[k].value;
                        var sText = sel.options[k].text.toLowerCase();
                        if (sVal === semTarget || sText.includes('semester ' + semTarget) || sText === semTarget) {
                            setNativeSelectValue(sel, sel.options[k].value);
                            break;
                        }
                    }
                });

                // 3. Set Year
                var yearInp = document.querySelector('.prs-year-wrap input') || document.getElementById('prs-year') || document.querySelector('input[placeholder*="year"]');
                if (yearInp && year) {
                    setNativeInputValue(yearInp, year);
                } else {
                    var yearSel = document.querySelector('select[name="examYear"], select[name="year"]');
                    if (yearSel && year) setNativeSelectValue(yearSel, year);
                }

                // 4. Set Roll & Reg
                var rollInp = document.getElementById('prs-roll') || document.querySelector('input[placeholder*="123456"]');
                if (rollInp && roll) setNativeInputValue(rollInp, roll);

                var regInp = document.getElementById('prs-reg') || document.querySelector('input[placeholder*="123456 or"]') || document.querySelector('input[placeholder*="Registration"]');
                if (regInp && reg) setNativeInputValue(regInp, reg);

                // 5. Solve Captcha
                setTimeout(function () {
                    solveBtebMathCaptcha();
                }, 300);

                var badge = document.getElementById('baust_status_badge');
                if (badge) {
                    badge.innerText = 'AUTO-FILLED ⚡';
                    badge.style.background = 'rgba(16,185,129,0.3)';
                    badge.style.color = '#34d399';
                    setTimeout(function () {
                        badge.innerText = 'READY';
                        badge.style.background = 'rgba(2,132,199,0.3)';
                        badge.style.color = '#38bdf8';
                    }, 4000);
                }
            }, 250);
        }, 200);
    }

    function autoFillForm(passedClip) {
        var processText = function (clip) {
            if (!clip) {
                if (!passedClip) alert("Clipboard is empty! Copy student details from Admission System first.");
                return;
            }

            if (clip.includes('Mode: SINGLE')) {
                sessionStorage.removeItem('batch_queue');
                sessionStorage.removeItem('batch_index');
                if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                    chrome.storage.local.remove(['batch_queue', 'batch_index']);
                }
                var banner = document.getElementById('baust_bq_banner');
                if (banner) banner.remove();
            }

            var serverM = clip.match(/ServerURL:\s*(https?:\/\/[^\s|]+)/i);
            if (serverM) {
                chrome.storage.sync.set({ server_url: serverM[1] });
                var lbl = document.getElementById('baust_server_label');
                if (lbl) lbl.innerText = 'Server: ' + serverM[1].replace(/^https?:\/\//, '');
            }

            var sidM = clip.match(/StudentID:\s*([A-Za-z0-9_]+)/i) || clip.match(/\b(080\d{13}|\d{16})\b/);
            if (sidM) sessionStorage.setItem('current_verify_sid', sidM[1]);

            var examM = clip.match(/Exam:\s*([A-Za-z0-9_]+)/i);
            if (examM) sessionStorage.setItem('current_verify_exam', examM[1].toUpperCase());
            var rollM = clip.match(/Roll:\s*(\d+)/i);
            var regM = clip.match(/Reg:\s*(\d+)/i);
            var yearM = clip.match(/Year:\s*(\d+)/i);
            var boardM = clip.match(/Board:\s*([A-Za-z\s]+)/i);
            var currM = clip.match(/Curriculum:\s*([A-Za-z0-9_\-]+)/i);
            var semM = clip.match(/Semester:\s*([A-Za-z0-9_]+)/i);

            var isBTEB = currentHost.includes('bteb.gov.bd') || (boardM && (boardM[1].toLowerCase().includes('tech') || boardM[1].toLowerCase().includes('bteb')));
            var bTag = document.getElementById('baust_board_tag');
            if (isBTEB && bTag) bTag.innerText = 'Board: BTEB Technical';

            if (currentHost.includes('bteb.gov.bd')) {
                executeBtebAutofill({
                    exam: examM ? examM[1] : 'SSC',
                    roll: rollM ? rollM[1] : '',
                    reg: regM ? regM[1] : '',
                    year: yearM ? yearM[1] : '',
                    curriculum: currM ? currM[1] : '',
                    semester: semM ? semM[1] : '2'
                });
                return;
            }

            // General Board (eboardresults.com)
            var examSel = document.querySelector('select[name="exam"]') || document.getElementById('exam');
            if (examSel && examM) {
                var exTarget = examM[1].toLowerCase();
                for (var i = 0; i < examSel.options.length; i++) {
                    var optText = examSel.options[i].text.toLowerCase();
                    var optVal = examSel.options[i].value.toLowerCase();
                    if (optVal.includes(exTarget) || optText.includes(exTarget)) {
                        examSel.selectedIndex = i;
                        triggerChange(examSel);
                        break;
                    }
                }
            }

            var yearSel = document.querySelector('select[name="year"]') || document.getElementById('year');
            if (yearSel && yearM) {
                yearSel.value = yearM[1];
                triggerChange(yearSel);
            }

            var boardSel = document.querySelector('select[name="board"]') || document.getElementById('board');
            if (boardSel && boardM) {
                var bTarget = boardM[1].trim().toLowerCase();
                for (var j = 0; j < boardSel.options.length; j++) {
                    var bText = boardSel.options[j].text.toLowerCase();
                    var bVal = boardSel.options[j].value.toLowerCase();
                    if (bVal.includes(bTarget) || bText.includes(bTarget) || (isBTEB && (bVal.includes('tec') || bText.includes('technical')))) {
                        boardSel.selectedIndex = j;
                        triggerChange(boardSel);
                        break;
                    }
                }
            }

            var resTypeSel = document.querySelector('select[name="result_type"]') || document.getElementById('result_type');
            if (resTypeSel) {
                for (var k = 0; k < resTypeSel.options.length; k++) {
                    if (resTypeSel.options[k].value == "1" || resTypeSel.options[k].text.toLowerCase().includes("individual")) {
                        resTypeSel.selectedIndex = k;
                        triggerChange(resTypeSel);
                        break;
                    }
                }
            }

            setTimeout(function () {
                var rollInp = document.querySelector('input[name="roll"]') || document.getElementById('roll');
                if (rollInp && rollM) { rollInp.value = rollM[1]; triggerChange(rollInp); }

                var regInp = document.querySelector('input[name="reg"]') || document.getElementById('reg');
                if (regInp && regM) { regInp.value = regM[1]; triggerChange(regInp); }

                var capInp = document.querySelector('input[name="captcha"]') || document.getElementById('captcha');
                if (capInp) capInp.focus();

                var badge = document.getElementById('baust_status_badge');
                if (badge) {
                    badge.innerText = 'AUTO-FILLED ⚡';
                    badge.style.background = 'rgba(16,185,129,0.3)';
                    badge.style.color = '#34d399';
                    setTimeout(function () {
                        badge.innerText = 'READY';
                        badge.style.background = 'rgba(2,132,199,0.3)';
                        badge.style.color = '#38bdf8';
                    }, 4000);
                }
            }, 250);
        };

        if (typeof passedClip === 'string' && passedClip.trim()) {
            processText(passedClip);
        } else if (navigator.clipboard && navigator.clipboard.readText) {
            navigator.clipboard.readText().then(processText).catch(function () {
                alert("Clipboard access failed. Please paste details when prompted.");
            });
        }
    }

    function autoFillFromBatchQueue(queue, index) {
        if (!queue || !queue[index]) return;
        var task = queue[index];

        sessionStorage.setItem('current_verify_sid', task.student_id);
        if (task.exam) sessionStorage.setItem('current_verify_exam', task.exam.toUpperCase());

        var rollM = task.roll ? [null, task.roll] : null;
        var regM = task.reg ? [null, task.reg] : null;
        var yearM = task.year ? [null, task.year] : null;
        var boardM = task.board ? [null, task.board] : null;
        var examM = task.exam ? [null, task.exam] : null;

        var isBTEB = currentHost.includes('bteb.gov.bd') || (boardM && (boardM[1].toLowerCase().includes('tech') || boardM[1].toLowerCase().includes('bteb')));
        if (isBTEB && document.getElementById('baust_board_tag')) {
            document.getElementById('baust_board_tag').innerText = 'Board: BTEB Technical';
        }

        if (currentHost.includes('bteb.gov.bd')) {
            executeBtebAutofill({
                exam: task.exam || 'SSC',
                roll: task.roll || '',
                reg: task.reg || '',
                year: task.year || '',
                curriculum: task.curriculum || '',
                semester: task.semester || '2'
            });
            return;
        }

        var examSel = document.querySelector('select[name="exam"]') || document.getElementById('exam');
        if (examSel && examM) {
            var exTarget = examM[1].toLowerCase();
            for (var i = 0; i < examSel.options.length; i++) {
                var optText = examSel.options[i].text.toLowerCase();
                var optVal = examSel.options[i].value.toLowerCase();
                if (optVal.includes(exTarget) || optText.includes(exTarget)) {
                    examSel.selectedIndex = i;
                    triggerChange(examSel);
                    break;
                }
            }
        }

        var yearSel = document.querySelector('select[name="year"]') || document.getElementById('year');
        if (yearSel && yearM) {
            yearSel.value = yearM[1];
            triggerChange(yearSel);
        }

        var boardSel = document.querySelector('select[name="board"]') || document.getElementById('board');
        if (boardSel && boardM) {
            var bTarget = boardM[1].trim().toLowerCase();
            for (var j = 0; j < boardSel.options.length; j++) {
                var bText = boardSel.options[j].text.toLowerCase();
                var bVal = boardSel.options[j].value.toLowerCase();
                if (bVal.includes(bTarget) || bText.includes(bTarget) || (isBTEB && (bVal.includes('tec') || bText.includes('technical')))) {
                    boardSel.selectedIndex = j;
                    triggerChange(boardSel);
                    break;
                }
            }
        }

        var resTypeSel = document.querySelector('select[name="result_type"]') || document.getElementById('result_type');
        if (resTypeSel) {
            for (var k = 0; k < resTypeSel.options.length; k++) {
                if (resTypeSel.options[k].value == "1" || resTypeSel.options[k].text.toLowerCase().includes("individual")) {
                    resTypeSel.selectedIndex = k;
                    triggerChange(resTypeSel);
                    break;
                }
            }
        }

        setTimeout(function () {
            var rollInp = document.querySelector('input[name="roll"]') || document.getElementById('roll');
            if (rollInp && rollM) { rollInp.value = rollM[1]; triggerChange(rollInp); }

            var regInp = document.querySelector('input[name="reg"]') || document.getElementById('reg');
            if (regInp && regM) { regInp.value = regM[1]; triggerChange(regInp); }

            var capInp = document.querySelector('input[name="captcha"]') || document.getElementById('captcha');
            if (capInp) capInp.focus();
        }, 250);
    }

    var BOARD_HEADER_BLACKLIST = [
        'BOARD OF', 'EDUCATION BOARD', 'TECHNICAL EDUCATION', 'INTERMEDIATE AND SECONDARY',
        'EXAMINATION RESULT', 'RESULT PUBLICATION', 'GOVERNMENT OF', 'BANGLADESH',
        'MINISTRY OF EDUCATION', 'WEB BASED RESULT', 'BOARD NAME', 'NAME OF EXAMINEE',
        'INSTITUTE NAME', 'HIGHER SECONDARY', 'SECONDARY SCHOOL CERTIFICATE', 'CENTRE NAME'
    ];

    function cleanBoardName(nameCandidate) {
        if (!nameCandidate) return '';
        var str = nameCandidate.trim().replace(/\s+/g, ' ');
        var upper = str.toUpperCase();
        if (upper.length < 3) return '';
        for (var i = 0; i < BOARD_HEADER_BLACKLIST.length; i++) {
            if (upper.indexOf(BOARD_HEADER_BLACKLIST[i]) !== -1) {
                return '';
            }
        }
        return str;
    }

    function isResultPageLoaded() {
        var rollInp = document.querySelector('input[name="roll"], #roll, #prs-roll');
        var capInp = document.querySelector('input[name="captcha"], #captcha, #prs-captcha');
        var scraped = scrapeBoardResult();

        var hasResultData = !!(scraped.name || scraped.gpa || scraped.inst || scraped.physics || scraped.chemistry || scraped.math);
        if ((rollInp || capInp) && !hasResultData) {
            return false;
        }
        return true;
    }

    function syncResult() {
        if (!isResultPageLoaded()) {
            alert("⚠️ Board result is not displayed on this page yet!\n\nPlease enter the roll, registration number & captcha, then click the 'Get Result' / 'Search' button on the board website first before syncing.");
            return;
        }

        chrome.storage.sync.get(['server_url'], function (items) {
            var serverUrl = items.server_url || 'https://portal.baust.edu.bd';

            var savedSid = sessionStorage.getItem('current_verify_sid');
            if (savedSid) {
                showPreSyncModal(savedSid, serverUrl);
            } else if (navigator.clipboard && navigator.clipboard.readText) {
                navigator.clipboard.readText().then(function (txt) {
                    var sidM = txt.match(/StudentID:\s*([A-Za-z0-9_]+)/i) || txt.match(/\b(080\d{13}|\d{16})\b/);
                    if (sidM) {
                        showPreSyncModal(sidM[1], serverUrl);
                    } else {
                        var p = prompt("Enter Student ID to sync:");
                        if (p) showPreSyncModal(p, serverUrl);
                    }
                }).catch(function () {
                    var p = prompt("Enter Student ID to sync:");
                    if (p) showPreSyncModal(p, serverUrl);
                });
            } else {
                var p = prompt("Enter Student ID to sync:");
                if (p) showPreSyncModal(p, serverUrl);
            }
        });
    }

    function showPreSyncModal(sid, serverUrl) {
        var scraped = scrapeBoardResult();

        var existingModal = document.getElementById('baust_sync_modal');
        if (existingModal) existingModal.remove();

        var modal = document.createElement('div');
        modal.id = 'baust_sync_modal';
        modal.style.cssText = `
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            z-index: 99999999;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        `;

        var savedExam = sessionStorage.getItem('current_verify_exam');
        var examType = savedExam || scraped.exam || 'SSC/HSC';

        var nameDisplay = scraped.name ? `<strong style="color:#4ade80; font-size:14px;">${scraped.name}</strong>` : `<span style="color:#fbbf24;">Name Not Scraped / Preserving Profile Name</span>`;
        var gpaDisplay = scraped.gpa ? `<strong style="color:#38bdf8; font-size:14px;">${scraped.gpa}</strong>` : `<span style="color:#fbbf24;">No GPA listed on transcript (Proceeding without GPA)</span>`;
        var fatherDisplay = scraped.father || 'N/A';
        var motherDisplay = scraped.mother || 'N/A';
        var instDisplay = scraped.inst || 'N/A';

        var subjArr = [];
        if (scraped.physics) subjArr.push(`Physics: <strong style="color:#e2e8f0;">${scraped.physics}</strong>`);
        if (scraped.chemistry) subjArr.push(`Chemistry: <strong style="color:#e2e8f0;">${scraped.chemistry}</strong>`);
        if (scraped.math) subjArr.push(`Math: <strong style="color:#e2e8f0;">${scraped.math}</strong>`);
        var subjDisplay = subjArr.length > 0 ? subjArr.join(' | ') : `<span style="color:#94a3b8;">No Physics/Chemistry/Math listed (Non-science or custom stream)</span>`;

        modal.innerHTML = `
            <div style="background: #1e293b; border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 20px; width: 90%; max-width: 480px; padding: 24px; color: #f8fafc; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.6); box-sizing: border-box;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:12px;">
                    <div>
                        <h3 style="margin:0; font-size:16px; color:#38bdf8; font-weight:800;">🔍 Confirm Board Result Sync</h3>
                        <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Student ID: <strong style="color:#f1f5f9;">${sid}</strong> | Exam: <strong style="color:#38bdf8;">${examType}</strong></div>
                    </div>
                    <button id="btn_modal_close_top" style="background:none; border:none; color:#94a3b8; font-size:18px; cursor:pointer; padding:4px;">✕</button>
                </div>

                <div style="background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.08); border-radius:14px; padding:14px 16px; margin-bottom:18px; font-size:12.5px; line-height:1.6; text-align:left;">
                    <div style="margin-bottom:8px;"><strong>Verified Board Name:</strong> ${nameDisplay}</div>
                    <div style="margin-bottom:8px;"><strong>GPA:</strong> ${gpaDisplay}</div>
                    <div style="margin-bottom:6px;"><strong>Father's Name:</strong> <span style="color:#cbd5e1;">${fatherDisplay}</span></div>
                    <div style="margin-bottom:6px;"><strong>Mother's Name:</strong> <span style="color:#cbd5e1;">${motherDisplay}</span></div>
                    <div style="margin-bottom:6px;"><strong>Institute:</strong> <span style="color:#cbd5e1;">${instDisplay}</span></div>
                    <div><strong>Subjects:</strong> ${subjDisplay}</div>
                </div>

                <div style="display:flex; gap:12px;">
                    <button id="btn_modal_cancel" style="flex:1; background:rgba(255,255,255,0.1); color:#cbd5e1; border:none; padding:11px; border-radius:12px; font-weight:bold; cursor:pointer; font-size:13px;">Cancel</button>
                    <button id="btn_modal_confirm" style="flex:2; background:linear-gradient(135deg,#16a34a,#15803d); color:#fff; border:none; padding:11px; border-radius:12px; font-weight:bold; cursor:pointer; font-size:13px; box-shadow:0 4px 15px rgba(22,163,74,0.4);">🚀 Confirm &amp; Sync Data</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        document.getElementById('btn_modal_close_top').onclick = function () { modal.remove(); };
        document.getElementById('btn_modal_cancel').onclick = function () { modal.remove(); };
        document.getElementById('btn_modal_confirm').onclick = function () {
            modal.remove();
            executeSync(sid, serverUrl);
        };
    }

    function executeSync(sid, serverUrl) {
        if (!sid || sid === 'NEW_ADMISSION') {
            copyResultToClipboard();
            return;
        }

        var scraped = scrapeBoardResult();
        var text = document.body.innerText || '';
        var mainTitle = '';
        var headerText = document.title || '';
        var headers = document.querySelectorAll('h1, h2, h3, h4, th, td, .panel-heading, .title, .header');
        for (var h = 0; h < headers.length; h++) headerText += " " + headers[h].innerText;

        var savedExam = sessionStorage.getItem('current_verify_exam');
        var exam = 'SSC';
        if (savedExam) {
            if (savedExam.includes('HSC') || savedExam.includes('ALIM') || savedExam.includes('HSC_VOC') || savedExam.includes('DIPLOMA') || savedExam.includes('POLY') || savedExam.includes('BM')) exam = 'HSC';
            else if (savedExam.includes('SSC') || savedExam.includes('DAKHIL') || savedExam.includes('SSC_VOC')) exam = 'SSC';
        } else {
            var titleEl = document.querySelector('h1, h2, h3, .panel-title, td.title');
            if (titleEl) mainTitle = titleEl.innerText;

            if (/Technical|BTEB|Diploma|Vocational|HSC\s*BM|SSC\s*Voc/i.test(mainTitle + ' ' + headerText)) {
                if (/Higher|HSC|Voc.*12|Voc.*Second\s*Year/i.test(mainTitle + ' ' + headerText)) exam = 'HSC';
                else exam = 'SSC';
            } else if (/Secondary\s*School\s*Certificate|SSC\/Dakhil|Result\s*of\s*SSC/i.test(mainTitle)) exam = 'SSC';
            else if (/Higher\s*Secondary|HSC\/Alim|Result\s*of\s*HSC/i.test(mainTitle)) exam = 'HSC';
            else if (/Higher\s*Secondary/i.test(headerText)) exam = 'HSC';
            else if (/Secondary\s*Certificate/i.test(headerText)) exam = 'SSC';
        }

        var targetEndpoint = serverUrl.replace(/\/$/, '') + '/api/manual-verify-student/';

        var formData = new FormData();
        function addF(n, v) { if (v) formData.append(n, v); }

        addF('student_id', sid.trim());
        addF('exam_type', exam);
        addF('student_name', scraped.name);
        addF('father_name', scraped.father);
        addF('mother_name', scraped.mother);
        addF('gender', scraped.gender);
        addF('dob', scraped.dob);
        addF('gpa', scraped.gpa);
        addF('inst_name', scraped.inst);
        addF('physics', scraped.physics);
        addF('chemistry', scraped.chemistry);
        addF('math', scraped.math);
        addF('source', 'extension');
        addF('format', 'extension');

        var badge = document.getElementById('baust_status_badge');
        if (badge) { badge.innerText = 'SYNCING...'; badge.style.background = 'rgba(251,191,36,0.3)'; badge.style.color = '#fbbf24'; }

        fetch(targetEndpoint, { method: 'POST', body: formData })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (badge) {
                    if (data.success) {
                        badge.innerText = 'SYNCED ✓';
                        badge.style.background = 'rgba(34,197,94,0.3)';
                        badge.style.color = '#4ade80';
                        var curIdx = parseInt(sessionStorage.getItem('batch_index') || '0', 10);
                        sessionStorage.setItem('batch_index', (curIdx + 1).toString());
                        setTimeout(function () {
                            badge.innerText = 'READY';
                            badge.style.background = 'rgba(2,132,199,0.3)';
                            badge.style.color = '#38bdf8';
                        }, 3000);
                    } else {
                        badge.innerText = 'ERROR';
                        badge.style.background = 'rgba(239,68,68,0.3)';
                        badge.style.color = '#f87171';
                        alert('Sync Error: ' + (data.error || 'Unknown error. Check student ID.'));
                    }
                }
            })
            .catch(function (err) {
                if (badge) { badge.innerText = 'FAILED'; badge.style.color = '#f87171'; }
                alert('Network error syncing result: ' + err.message);
            });
    }

    function scrapeBoardResult() {
        var text = document.body.innerText || '';
        var gpa = '', name = '', father = '', mother = '', gender = '', dob = '', inst = '';
        var physics = '', chemistry = '', math = '';

        // BTEB React SPA result page elements (<dl class="prv-identity">, <span class="prv-doc-gpa-value">)
        var btebGpaEl = document.querySelector('.prv-doc-gpa-value, span[class*="gpa-value"]');
        if (btebGpaEl) {
            var gTxt = btebGpaEl.innerText.trim();
            var gM = gTxt.match(/([0-5]\.[0-9]{1,2})/);
            if (gM) gpa = gM[1];
        }

        var identityDl = document.querySelector('dl.prv-identity, dl[class*="identity"]');
        if (identityDl) {
            var dts = identityDl.querySelectorAll('dt');
            var dds = identityDl.querySelectorAll('dd');
            for (var i = 0; i < dts.length; i++) {
                var dtLabel = dts[i].innerText.trim().toLowerCase();
                var ddVal = dds[i] ? dds[i].innerText.trim() : '';
                if (dtLabel.includes('name') && !dtLabel.includes('father') && !dtLabel.includes('mother')) name = cleanBoardName(ddVal);
                if (dtLabel.includes('father')) father = cleanBoardName(ddVal);
                if (dtLabel.includes('mother')) mother = cleanBoardName(ddVal);
                if (dtLabel.includes('birth') || dtLabel.includes('dob')) dob = ddVal;
                if (dtLabel.includes('gender') || dtLabel.includes('sex')) gender = ddVal;
                if (dtLabel.includes('institute')) inst = cleanBoardName(ddVal);
            }
        }

        // Table scraping (Works for both eboardresults and BTEB subject tables)
        var rows = document.querySelectorAll('tr');
        for (var r = 0; r < rows.length; r++) {
            var cols = rows[r].querySelectorAll('td, th');
            if (cols.length >= 2) {
                var rowText = rows[r].innerText.trim().toLowerCase();
                var label = cols[0].innerText.trim().toLowerCase();
                var val = cols[1].innerText.trim();

                if (!name && (label.includes('student') || label.includes('name of examinee') || label === 'name')) {
                    name = cleanBoardName(val);
                }
                if (!father && label.includes('father')) father = cleanBoardName(val);
                if (!mother && label.includes('mother')) mother = cleanBoardName(val);
                if (!gender && (label.includes('gender') || label.includes('sex'))) gender = val;
                if (!dob && (label.includes('date of birth') || label.includes('dob'))) dob = val;
                if (!inst && (label.includes('institute') || label.includes('school') || label.includes('college'))) inst = cleanBoardName(val);
                if (!gpa && (label.includes('gpa') || label.includes('result'))) {
                    var gMatch = val.match(/([0-5]\.[0-9]{1,2})/);
                    if (gMatch) gpa = gMatch[1];
                }

                var lastColText = cols[cols.length - 1].innerText.trim();
                var gMatchSubj = lastColText.match(/(A\+|A\-|A|B|C|D|F|[0-5]\.[0-9]{1,2})/i);
                if (!gMatchSubj && cols.length >= 3) {
                    var midColText = cols[cols.length - 2].innerText.trim();
                    gMatchSubj = midColText.match(/(A\+|A\-|A|B|C|D|F|[0-5]\.[0-9]{1,2})/i);
                }
                var gradeVal = gMatchSubj ? gMatchSubj[1].toUpperCase() : lastColText;

                if (rowText.includes('physics')) physics = physics || gradeVal;
                if (rowText.includes('chemistry')) chemistry = chemistry || gradeVal;
                if (rowText.includes('math')) math = math || gradeVal;
            }
        }

        // Fallback text regex patterns
        if (!name) { var nM = text.match(/Name\s*[:\-\s]+([^\n\r]+)/i); if (nM) name = cleanBoardName(nM[1]); }
        if (!father) { var fM = text.match(/Father['’]?s?\s*Name\s*[:\-\s]+([^\n\r]+)/i); if (fM) father = cleanBoardName(fM[1]); }
        if (!mother) { var mM = text.match(/Mother['’]?s?\s*Name\s*[:\-\s]+([^\n\r]+)/i); if (mM) mother = cleanBoardName(mM[1]); }
        if (!gender) { var gM = text.match(/Gender\s*[:\-\s]+([A-Za-z]+)/i) || text.match(/Sex\s*[:\-\s]+([A-Za-z]+)/i); if (gM) gender = gM[1].trim(); }
        if (!dob) { var dM = text.match(/Date\s*of\s*Birth\s*[:\-\s]+([0-9\-\/\w]+)/i) || text.match(/DOB\s*[:\-\s]+([0-9\-\/\w]+)/i); if (dM) dob = dM[1].trim(); }
        if (!inst) { var iM = text.match(/Institute\s*[:\-\s]+([^\n\r]+)/i); if (iM) inst = cleanBoardName(iM[1]); }

        if (!gpa) {
            var gpaM = text.match(/GPA\s*[:=\s]+([0-5]\.[0-9]{1,2})/i) || text.match(/Result\s*[:\-\s]+PASSED?\s*\(?\s*([0-5]\.[0-9]{1,2})\)?/i) || text.match(/PASSED[^\d]*?([0-5]\.[0-9]{1,2})/i) || text.match(/GPA[^\d]*?([0-5]\.[0-9]{2})/i) || text.match(/([0-5]\.[0-9]{2})/i);
            if (gpaM) gpa = gpaM[1].trim();
        }

        return {
            name: name, father: father, mother: mother, gender: gender,
            dob: dob, gpa: gpa, inst: inst, physics: physics,
            chemistry: chemistry, math: math
        };
    }

    function copyResultToClipboard() {
        if (!isResultPageLoaded()) {
            alert("⚠️ Board result is not displayed on this page yet!\n\nPlease enter the roll, registration number & captcha, then click the 'Get Result' / 'Search' button on the board website first before copying.");
            return;
        }

        var scraped = scrapeBoardResult();
        if (!scraped || (!scraped.name && !scraped.gpa && !scraped.inst)) {
            alert("No board result found on this page yet. Please enter roll, registration & captcha, then click Submit first!");
            return;
        }

        var pageText = document.body.innerText || '';
        var curExam = sessionStorage.getItem('current_verify_exam') || scraped.exam || '';
        if (!curExam) {
            var examSel = document.querySelector('select[name="exam"]') || document.getElementById('exam');
            if (examSel && examSel.options && examSel.selectedIndex >= 0) {
                curExam = examSel.options[examSel.selectedIndex].text;
            }
        }
        if (!curExam) {
            if (/hsc|alim|diploma/i.test(pageText)) curExam = 'HSC';
            else if (/ssc|dakhil/i.test(pageText)) curExam = 'SSC';
        }

        var textArr = [];
        if (curExam) textArr.push("Exam: " + curExam.trim().toUpperCase());
        if (scraped.name) textArr.push("Name: " + scraped.name);
        if (scraped.father) textArr.push("Father's Name: " + scraped.father);
        if (scraped.mother) textArr.push("Mother's Name: " + scraped.mother);
        if (scraped.gender) textArr.push("Gender: " + scraped.gender);
        if (scraped.dob) textArr.push("Date of Birth: " + scraped.dob);
        if (scraped.gpa) textArr.push("GPA: " + scraped.gpa);
        if (scraped.inst) textArr.push("Institute: " + scraped.inst);
        if (scraped.physics) textArr.push("Physics: " + scraped.physics);
        if (scraped.chemistry) textArr.push("Chemistry: " + scraped.chemistry);
        if (scraped.math) textArr.push("Math: " + scraped.math);

        var copyStr = textArr.join(" | ");

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(copyStr).then(function () {
                var badge = document.getElementById('baust_status_badge');
                if (badge) {
                    badge.innerText = 'COPIED ✓';
                    badge.style.background = 'rgba(217,119,6,0.3)';
                    badge.style.color = '#fbbf24';
                    setTimeout(function () {
                        badge.innerText = 'READY';
                        badge.style.background = 'rgba(2,132,199,0.3)';
                        badge.style.color = '#38bdf8';
                    }, 3000);
                }
                alert("Board Result Copied to Clipboard!\n\nSwitch back to the Admission System and click 'Paste Result'.");
            });
        } else {
            prompt("Copy this result text, then click 'Paste Result' on the Admission System form:", copyStr);
        }
    }

    setTimeout(injectWidget, 500);
})();
