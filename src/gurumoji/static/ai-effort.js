/* Original radios and readAiEfforts remain the only setting state. */
const effortStages = [
  ['outline', '会話の流れを整理', '会話全体を話題ごとに整理します。AI見解にも共通の設定です。', 'create-outline'],
  ['cleanup', '文章の仕上げ', '文章を整える強さです。追加推論の強さとは別の設定です。', 'clean-transcript'],
  ['name_extract', '話者名を確認', '自己紹介から名前の候補を探します。', 'detect-names'],
  ['name_verify', '話者を再確認', '名前と発話の対応を確認します。', 'detect-names']
];
const effortLevels = [['low', '低'], ['medium', '中'], ['high', '高'], ['ultra', '最大']];
const cleanupEffortLevels = [['off', 'なし'], ['low', '小'], ['medium', '中'], ['high', '高'], ['ultra', 'MAX']];
const effortDescriptions = {
  off: '詳しい検討はOFF／提供元の最小設定を要求します。処理そのものは停止しません。実際の推論量はモデルに依存します。',
  low: '短めの検討を要求します。処理そのものは実行します。',
  medium: '標準的な詳しさでの検討を要求します。',
  high: '詳しい検討を要求します。時間や使用量が増える場合があります。',
  ultra: '最大の詳しさでの検討を要求します。時間や使用量が増える場合があります。'
};
const cleanupEffortDescriptions = {
  off: '文章の校正を実行せず、認識結果を残します。他の処理は個別の設定に従います。',
  low: '明らかな誤りを中心に整えます。',
  medium: '誤認識や聞き取りにくい箇所を整えます。',
  high: '文脈を参考にして整えます。',
  ultra: '文脈を参考に、文章を詳しく整えます。'
};
const effortIconPaths = {
  outline: '<path d="M6 5h12v14H6m12-7h-5"/><circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="13" cy="12" r="2"/>',
  cleanup: '<path d="M13 3H4v18h14v-8M7 7h5M7 11h3m2 5 8-8-3-3-8 8-1 4z"/>',
  name_extract: '<rect x="2" y="4" width="20" height="16" rx="2"/><circle cx="8" cy="10" r="2"/><path d="M4 17c1-5 7-5 8 0m3-8h4m-4 5h4"/>',
  name_verify: '<path d="M5 3h14a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3h-8l-6 3 1-3H5a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3zm2 8 3 3 7-7"/>'
};
let localEffortCapability = null;
let localEffortModel = null;
let localEffortGeneration = 0;
let localEffortState = 'idle';
const effortRoot = document.querySelector('#ai-effort-settings');
if (effortRoot) {
  effortStages.forEach(([key, title, detail]) => {
    const disclosure = document.createElement('details');
    disclosure.className = 'effort-disclosure';
    const cleanup = key === 'cleanup';
    const levels = cleanup ? cleanupEffortLevels : effortLevels;
    const thinkingMode = `<div class="effort-thinking" ${cleanup ? 'hidden' : ''}><span class="effort-group-title">AIで詳しく確認</span><div class="thinking-mode effort-options">${[['on', 'する'], ['off', 'しない（OFF／最小）']].map(([value, label]) => `<label><input type="radio" name="ai_thinking_mode_${key}" value="${value}" ${value === 'on' ? 'checked' : ''}><span>${label}</span></label>`).join('')}</div></div>`;
    const choices = cleanup ? levels : [['off', 'OFF／最小'], ...levels];
    disclosure.innerHTML = `<summary><span class="effort-icon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false">${effortIconPaths[key]}</svg></span><strong>${title}</strong><span class="effort-current"></span><span class="effort-open-label">設定を開く</span><span class="effort-status"></span></summary><fieldset class="effort-card" data-stage="${key}" aria-describedby="effort-description-${key} effort-capability-${key}"><legend>${title}の設定</legend><p>${detail}</p><input type="hidden" name="ai_effort_${key}" value="medium"><div class="effort-simple"><label for="effort-select-${key}">${cleanup ? '文章の調整レベル' : '要求する検討の詳しさ'}</label><select id="effort-select-${key}" class="effort-select">${choices.map(([value, label]) => `<option value="${value}">${label}</option>`).join('')}<option value="on" hidden>する（選択した詳しさを維持）</option></select></div><div class="effort-detailed" hidden>${thinkingMode}<div class="effort-grades"><span class="effort-group-title">${cleanup ? '文章の調整レベル' : '確認の詳しさ'}</span><div class="effort-options">${levels.map(([value, label]) => `<label><input type="radio" name="ai_effort_choice_${key}" value="${value}" ${value === 'medium' ? 'checked' : ''}><span>${label}</span></label>`).join('')}</div></div></div><p id="effort-description-${key}" class="effort-description"></p><p id="effort-capability-${key}" class="effort-capability"></p></fieldset><button type="button" class="effort-close">設定を閉じる</button>`;
    disclosure.querySelector('.effort-select').addEventListener('change', event => {
      event.stopPropagation();
      setAiEffortChoice(key, event.target.value);
    });
    const close = () => { disclosure.open = false; disclosure.querySelector('summary').focus(); };
    disclosure.querySelector('.effort-close').addEventListener('click', close);
    disclosure.addEventListener('keydown', event => { if (event.key === 'Escape' && disclosure.open) { event.preventDefault(); close(); } });
    disclosure.addEventListener('toggle', () => { disclosure.querySelector('.effort-open-label').textContent = disclosure.open ? '設定を閉じる' : '設定を開く'; });
    effortRoot.append(disclosure);
  });
  try {
    const saved = JSON.parse(localStorage.getItem('gurumoji.ai-efforts') || '{}');
    if (saved && typeof saved === 'object' && !Array.isArray(saved)) effortStages.forEach(([key]) => {
      const value = saved[key] === 'auto' ? 'medium' : saved[key];
      if (['off', 'low', 'medium', 'high', 'ultra'].includes(value)) setAiEffortChoice(key, value, false);
    });
  } catch (_) { /* Storage is optional; retain independent defaults. */ }
  effortRoot.addEventListener('change', event => {
    if (event.target.name === 'ai_effort_choice_cleanup') effortRoot.querySelector('[name="ai_thinking_mode_cleanup"][value="on"]').checked = true;
    try { localStorage.setItem('gurumoji.ai-efforts', JSON.stringify(readAiEfforts())); } catch (_) {}
    syncAiEffortSettings();
    if (typeof updateCreateSummary === 'function') updateCreateSummary();
  });
  document.querySelector('#effort-detail-toggle')?.addEventListener('click', event => {
    const detailed = event.currentTarget.getAttribute('aria-pressed') !== 'true';
    event.currentTarget.setAttribute('aria-pressed', String(detailed));
    effortRoot.querySelectorAll('.effort-simple').forEach(node => { node.hidden = detailed; });
    effortRoot.querySelectorAll('.effort-detailed').forEach(node => { node.hidden = !detailed; });
  });
  document.querySelector('#effort-capability-retry')?.addEventListener('click', () => {
    localEffortModel = null;
    syncAiEffortSettings();
  });
  ['ai-provider', 'finish-in-obsidian', 'clean-transcript', 'detect-names', 'create-outline'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', syncAiEffortSettings);
  });
  document.querySelectorAll('[name="transcript_finishing_mode"]').forEach(input => input.addEventListener('change', syncAiEffortSettings));
  syncAiEffortSettings();
}
function setAiEffortChoice(key, value, notify = true) {
  const card = effortRoot?.querySelector(`[data-stage="${key}"]`);
  if (!card || !['off', 'low', 'medium', 'high', 'ultra', 'on'].includes(value)) return;
  const mode = card.querySelector(`[name="ai_thinking_mode_${key}"][value="${value === 'off' && key !== 'cleanup' ? 'off' : 'on'}"]`);
  if (mode) mode.checked = true;
  const choice = card.querySelector(`[name="ai_effort_choice_${key}"][value="${value}"]`);
  if (choice) choice.checked = true;
  if (notify) (choice || mode)?.dispatchEvent(new Event('change', {bubbles: true}));
}
function readAiEfforts() {
  return {notation: document.querySelector('[name="ai_effort_notation"]')?.value || 'off', ...Object.fromEntries(effortStages.map(([key]) => {
    const mode = document.querySelector(`input[name="ai_thinking_mode_${key}"]:checked`)?.value || 'on';
    const effort = document.querySelector(`input[name="ai_effort_choice_${key}"]:checked`)?.value || 'medium';
    return [key, mode === 'off' ? 'off' : effort];
  }))};
}
function localEffortSupport(value) {
  const allowed = localEffortCapability?.allowed_options;
  if (!Array.isArray(allowed) || !allowed.length) return null;
  if (value === 'off') return allowed.includes('off');
  const aliases = {low: ['low', 'minimal'], medium: ['medium', 'low', 'minimal'], high: ['high', 'xhigh', 'medium', 'low', 'minimal'], ultra: ['xhigh', 'high', 'medium', 'low', 'minimal']};
  return (aliases[value] || []).some(option => allowed.includes(option)) || (allowed.includes('on') && localEffortCapability.default === 'on');
}
function aiEffortStagePlan() {
  // Mirror transcription_start's mode normalization without changing stored
  // checkbox preferences. Cleanup OFF still suppresses polishing and its outline.
  const mode = document.querySelector('input[name="transcript_finishing_mode"]:checked')?.value || 'custom';
  const advanced = mode === 'advanced', recommended = mode === 'recommended';
  const deferred = mode !== 'off' && !advanced && Boolean(document.querySelector('#finish-in-obsidian')?.checked);
  const cleanupLevel = readAiEfforts().cleanup;
  const fullCleanup = advanced || (!recommended && (document.querySelector('#clean-transcript')?.checked || document.querySelector('#jev-compare')?.checked));
  const recommendedCleanup = recommended && !deferred && Boolean(typeof tokenConfigSnapshot !== 'undefined' && tokenConfigSnapshot.typesafe);
  const cleanup = mode !== 'off' && cleanupLevel !== 'off' && (deferred || fullCleanup || recommendedCleanup);
  const contextOutline = cleanup && (deferred || fullCleanup || ['high', 'ultra'].includes(cleanupLevel));
  const outline = mode !== 'off' && (contextOutline || (!recommended && document.querySelector('#create-outline')?.checked));
  const names = mode !== 'off' && (advanced || Boolean(document.querySelector('#detect-names')?.checked));
  return {mode, advanced, deferred, contextOutline,
    requested: {cleanup: Boolean(cleanup), outline: Boolean(outline), name_extract: names, name_verify: names},
    configurable: {cleanup: mode !== 'off' && Boolean(recommended || deferred || fullCleanup), outline: Boolean(outline), name_extract: names, name_verify: names}};
}
function aiEffortStageEnabled(key) {
  return aiEffortStagePlan().configurable[key];
}
function syncAiEffortMandatedControls(provider, plan) {
  // In full mode these are statements, not functioning opt-out checkboxes.
  // Hidden/disabled original inputs retain their custom-mode checked preferences.
  for (const id of ['clean-transcript', 'detect-names']) {
    const input = document.getElementById(id);
    if (!input) continue;
    input.hidden = plan.advanced;
    input.disabled = Boolean(plan.advanced || provider?.disabled || provider?.value === 'none');
    const note = document.getElementById(`${id}-mode-note`);
    if (note) note.hidden = !plan.advanced;
  }
}
function aiEffortReadiness() {
  const blockers = [], notes = [];
  if (document.querySelector('#ai-provider')?.value !== 'lmstudio') return {blockers, notes};
  const values = readAiEfforts();
  const plan = aiEffortStagePlan();
  effortStages.forEach(([key, title]) => {
    if (!plan.requested[key]) return;
    if (localEffortState === 'pending' || localEffortModel !== (typeof tokenConfigSnapshot === 'undefined' ? '' : tokenConfigSnapshot.lmstudio_model || '')) {
      blockers.push(`${title}: ローカルモデルの対応設定を確認中です`);
    } else if (localEffortState !== 'loaded' || localEffortSupport(values[key]) === null) {
      notes.push(key === 'cleanup' ? `${title}: 調整レベルは維持します。追加推論は未確認で、モデル既定になる場合があります` : `${title}: 推論設定は未確認です。モデル既定で実行される場合があり、選択したOFFも有効OFFを保証しません`);
    } else if (!localEffortSupport(values[key])) {
      if (key === 'cleanup') notes.push(`${title}: 調整レベルは維持し、追加推論はモデル既定を使います`);
      else blockers.push(`${title}: 選択した設定はこのモデル連携では未対応です。カードを開いて対応する設定を選んでください`);
    }
  });
  return {blockers, notes};
}
function syncAiEffortSettings() {
  const provider = document.querySelector('#ai-provider');
  const local = provider?.value === 'lmstudio';
  const plan = aiEffortStagePlan();
  const notationChoice = document.querySelector('[name="ai_effort_notation"]');
  if (notationChoice) notationChoice.disabled = Boolean(provider?.disabled || provider?.value === 'none' || plan.mode === 'off');
  syncAiEffortMandatedControls(provider, plan);
  const model = typeof tokenConfigSnapshot === 'undefined' ? '' : tokenConfigSnapshot.lmstudio_model || '';
  if (!local && localEffortModel !== null) {
    localEffortGeneration += 1; localEffortModel = null; localEffortCapability = null; localEffortState = 'idle';
  }
  if (local && localEffortModel !== model) {
    localEffortModel = model; localEffortCapability = null; localEffortState = model ? 'pending' : 'unknown';
    const generation = ++localEffortGeneration;
    const current = () => generation === localEffortGeneration && document.querySelector('#ai-provider')?.value === 'lmstudio' && localEffortModel === model && (typeof tokenConfigSnapshot === 'undefined' ? '' : tokenConfigSnapshot.lmstudio_model || '') === model;
    if (model) apiFetch('/api/ai/lmstudio-reasoning', {signal: AbortSignal.timeout(10000)}).then(r => r.ok ? r.json() : Promise.reject(new Error('lookup failed')))
      .then(data => {
        if (!current()) return;
        if (data.model !== model) { localEffortState = 'mismatch'; localEffortCapability = null; }
        else { localEffortCapability = data.reasoning && typeof data.reasoning === 'object' ? data.reasoning : {}; localEffortState = 'loaded'; }
        syncAiEffortSettings();
        if (typeof updateCreateSummary === 'function') updateCreateSummary();
      }).catch(() => {
        if (!current()) return;
        localEffortCapability = null; localEffortState = 'error'; syncAiEffortSettings();
        if (typeof updateCreateSummary === 'function') updateCreateSummary();
      });
  }
  const allowed = Array.isArray(localEffortCapability?.allowed_options) ? localEffortCapability.allowed_options : [];
  const binary = local && allowed.includes('on') && !allowed.some(value => ['minimal', 'low', 'medium', 'high', 'xhigh'].includes(value));
  const retry = document.querySelector('#effort-capability-retry');
  if (retry) { retry.hidden = !local; retry.disabled = Boolean(provider?.disabled || localEffortState === 'pending'); }
  const values = readAiEfforts();
  effortStages.forEach(([key, , , toggle]) => {
    const card = effortRoot?.querySelector(`[data-stage="${key}"]`);
    if (!card) return;
    const cleanup = key === 'cleanup', level = values[key];
    const enabled = aiEffortStageEnabled(key, toggle);
    const baseDisabled = Boolean(provider?.disabled || provider?.value === 'none' || !enabled);
    // Keep the hidden payload fields successful even when editing is unavailable.
    card.setAttribute('aria-disabled', String(baseDisabled));
    const uncertain = local && (localEffortState !== 'loaded' || !allowed.length);
    const support = local ? localEffortSupport(level) : true;
    card.querySelectorAll('[name^="ai_thinking_mode_"]').forEach(input => {
      input.disabled = baseDisabled || (!cleanup && (uncertain || local && (input.value === 'off' ? localEffortSupport('off') === false : !effortLevels.some(([value]) => localEffortSupport(value) === true))));
    });
    const thinkingOn = card.querySelector('[name^="ai_thinking_mode_"]:checked')?.value !== 'off';
    card.querySelectorAll('[name^="ai_effort_choice_"]').forEach(input => {
      input.disabled = baseDisabled || (!cleanup && (!thinkingOn || uncertain || binary || local && localEffortSupport(input.value) === false));
    });
    card.querySelector('.effort-grades').hidden = !cleanup && binary;
    const select = card.querySelector('.effort-select');
    select.disabled = baseDisabled || (!cleanup && uncertain);
    [...select.options].forEach(option => {
      option.hidden = option.value === 'on' ? cleanup || !binary : !cleanup && binary && option.value !== 'off';
      option.disabled = option.value === 'on' ? localEffortCapability?.default !== 'on' : !cleanup && local && localEffortSupport(option.value) === false;
    });
    select.value = !cleanup && binary && level !== 'off' ? 'on' : level;
    card.querySelector('input[type="hidden"]').value = level;
    card.dataset.effort = level;
    const disclosure = card.parentElement;
    const label = (cleanup ? cleanupEffortLevels : [['off', 'OFF／最小'], ...effortLevels]).find(([value]) => value === level)?.[1] || level;
    disclosure.querySelector('.effort-current').textContent = `選択値: ${label}`;
    let status = '';
    if (local && !(cleanup && level === 'off')) {
      if (localEffortState === 'pending') status = '対応設定を確認中です。';
      else if (localEffortState === 'error') status = '対応設定の取得に失敗しました。再確認できます。';
      else if (localEffortState === 'mismatch') status = '応答のモデルが一致しません。再確認してください。';
      else if (uncertain) status = '対応設定は不明です。モデル既定で動作する場合があり、有効なON/OFFは確認できません。';
      else if (!support) status = cleanup ? '調整の強さは維持します。追加推論はモデル既定を使います。' : '選択値は未対応です。対応する設定へ変更するまで実行できません。';
      else if (binary) status = 'ON/OFF型です。段階差は適用せず、選択した詳しさを保持します。ONはモデル既定がONの場合のみ対応します。';
      else status = 'モデルが対応する推論設定へ割り当てます。選択値は変えません。';
    }
    if (!enabled) status = `この処理は現在無効です。選択値は維持します。 ${status}`;
    else if (provider?.value === 'none') status = 'AIを選択すると設定できます。選択値は維持します。';
    else if (provider?.disabled) status = `実行中は変更できません。 ${status}`;
    const compactStatus = !enabled ? '現在無効（選択値は維持）' : provider?.value === 'none' ? 'AI未選択（選択値は維持）'
      : provider?.disabled ? '実行中は変更できません' : !status ? ''
      : localEffortState === 'pending' ? 'モデルの対応設定を確認中'
      : localEffortState === 'error' ? '対応設定の取得失敗・再確認が必要'
      : localEffortState === 'mismatch' ? 'モデル不一致・再確認が必要'
      : uncertain ? '対応設定不明・実際の推論は未確認'
      : !support ? cleanup ? '追加推論はモデル既定' : '選択値は未対応・変更が必要'
      : binary ? 'ON/OFFのみ（段階差なし）' : 'モデルの対応値へ割り当て';
    disclosure.querySelector('.effort-status').textContent = [plan.advanced && key !== 'outline' ? '全文方式の対象' : plan.contextOutline && key === 'outline' ? '校正の参照用も対象' : '', compactStatus].filter(Boolean).join(' · ');
    const mandated = plan.advanced && key !== 'outline' ? (cleanup ? '全文方式に含まれる校正です。「なし」で校正を停止できます。' : '全文方式に含まれる話者確認です。検討のOFF／最小でも話者確認そのものは実行します。') : plan.contextOutline && key === 'outline' ? '文章校正の参照用アウトラインも、この設定で実行します。独立したアウトライン出力の選択とは別です。' : '';
    card.querySelector('.effort-capability').textContent = [mandated, status].filter(Boolean).join(' ');
    let description = cleanup ? cleanupEffortDescriptions[level] : effortDescriptions[level];
    if (cleanup && level !== 'off') description += ' おすすめ方式では、小・中は発話単位、高は直前、MAXは前後の文脈を参照します。詳細方式の全文校正は同じ参照範囲ではありません。';
    card.querySelector('.effort-description').textContent = description;
  });
}
function renderAiFinishingActivity(job) {
  const panel = document.querySelector('#ai-finishing-activity');
  if (!panel) return;
  const active = job.status === 'running' && ['finishing', 'speaker_names', 'outline'].includes(job.stage);
  panel.hidden = !active;
  panel.setAttribute('aria-busy', String(active));
  if (!active) return;
  const title = panel.querySelector('[data-finishing-title]');
  title.textContent = job.stage_label || 'AI仕上げ中';
  panel.querySelector('[data-finishing-detail]').textContent = job.message || 'AIの応答を待っています…';
}

// Poll only the displayed conversation; never start a finishing operation here.
let obsidianPollBusy = false;
setInterval(async () => {
  const panel = document.querySelector('#obsidian-finishing-activity');
  if (!panel || obsidianPollBusy || document.hidden) return;
  const itemId = typeof currentJobId === 'undefined' ? '' : currentJobId;
  if (!itemId) { panel.hidden = true; return; }
  obsidianPollBusy = true;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/obsidian-finishing`, {
      signal: AbortSignal.timeout(5000)
    });
    if (!response.ok) throw new Error('status unavailable');
    const state = await response.json();
    if (itemId !== currentJobId) { panel.hidden = true; return; }
    // A prepared workbench is inert while the watcher is stopped (OBS-09); say so.
    const watcher = state.watcher && typeof state.watcher === 'object' ? state.watcher : {};
    const watcherDown = state.status !== 'unprepared' && watcher.state === 'failed';
    panel.hidden = !watcherDown && ['unprepared', 'ready'].includes(state.status);
    panel.setAttribute('aria-busy', String(!watcherDown && state.status === 'running'));
    panel.querySelector('.finishing-orbit').hidden = watcherDown || state.status !== 'running';
    panel.querySelector('[data-obsidian-detail]').textContent = watcherDown
      ? [watcher.message, watcher.detail].filter(Boolean).join(' ')
      : state.message;
  } catch (_) { panel.hidden = true; }
  finally { obsidianPollBusy = false; }
}, 3000);
