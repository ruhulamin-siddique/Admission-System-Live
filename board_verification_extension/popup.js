function switchTab(tabId, el) {
    var tabs = document.querySelectorAll('.nav-tab');
    var panes = document.querySelectorAll('.tab-pane');

    tabs.forEach(function (t) { t.classList.remove('active'); });
    panes.forEach(function (p) { p.classList.remove('active'); });

    var targetPane = document.getElementById(tabId);
    if (targetPane) targetPane.classList.add('active');
    if (el) el.classList.add('active');
}

document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('server_url');
    var btn = document.getElementById('btn_save');
    var status = document.getElementById('save_status');

    chrome.storage.sync.get(['server_url', 'stat_verified', 'stat_mismatch'], function (items) {
        input.value = items.server_url || 'https://portal.baust.edu.bd';
        document.getElementById('stat_verified').innerText = items.stat_verified || '0';
        document.getElementById('stat_mismatch').innerText = items.stat_mismatch || '0';
    });

    btn.addEventListener('click', function () {
        var url = input.value.trim() || 'https://portal.baust.edu.bd';
        chrome.storage.sync.set({ server_url: url }, function () {
            status.style.display = 'block';
            setTimeout(function () { status.style.display = 'none'; }, 2000);
        });
    });

    // Batch Queue Runner
    document.getElementById('btn_run_queue').addEventListener('click', function () {
        var batch = document.getElementById('queue_batch_filter').value;
        var sUrl = input.value.trim() || 'https://portal.baust.edu.bd';
        var endpoint = sUrl.replace(/\/$/, '') + '/api/batch-verify-queue/?batch=' + encodeURIComponent(batch);

        document.getElementById('queue_progress_box').innerText = 'Fetching queue from server...';

        fetch(endpoint)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success && data.queue.length > 0) {
                    document.getElementById('queue_progress_box').innerText = 'Loaded ' + data.queue.length + ' students into queue!';
                    // Bug #3 Fix: stringify before storing — content.js uses JSON.parse() to read it
                    chrome.storage.local.set({ batch_queue: JSON.stringify(data.queue), batch_index: '0' });
                } else {
                    document.getElementById('queue_progress_box').innerText = 'No unverified students found in batch.';
                }
            })
            .catch(function (err) {
                document.getElementById('queue_progress_box').innerText = 'Error connecting to server endpoint.';
            });
    });

    // BTEB Technical Mode Toggle
    document.getElementById('btn_bteb_mode').addEventListener('click', function () {
        var p = document.getElementById('bteb_exam_type').value;
        chrome.storage.sync.set({ bteb_mode: p }, function () {
            alert('BTEB Mode activated for ' + p + '! Open eboardresults.com to auto-select Technical Board.');
        });
    });
});
