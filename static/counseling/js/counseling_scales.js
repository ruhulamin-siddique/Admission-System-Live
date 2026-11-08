/**
 * counseling_scales.js
 * ====================
 * Client-side reactivity for:
 * 1. Discretion / Privacy Desk Shield Blur Toggle (Alt+P)
 * 2. Dynamic PHQ-9, GAD-7, and DASS-21 live score calculation & gauge animation
 * 3. Keyboard hotkeys for fast assessment completion (Keys 1, 2, 3, 4)
 * 4. SOAP note localStorage auto-save draft & restore
 * 5. One-click clinical snippet insertion
 */

document.addEventListener('DOMContentLoaded', function () {

  // --------------------------------------------------------------------------
  // 1. Discretion / Privacy Desk Shield
  // --------------------------------------------------------------------------
  const privacyToggleBtn = document.getElementById('privacyShieldToggle');
  const isPrivacySaved = localStorage.getItem('counseling_privacy_mode') === 'true';

  if (isPrivacySaved) {
    document.body.classList.add('privacy-mode-active');
    if (privacyToggleBtn) privacyToggleBtn.classList.add('btn-danger');
  }

  window.toggleCounselingPrivacy = function () {
    const isActive = document.body.classList.toggle('privacy-mode-active');
    localStorage.setItem('counseling_privacy_mode', isActive);
    if (privacyToggleBtn) {
      if (isActive) {
        privacyToggleBtn.innerHTML = '<i class="fas fa-eye-slash mr-1"></i> <span>Privacy Shield ON</span>';
      } else {
        privacyToggleBtn.innerHTML = '<i class="fas fa-eye mr-1"></i> <span>Privacy Shield</span>';
      }
    }
  };

  if (privacyToggleBtn) {
    privacyToggleBtn.addEventListener('click', window.toggleCounselingPrivacy);
  }

  // Keyboard shortcut: Alt + P
  document.addEventListener('keydown', function (e) {
    if (e.altKey && (e.key === 'p' || e.key === 'P')) {
      e.preventDefault();
      window.toggleCounselingPrivacy();
    }
  });


  // --------------------------------------------------------------------------
  // 2. Assessment Live Score & Gauge Calculation
  // --------------------------------------------------------------------------
  const scaleForm = document.getElementById('psychAssessmentForm');
  const scaleTypeInput = document.getElementById('scaleTypeInput');

  if (scaleForm && scaleTypeInput) {
    const scaleType = scaleTypeInput.value.toUpperCase();
    const scoreDisplay = document.getElementById('liveScoreValue');
    const tierDisplay = document.getElementById('liveSeverityTier');
    const progressBar = document.getElementById('assessmentProgressBar');
    const allQuestions = scaleForm.querySelectorAll('.scale-question-card');
    const totalQuestionsCount = allQuestions.length;

    function recalculateScore() {
      let total = 0;
      let answeredCount = 0;
      const responses = {};

      allQuestions.forEach((qCard) => {
        const qid = qCard.dataset.qid;
        const checked = qCard.querySelector('input[type="radio"]:checked');
        if (checked) {
          const val = parseInt(checked.value, 10);
          total += val;
          answeredCount++;
          responses[qid] = val;
        }
      });

      // Progress bar
      const progressPercent = Math.round((answeredCount / totalQuestionsCount) * 100);
      if (progressBar) {
        progressBar.style.width = progressPercent + '%';
        progressBar.setAttribute('aria-valuenow', progressPercent);
      }

      // Compute Tiers
      let tierText = 'Incomplete';
      let tierColor = '#1e40af';

      if (scaleType === 'PHQ9') {
        if (total <= 4) { tierText = 'Minimal / No Depression'; tierColor = '#10b981'; }
        else if (total <= 9) { tierText = 'Mild Depression'; tierColor = '#0284c7'; }
        else if (total <= 14) { tierText = 'Moderate Depression'; tierColor = '#f59e0b'; }
        else if (total <= 19) { tierText = 'Moderately Severe Depression'; tierColor = '#f97316'; }
        else { tierText = 'Severe Depression'; tierColor = '#ef4444'; }
      } else if (scaleType === 'GAD7') {
        if (total <= 4) { tierText = 'Minimal Anxiety'; tierColor = '#10b981'; }
        else if (total <= 9) { tierText = 'Mild Anxiety'; tierColor = '#0284c7'; }
        else if (total <= 14) { tierText = 'Moderate Anxiety'; tierColor = '#f59e0b'; }
        else { tierText = 'Severe Anxiety'; tierColor = '#ef4444'; }
      } else if (scaleType === 'DASS21') {
        tierText = 'Multi-Scale Sum: ' + total;
        tierColor = '#0d9488';
      }

      if (scoreDisplay) {
        scoreDisplay.textContent = total;
        scoreDisplay.style.color = tierColor;
      }
      if (tierDisplay) {
        tierDisplay.textContent = tierText;
        tierDisplay.style.color = tierColor;
      }
    }

    scaleForm.addEventListener('change', recalculateScore);
    recalculateScore(); // initial run

    // Keyboard Shortcuts (1, 2, 3, 4)
    document.addEventListener('keydown', function (e) {
      if (['1', '2', '3', '4'].includes(e.key) && document.activeElement.tagName !== 'TEXTAREA') {
        const val = parseInt(e.key, 10) - 1; // '1'->0, '2'->1, '3'->2, '4'->3
        // Find next unanswered question
        for (let i = 0; i < allQuestions.length; i++) {
          const qCard = allQuestions[i];
          const isAnswered = qCard.querySelector('input[type="radio"]:checked');
          if (!isAnswered) {
            const targetRadio = qCard.querySelector(`input[type="radio"][value="${val}"]`);
            if (targetRadio) {
              targetRadio.checked = true;
              recalculateScore();
              // Scroll smoothly to next
              if (allQuestions[i + 1]) {
                allQuestions[i + 1].scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            }
            break;
          }
        }
      }
    });
  }


  // --------------------------------------------------------------------------
  // 3. SOAP Notes LocalStorage Auto-Draft & Snippet Insertion
  // --------------------------------------------------------------------------
  const soapForm = document.getElementById('soapRecordForm');
  if (soapForm) {
    const caseId = soapForm.dataset.caseId || 'new';
    const draftKey = `counseling_soap_draft_${caseId}`;
    const fields = ['id_subjective', 'id_objective', 'id_assessment', 'id_plan'];
    const autoSaveBadge = document.getElementById('soapAutoSaveBadge');

    // Restore draft if exists and fields are empty
    const savedDraft = localStorage.getItem(draftKey);
    if (savedDraft) {
      try {
        const data = JSON.parse(savedDraft);
        fields.forEach(fId => {
          const el = document.getElementById(fId);
          if (el && !el.value && data[fId]) {
            el.value = data[fId];
          }
        });
        if (autoSaveBadge) autoSaveBadge.textContent = 'Restored unsaved draft from local storage.';
      } catch (err) {}
    }

    // Auto-save interval (every 5 seconds)
    setInterval(function () {
      const data = {};
      let hasContent = false;
      fields.forEach(fId => {
        const el = document.getElementById(fId);
        if (el) {
          data[fId] = el.value;
          if (el.value.trim()) hasContent = true;
        }
      });
      if (hasContent) {
        localStorage.setItem(draftKey, JSON.stringify(data));
        if (autoSaveBadge) {
          const timeStr = new Date().toLocaleTimeString();
          autoSaveBadge.innerHTML = `<i class="fas fa-check-circle text-success mr-1"></i> Draft auto-saved at ${timeStr}`;
        }
      }
    }, 5000);

    // Clear draft on successful submit
    soapForm.addEventListener('submit', function () {
      localStorage.removeItem(draftKey);
    });

    // Snippet Click Insert
    document.querySelectorAll('.snippet-chip').forEach(chip => {
      chip.addEventListener('click', function () {
        const targetFieldId = this.dataset.target;
        const snippetText = this.dataset.snippet;
        const targetEl = document.getElementById(targetFieldId);
        if (targetEl) {
          if (targetEl.value.trim().length > 0) {
            targetEl.value += '\n• ' + snippetText;
          } else {
            targetEl.value = '• ' + snippetText;
          }
          targetEl.focus();
        }
      });
    });
  }

});
