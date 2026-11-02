/* 公開版の画面処理: setup。共有状態はapp.jsで管理する。 */

function startBootSequence() {
  if (!bootSplash) {
    document.body.classList.remove('booting');
    return;
  }
  // The splash is an intro, not a real check: show it once per browser session
  // and keep it short, so reloads go straight to the workspace (UX-08).
  let seen = false;
  try {
    seen = window.sessionStorage.getItem('gurumoji.bootSplashSeen') === '1';
    window.sessionStorage.setItem('gurumoji.bootSplashSeen', '1');
  } catch (error) {
    seen = false;
  }
  if (seen) {
    bootSplash.hidden = true;
    bootSplash.setAttribute('aria-hidden', 'true');
    document.body.classList.add('boot-skipped');
    document.body.classList.remove('booting');
    return;
  }
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.setTimeout(() => {
    bootSplash.classList.add('show-main');
    window.setTimeout(() => {
      bootSplash.classList.add('is-leaving');
      document.body.classList.remove('booting');
      window.setTimeout(() => {
        bootSplash.hidden = true;
        bootSplash.setAttribute('aria-hidden', 'true');
      }, reducedMotion ? 50 : 400);
    }, reducedMotion ? 150 : 650);
  }, reducedMotion ? 200 : 1200);
}

function vocabularyTermsFromInput(value = customVocabulary && customVocabulary.value) {
  return String(value || '')
    .split(/\r?\n/)
    .map(term => term.trim())
    .filter(Boolean);
}

function setCustomVocabularyStatus(message, error = false) {
  if (!customVocabularyStatus) return;
  customVocabularyStatus.textContent = message;
  customVocabularyStatus.classList.toggle('error', error);
}

function customVocabularyCountLabel(terms) {
  const count = Array.isArray(terms) ? terms.length : 0;
  return count ? `${count}語を登録` : '未登録';
}

async function loadCustomVocabulary() {
  if (!customVocabulary) return;
  try {
    const response = await apiFetch('/api/custom-vocabulary', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '単語登録を読み込めませんでした。');
    const terms = Array.isArray(data.terms) ? data.terms.map(term => String(term).trim()).filter(Boolean) : [];
    if (!customVocabularyTouched) customVocabulary.value = terms.join('\n');
    setCustomVocabularyStatus(customVocabularyCountLabel(
      customVocabularyTouched ? vocabularyTermsFromInput() : terms
    ));
    updateCreateSummary();
  } catch (error) {
    setCustomVocabularyStatus(error.message || '単語登録を読み込めませんでした。', true);
  }
}

async function saveCustomVocabulary(saveGeneration) {
  if (!customVocabulary) return;
  const sourceText = customVocabulary.value;
  const terms = vocabularyTermsFromInput(sourceText);
  setCustomVocabularyStatus('保存中…');
  try {
    const response = await apiFetch('/api/custom-vocabulary', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({terms})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '単語登録を保存できませんでした。');
    if (saveGeneration !== customVocabularyMutationGeneration) return;
    const savedTerms = Array.isArray(data.terms) ? data.terms.map(term => String(term).trim()).filter(Boolean) : [];
    customVocabulary.value = savedTerms.join('\n');
    setCustomVocabularyStatus(customVocabularyCountLabel(savedTerms));
    updateCreateSummary();
  } catch (error) {
    if (saveGeneration === customVocabularyMutationGeneration) {
      setCustomVocabularyStatus(error.message || '単語登録を保存できませんでした。', true);
    }
  }
}

function scheduleCustomVocabularySave({immediate = false} = {}) {
  if (!customVocabulary) return;
  if (customVocabularySaveTimer !== null) window.clearTimeout(customVocabularySaveTimer);
  const saveGeneration = customVocabularyMutationGeneration;
  setCustomVocabularyStatus('保存待ち…');
  const save = () => {
    customVocabularySaveTimer = null;
    saveCustomVocabulary(saveGeneration);
  };
  if (immediate) save();
  else customVocabularySaveTimer = window.setTimeout(save, 450);
}

function hasSelectedSource() {
  return Boolean(
    (sourcePath && sourcePath.value.trim())
    || (inputFile && inputFile.files && inputFile.files.length)
  );
}

function isMobileWizard() {
  return mobileWizardMedia.matches;
}

function updateBrowseButtonLabel() {
  if (!browsePathButton || browsePathButton.disabled) return;
  browsePathButton.textContent = isMobileWizard()
    ? '端末から選択'
    : (browserFilePickerOnly ? '端末からアップロード' : 'ファイルを選択');
}

function renderFlowSteps() {
  const hasSource = hasSelectedSource();
  const mobile = isMobileWizard();
  flowStepItems.forEach(item => {
    const step = Number(item.dataset.flowStep);
    item.classList.remove('active', 'complete', 'ready');
    if (mobile) {
      if (step === currentMobileStep) item.classList.add('active');
      else if (step < currentMobileStep) item.classList.add('complete');
      else if (step === 3 && hasSource) item.classList.add('ready');
    } else if (step === 1) {
      item.classList.add(hasSource ? 'complete' : 'active');
    } else if (step === 2) {
      if (hasSource) item.classList.add('active');
    } else if (hasSource) {
      item.classList.add('ready');
    }
    const button = item.querySelector('[data-flow-jump]');
    if (button) button.setAttribute('aria-current', item.classList.contains('active') ? 'step' : 'false');
  });
}

function renderMobileWizard() {
  if (!form) return;
  const mobile = isMobileWizard();
  form.classList.toggle('mobile-wizard-ready', mobile);
  [1, 2, 3].forEach(step => form.classList.toggle(`mobile-step-${step}`, step === currentMobileStep));
  flowSections.forEach(section => {
    const active = Number(section.dataset.flowSection) === currentMobileStep;
    section.classList.toggle('mobile-active', active);
    if (mobile) section.toggleAttribute('inert', !active);
    else section.removeAttribute('inert');
  });
  const content = mobileStepContent[currentMobileStep] || mobileStepContent[1];
  if (mobileNavStep) mobileNavStep.textContent = `${currentMobileStep} / 3`;
  if (mobileNavLabel) mobileNavLabel.textContent = content.label;
  if (mobileStepBack) mobileStepBack.disabled = jobRunning || currentMobileStep === 1;
  if (mobileStepNext) {
    mobileStepNext.disabled = jobRunning || currentMobileStep >= 3 || (currentMobileStep === 1 && !hasSelectedSource());
    mobileStepNext.textContent = content.next;
  }
  renderFlowSteps();
}

function validateMobileStep(step) {
  if (step === 1 && !hasSelectedSource()) {
    setAlert(pathError, '先に音声・動画ファイルを選択してください。', true);
    if (fileDropZone) fileDropZone.focus();
    return false;
  }
  const section = flowSections.find(item => Number(item.dataset.flowSection) === step);
  if (!section) return true;
  const invalid = [...section.querySelectorAll('input, select, textarea')].find(input => !input.checkValidity());
  if (invalid) {
    setAlert(formError, '入力内容を確認してください。', true);
    const panel = invalid.closest('[data-settings-panel]');
    if (panel) panel.open = true;
    invalid.reportValidity();
    invalid.focus();
    return false;
  }
  return true;
}

function setMobileStep(nextStep, {focusHeading = true, validateCurrent = false} = {}) {
  const target = Math.max(1, Math.min(3, Number(nextStep) || 1));
  if (validateCurrent && target > currentMobileStep && !validateMobileStep(currentMobileStep)) return false;
  currentMobileStep = target;
  setAlert(formError, '');
  renderMobileWizard();
  if (focusHeading && isMobileWizard()) {
    const steps = document.querySelector('#flow-steps');
    if (steps) steps.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
    const section = flowSections.find(item => Number(item.dataset.flowSection) === target);
    const heading = section ? section.querySelector('h2') : null;
    if (heading) {
      heading.setAttribute('tabindex', '-1');
      window.setTimeout(() => heading.focus({preventScroll: true}), 220);
    }
  }
  return true;
}

function jumpToFlowStep(step) {
  const target = Math.max(1, Math.min(3, Number(step) || 1));
  if (isMobileWizard()) {
    setMobileStep(target, {validateCurrent: target > currentMobileStep});
    return;
  }
  const section = flowSections.find(item => Number(item.dataset.flowSection) === target);
  if (section) section.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
}

function openSettingsPanel(name, {focus = true} = {}) {
  const panel = settingsPanels.find(item => item.dataset.settingsPanel === name);
  if (!panel) return;
  if (isMobileWizard() && currentMobileStep !== 2) setMobileStep(2, {focusHeading: false});
  panel.open = true;
  window.requestAnimationFrame(() => {
    panel.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
    if (!focus) return;
    const control = panel.querySelector('input:not([type="hidden"]):not(:disabled), select:not(:disabled), textarea:not(:disabled)');
    if (control) window.setTimeout(() => control.focus({preventScroll: true}), 260);
  });
}

function selectedConversationMode() {
  const selected = conversationModeInputs.find(input => input.checked);
  return selected && conversationModePresets[selected.value]
    ? selected.value
    : 'meeting';
}

function isSpeakerCountFixed() {
  return speakerCountFixButton?.getAttribute('aria-pressed') === 'true';
}

function syncFixedSpeakerCount() {
  if (!isSpeakerCountFixed()) return;
  minSpeakersInput.value = fixedSpeakerCountInput.value;
  maxSpeakersInput.value = fixedSpeakerCountInput.value;
  updateCreateSummary();
}

function setSpeakerCountFixed(fixed, {restoreRange = true} = {}) {
  if (fixed) {
    speakerRangeBeforeFix = {
      min: minSpeakersInput.value,
      max: maxSpeakersInput.value,
      editedMin: manuallyEditedModeFields.has('minSpeakers'),
      editedMax: manuallyEditedModeFields.has('maxSpeakers')
    };
    if (minSpeakersInput.value && minSpeakersInput.value === maxSpeakersInput.value) {
      fixedSpeakerCountInput.value = minSpeakersInput.value;
    }
    manuallyEditedModeFields.add('minSpeakers');
    manuallyEditedModeFields.add('maxSpeakers');
  } else if (speakerRangeBeforeFix && restoreRange) {
    minSpeakersInput.value = speakerRangeBeforeFix.min;
    maxSpeakersInput.value = speakerRangeBeforeFix.max;
    if (!speakerRangeBeforeFix.editedMin) manuallyEditedModeFields.delete('minSpeakers');
    if (!speakerRangeBeforeFix.editedMax) manuallyEditedModeFields.delete('maxSpeakers');
  }
  speakerCountFixButton.setAttribute('aria-pressed', String(fixed));
  speakerCountFixButton.textContent = fixed ? '人数の固定を解除する' : '話者数を固定する';
  fixedSpeakerCountField.hidden = !fixed;
  fixedSpeakerCountInput.disabled = !fixed;
  minSpeakersField.hidden = fixed;
  maxSpeakersField.hidden = fixed;
  if (fixed) {
    syncFixedSpeakerCount();
    fixedSpeakerCountInput.focus();
  } else {
    speakerRangeBeforeFix = null;
    applyConversationMode();
  }
}

function applyConversationMode(mode = selectedConversationMode()) {
  const preset = conversationModePresets[mode] || conversationModePresets.meeting;
  if (createView) createView.dataset.conversationMode = conversationModePresets[mode] ? mode : 'meeting';
  const keptLabels = [];
  conversationModeFields.forEach(field => {
    const presetValue = field.property === 'checked' ? preset[field.key] : String(preset[field.key]);
    if (!manuallyEditedModeFields.has(field.key)) {
      field.input[field.property] = presetValue;
    } else if (field.input[field.property] !== presetValue) {
      keptLabels.push(field.label);
    }
  });
  if (conversationModeHint) {
    conversationModeHint.textContent = keptLabels.length
      ? `${preset.hint} 手動で変更した「${keptLabels.join('」「')}」は変更せずに残しています。`
      : preset.hint;
  }
  if (conversationModeResetButton) conversationModeResetButton.hidden = !keptLabels.length;

  // A mode adjusts local, deterministic recognition settings only. External AI
  // remains an explicit choice in the AI finishing section.
  syncQuietFields();
  updateCreateSummary();
}

function syncTranscriptionBackend() {
  const haasSelected = transcriptionBackend?.value === 'haas_ja';
  const asrDevice = document.querySelector('#transcription-device');
  const cpuOption = asrDevice?.querySelector('option[value="cpu"]');
  if (cpuOption) cpuOption.disabled = haasSelected;
  if (haasSelected && asrDevice?.querySelector('option[value="cuda"]:not(:disabled)')) {
    asrDevice.value = 'cuda';
  }
  // Both isolated stacks diarize with Nemotron 3 and skip the WhisperX controls.
  const qwenSelected = transcriptionBackend?.value === 'qwen3_nemotron' || haasSelected;
  if (qwenSelected && isSpeakerCountFixed()) setSpeakerCountFixed(false);
  if (modelName) modelName.disabled = qwenSelected;
  if (triplePass) {
    triplePass.disabled = qwenSelected;
    if (qwenSelected) triplePass.checked = false;
  }
  [boostQuietSpeech, vadOnset, vadOffset].forEach(input => {
    if (input) input.disabled = qwenSelected;
  });
  if (speakerCountFixButton) {
    speakerCountFixButton.disabled = qwenSelected;
    const speakerCountField = speakerCountFixButton.closest('.field');
    if (speakerCountField) speakerCountField.hidden = qwenSelected;
  }
  [minSpeakersField, maxSpeakersField].forEach(field => {
    if (field) field.hidden = qwenSelected || isSpeakerCountFixed();
  });
  [minSpeakersInput, maxSpeakersInput].forEach(input => {
    if (input) input.disabled = qwenSelected;
  });
  if (qwenBackendNote) qwenBackendNote.hidden = transcriptionBackend?.value !== 'qwen3_nemotron';
  if (haasBackendNote) haasBackendNote.hidden = !haasSelected;
  if (haasSelected && languageSelect && languageSelect.value !== 'ja') languageSelect.value = 'ja';
  if (qwenVocabularyNote) qwenVocabularyNote.hidden = !qwenSelected;
}

function transcriptFinishingPlan() {
  // 実行側のモード正規化に合わせ、保存中の選択値と今回の処理を分ける。
  const mode = document.querySelector('input[name="transcript_finishing_mode"]:checked')?.value || 'custom';
  const enabled = mode !== 'off' && (document.querySelector('#ai-provider')?.value || 'none') !== 'none';
  const advanced = mode === 'advanced';
  const recommended = mode === 'recommended';
  const deferred = false;
  const values = typeof readAiEfforts === 'function' ? readAiEfforts() : {
    cleanup: document.querySelector('[name="ai_effort_cleanup"]')?.value || 'medium',
    notation: document.querySelector('[name="ai_effort_notation"]')?.value || 'off'
  };
  const fullCleanup = enabled && (advanced || (!recommended && Boolean(document.querySelector('#clean-transcript')?.checked || document.querySelector('#jev-compare')?.checked)));
  const recommendedCleanup = enabled && recommended && !deferred && values.cleanup !== 'off'
    && Boolean(typeof tokenConfigSnapshot !== 'undefined' && tokenConfigSnapshot.typesafe);
  const cleanup = !deferred && values.cleanup !== 'off' && (fullCleanup || recommendedCleanup);
  const contextOutline = cleanup && (fullCleanup || ['high', 'ultra'].includes(values.cleanup));
  const outlineOutput = enabled && !deferred && !recommended && Boolean(document.querySelector('#create-outline')?.checked);
  const names = enabled && (advanced || Boolean(document.querySelector('#detect-names')?.checked));
  const notation = enabled && !deferred && values.notation !== 'off';
  const compare = cleanup && !recommended && Boolean(document.querySelector('#jev-compare')?.checked);
  return {mode, advanced, deferred, fullCleanup, recommendedCleanup, contextOutline, outlineOutput, notation, compare,
    requested: {cleanup: Boolean(cleanup), outline: Boolean(contextOutline || outlineOutput), name_extract: Boolean(names), name_verify: Boolean(names)},
    configurable: {cleanup: enabled && Boolean(recommended || deferred || fullCleanup), outline: Boolean(contextOutline || outlineOutput), name_extract: Boolean(names), name_verify: Boolean(names)}};
}

function enabledTextDestinations() {
  const provider = aiProvider?.value || 'none';
  const mode = selectedTranscriptFinishingMode();
  if (provider === 'none' || mode === 'off') return [];
  const plan = transcriptFinishingPlan();
  const destinations = [];
  if (Object.values(plan.requested).some(Boolean) || plan.notation) {
    destinations.push({provider, label: selectedOptionText(aiProvider), model: tokenConfigSnapshot[`${provider}_model`] || 'モデル未設定'});
  }
  if (plan.recommendedCleanup || plan.compare) {
    destinations.push({provider: 'typesafe', label: 'TypeSafe Jev（外部サービス）', model: tokenConfigSnapshot.typesafe_model || 'jev-latest'});
  }
  return destinations;
}

function readSeenNotices() {
  try {
    const stored = JSON.parse(localStorage.getItem(seenNoticeStorageKey) || '[]');
    return new Set(Array.isArray(stored) ? stored : []);
  } catch (_) { return new Set(); }
}

function rememberSeenNotices(notices) {
  if (!notices || !notices.length) return;
  const seen = readSeenNotices();
  notices.forEach(notice => seen.add(notice));
  try { localStorage.setItem(seenNoticeStorageKey, JSON.stringify([...seen])); } catch (_) { /* shown again next time */ }
}

function createReadiness() {
  const blockers = [];
  const notes = [];
  const acknowledgementNotes = new Set();
  let requiresModelAcknowledgement = false;
  if (configLoadState !== 'loaded') blockers.push(configLoadState === 'error' ? '設定を確認できません。接続と処理装置から再確認してください' : '実行環境と設定を確認中です');
  if (configLoadState === 'loaded') {
    const backend = transcriptionBackend?.value || 'whisperx';
    if (audioPreprocess?.value === 'reuse') {
      const audioReadiness = tokenConfigSnapshot.transcription_readiness?.audio_preprocess?.reuse;
      if (!audioReadiness) blockers.push('RE-USEの準備状態を確認できません。設定を再確認してください');
      else {
        blockers.push(...(audioReadiness.blockers || []));
        (audioReadiness.notes || []).forEach(note => notes.push(note));
      }
    }
    if (backend === 'whisperx' && !tokenConfigSnapshot.huggingface) blockers.push('話者分離に必要なHugging Faceトークンが未設定です');
    const readiness = tokenConfigSnapshot.transcription_readiness?.[backend];
    if (!readiness) blockers.push('方式・モデルの準備状態を取得できません。設定を再確認してください');
    else {
      blockers.push(...(readiness.blockers || []));
      (readiness.notes || []).forEach(note => { notes.push(note); acknowledgementNotes.add(note); });
      const device = document.querySelector('#transcription-device')?.value || 'cpu';
      const model = readiness.models?.[device]?.[modelName?.value];
      if (model) {
        const note = `認識モデル: ${model.message}`;
        notes.push(note);
        if (model.status !== 'cached') acknowledgementNotes.add(note);
      } else if (backend === 'whisperx') {
        const note = '選択した認識モデルの取得状況は未確認です';
        notes.push(note);
        acknowledgementNotes.add(note);
      }
    }
    enabledTextDestinations().forEach(destination => {
      if (!tokenConfigSnapshot[destination.provider]) blockers.push(`${destination.label}が未設定または接続できません`);
      if (destination.provider === 'lmstudio' && !tokenConfigSnapshot.lmstudio_model) blockers.push('ローカルLLMのモデルが未設定です');
    });
    if (selectedTranscriptFinishingMode() === 'advanced' && aiProvider?.value === 'none') blockers.push('全文仕上げに使うAIを選択してください');
  }
  if (typeof aiEffortReadiness === 'function') {
    const effortReadiness = aiEffortReadiness();
    blockers.push(...effortReadiness.blockers);
    notes.push(...effortReadiness.notes);
  }
  const seen = readSeenNotices();
  const pendingNotes = [...new Set(notes)].filter(note => !seen.has(note));
  requiresModelAcknowledgement = pendingNotes.some(note => acknowledgementNotes.has(note));
  const acknowledged = Boolean(document.querySelector('#model-readiness-ack')?.checked);
  return {ready: hasSelectedSource() && !blockers.length && (!requiresModelAcknowledgement || acknowledged), requiresModelAcknowledgement, acknowledged, blockers: [...new Set(blockers)], notes: pendingNotes};
}

function updateCreateSummary() {
  const hasSource = hasSelectedSource();
  if (fileDropZone) fileDropZone.classList.toggle('has-file', hasSource);
  if (pathDetail) pathDetail.classList.toggle('selected', hasSource);

  const readiness = createReadiness();
  const readyMessage = !hasSource ? 'ファイルを選択してください'
    : readiness.blockers.length ? 'ファイル選択済み・開始前の確認が必要です'
    : readiness.requiresModelAcknowledgement ? 'ファイル選択済み・モデルの確認や取得が必要です' : 'ファイル選択済み・開始時にモデルを読み込みます';
  const modelAcknowledgement = document.querySelector('#model-readiness-ack-row');
  if (modelAcknowledgement) modelAcknowledgement.hidden = !readiness.requiresModelAcknowledgement;
  setAlert(document.querySelector('#setup-readiness-details'), [...readiness.blockers, ...readiness.notes].join('。'), Boolean(readiness.blockers.length));
  const destinations = enabledTextDestinations();
  const destinationText = destinations.length ? destinations.map(item => `${item.label} / ${item.model}`).join('、') : '送信なし';
  document.querySelectorAll('[data-text-destinations]').forEach(element => { element.textContent = `今回のテキスト送信先: ${destinationText}`; });
  const deferredNote = document.querySelector('#deferred-destination-note');
  if (deferredNote) deferredNote.hidden = !(false && selectedTranscriptFinishingMode() === 'recommended');
  if (setupReadyState) setupReadyState.textContent = readyMessage;
  document.querySelectorAll('[data-setup-ready]').forEach(element => { element.textContent = readyMessage; });

  const modePreset = conversationModePresets[selectedConversationMode()];
  const mode = modePreset ? modePreset.label : '会議モード';
  const haasSelected = transcriptionBackend?.value === 'haas_ja';
  const qwenSelected = transcriptionBackend?.value === 'qwen3_nemotron' || haasSelected;
  const model = haasSelected
    ? 'Haas-ja v1.0（公式・実験的） + Nemotron 3'
    : qwenSelected
    ? 'Qwen3-ASR + ForcedAligner + Nemotron 3'
    : (selectedOptionText(modelName).split(' \u2014 ')[0] || '\u81ea\u52d5');
  const language = selectedOptionText(languageSelect) || '自動判定';
  const preprocess = selectedOptionText(audioPreprocess).split(' — ')[0] || 'おすすめ';
  const transcriptionDevice = document.querySelector('#transcription-device');
  const diarizationDevice = document.querySelector('#diarization-device');
  const transcriptionHardware = transcriptionDevice && transcriptionDevice.value === 'cuda' ? 'GPU (CUDA)' : 'CPU';
  const diarizationHardware = diarizationDevice && diarizationDevice.value === 'cuda' ? 'GPU (CUDA)' : 'CPU';
  const vocabularyTerms = vocabularyTermsFromInput();
  const recognitionExtras = [];
  if (vocabularyTerms.length && !qwenSelected) recognitionExtras.push(`\u5358\u8a9e\u767b\u9332 ${vocabularyTerms.length}\u8a9e`);
  const fixedSpeakerLabel = isSpeakerCountFixed() ? `話者数 ${fixedSpeakerCountInput.value || '未入力'}人に固定` : '';
  if (fixedSpeakerLabel) recognitionExtras.push(fixedSpeakerLabel);
  const finishExtras = [];
  if (triplePass && triplePass.checked) finishExtras.push('詳細処理');
  const providerLabel = aiProvider && aiProvider.value !== 'none' ? selectedOptionText(aiProvider) : '';
  const finishingPlan = transcriptFinishingPlan();
  const finishInVault = finishingPlan.deferred;
  const finishNow = Object.values(finishingPlan.requested).some(Boolean) || finishingPlan.notation;
  const configuredModel = finishNow ? String(tokenConfigSnapshot[`${aiProvider.value}_model`] || '').trim() : '';
  const finishingState = finishNow ? 'する' : 'しない';
  const finishingModel = finishNow
    ? `${providerLabel} / ${configuredModel || 'モデル未設定'}`
    : '使用モデルなし';
  const finishingDetail = (finishNow ? [finishingPlan.requested.cleanup ? (finishingPlan.recommendedCleanup ? '必要な箇所を整える' : '全文を整える') : '', finishingPlan.requested.name_extract ? '話者を確認する' : '', finishingPlan.outlineOutput ? 'アウトラインを出力' : '', finishingPlan.notation ? '表記ゆれを統一' : ''].filter(Boolean).join(' / ') : '認識結果をそのまま残す');
  const finishingLabel = `${finishingState} / ${finishingModel}`;
  finishExtras.push(`AI仕上げ: ${finishingState}`);
  if (finishingPlan.compare) finishExtras.push('Jev修正要否比較');
  const outputParts = ['TXT', 'JSON'];
  const outputExtras = [];
  if (writeSrt && writeSrt.checked) { outputParts.push('SRT'); outputExtras.push('SRT'); }
  if (burnSubtitledVideo && burnSubtitledVideo.checked) { outputParts.push('字幕付き動画'); outputExtras.push('字幕付き動画'); }
  const extras = [...recognitionExtras, ...finishExtras, ...outputExtras];
  const engineLabel = qwenSelected ? model : `WhisperX / ${model}`;
  const summaryText = `${mode} / ${engineLabel} / ${language} / \u524d\u51e6\u7406: ${preprocess}${extras.length ? ` / ${extras.join(' / ')}` : ''}`;
  const launchText = `\u6587\u5b57\u8d77\u3053\u3057\u65b9\u5f0f ${engineLabel}\u30fb${transcriptionHardware} / \u8a71\u8005\u5206\u96e2 ${diarizationHardware} / AI\u4ed5\u4e0a\u3052 ${finishingState}`;
  if (setupSummary) setupSummary.textContent = launchText;
  document.querySelectorAll('[data-setup-summary]').forEach(element => { element.textContent = summaryText; });

  const selectedFile = inputFile && inputFile.files && inputFile.files[0];
  const directPath = sourcePath ? sourcePath.value.trim() : '';
  const sourceLabel = selectedFile
    ? selectedFile.name
    : (directPath ? directPath.split(/[\\/]/).pop() : '未選択');
  const setText = (selector, value) => {
    document.querySelectorAll(selector).forEach(element => { element.textContent = value; });
  };
  setText('[data-choice-transcription-device]', transcriptionHardware);
  setText('[data-choice-recognition-model]', `\u6587\u5b57\u8d77\u3053\u3057\u65b9\u5f0f ${engineLabel}`);
  setText('[data-choice-recognition-detail]', `話者分離 ${diarizationHardware}${fixedSpeakerLabel ? ` / ${fixedSpeakerLabel}` : ''} / ${language} / 前処理 ${preprocess}`);
  setText('[data-settings-value="vocabulary"]', vocabularyTerms.length ? `${vocabularyTerms.length}語を登録` : '未登録');
  setText('[data-choice-finishing-state]', finishingState);
  setText('[data-choice-finishing-model]', finishingModel);
  setText('[data-choice-finishing-detail]', finishingDetail);
  document.querySelectorAll('[data-choice-finishing-state]').forEach(element => element.classList.toggle('is-off', !finishNow));
  document.querySelectorAll('[data-open-panel="finishing"]').forEach(element => element.dataset.active = finishNow ? 'true' : 'false');
  setText('[data-settings-value="output"]', outputParts.join(' / '));
  setText('[data-review-source]', sourceLabel);
  setText('[data-review-transcription-compact]', `認識モデル ${model}・${transcriptionHardware} / 話者分離 ${diarizationHardware}`);
  setText('[data-review-transcription]', `認識モデル: ${model} / ${transcriptionHardware}`);
  setText('[data-review-diarization]', `話者分離: ${qwenSelected ? 'Nemotron 3' : 'pyannote.audio'} / ${diarizationHardware}${fixedSpeakerLabel ? ` / ${fixedSpeakerLabel}` : ''}`);
  setText('[data-review-output]', outputParts.join(' / '));
  setText('[data-flow-detail="1"]', hasSource ? sourceLabel : '未選択');
  setText('[data-flow-detail="2"]', `${mode} / ${model} / ${language}`);
  setText('[data-flow-detail="3"]', readiness.ready ? '開始時にモデル確認' : hasSource ? '開始前に要確認' : 'ファイルを選択');

  if (startButton) startButton.disabled = jobRunning || !readiness.ready;
  renderMobileWizard();
}

function isVideoSource(value) {
  return /\.(mp4|m4v|mov|mkv)$/i.test(String(value || '').trim().split(/[?#]/)[0]);
}

function hideSourcePreview() {
  window.clearTimeout(thumbnailTimer);
  thumbnailRequestId += 1;
  if (sourceThumbnailController) sourceThumbnailController.abort();
  sourceThumbnailController = null;
  if (sourceThumbnailObjectUrl) URL.revokeObjectURL(sourceThumbnailObjectUrl);
  sourceThumbnailObjectUrl = null;
  if (sourceThumbnail) {
    sourceThumbnail.removeAttribute('src');
    sourceThumbnail.hidden = true;
  }
  if (sourcePreview) {
    sourcePreview.classList.remove('loaded');
    sourcePreview.hidden = true;
  }
  if (sourcePreviewMessage) sourcePreviewMessage.textContent = '';
}

async function showSourceThumbnail(path, name = '') {
  if (!sourcePreview || !sourceThumbnail || !sourcePreviewMessage) return;
  const value = String(path || '').trim();
  if (!isVideoSource(value)) {
    hideSourcePreview();
    return;
  }
  const requestId = ++thumbnailRequestId;
  if (sourceThumbnailController) sourceThumbnailController.abort();
  sourceThumbnailController = new AbortController();
  if (sourceThumbnailObjectUrl) URL.revokeObjectURL(sourceThumbnailObjectUrl);
  sourceThumbnailObjectUrl = null;
  sourcePreview.hidden = false;
  sourcePreview.classList.remove('loaded');
  sourceThumbnail.hidden = true;
  sourcePreviewMessage.textContent = `${name || value.split(/[\\/]/).pop()} のサムネイルを作成しています…`;
  sourceThumbnail.onload = () => {
    if (requestId !== thumbnailRequestId) return;
    if (sourceThumbnailObjectUrl) URL.revokeObjectURL(sourceThumbnailObjectUrl);
    sourceThumbnailObjectUrl = null;
    sourcePreview.classList.add('loaded');
    sourceThumbnail.hidden = false;
    sourcePreviewMessage.textContent = name || value;
  };
  const showThumbnailError = () => {
    if (requestId !== thumbnailRequestId) return;
    sourcePreview.classList.remove('loaded');
    sourceThumbnail.hidden = true;
    sourcePreviewMessage.textContent = 'サムネイルを作成できませんでした。動画として開けるファイルか確認してください。';
  };
  sourceThumbnail.onerror = showThumbnailError;
  try {
    const response = await apiFetch('/api/source-thumbnail', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path: value}),
      cache: 'no-store',
      signal: sourceThumbnailController.signal
    });
    if (!response.ok) throw new Error('thumbnail request failed');
    const blob = await response.blob();
    if (requestId !== thumbnailRequestId) return;
    sourceThumbnailObjectUrl = URL.createObjectURL(blob);
    sourceThumbnail.src = sourceThumbnailObjectUrl;
  } catch (error) {
    if (error && error.name === 'AbortError') return;
    showThumbnailError();
  } finally {
    if (requestId === thumbnailRequestId) sourceThumbnailController = null;
  }
}

function scheduleSourceThumbnail(path) {
  window.clearTimeout(thumbnailTimer);
  const value = String(path || '').trim();
  if (!value || !isVideoSource(value)) {
    hideSourcePreview();
    return;
  }
  thumbnailTimer = window.setTimeout(() => showSourceThumbnail(value), 450);
}
