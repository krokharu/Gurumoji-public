/* 公開版の画面処理: processing。共有状態はapp.jsで管理する。 */
function handleInputFileSelection() {
  setAlert(pathError, '');
  const file = inputFile.files && inputFile.files[0];
  if (file) {
    if (!/\.(mp4|m4v|mov|mkv|wav|mp3|m4a|flac)$/i.test(file.name)) {
      inputFile.value = '';
      sourcePath.value = '';
      hideSourcePreview();
      pathDetail.textContent = 'ファイルが選択されていません';
      setAlert(pathError, '対応している動画・音声ファイルを選択してください。', true);
      updateCreateSummary();
      return;
    }
    sourcePath.value = '';
    pathDetail.textContent = browserFilePickerOnly
      ? `${file.name} / ${formatBytes(file.size)} — Colabへ一時アップロードして処理します`
      : `${file.name} / ${formatBytes(file.size)} — Gurumoji実行環境へ一時コピーして処理します`;
    hideSourcePreview();
  } else if (!sourcePath.value.trim()) {
    pathDetail.textContent = 'ファイルが選択されていません';
  }
  updateCreateSummary();
}

function setHardwareLight(element, available, availableText, unavailableText, title = '') {
  if (!element) return;
  element.classList.remove('checking', 'available', 'unavailable');
  element.classList.add(available ? 'available' : 'unavailable');
  element.textContent = available ? availableText : unavailableText;
  element.title = title;
}

function setHardwareLights(kind, available, availableText, unavailableText, title = '') {
  document.querySelectorAll(`[data-hardware="${kind}"]`).forEach(element => {
    setHardwareLight(element, available, availableText, unavailableText, title);
  });
  document.querySelectorAll(`[data-device-dot="${kind}"]`).forEach(element => {
    element.classList.remove('checking', 'available', 'unavailable');
    element.classList.add(available ? 'available' : 'unavailable');
    element.title = title;
  });
}

function applyMachineProfile(machine, {reset = false} = {}) {
  if (!machine) return;
  lastMachineProfile = machine;
  if (reset) manuallySelectedMachineFields.clear();
  const changes = [];
  const cpu = machine.cpu || {};
  const gpu = machine.gpu || {};
  const recommended = machine.recommended || {};
  const summary = document.querySelector('#machine-summary');
  const recommendation = document.querySelector('#machine-recommendation');
  const modelSelect = document.querySelector('#model-name');
  const transcriptionDevice = document.querySelector('#transcription-device');
  const diarizationDevice = document.querySelector('#diarization-device');

  setHardwareLights(
    'cpu',
    Boolean(cpu.available),
    'CPU 利用可',
    'CPU 利用不可',
    `${cpu.name || 'CPU'} / ${cpu.logical_threads || '?'} threads`
  );
  setHardwareLights(
    'gpu',
    Boolean(gpu.cuda_available),
    'GPU 利用可',
    'GPU 利用不可',
    gpu.cuda_available
      ? `${gpu.name || 'CUDA GPU'} / VRAM ${Number(gpu.vram_gib || 0).toFixed(1)} GB`
      : (gpu.reason || 'CUDAを利用できません')
  );

  const cpuParts = [
    cpu.name || 'CPU',
    `${cpu.logical_threads || '?'} threads`,
  ];
  if (Number(machine.memory_gib) > 0) cpuParts.push(`RAM ${Number(machine.memory_gib).toFixed(1)} GB`);
  const gpuText = gpu.cuda_available
    ? `${gpu.name} / VRAM ${Number(gpu.vram_gib || 0).toFixed(1)} GB / CUDA ${gpu.cuda_version || '?'} / CC ${gpu.capability || '?'}`
    : (gpu.reason || 'CUDA GPUは利用できません');
  if (summary) summary.textContent = `${cpuParts.join(' / ')}　｜　${gpuText}`;

  [transcriptionDevice, diarizationDevice].forEach(select => {
    if (!select) return;
    const cudaOption = select.querySelector('option[value="cuda"]');
    if (cudaOption) cudaOption.disabled = !gpu.cuda_available;
    if (!gpu.cuda_available && select.value === 'cuda') {
      select.value = 'cpu';
      changes.push('選択したGPUを利用できないためCPUに変更しました');
    }
  });

  if (modelSelect && !manuallySelectedMachineFields.has(modelSelect.id) && [...modelSelect.options].some(option => option.value === recommended.model_name)) {
    modelSelect.value = recommended.model_name;
  }
  if (transcriptionDevice && !manuallySelectedMachineFields.has(transcriptionDevice.id) && [...transcriptionDevice.options].some(option => (
    option.value === recommended.device && !option.disabled
  ))) {
    transcriptionDevice.value = recommended.device;
  }
  if (diarizationDevice && !manuallySelectedMachineFields.has(diarizationDevice.id) && [...diarizationDevice.options].some(option => (
    option.value === recommended.diarization_device && !option.disabled
  ))) {
    diarizationDevice.value = recommended.diarization_device;
  }

  if (recommendation) {
    const deviceLabel = recommended.device === 'cuda' ? 'GPU' : 'CPU';
    const diarizationLabel = recommended.diarization_device === 'cuda' ? 'GPU' : 'CPU';
    recommendation.textContent = recommended.model_name
      ? `推奨設定（手動選択を保持）: ${recommended.model_name} / 文字起こし ${deviceLabel} / 話者分離 ${diarizationLabel}。${recommended.reason || ''}`
      : '';
  }
  setAlert(document.querySelector('#machine-selection-message'), [...new Set(changes)].join('。'), Boolean(changes.length));
  syncTranscriptionBackend();
  updateCreateSummary();
}

async function loadConfig() {
  const message = document.querySelector('#token-message');
  if (!message) return;
  configLoadState = 'loading';
  updateCreateSummary();
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await apiFetch('/api/config', {cache: 'no-store', signal: controller.signal});
    const data = await readJsonResponse(response);
    if (!response.ok || !data.ok) throw new Error(data.error || '設定を取得できません');
    tokenConfigSnapshot = data && typeof data === 'object' ? data : {};
    configLoadState = 'loaded';
    applyMachineProfile(data.machine);

    const runtime = data.runtime || {};
    browserFilePickerOnly = Boolean(runtime.browser_upload);
    if (browsePathButton) {
      browsePathButton.dataset.pickerMode = browserFilePickerOnly ? 'browser' : 'native';
      updateBrowseButtonLabel();
    }
    if (!response.ok || !data.ok) throw new Error(data.error || '設定を取得できません');
    const recognized = [];
    const localLlmShortLabel = String(data.local_llm_short_label || 'LM Studio');
    [
      ['hf', 'huggingface', 'Hugging Face'],
      ['openai', 'openai', 'OpenAI'],
      ['google', 'google', 'Google'],
      ['typesafe', 'typesafe', 'TypeSafe Jev'],
      ['lmstudio', 'lmstudio', localLlmShortLabel]
    ].forEach(([id, key, label]) => {
      // The hero pills are hidden on phones; the mobile header repeats them (UX-10).
      document.querySelectorAll(`#status-${id}, [data-status-provider="${id}"]`).forEach(pill => {
        pill.classList.remove('loading', 'ready', 'missing');
        pill.classList.add(data[key] ? 'ready' : 'missing');
        pill.textContent = data[key] ? `${label} ✓` : label;
        const lmStudioStatus = key === 'lmstudio' && data.lmstudio_status && typeof data.lmstudio_status === 'object'
          ? data.lmstudio_status : null;
        pill.title = lmStudioStatus
          ? String(lmStudioStatus.message || '')
          : (data[key] ? '設定済み' : '未設定');
        if (pill.dataset.modelProvider) {
          const currentModel = String(data[`${key}_model`] || '').trim();
          pill.dataset.currentModel = currentModel;
          pill.title = key === 'lmstudio'
            ? `${lmStudioStatus && lmStudioStatus.message || 'ローカルLLMの状態を確認できません。'}${currentModel ? ` 現在: ${currentModel}` : ''}`
            : data[key]
            ? `クリックしてモデルを変更（現在: ${currentModel || 'tokens.json の設定'}）`
            : `${label} APIキーがtokens.jsonに設定されていません`;
        }
      });
      document.querySelectorAll(`[data-provider-model="${key}"]`).forEach(element => {
        element.textContent = String(data[`${key}_model`] || '').trim() || '未設定';
      });
      document.querySelectorAll(`[data-connection-dot="${id}"]`).forEach(dot => {
        dot.classList.toggle('ready', Boolean(data[key]));
        dot.classList.toggle('missing', !data[key]);
      });
      if (data[key]) recognized.push(label);
    });
    const outputDir = document.querySelector('#output-dir');
    if (outputDir) outputDir.placeholder = data.default_output_dir;
    message.textContent = recognized.length
      ? `利用可能: ${recognized.join(' / ')}。発光している項目を使用できます。`
      : 'トークンを認識できません。tokens.json を確認してください。';
    applyLmStudioDefaults(data);
    syncAiFields();
    updateCreateSummary();
  } catch (error) {
    configLoadState = 'error';
    message.textContent = error.name === 'AbortError'
      ? '設定確認がタイムアウトしました。アプリを再起動して http://127.0.0.1:7860 を開き直してください。'
      : error.message;
    message.style.color = '#913733';
  } finally {
    window.clearTimeout(timeoutId);
    updateCreateSummary();
  }
}


function applyLmStudioDefaults(config) {
  // A ready, explicitly selected local model is an opt-in.  Make the
  // transcription form ready to use it without requiring three more clicks.
  // Do not choose the local server when it is offline or a model was not
  // selected yet: either state would make the default form fail at submission.
  if (!aiProvider || aiProviderManuallySelected || aiProvider.value !== 'none' || !config || !config.lmstudio || !String(config.lmstudio_model || '').trim()) return;
  aiProvider.value = 'lmstudio';
  applyTranscriptFinishingPreset();
  syncAiFields();
  updateCreateSummary();
}

function clearSystemActivityPolling() {
  if (systemActivityTimer !== null) window.clearTimeout(systemActivityTimer);
  systemActivityTimer = null;
  if (systemActivityController) systemActivityController.abort();
  systemActivityController = null;
}

function formatActivityRate(mebibytesPerSecond) {
  const value = Math.max(0, Number(mebibytesPerSecond) || 0);
  if (value >= 1) return `${value.toFixed(value >= 10 ? 0 : 1)} MB/s`;
  return `${Math.round(value * 1024)} KB/s`;
}

function setResourceMetric(name, payload, detail) {
  const available = Boolean(payload && payload.available);
  const percent = Math.max(0, Math.min(100, Number(payload && payload.utilization_percent) || 0));
  const value = document.querySelector(`#monitor-${name}-value`);
  const bar = document.querySelector(`#monitor-${name}-bar`);
  const detailElement = document.querySelector(`#monitor-${name}-detail`);
  const card = value ? value.closest('.resource-metric') : null;
  if (value) {
    const displayedPercent = name === 'cpu' ? percent.toFixed(1) : Math.round(percent);
    value.textContent = available ? `${displayedPercent}%` : '--%';
  }
  if (bar) bar.style.width = available ? `${percent}%` : '0%';
  if (detailElement) detailElement.textContent = available ? detail : '利用できません';
  if (card) card.classList.toggle('is-unavailable', !available);
}

function renderSystemActivity(activity) {
  document.querySelectorAll('.resource-metric').forEach(card => card.classList.remove('is-stale'));
  const cpu = activity && activity.cpu ? activity.cpu : {};
  const memory = activity && activity.memory ? activity.memory : {};
  const gpu = activity && activity.gpu ? activity.gpu : {};
  const disk = activity && activity.disk ? activity.disk : {};
  setResourceMetric('cpu', cpu, 'システム全体の使用率');
  setResourceMetric(
    'memory',
    memory,
    `${Number(memory.used_gib || 0).toFixed(1)} / ${Number(memory.total_gib || 0).toFixed(1)} GB`
  );
  setResourceMetric(
    'gpu',
    gpu,
    gpu.available
      ? `VRAM ${Number(gpu.memory_used_gib || 0).toFixed(1)} / ${Number(gpu.memory_total_gib || 0).toFixed(1)} GB (${Math.round(Number(gpu.memory_percent || 0))}%)`
      : ''
  );
  const readLight = document.querySelector('#monitor-read-light');
  const writeLight = document.querySelector('#monitor-write-light');
  const readRate = document.querySelector('#monitor-read-rate');
  const writeRate = document.querySelector('#monitor-write-rate');
  if (readLight) readLight.classList.toggle('is-active', Boolean(disk.available && disk.read_active));
  if (writeLight) writeLight.classList.toggle('is-active', Boolean(disk.available && disk.write_active));
  if (readRate) readRate.textContent = disk.available ? formatActivityRate(disk.read_mib_per_second) : '--';
  if (writeRate) writeRate.textContent = disk.available ? formatActivityRate(disk.write_mib_per_second) : '--';
}

function scheduleSystemActivityPolling() {
  if (!jobRunning || systemActivityTimer !== null || systemActivityController) return;
  systemActivityTimer = window.setTimeout(() => {
    systemActivityTimer = null;
    pollSystemActivity();
  }, systemActivityDelayMs);
}

async function pollSystemActivity() {
  if (!jobRunning || !progressCard || progressCard.hidden || systemActivityController) return;
  const controller = new AbortController();
  systemActivityController = controller;
  try {
    const response = await apiFetch('/api/system/activity', {cache: 'no-store', signal: controller.signal});
    const activity = await readJsonResponse(response);
    if (!response.ok) throw new Error(activity.error || 'システム使用状況を取得できませんでした。');
    if (jobRunning) renderSystemActivity(activity);
  } catch (error) {
    if (error.name !== 'AbortError') {
      document.querySelectorAll('.resource-metric').forEach(card => card.classList.add('is-stale'));
    }
  } finally {
    if (systemActivityController === controller) systemActivityController = null;
    scheduleSystemActivityPolling();
  }
}

function startSystemActivityPolling() {
  if (!jobRunning || !progressCard || progressCard.hidden) return;
  if (systemActivityTimer === null && !systemActivityController) pollSystemActivity();
}

function setRunning(running) {
  if (!form) return;
  jobRunning = running;
  if (running) startSystemActivityPolling();
  else clearSystemActivityPolling();
  [...form.elements].forEach(element => {
    element.disabled = running || element.dataset.alwaysDisabled === 'true';
  });
  if (fixedSpeakerCountInput) fixedSpeakerCountInput.disabled = running || !isSpeakerCountFixed();
  if (cancelButton) cancelButton.disabled = !running;
  syncQuietFields();

  syncAiFields();
  updateCreateSummary();
  syncCreateViewState();
}

function syncQuietFields() {
  const controlsDisabled = (boostQuietSpeech && boostQuietSpeech.disabled) || (triplePass && triplePass.disabled);
  const enabled = ((boostQuietSpeech && boostQuietSpeech.checked) || (triplePass && triplePass.checked)) && !controlsDisabled;
  [vadOnset, vadOffset].forEach(input => { if (input) input.disabled = !enabled; });
}


function syncAiFields() {
  if (!aiProvider) return;
  const providerDisabled = aiProvider.disabled;
  const disabled = providerDisabled || aiProvider.value === 'none';
  aiOptionInputs.forEach(input => {
    if (aiProvider.value === 'none') input.checked = false;
    input.disabled = disabled;
    const row = input.closest('.check-row');
    if (row) row.classList.toggle('disabled', disabled);
  });
  if (jevCompare) {
    const jevDisabled = disabled || !tokenConfigSnapshot.typesafe;
    if (jevDisabled) jevCompare.checked = false;
    jevCompare.disabled = jevDisabled;
    const row = jevCompare.closest('.check-row');
    if (row) row.classList.toggle('disabled', jevDisabled);
    if (jevConfigStatus) {
      jevConfigStatus.textContent = tokenConfigSnapshot.typesafe
        ? `TypeSafe ${tokenConfigSnapshot.typesafe_model || 'jev-latest'} を使用できます。`
        : 'おすすめのJev判定／Jev比較には tokens.json の typesafe_api_key が必要です。';
    }
  }
  if (typeof syncAiEffortSettings === 'function') syncAiEffortSettings();
}

function selectedTranscriptFinishingMode() {
  const selected = transcriptFinishingModeInputs.find(input => input.checked);
  return selected ? selected.value : 'recommended';
}

function applyTranscriptFinishingModeChange() {
  const mode = selectedTranscriptFinishingMode();
  if (mode === lastTranscriptFinishingMode) return;
  const controls = [cleanTranscript, detectNames, createOutline, jevCompare];
  transcriptFinishingPreferences.set(lastTranscriptFinishingMode, controls.map(input => Boolean(input?.checked)));
  const saved = transcriptFinishingPreferences.get(mode);
  applyTranscriptFinishingPreset();
  if (saved) controls.forEach((input, index) => { if (input) input.checked = saved[index]; });
  lastTranscriptFinishingMode = mode;
}

function applyTranscriptFinishingPreset() {
  const mode = selectedTranscriptFinishingMode();
  const hasAi = Boolean(aiProvider && aiProvider.value !== 'none');
  if (cleanTranscript) cleanTranscript.checked = mode === 'advanced' && hasAi;
  if (detectNames) detectNames.checked = mode !== 'off' && hasAi;
  if (createOutline) createOutline.checked = mode === 'advanced' && hasAi;
  // An additional external destination must be an explicit choice.
  if (jevCompare && (mode !== 'advanced' || !hasAi)) jevCompare.checked = false;
  document.querySelectorAll('[data-advanced-finishing-only]').forEach(row => {
    row.hidden = mode !== 'advanced';
  });
  document.querySelectorAll('[data-speaker-finishing-option]').forEach(row => {
    row.hidden = mode === 'off';
  });
  if (finishingModeHint) {
    finishingModeHint.textContent = {
      recommended: 'AI仕上げを使う場合は、必要な箇所だけ読みやすく整えます。',
      advanced: '文章全体を見直します。話者の確認や比較など、追加の処理も選べます。',
      off: '文章は変更せず、認識結果をそのまま残します。'
    }[mode] || '';
  }
}

function selectDefaultAiOptions() {
  if (!aiProvider) return;
  applyTranscriptFinishingPreset();
  syncAiFields();
  updateCreateSummary();
}

function syncFinishingMode() {
  const mode = selectedTranscriptFinishingMode();
  document.querySelectorAll('[data-advanced-finishing-only]').forEach(row => {
    row.hidden = mode !== 'advanced';
  });
  document.querySelectorAll('[data-speaker-finishing-option]').forEach(row => {
    row.hidden = mode === 'off';
  });
}

function syncSidebarPanels() {
  sidebarPanelButtons.forEach(button => {
    const panel = settingsPanels.find(item => item.dataset.settingsPanel === button.dataset.openPanel);
    button.classList.toggle('active', Boolean(panel && panel.open));
  });
}

function jobFromPayload(payload) {
  if (!payload || typeof payload !== 'object') return null;
  if (payload.id && payload.status) return payload;
  for (const key of ['job', 'active_job', 'activeJob']) {
    const job = payload[key];
    if (job && typeof job === 'object' && job.id && job.status) return job;
  }
  return null;
}

function clearPollTimer() {
  if (pollTimer !== null) window.clearTimeout(pollTimer);
  pollTimer = null;
}

function schedulePoll(delay = pollBaseDelayMs) {
  clearPollTimer();
  if (!activeJobId || !jobRunning) return;
  pollTimer = window.setTimeout(() => {
    pollTimer = null;
    pollJob();
  }, delay);
}

async function fetchActiveJob() {
  const response = await apiFetch('/api/jobs/active', {cache: 'no-store'});
  if (response.status === 204 || response.status === 404) return null;
  const payload = await readJsonResponse(response);
  if (!response.ok) throw new Error(payload.error || '実行中ジョブを確認できませんでした。');
  return jobFromPayload(payload);
}

async function fetchPersistedJob(jobId) {
  if (!jobId) return null;
  const response = await apiFetch(`/api/library/${encodeURIComponent(jobId)}`, {cache: 'no-store'});
  if (response.status === 404) return null;
  const payload = await readJsonResponse(response);
  if (!response.ok) throw new Error(payload.error || '保存済み結果を確認できませんでした。');
  return jobFromPayload(payload);
}

function resumeJob(job, {scroll = false} = {}) {
  if (!job || !job.id) return false;
  const cancellable = ['queued', 'running'].includes(job.status);
  const active = cancellable || ['admitting', 'committing'].includes(job.status);
  activeJobId = String(job.id);
  storePendingSubmissionId('');
  clearPollTimer();
  renderProgress(job);
  showProgressCard({scroll});
  if (active) {
    storeActiveJobId(activeJobId);
    setRunning(true);
    if (cancelButton) cancelButton.disabled = !cancellable;
    schedulePoll();
    return true;
  }
  storeActiveJobId('');
  activeJobId = null;
  setRunning(false);
  if (cancelButton) cancelButton.disabled = true;
  if (job.status === 'completed') {
    // Open the result only while the progress screen is on view. Elsewhere the
    // header chip offers it, so a record being edited is never replaced (UX-16).
    if (createView && !createView.hidden) {
      completedJob = null;
      renderResult(job);
    } else {
      completedJob = job;
      updateJobChip(job);
    }
  }
  return true;
}

async function restoreActiveJob() {
  const restoreGeneration = ++jobFlowGeneration;
  setRunning(true);
  if (cancelButton) cancelButton.disabled = true;
  const storedId = storedActiveJobId();
  if (storedId) {
    try {
      const response = await apiFetch(`/api/jobs/${encodeURIComponent(storedId)}`, {cache: 'no-store'});
      const payload = await readJsonResponse(response);
      if (restoreGeneration !== jobFlowGeneration) return;
      if (response.ok) {
        const job = jobFromPayload(payload);
        if (job) {
          pollFailureCount = 0;
          resumeJob(job);
          return;
        }
      } else if (response.status !== 404) {
        throw new Error(payload.error || '保存したジョブへ再接続できませんでした。');
      }
      const persistedJob = await fetchPersistedJob(storedId);
      if (restoreGeneration !== jobFlowGeneration) return;
      if (persistedJob) {
        pollFailureCount = 0;
        resumeJob(persistedJob);
        return;
      }
      storeActiveJobId('');
    } catch (_) {
      if (restoreGeneration !== jobFlowGeneration) return;
      activeJobId = storedId;
      storeActiveJobId(storedId);
      setRunning(true);
      showProgressCard();
      const message = document.querySelector('#progress-message');
      if (message) message.textContent = '実行中ジョブへ再接続しています…';
      schedulePoll();
      return;
    }
  }
  const pendingSubmissionId = storedPendingSubmissionId();
  if (pendingSubmissionId) {
    if (pendingSubmissionRetryAllowed(pendingSubmissionId)) {
      setRunning(false);
      setAlert(
        formError,
        '前回の送信は未受付と確認されました。同じ送信IDで安全に再送できます。必要ならファイルを選び直して［文字起こしを開始］を押してください。',
        true
      );
      return;
    }
    setRunning(true);
    showProgressCard();
    const message = document.querySelector('#progress-message');
    if (message) message.textContent = '送信中だったジョブの受付状況を確認しています…';
    await recoverSubmittedJob(
      '送信中にページが再読み込みされました。',
      pendingSubmissionId,
      0,
      restoreGeneration
    );
    return;
  }
  try {
    const activeJob = await fetchActiveJob();
    if (restoreGeneration !== jobFlowGeneration) return;
    if (activeJob) {
      pollFailureCount = 0;
      resumeJob(activeJob);
      return;
    }
  } catch (_) {
    // Older backends may not expose /api/jobs/active yet. Normal startup continues.
  }
  if (restoreGeneration === jobFlowGeneration) {
    activeJobId = null;
    setRunning(false);
    if (cancelButton) cancelButton.disabled = true;
  }
}

async function recoverSubmittedJob(
  errorMessage,
  submissionId,
  attempt = 0,
  recoveryGeneration = jobFlowGeneration,
  absenceConfirmed = false
) {
  if (recoveryGeneration !== jobFlowGeneration) return;
  let confirmedAbsentThisAttempt = false;
  try {
    let recoveredJob = null;
    let exactAbsent = !submissionId;
    let persistedAbsent = !submissionId;
    if (submissionId) {
      const response = await apiFetch(`/api/jobs/${encodeURIComponent(submissionId)}`, {cache: 'no-store'});
      if (response.ok) recoveredJob = jobFromPayload(await readJsonResponse(response));
      else if (response.status !== 404) {
        const payload = await readJsonResponse(response);
        throw new Error(payload.error || '送信したジョブを確認できませんでした。');
      } else {
        exactAbsent = true;
      }
      if (!recoveredJob) {
        recoveredJob = await fetchPersistedJob(submissionId);
        persistedAbsent = !recoveredJob;
      }
    }
    let activeAbsent = false;
    if (!recoveredJob) {
      recoveredJob = await fetchActiveJob();
      activeAbsent = !recoveredJob;
    }
    confirmedAbsentThisAttempt = exactAbsent && persistedAbsent && activeAbsent;
    if (recoveryGeneration !== jobFlowGeneration) return;
    if (recoveredJob) {
      pollFailureCount = 0;
      resumeJob(recoveredJob, {scroll: true});
      setAlert(formError, '送信結果を再確認し、文字起こしジョブへ接続しました。', true);
      return;
    }
  } catch (_) {
    // A transient read failure is handled by the same bounded retry as a 404/204.
  }
  if (recoveryGeneration !== jobFlowGeneration) return;
  const confirmedAbsent = absenceConfirmed || confirmedAbsentThisAttempt;
  if (attempt + 1 >= submitRecoveryMaxAttempts) {
    storeActiveJobId('');
    activeJobId = null;
    setRunning(false);
    if (progressCard) progressCard.hidden = true;
    if (confirmedAbsent) markPendingSubmissionRetryable(submissionId);
    setAlert(
      formError,
      confirmedAbsent
        ? `${errorMessage} サーバーで受付が確認されませんでした。同じ送信IDで再送するため、もう一度［文字起こしを開始］を押してください。`
        : `${errorMessage} 受付状況を確認できません。前回の送信IDを保護しています。接続回復後にもう一度［文字起こしを開始］を押すか、ページを再読み込みしてください。`,
      true
    );
    return;
  }
  const delay = Math.min(pollMaxDelayMs, pollBaseDelayMs * (2 ** attempt));
  const message = document.querySelector('#progress-message');
  if (message) message.textContent = `送信の受付状況を確認しています… ${Math.ceil(delay / 1000)}秒後に再試行します。`;
  if (cancelButton) cancelButton.disabled = true;
  window.setTimeout(() => {
    if (recoveryGeneration === jobFlowGeneration) {
      recoverSubmittedJob(
        errorMessage,
        submissionId,
        attempt + 1,
        recoveryGeneration,
        confirmedAbsent
      );
    }
  }, delay);
}

async function pollJob() {
  if (!activeJobId) return;
  const requestedJobId = activeJobId;
  try {
    const response = await apiFetch(`/api/jobs/${encodeURIComponent(requestedJobId)}`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (requestedJobId !== activeJobId) return;
    if (response.status === 404) {
      const persistedJob = await fetchPersistedJob(requestedJobId);
      if (persistedJob) {
        pollFailureCount = 0;
        resumeJob(persistedJob);
        return;
      }
      let activeJob = null;
      try { activeJob = await fetchActiveJob(); } catch (_) { activeJob = null; }
      if (activeJob) {
        pollFailureCount = 0;
        resumeJob(activeJob);
        return;
      }
      clearPollTimer();
      storeActiveJobId('');
      activeJobId = null;
      setRunning(false);
      if (cancelButton) cancelButton.disabled = true;
      throw new Error(data.error || '実行中ジョブが見つかりません。アプリを再起動した可能性があります。');
    }
    if (!response.ok) throw new Error(data.error || '進捗を取得できません。');
    pollFailureCount = 0;
    resumeJob(data);
  } catch (error) {
    if (!activeJobId || !jobRunning) {
      document.querySelector('#progress-message').textContent = error.message;
      return;
    }
    pollFailureCount += 1;
    const delay = Math.min(pollMaxDelayMs, pollBaseDelayMs * (2 ** Math.min(pollFailureCount - 1, 5)));
    document.querySelector('#progress-message').textContent = `${error.message} ${Math.ceil(delay / 1000)}秒後に再接続します…`;
    schedulePoll(delay);
  }
}

function fallbackProgressStage(job, progress) {
  if (job.status === 'admitting') return {label: '送信データの受付', progress: 0};
  if (job.status === 'queued') return {label: '開始準備', progress: 0};
  if (job.status === 'committing') return {label: '結果ファイルの保存', progress: Math.max(75, progress)};
  if (job.status === 'completed') return {label: '処理完了', progress: 100};
  const stages = [
    [0, 8, '処理環境の確認'],
    [8, 52, '文字起こし'],
    [52, 64, '発話時刻の補正'],
    [64, 80, '話者の分離'],
    [80, 88, '文字起こしの仕上げ'],
    [88, 90, '音声感情の分析'],
    [90, 94, '話者名の確認'],
    [94, 97, '議題アウトラインの作成'],
    [97, 100, '結果ファイルの保存']
  ];
  const stage = stages.find(([start, end]) => progress >= start && progress < end) || stages.at(-1);
  const [start, end, label] = stage;
  return {label, progress: Math.round(100 * (progress - start) / Math.max(1, end - start))};
}

function renderAiTokenUsage(rootSelector, rawUsage) {
  const root = document.querySelector(rootSelector);
  if (!root) return;
  const usage = rawUsage && typeof rawUsage === 'object' ? rawUsage : {};
  const provider = String(usage.provider || '').toLowerCase();
  const requestCount = Math.max(0, Number(usage.request_count) || 0);
  const visible = ['openai', 'google', 'lmstudio'].includes(provider) && requestCount > 0;
  root.hidden = !visible;
  if (!visible) return;
  const format = value => new Intl.NumberFormat('ja-JP').format(Math.max(0, Number(value) || 0));
  const providerElement = root.querySelector('[data-ai-provider]');
  const modelElement = root.querySelector('[data-ai-model]');
  const inputElement = root.querySelector('[data-ai-input]');
  const outputElement = root.querySelector('[data-ai-output]');
  const totalElement = root.querySelector('[data-ai-total]');
  const requestsElement = root.querySelector('[data-ai-requests]');
  if (providerElement) providerElement.textContent = {
    openai: 'OpenAI',
    google: 'Google Gemini',
    lmstudio: String(tokenConfigSnapshot.local_llm_label || 'LM Studio（ローカル）')
  }[provider] || 'AI';
  if (modelElement) modelElement.textContent = String(usage.model || '');
  if (inputElement) inputElement.textContent = format(usage.input_tokens);
  if (outputElement) outputElement.textContent = format(usage.output_tokens);
  if (totalElement) totalElement.textContent = format(usage.total_tokens);
  if (requestsElement) requestsElement.textContent = `${format(requestCount)}回`;
  const optionalDetails = [
    ['[data-ai-cached]', usage.cached_tokens],
    ['[data-ai-reasoning]', usage.reasoning_tokens]
  ];
  optionalDetails.forEach(([selector, value]) => {
    const element = root.querySelector(selector);
    const count = Math.max(0, Number(value) || 0);
    if (!element) return;
    element.hidden = count <= 0;
    const number = element.querySelector('b');
    if (number) number.textContent = format(count);
  });
  const unreported = root.querySelector('[data-ai-unreported]');
  if (unreported) unreported.hidden = Boolean(usage.reported);
}

function renderProgress(job) {
  lastProgressJob = job;
  if (typeof renderAiFinishingActivity === 'function') renderAiFinishingActivity(job);
  const progress = Number(job.progress || 0);
  const fallbackStage = fallbackProgressStage(job, progress);
  const hasCurrentStage = Boolean(job.stage_label)
    && !(job.stage === 'queued' && job.status === 'running' && progress > 0);
  const stageLabel = hasCurrentStage ? job.stage_label : fallbackStage.label;
  const stageProgress = Math.max(0, Math.min(100, Number(
    hasCurrentStage ? job.stage_progress : fallbackStage.progress
  ) || 0));
  const active = ['admitting', 'queued', 'running', 'committing'].includes(job.status);
  const activityLabels = {
    admitting: 'RECEIVING', queued: 'WAITING', running: 'RUNNING', committing: 'SAVING',
    completed: 'COMPLETED', failed: 'ERROR', cancelled: 'STOPPED'
  };
  progressCard.classList.toggle('is-active', active);
  progressCard.classList.toggle('has-error', ['failed', 'cancelled'].includes(job.status));
  document.querySelector('#progress-number').textContent = `${progress}%`;
  document.querySelector('#progress-bar').style.width = `${progress}%`;
  document.querySelector('#progress-overall-track').setAttribute('aria-valuenow', String(progress));
  document.querySelector('#progress-stage-label').textContent = stageLabel;
  document.querySelector('#progress-stage-number').textContent = `${stageProgress}%`;
  document.querySelector('#progress-stage-bar').style.width = `${stageProgress}%`;
  document.querySelector('#progress-stage-track').setAttribute('aria-valuenow', String(stageProgress));
  document.querySelector('#progress-activity-label').textContent = activityLabels[job.status] || 'WORKING';
  document.querySelector('#progress-message').textContent = job.message || '';
  document.querySelector('#progress-log').textContent = (job.logs || []).join('\n');
  renderAiTokenUsage('#progress-ai-usage', job.ai_usage);
  const titles = {admitting: '受付中', queued: '開始待ち', running: '文字起こし中', committing: '結果を保存中', completed: '処理完了', failed: 'エラー', cancelled: '中止しました'};
  document.querySelector('#progress-title').textContent = titles[job.status] || '処理中';
  document.querySelector('#progress-message').style.color = ['failed', 'cancelled'].includes(job.status) ? '#913733' : '';
  updateJobChip(job);
  syncCreateViewState();
}


function selectedAiModelEntry() {
  if (!aiModelSelect) return null;
  return aiModelCatalog.find(item => item.id === aiModelSelect.value) || null;
}

function updateAiModelDescription() {
  if (!aiModelDescription) return;
  const entry = selectedAiModelEntry();
  aiModelDescription.textContent = entry
    ? (entry.description || `モデルID: ${entry.id}`)
    : 'モデルを選択してください。';
}

function renderAiModelOptions() {
  if (!aiModelSelect) return;
  const query = String(aiModelSearch && aiModelSearch.value || '').trim().toLocaleLowerCase();
  const previous = aiModelSelect.value || String(aiModelDialog && aiModelDialog.dataset.selectedModel || '');
  const visible = aiModelCatalog.filter(item => {
    const haystack = `${item.id} ${item.label || ''} ${item.description || ''}`.toLocaleLowerCase();
    return !query || haystack.includes(query);
  });
  aiModelSelect.replaceChildren();
  visible.forEach(item => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.label && item.label !== item.id
      ? `${item.label} (${item.id})`
      : item.id;
    aiModelSelect.append(option);
  });
  if (visible.some(item => item.id === previous)) aiModelSelect.value = previous;
  else if (visible.length) aiModelSelect.selectedIndex = 0;
  if (saveAiModelButton) saveAiModelButton.disabled = visible.length === 0;
  updateAiModelDescription();
}

async function openAiModelDialog(provider) {
  const normalizedProvider = String(provider || '').trim().toLowerCase();
  if (!['openai', 'google', 'lmstudio'].includes(normalizedProvider)) return;
  const label = {
    openai: 'OpenAI',
    google: 'Google Gemini',
    lmstudio: String(tokenConfigSnapshot.local_llm_label || 'LM Studio（ローカル）')
  }[normalizedProvider];
  if (normalizedProvider !== 'lmstudio' && !tokenConfigSnapshot[normalizedProvider]) {
    window.alert(`${label} APIキーがtokens.jsonに設定されていません。`);
    return;
  }
  activeAiModelProvider = normalizedProvider;
  aiModelCatalog = [];
  if (aiModelProviderLabel) aiModelProviderLabel.textContent = label;
  if (aiModelCurrent) aiModelCurrent.textContent = String(tokenConfigSnapshot[`${normalizedProvider}_model`] || '読込中…');
  if (aiModelSearch) aiModelSearch.value = '';
  if (aiModelDescription) aiModelDescription.textContent = 'APIから利用可能なモデルを取得しています…';
  setAlert(aiModelError, '');
  if (aiModelSelect) {
    const loadingOption = document.createElement('option');
    loadingOption.textContent = 'モデル一覧を読込中…';
    loadingOption.disabled = true;
    aiModelSelect.replaceChildren(loadingOption);
  }
  if (saveAiModelButton) saveAiModelButton.disabled = true;
  if (!aiModelDialog || typeof aiModelDialog.showModal !== 'function') {
    window.alert('このブラウザではモデル選択画面を開けません。');
    return;
  }
  if (!aiModelDialog.open) aiModelDialog.showModal();
  try {
    const response = await apiFetch(`/api/ai/models?provider=${encodeURIComponent(normalizedProvider)}`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'モデル一覧を取得できませんでした。');
    const selected = String(data.selected_model || '').trim();
    const models = Array.isArray(data.models) ? data.models : [];
    aiModelCatalog = models
      .map(item => ({
        id: String(item && item.id || '').trim(),
        label: String(item && item.label || '').trim(),
        description: String(item && item.description || '').trim()
      }))
      .filter(item => item.id);
    if (selected && !aiModelCatalog.some(item => item.id === selected)) {
      aiModelCatalog.unshift({
        id: selected,
        label: selected,
        description: 'tokens.jsonで現在選択されているモデルです。'
      });
    }
    aiModelDialog.dataset.selectedModel = selected;
    if (aiModelCurrent) aiModelCurrent.textContent = selected || '未設定';
    renderAiModelOptions();
    window.requestAnimationFrame(() => aiModelSearch && aiModelSearch.focus());
  } catch (error) {
    if (aiModelSelect) aiModelSelect.replaceChildren();
    if (aiModelDescription) aiModelDescription.textContent = '';
    setAlert(aiModelError, error.message, true);
  }
}

function updateJobChip(job) {
  if (!jobChip || !jobChipLabel) return;
  const status = job ? String(job.status || '') : '';
  const active = ['admitting', 'queued', 'running', 'committing'].includes(status);
  const pendingCompleted = Boolean(completedJob && job && completedJob.id === job.id && status === 'completed');
  const failed = ['failed', 'cancelled'].includes(status) && Boolean(progressCard && !progressCard.hidden);
  jobChip.hidden = !(active || pendingCompleted || failed);
  jobChip.classList.toggle('is-active', active);
  jobChip.classList.toggle('is-complete', pendingCompleted);
  jobChip.classList.toggle('has-error', failed);
  const titles = {admitting: '受付中', queued: '開始待ち', running: '文字起こし中', committing: '結果を保存中', failed: 'エラー', cancelled: '中止しました'};
  if (active) jobChipLabel.textContent = `${titles[status] || '処理中'} ${Number(job.progress || 0)}%`;
  else if (pendingCompleted) jobChipLabel.textContent = '文字起こしが完了 — 結果を開く';
  else jobChipLabel.textContent = titles[status] || '処理状況';
}

function showProgressCard({scroll = false} = {}) {
  if (!progressCard) return;
  progressCard.hidden = false;
  syncCreateViewState();
  if (scroll && createView && !createView.hidden) {
    progressCard.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
  }
}

function storedActiveJobId() {
  try {
    return String(window.sessionStorage.getItem(activeJobStorageKey) || '').trim();
  } catch (_) {
    return '';
  }
}

function storeActiveJobId(jobId) {
  try {
    if (jobId) window.sessionStorage.setItem(activeJobStorageKey, String(jobId));
    else window.sessionStorage.removeItem(activeJobStorageKey);
  } catch (_) {
    // Storage can be unavailable in hardened or private browser contexts.
  }
}

function storedPendingSubmissionId() {
  try {
    const raw = window.sessionStorage.getItem(pendingSubmissionStorageKey);
    if (!raw) return '';
    const pending = JSON.parse(raw);
    const submissionId = String(pending && pending.id || '').trim();
    const createdAt = Number(pending && pending.createdAt);
    if (!/^[0-9a-f]{32}$/.test(submissionId)
        || !Number.isFinite(createdAt)) {
      window.sessionStorage.removeItem(pendingSubmissionStorageKey);
      return '';
    }
    return submissionId;
  } catch (_) {
    try { window.sessionStorage.removeItem(pendingSubmissionStorageKey); } catch (_) {}
    return '';
  }
}

function storePendingSubmissionId(submissionId, retryAllowed = false) {
  try {
    if (submissionId) {
      window.sessionStorage.setItem(pendingSubmissionStorageKey, JSON.stringify({
        id: String(submissionId),
        createdAt: Date.now(),
        retryAllowed: Boolean(retryAllowed)
      }));
    } else {
      window.sessionStorage.removeItem(pendingSubmissionStorageKey);
    }
  } catch (_) {
    // Storage can be unavailable in hardened or private browser contexts.
  }
}

function pendingSubmissionRetryAllowed(submissionId) {
  try {
    const pending = JSON.parse(window.sessionStorage.getItem(pendingSubmissionStorageKey) || '{}');
    return pending.id === submissionId && pending.retryAllowed === true;
  } catch (_) {
    return false;
  }
}

function markPendingSubmissionRetryable(submissionId) {
  storePendingSubmissionId(submissionId, true);
}

function createSubmissionId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID().replaceAll('-', '');
  }
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
}
