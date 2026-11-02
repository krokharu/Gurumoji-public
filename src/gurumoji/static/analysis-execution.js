/* Durable M0-M7 analysis execution UI.  The server owns plans, ordering,
   attempts, cancellation and recovery; this file only edits plans and renders
   versioned state returned by the analysis core. */
const analysisExecutionStorageKey = 'gurumoji.analysisExecution.v2';
const analysisExecutionStageDefinitions = Array.from({length: 8}, (_, index) => ({
  id: `M${index}`,
  label: `M${index}`,
  title: [
    '入力・計画枠', 'アウトライン範囲', '一次分析', '図表仕様',
    '実行定義の確定', '本分析', '比較範囲', '成果物・公開'
  ][index]
}));

const analysisExecutionState = {
  id: '', itemId: '', itemName: '', mode: 'automatic', status: 'idle', active: false,
  currentIndex: -1, stages: [], settings: {}, logs: [], startedAt: 0,
  cancelRequested: false, generation: 0, restored: false, resuming: false,
  definitionRevision: 0, pollTimer: null
};

const analysisRunDialog = document.querySelector('#analysis-run-dialog');
const analysisRunForm = document.querySelector('#analysis-run-form');
const analysisRunButton = document.querySelector('#analysis-run-button');
const analysisRunSettingsButton = document.querySelector('#analysis-run-settings-button');
const analysisRunStartButton = document.querySelector('#analysis-run-start');
const analysisRunDialogMessage = document.querySelector('#analysis-run-dialog-message');
const analysisAdvisorObjective = document.querySelector('#analysis-advisor-objective');
const analysisAdvisorEngine = document.querySelector('#analysis-advisor-engine');
const analysisAdvisorModel = document.querySelector('#analysis-advisor-model');
const analysisAdvisorModelField = document.querySelector('#analysis-advisor-model-field');
const analysisAdvisorProposeButton = document.querySelector('#analysis-advisor-propose');
const analysisAdvisorFlow = document.querySelector('#analysis-advisor-flow');
const analysisAdvisorResult = document.querySelector('#analysis-advisor-result');
let analysisDialogGeneration = 0;
let analysisAdvisorGeneration = 0;
let analysisStartOwner = null;
let analysisPlanGeneration = 0;
let analysisRunOwner = 0;
const analysisRunOperations = new Map();
function captureAnalysisDialog() {
  const context = captureAnalysisContext();
  const generation = analysisDialogGeneration;
  return {context, current: () => generation === analysisDialogGeneration && analysisRunDialog?.open && isAnalysisContextCurrent(context)};
}
function invalidateAnalysisDialog() {
  ++analysisDialogGeneration;
  ++analysisAdvisorGeneration;
  ++analysisPlanGeneration;
  if (analysisAdvisorProposeButton) analysisAdvisorProposeButton.disabled = false;
}
function closeAnalysisExecutionDialog() {
  // Native close events may be delivered after another opening; retire now.
  invalidateAnalysisDialog();
  if (!analysisRunDialog?.open) return false;
  analysisRunDialog.close();
  return true;
}
function captureAnalysisRun(operation) {
  const itemId = analysisExecutionState.itemId, id = analysisExecutionState.id;
  const owner = analysisRunOwner, generation = analysisExecutionState.generation;
  const token = {};
  analysisRunOperations.set(operation, token);
  return {itemId, id, current: () => owner === analysisRunOwner && id === analysisExecutionState.id
    && itemId === analysisExecutionState.itemId && generation === analysisExecutionState.generation
    && analysisRunOperations.get(operation) === token,
    release: () => { if (analysisRunOperations.get(operation) === token) analysisRunOperations.delete(operation); }};
}
let analysisPlanningProposal = null;
let analysisPlanningItemId = '';
let analysisAdvisorItemId = '';
const analysisExecutionView = document.querySelector('#analysis-execution-view');
const analysisExecutionChip = document.querySelector('#analysis-job-chip');
const analysisExecutionChipLabel = document.querySelector('#analysis-job-chip-label');
let analysisExecutionElapsedTimer = null;

function analysisExecutionSetDialogMessage(message = '', error = false) {
  setAlert(analysisRunDialogMessage, message, error);
}

function analysisExecutionMode() {
  return document.querySelector('input[name="analysis_run_mode"]:checked')?.value || 'automatic';
}

const analysisMeasurementPresets = {
  text_length: {name: '発話の文字数', description: '発話本文の文字数を数えます。内容の良さや重要度は測りません。', source: 'text', rule: 'text_length', type: 'number', level: 'ratio', method: 'descriptive', limits: '文字数は発話内容の意味・重要度・理解度を表しません。'},
  duration: {name: '発話時間', description: '有効な開始・終了時刻の差を秒で測ります。', source: 'duration', rule: 'duration', type: 'number', level: 'ratio', method: 'descriptive', limits: '時刻不明・不正な発話は欠測です。重なりを含むため会議全体の長さとは一致しません。'},
  speaker_frequency: {name: '話者ID別の度数', description: '各発話の話者IDをカテゴリとして数えます。', source: 'speaker', rule: 'identity', type: 'category', level: 'nominal', method: 'frequency', limits: '発話の分割単位に依存します。話者の役割・参加意欲・影響力を推定しません。'},
  role_frequency: {name: '役割別の度数', description: '各発話に登録された役割をカテゴリとして数えます。', source: 'role', rule: 'identity', type: 'category', level: 'nominal', method: 'frequency', limits: '会話で明示設定した役割、話者管理の登録値、分析準備の発話別の役割を集計します。自動の「参加者」補完と記録元が不明な値は欠測です。分析準備の役割があれば優先し、本文から役割を推測しません。'}
};
let analysisMeasurement = null;
function analysisMeasurementPreset() {
  return analysisMeasurementPresets[document.querySelector('#analysis-definition-preset')?.value] || analysisMeasurementPresets.text_length;
}
function analysisMeasurementNewIdentity() {
  const suffix = (typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : createSubmissionId()).replace(/[^A-Za-z0-9]/g, '').slice(0, 32);
  return `measure_${suffix}`;
}
function analysisMeasurementReset() {
  analysisMeasurement = {context: captureAnalysisContext(), touched: new Set(), saved: null, trial: null, adopted: null, operation: null};
  for (const key of ['name', 'id', 'description', 'output']) {
    const input = document.querySelector(`#analysis-definition-${key}`);
    if (input) input.value = '';
  }
  analysisMeasurementFillGenerated();
}
function analysisMeasurementFillGenerated() {
  const state = analysisMeasurement, preset = analysisMeasurementPreset();
  if (!state) return;
  const generatedId = analysisMeasurementNewIdentity();
  const values = {name: preset.name, description: preset.description, id: generatedId, output: generatedId};
  for (const [key, value] of Object.entries(values)) {
    const input = document.querySelector(`#analysis-definition-${key}`);
    if (input && !state.touched.has(key) && (key !== 'id' && key !== 'output' || !input.value)) input.value = value;
  }
}
function analysisMeasurementFingerprint() { return JSON.stringify(analysisExecutionDefinitionFromForm('draft')); }
function analysisMeasurementCurrent() { return analysisMeasurement && isAnalysisContextCurrent(analysisMeasurement.context); }
function analysisMeasurementRefreshContext() {
  const previous = analysisMeasurement;
  if (!previous || analysisMeasurementCurrent()
      || previous.context.itemId !== analysisState.itemId
      || previous.context.navigation !== analysisNavigationGeneration || !analysisState.data) return false;
  const protectStoredIdentity = Boolean(previous.saved || previous.adopted || previous.pendingAdoption || previous.operation);
  analysisMeasurement = {context: captureAnalysisContext(), touched: new Set(previous.touched),
    saved: null, trial: null, adopted: null, operation: null,
    contextNotice: '入力版が更新されました。定義の文言を保持し、前の試行・採用を失効しました。下書き保存と少数試行から確認してください。'};
  if (protectStoredIdentity) {
    // Preserve any already stored or uncertain old definition; never rewrite it.
    document.querySelector('#analysis-definition-id').value = analysisMeasurementNewIdentity();
    analysisMeasurement.touched.delete('id');
    analysisMeasurement.contextNotice += ' 旧定義を保つため別の下書きIDを用意しました。';
  }
  const confirm = document.querySelector('#analysis-definition-confirm');
  if (confirm) confirm.checked = false;
  analysisMeasurementRender();
  analysisExecutionUpdatePlanSummary({preserveMessage: true});
  if (analysisRunDialog?.open) analysisExecutionSetDialogMessage(analysisMeasurement.contextNotice
    + (hasUnsavedAnalysisChanges() ? ' 分析設定に追加の未保存変更があります。先に保存してください。' : ''), true);
  return true;
}
function analysisMeasurementInvalidate(event) {
  if (!analysisMeasurementCurrent()) return;
  const state = analysisMeasurement;
  ++analysisPlanGeneration;
  const key = event?.target?.id?.replace('analysis-definition-', '');
  if (['name', 'id', 'description', 'output'].includes(key)) state.touched.add(key);
  if (state.adopted) {
    // Keep the adopted record intact. An edit always begins another identity.
    const id = analysisMeasurementNewIdentity();
    const explicitNewId = key === 'id' && document.querySelector('#analysis-definition-id').value !== state.adopted.definition_id;
    if (!explicitNewId) document.querySelector('#analysis-definition-id').value = id;
    if (!explicitNewId) state.touched.delete('id');
    state.saved = null;
  } else if (key === 'id') state.saved = null;
  state.operation = null; state.trial = null; state.adopted = null; state.blocked = false;
  const confirm = document.querySelector('#analysis-definition-confirm');
  if (confirm) confirm.checked = false;
  analysisMeasurementFillGenerated();
  analysisMeasurementRender();
  analysisExecutionUpdatePlanSummary();
}
function analysisMeasurementRender() {
  const state = analysisMeasurement, preset = analysisMeasurementPreset();
  const definition = analysisExecutionDefinitionFromForm();
  const current = analysisMeasurementCurrent();
  const unchanged = current && state.saved && state.saved.fingerprint === analysisMeasurementFingerprint();
  const busy = Boolean(state?.operation || state?.pendingAdoption);
  const analysisUnsaved = hasUnsavedAnalysisChanges();
  const confirmed = Boolean(document.querySelector('#analysis-definition-confirm')?.checked);
  const setText = (selector, text) => { const node = document.querySelector(selector); if (node) node.textContent = text; };
  setText('#analysis-definition-summary', `定義名: ${definition.name || '未入力'} ／ ID: ${definition.definition_id || '未入力'} ／ 列: ${definition.output_column || '未入力'} ／ 説明: ${definition.description || '未入力'}`);
  setText('#analysis-definition-conditions', `計算条件（読取専用）: 発話単位 / 入力 ${preset.source} / 規則 ${preset.rule} / 型 ${preset.type} / 尺度 ${preset.level} / 集計 ${preset.method} / 分母は対象発話全体 / 欠測は理由付きnull`);
  setText('#analysis-definition-limits', `測定の限界: ${preset.limits} 試行は固定された最大20発話です。全件の代表性を保証しません。外部AIへの送信はありません。`);
  setText('#analysis-definition-state', state?.pendingAdoption ? '採用結果が未確定です。保存状態の確認前にもう一度更新しません。' : state?.adopted ? `採用済み: 第${state.adopted.version}版。下の「全件分析を開始」で実行します。`
    : state?.trial ? '試行結果を確認し、チェックを付けてから採用してください。'
      : unchanged ? '下書き保存済み。少数試行はまだ採用されていません。' : '未保存の測定下書きです。');
  const stateNotice = document.querySelector('#analysis-definition-state');
  if (state?.contextNotice && stateNotice) stateNotice.textContent = `${state.contextNotice} ${stateNotice.textContent}`;
  for (const [selector, disabled] of [
    ['#analysis-definition-save', busy || !current || analysisUnsaved || Boolean(state?.blocked)], ['#analysis-definition-trial', busy || !unchanged || analysisUnsaved || Boolean(state?.adopted) || Boolean(state?.blocked)],
    ['#analysis-definition-confirm', busy || !state?.trial || Boolean(state?.adopted)],
    ['#analysis-definition-adopt', busy || !state?.trial || !confirmed || analysisUnsaved || Boolean(state?.adopted)]
  ]) { const button = document.querySelector(selector); if (button) button.disabled = disabled; }
  const inspect = document.querySelector('#analysis-definition-inspect');
  if (inspect) { inspect.hidden = !state?.pendingAdoption;inspect.disabled = Boolean(state?.operation); }
  document.querySelectorAll('#analysis-manual-definition input:not([type="checkbox"]), #analysis-definition-preset').forEach(control => { control.disabled = busy; });
  const host = document.querySelector('#analysis-definition-trial-result');
  if (!host) return;
  host.replaceChildren();
  const trial = state?.trial;
  if (!trial) return;
  const note = document.createElement('p');
  note.textContent = `固定試行 ${trial.sample_size}件 / 対象${trial.total_count}件・除外${trial.excluded_count}件 / 有効${trial.valid_count}件・欠測${trial.missing_count}件 / 定義 第${trial.definition_version}版・revision ${trial.definition_revision} / 入力 ${trial.input_hash} / 本文と音声は現在のデータから補完しません。`;
  const table = document.createElement('table'); table.className = 'analysis-table';
  const caption = document.createElement('caption'); caption.textContent = '保存された試行行（欠測はnullと理由を表示）';table.append(caption);
  const columns = [...new Set((trial.rows || []).flatMap(row => Object.keys(row)))];
  const head = document.createElement('tr');for (const key of columns) { const th = document.createElement('th');th.scope = 'col';th.textContent = key;head.append(th); }table.append(head);
  for (const row of trial.rows || []) {
    const tr = document.createElement('tr');
    for (const key of columns) {
      const td = document.createElement('td');
      td.textContent = row[key] === null ? 'null（欠測）' : row[key] === undefined ? '—' : String(row[key]);
      if (key.endsWith('__missing_reason') && row[key] === 'role_not_recorded') {
        td.textContent += '（役割未記録：自動補完は測定に使用しません）';
      } else if (key.endsWith('__missing_reason') && row[key] === 'role_provenance_unknown') {
        td.textContent += '（役割の記録元不明：旧データ等）';
      }
      tr.append(td);
    }
    table.append(tr);
  }
  const wrap = document.createElement('div');wrap.className = 'analysis-table-wrap';wrap.append(table);host.append(note, wrap);
}
function analysisExecutionSyncDisplay() {
  const detail = document.querySelector('input[name="analysis_display_mode"]:checked')?.value === 'detail';
  document.querySelectorAll('[data-analysis-detail]').forEach(node => { node.hidden = !detail; });
}
async function analysisMeasurementInspect() {
  const state = analysisMeasurement;
  if (!analysisMeasurementCurrent() || !state.pendingAdoption) return;
  if (state.operation) {
    const waitingDialog = captureAnalysisDialog(), pending = state.pendingAdoption;
    if (!state.operation.finished) return;
    await state.operation.finished;
    if (waitingDialog.current() && state === analysisMeasurement && state.pendingAdoption === pending) return analysisMeasurementInspect();
    return;
  }
  const pending = state.pendingAdoption, dialog = captureAnalysisDialog(), token = {};
  token.finished = new Promise(resolve => { token.finish = resolve; });
  state.operation = token;
  const owns = () => state === analysisMeasurement && state.operation === token && state.pendingAdoption === pending
    && dialog.current() && pending.fingerprint === analysisMeasurementFingerprint();
  analysisMeasurementRender();
  try {
    const result = await analysisExecutionRequestJson(pending.base, {cache: 'no-store'});
    if (!owns()) return;
    const definition = result.definition;
    const same = !definition.validation_error && Object.entries(pending.draft).every(([key, value]) => key === 'status' || JSON.stringify(definition[key]) === JSON.stringify(value));
    if (same && definition.status === 'adopted' && definition.last_trial?.trial_id === pending.trial.trial_id
        && definition.last_trial?.input_hash === pending.trial.input_hash && definition.last_trial?.definition_hash === pending.trial.definition_hash) {
      state.adopted = definition; state.trial = pending.trial; state.saved = {definition, fingerprint: pending.fingerprint};
      state.pendingAdoption = null;state.blocked = false;
      analysisExecutionSetDialogMessage('確認済み試行と一致する採用版を保存先で確認しました。');
    } else if (same && definition.status === 'draft') {
      state.saved = {definition, fingerprint: pending.fingerprint};state.trial = null;state.adopted = null;
      state.pendingAdoption = null;state.blocked = false;
      analysisExecutionSetDialogMessage('保存先は下書きです。少数試行から確認し直してください。');
    } else {
      state.trial = null;state.adopted = null;state.pendingAdoption = null;state.blocked = true;
      analysisExecutionSetDialogMessage('保存先の定義が変更・廃止されています。別の定義IDで下書きを作成してください。', true);
    }
  } catch (error) {
    if (owns()) analysisExecutionSetDialogMessage('採用の保存状態を取得できませんでした。「保存状態を再確認」で取得するまで更新を止めています。', true);
  } finally {
    const refresh = state === analysisMeasurement && state.operation === token
      && analysisMeasurementCurrent() && analysisRunDialog?.open;
    if (state.operation === token) state.operation = null;
    token.finish();
    if (refresh) { analysisMeasurementRender();analysisExecutionUpdatePlanSummary({preserveMessage:true}); }
  }
}

async function analysisMeasurementAction(action) {
  if (!analysisMeasurementCurrent() || analysisMeasurement.operation) return;
  if (analysisMeasurement.pendingAdoption) { await analysisMeasurementInspect(); return; }
  if (analysisMeasurement.blocked) return;
  const validation = analysisExecutionValidateDefinition();
  if (validation) { analysisExecutionSetDialogMessage(validation, true); return; }
  const state = analysisMeasurement, dialog = captureAnalysisDialog(), fingerprint = analysisMeasurementFingerprint();
  const token = {}; token.finished = new Promise(resolve => { token.finish = resolve; }); state.operation = token;
  let adoptionSubmitted = false;
  const owns = () => state === analysisMeasurement && state.operation === token && dialog.current() && fingerprint === analysisMeasurementFingerprint();
  const draft = analysisExecutionDefinitionFromForm('draft');
  const base = `/api/library/${encodeURIComponent(state.context.itemId)}/analysis/definitions/${encodeURIComponent(draft.definition_id)}`;
  const headers = {'Content-Type': 'application/json'};
  analysisMeasurementRender();
  try {
    if (action === 'save') {
      if (state.adopted) throw new Error('採用済み定義は保持されます。編集すると別の下書きになります。');
      const result = await analysisExecutionRequestJson(base, {method: 'PUT', headers, body: JSON.stringify({...draft, expected_revision: state.saved?.definition.definition_id === draft.definition_id ? state.saved.definition.revision : 0})});
      if (!owns()) return;
      state.saved = {definition: result.definition, fingerprint};state.trial = null;state.adopted = null;state.contextNotice = '';
    } else if (action === 'trial') {
      if (!state.saved || state.saved.fingerprint !== fingerprint || state.adopted) throw new Error('変更した下書きを先に保存してください。');
      state.trial = null;
      document.querySelector('#analysis-definition-confirm').checked = false;
      analysisMeasurementRender();
      const result = await analysisExecutionRequestJson(`${base}/trials`, {method: 'POST', headers, body: JSON.stringify({limit: 20})});
      if (!owns()) return;
      if (result.trial.definition_id !== draft.definition_id || result.trial.definition_revision !== state.saved.definition.revision || result.trial.definition_version !== state.saved.definition.version) throw new Error('試行中に定義が更新されました。下書きを再読込してください。');
      state.trial = result.trial;
      document.querySelector('#analysis-definition-confirm').checked = false;
    } else if (action === 'adopt') {
      if (!state.trial || !document.querySelector('#analysis-definition-confirm')?.checked || state.adopted) throw new Error('固定試行を確認し、確認欄にチェックしてください。');
      adoptionSubmitted = true;
      state.pendingAdoption = {base, draft, trial: state.trial, fingerprint};
      const result = await analysisExecutionRequestJson(base, {method: 'PUT', headers, body: JSON.stringify({...draft, status: 'adopted', expected_revision: state.saved.definition.revision, expected_trial: state.trial})});
      if (!owns()) return;
      state.pendingAdoption = null;
      state.adopted = result.definition;
      state.saved = {definition: result.definition, fingerprint};
    }
    if (owns()) analysisExecutionSetDialogMessage('');
  } catch (error) {
    if (!owns()) return;
    if (action === 'adopt' && adoptionSubmitted) {
      state.operation = null;
      document.querySelector('#analysis-definition-confirm').checked = false;
      await analysisMeasurementInspect();
    } else if (action === 'save' && !state.saved && !state.touched.has('id')
        && (error.code === 'revision_conflict' || error.status === 409)) {
      document.querySelector('#analysis-definition-id').value = analysisMeasurementNewIdentity();
      if (!state.touched.has('output')) document.querySelector('#analysis-definition-output').value = document.querySelector('#analysis-definition-id').value;
      state.trial = null;state.operation = null;
      analysisMeasurementRender();
      analysisExecutionUpdatePlanSummary({preserveMessage:true});
      analysisExecutionSetDialogMessage('生成IDが既存の定義と重なりました。別の下書きIDを用意しました。内容を確認して保存してください。', true);
    } else analysisExecutionSetDialogMessage(error.message, true);
  } finally {
    // A reopened dialog still displays this same operation's busy state.
    // Release its controls without accepting the retired opening's result.
    const refresh = state === analysisMeasurement && state.operation === token
      && analysisMeasurementCurrent() && analysisRunDialog?.open;
    if (state.operation === token) state.operation = null;
    token.finish();
    if (refresh) { analysisMeasurementRender(); analysisExecutionUpdatePlanSummary({preserveMessage: true}); }
  }
}

function analysisExecutionDefinitionFromForm(status = 'draft') {
  const preset = analysisMeasurementPreset();
  return {
    definition_id: document.querySelector('#analysis-definition-id')?.value.trim() || '',
    name: document.querySelector('#analysis-definition-name')?.value.trim() || '',
    description: document.querySelector('#analysis-definition-description')?.value.trim() || '',
    unit_of_analysis: 'segment', source_columns: [preset.source], aggregation: 'none', missing_rule: 'null_with_reason', denominator: 'all_included_segments',
    output_column: document.querySelector('#analysis-definition-output')?.value.trim() || '',
    data_type: preset.type, measurement_level: preset.level, measurement_rule: preset.rule, method: preset.method,
    status
  };
}

function analysisExecutionSyncManualFields() {
  const manual = analysisExecutionMode() === 'manual';
  const editor = document.querySelector('#analysis-manual-definition');
  const option = document.querySelector('[data-analysis-run-option="manual_measurement"] input');
  if (editor) editor.hidden = !manual;
  if (option) {
    option.checked = manual;
    option.disabled = !manual;
  }
  const preset = document.querySelector('#analysis-run-preset-field');
  if (preset) preset.hidden = manual;
}

function analysisExecutionValidatePlan() {
  if (!analysisState.itemId || !analysisState.data) return '先に分析対象を読み込んでください。';
  if (hasUnsavedAnalysisChanges()) return '未保存の分析設定・手動コード・準備記録があります。保存してから実行してください。';
  if (typeof isAnalysisOrchestrationActive === 'function' && isAnalysisOrchestrationActive()) return '自律分析の実行または開始確認中です。保存済み実行の状態を確認してください。';
  if (analysisExecutionMode() !== 'manual') return '';
  const error = analysisExecutionValidateDefinition();
  if (error) return error;
  if (!analysisMeasurementCurrent() || !analysisMeasurement.adopted || !analysisMeasurement.trial
      || analysisMeasurement.saved?.fingerprint !== analysisMeasurementFingerprint()) return '下書きを保存し、少数試行を確認して採用してから全件分析を開始してください。';
  return '';
}

function analysisExecutionValidateDefinition() {
  if (!analysisState.itemId || !analysisState.data || hasUnsavedAnalysisChanges()) return '対象の分析設定・準備記録を保存してください。';
  const value = analysisExecutionDefinitionFromForm();
  if (!value.name) return '手動実行ではラベル名を入力してください。';
  if (!/^[A-Za-z][A-Za-z0-9_-]{2,63}$/.test(value.definition_id)) return '定義IDは英字で始まる3〜64文字の英数字・_・-です。';
  if (!value.description) return '測定方法を入力してください。';
  if (!/^[A-Za-z][A-Za-z0-9_]{1,62}$/.test(value.output_column)) return '生成する列は英字で始まる英数字・_です。';
  if (value.method === 'descriptive' && !['interval', 'ratio'].includes(value.measurement_level)) {
    return '名義・順序尺度には度数集計を選んでください。平均へ自動置換しません。';
  }
  return '';
}

function analysisExecutionUpdatePlanSummary(options = {}) {
  analysisExecutionSyncManualFields();
  const manual = analysisExecutionMode() === 'manual';
  const summary = document.querySelector('#analysis-run-plan-summary');
  if (summary) {
    summary.replaceChildren();
    const strong = document.createElement('strong');
    strong.textContent = 'M0〜M7の固定計画：';
    summary.append(strong, document.createTextNode(
      manual
        ? '手入力定義を少数試行 → 採用版をM4で固定 → 既存2手法と全件測定 ／ 基礎分析の実行は外部送信なし'
        : '既存の発話量・会話時間構造をM2で並列実行 ／ 基礎分析の実行は外部送信なし'
    ));
    if (analysisPlanningProposal && analysisPlanningItemId === analysisState.itemId) {
      summary.append(document.createTextNode(` ／ O01の優先確認: ${analysisPlanningProposal.primary_method === 'participation' ? '発話量・参加バランス' : '会話の時間構造'}`));
    }
  }
  const error = analysisExecutionValidatePlan();
  if (!options.preserveMessage) analysisExecutionSetDialogMessage(error, Boolean(error));
  if (analysisRunStartButton) analysisRunStartButton.disabled = Boolean(error || analysisStartOwner);
}

function openAnalysisExecutionDialog(options = {}) {
  if (!analysisRunDialog || typeof analysisRunDialog.showModal !== 'function') return;
  if (typeof isAnalysisOrchestrationActive === 'function' && isAnalysisOrchestrationActive()) { showAnalysisOrchestration(); return; }
  if (analysisExecutionState.active) {
    showAnalysisExecutionView();
    return;
  }
  invalidateAnalysisDialog();
  if (!analysisMeasurementCurrent() && !analysisMeasurementRefreshContext()) analysisMeasurementReset();
  if (document.querySelector('#analysis-definition-confirm')) document.querySelector('#analysis-definition-confirm').checked = false;
  analysisMeasurementRender();
  analysisExecutionSyncDisplay();
  const requestedMode = options.mode === 'manual' ? 'manual' : 'automatic';
  if (analysisPlanningItemId && analysisPlanningItemId !== analysisState.itemId) {
    analysisPlanningProposal = null;
    analysisPlanningItemId = '';
    if (analysisAdvisorResult) analysisAdvisorResult.replaceChildren();
  }
  if (analysisAdvisorItemId !== analysisState.itemId) {
    analysisAdvisorItemId = analysisState.itemId;
    analysisAdvisorClearProposal();
    if (analysisAdvisorObjective) analysisAdvisorObjective.value = String(analysisState.config?.research_question || '').slice(0, 500);
  }
  const mode = document.querySelector(`input[name="analysis_run_mode"][value="${requestedMode}"]`);
  if (mode) mode.checked = true;
  const details = document.querySelector('#analysis-run-details');
  if (details) details.open = Boolean(options.showDetails || requestedMode === 'manual');
  analysisExecutionUpdatePlanSummary();
  if (!analysisRunDialog.open) analysisRunDialog.showModal();
  if (analysisMeasurement?.pendingAdoption) analysisMeasurementInspect();
  window.requestAnimationFrame(() => document.querySelector('input[name="analysis_run_mode"]:checked')?.focus());
}

function analysisAdvisorClearProposal() {
  ++analysisAdvisorGeneration;
  ++analysisPlanGeneration;
  if (analysisAdvisorProposeButton) analysisAdvisorProposeButton.disabled = false;
  analysisPlanningProposal = null;
  analysisPlanningItemId = '';
  if (analysisAdvisorFlow) { analysisAdvisorFlow.hidden = true; analysisAdvisorFlow.replaceChildren(); }
  if (analysisAdvisorResult) analysisAdvisorResult.replaceChildren();
  analysisExecutionUpdatePlanSummary();
}

function analysisProcessProviderLabel(provider) {
  return {transformer: 'Transformer（このPC）', local_transformer: 'Transformer（このPC）', lmstudio: 'LM Studio（このPC）',
    openai: 'OpenAI', google: 'Gemini'}[provider] || provider || '選択したモデル';
}

function analysisProcessMethodLabel(method) {
  return method === 'participation' ? '発話量・参加バランス'
    : method === 'conversation_dynamics' ? '会話の時間構造' : '確認待ち';
}

function analysisProcessObjectiveTerms(objective) {
  const value = String(objective || '').trim();
  if (!value) return [];
  const words = typeof Intl.Segmenter === 'function'
    ? [...new Intl.Segmenter('ja', {granularity: 'word'}).segment(value)]
      .filter(part => part.isWordLike).map(part => part.segment)
    : value.split(/[\s、，。,.]+/);
  const terms = [...new Set(words.filter(word => word.length >= 2))].slice(0, 3);
  return terms.length ? terms : [value.slice(0, 20)];
}

function renderAnalysisAdvisorFlow({state, objective, provider, model = '', proposal = null}) {
  if (!analysisAdvisorFlow) return;
  analysisAdvisorFlow.hidden = false;
  const completed = state === 'complete';
  const failed = state === 'failed';
  analysisAdvisorFlow.replaceChildren(buildAnalysisProcessFlow({
    title: completed ? 'O01 計画候補を検証しました' : failed ? 'O01 計画候補を生成できませんでした' : 'O01 計画候補を生成中',
    note: '線の動きはAPI要求の状態です。モデル内部の単語間計算は表示しません。',
    nodes: [
      {id: 'input', kind: '入力', label: '分析目的・集計条件', detail: String(objective).slice(0, 70),
        terms: analysisProcessObjectiveTerms(objective), state: 'complete'},
      {id: 'model', kind: '選択したモデル', label: analysisProcessProviderLabel(provider),
        detail: model || '設定済みモデルを使用', state: completed ? 'complete' : failed ? 'failed' : 'running'},
      {id: 'validation', kind: '照合', label: '実行可能な手法を確認',
        detail: '既存の2手法と確認事項', state: completed ? 'complete' : 'pending'},
      {id: 'proposal', kind: '候補', label: completed ? analysisProcessMethodLabel(proposal?.primary_method) : '応答待ち',
        detail: completed ? '優先して確認する手法' : '', state: completed ? 'complete' : 'pending'}
    ]
  }));
}

function analysisAdvisorSyncEngine() {
  if (analysisAdvisorModelField) analysisAdvisorModelField.hidden = analysisAdvisorEngine?.value === 'transformer';
  analysisAdvisorClearProposal();
}

async function analysisAdvisorPropose() {
  if (!analysisState.itemId || !analysisState.data) {
    analysisExecutionSetDialogMessage('先に分析対象を読み込んでください。', true);
    return;
  }
  if (hasUnsavedAnalysisChanges()) {
    analysisExecutionSetDialogMessage('分析設定を保存してから計画候補を生成してください。', true);
    return;
  }
  const objective = analysisAdvisorObjective?.value.trim() || '';
  if (objective.length < 3 || objective.length > 500) {
    analysisExecutionSetDialogMessage('分析目的を3〜500文字で入力してください。', true);
    analysisAdvisorObjective?.focus();
    return;
  }
  const selected = analysisAdvisorEngine?.value || 'transformer';
  const selectedModel = analysisAdvisorModel?.value.trim() || '';
  const cloud = selected === 'openai' || selected === 'google';
  const item = analysisState.data.item;
  const requestedItemId = analysisState.itemId;
  analysisAdvisorClearProposal();
  const dialog = captureAnalysisDialog();
  const owner = ++analysisAdvisorGeneration;
  const owns = () => dialog.current() && owner === analysisAdvisorGeneration;
  renderAnalysisAdvisorFlow({state: 'running', objective, provider: selected, model: selectedModel});
  if (analysisAdvisorProposeButton) analysisAdvisorProposeButton.disabled = true;
  analysisExecutionSetDialogMessage('計画候補を生成しています。');
  try {
    const response = await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(requestedItemId)}/analysis/plans/proposals`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        source_revision: item.revision_count, analysis_revision: item.analysis_revision,
        objective, engine: selected === 'transformer' ? 'transformer' : 'llm',
        provider: selected === 'transformer' ? undefined : selected,
        model: selected === 'transformer' ? undefined : selectedModel,
        provider_policy: cloud ? 'cloud_allowed' : 'local_only'
      })
    });
    if (!owns() || analysisState.itemId !== requestedItemId || analysisAdvisorEngine?.value !== selected
        || analysisAdvisorObjective?.value.trim() !== objective
        || (selected !== 'transformer' && (analysisAdvisorModel?.value.trim() || '') !== selectedModel)) return;
    analysisPlanningProposal = response.proposal;
    analysisPlanningItemId = requestedItemId;
    const proposal = analysisPlanningProposal;
    renderAnalysisAdvisorFlow({state: 'complete', objective, provider: proposal.provider,
      model: proposal.model, proposal});
    const label = proposal.primary_method === 'participation' ? '発話量・参加バランス' : '会話の時間構造';
    if (analysisAdvisorResult) {
      analysisAdvisorResult.replaceChildren();
      const lead = document.createElement('p');
      lead.textContent = `優先して確認: ${label}（${proposal.provider} / ${proposal.model}）`;
      const reason = document.createElement('p');
      reason.textContent = proposal.rationale;
      analysisAdvisorResult.append(lead, reason);
      for (const check of proposal.checks) {
        const line = document.createElement('p');
        line.textContent = `確認: ${check.message}`;
        analysisAdvisorResult.append(line);
      }
    }
    analysisExecutionUpdatePlanSummary();
    analysisExecutionSetDialogMessage('計画候補を確認しました。開始すると既存2手法を実行し、候補を実行記録へ残します。');
  } catch (error) {
    if (!owns()) return;
    renderAnalysisAdvisorFlow({state: 'failed', objective, provider: selected, model: selectedModel});
    analysisExecutionSetDialogMessage(error.message || '計画候補を生成できませんでした。', true);
  } finally {
    if (owns() && analysisAdvisorProposeButton) analysisAdvisorProposeButton.disabled = false;
  }
}

function analysisExecutionPersist() {
  const value = {
    id: analysisExecutionState.id, itemId: analysisExecutionState.itemId,
    itemName: analysisExecutionState.itemName, mode: analysisExecutionState.mode,
    startedAt: analysisExecutionState.startedAt
  };
  try { sessionStorage.setItem(analysisExecutionStorageKey, JSON.stringify(value)); } catch (_) { /* memory only */ }
}

function analysisExecutionRestore() {
  let stored = null;
  try { stored = JSON.parse(sessionStorage.getItem(analysisExecutionStorageKey) || 'null'); } catch (_) { /* unavailable */ }
  if (!stored?.id || !stored?.itemId) return false;
  Object.assign(analysisExecutionState, stored, {status: 'accepted', active: true, restored: true});
  return true;
}

function analysisExecutionClearPersisted() {
  try { sessionStorage.removeItem(analysisExecutionStorageKey); } catch (_) { /* unavailable */ }
}

function analysisExecutionLogFromEvents(events) {
  const labels = {
    pipeline_accepted: '実行計画を受け付けました。', pipeline_running: '固定計画の実行を開始しました。',
    milestone_started: '段階を開始', milestone_committed: '段階を確定',
    milestone_waiting: '段階を停止', cancel_requested: '取消を要求しました。',
    pipeline_cancelled: '分析を中止しました。', retry_accepted: '失敗した処理の再試行を受け付けました。',
    process_restart: 'アプリの再起動により中断しました。', resume_accepted: '固定入力からの再開を受け付けました。',
    pipeline_completed: '全成果物と公開状態を確定しました。', pipeline_failed: 'pipelineが停止しました。'
  };
  return (events || []).filter(event => event.type !== 'state_transition').map(event => {
    const time = new Date(event.created_at).toLocaleTimeString('ja-JP', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
    const milestone = event.payload?.milestone ? ` ${event.payload.milestone}` : '';
    return `${time}  ${labels[event.type] || event.type}${milestone}`;
  });
}

function analysisExecutionApplyResponse(response) {
  if (response.pipeline_id && response.pipeline_id !== analysisExecutionState.id) return;
  analysisExecutionState.generation = response.generation ?? analysisExecutionState.generation;
  analysisExecutionState.status = response.status;
  analysisExecutionState.active = ['accepted', 'running', 'waiting', 'cancelling'].includes(response.status)
    && Boolean(response.allowed_actions?.length);
  analysisExecutionState.currentIndex = Math.max(0, analysisExecutionStageDefinitions.findIndex(
    value => value.id === response.current_milestone
  ));
  analysisExecutionState.stages = (response.milestones || []).map(value => ({
    id: value.id,
    label: value.id,
    title: analysisExecutionStageDefinitions.find(stage => stage.id === value.id)?.title || value.id,
    status: value.status,
    steps: value.steps || []
  }));
  analysisExecutionState.settings = {
    ...(analysisExecutionState.settings || {}), progress: response.progress,
    planning: response.planning || null,
    publications: response.publications || [], allowedActions: response.allowed_actions || [],
    recovery: response.recovery || null,
    error: response.error || '', waitReason: response.wait_reason || '', resultRun: response.result_run
  };
  analysisExecutionState.logs = analysisExecutionLogFromEvents(response.events);
  analysisExecutionState.cancelRequested = response.status === 'cancelling';
  if (['completed', 'cancelled', 'failed'].includes(response.status)) analysisExecutionClearPersisted();
  else analysisExecutionPersist();
  renderAnalysisExecution();
}

function analysisExecutionStatusLabel(status) {
  return {
    idle: '開始準備', accepted: '受付済み', running: '実行中', cancelling: '中止待ち', completed: '処理完了', pending: '待機', active: '実行中', waiting: '入力・回復待ち', committed: '完了',
    failed: '失敗', cancelled: '取消', not_applicable: '対象外', reused: '再利用'
  }[status] || `不明な状態 (${status || '未取得'})`;
}

function analysisExecutionPercent() {
  if (Number.isFinite(analysisExecutionState.settings?.progress)) return analysisExecutionState.settings.progress;
  if (!analysisExecutionState.stages.length) return 0;
  return Math.round(100 * analysisExecutionState.stages.filter(value => value.status === 'committed').length
    / analysisExecutionState.stages.length);
}

function analysisExecutionElapsedText() {
  const seconds = Math.max(0, Math.floor((Date.now() - Number(analysisExecutionState.startedAt || Date.now())) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

function renderAnalysisExecutionFlow(current) {
  const host = document.querySelector('#analysis-execution-flow');
  if (!host) return;
  const planning = analysisExecutionState.settings?.planning;
  const running = ['accepted', 'running', 'cancelling'].includes(analysisExecutionState.status);
  const done = analysisExecutionState.status === 'completed';
  const index = analysisExecutionState.currentIndex;
  const signature = JSON.stringify([planning, analysisExecutionState.status, index,
    current?.id, current?.title]);
  if (host.dataset.flowSignature === signature) return;
  host.dataset.flowSignature = signature;
  host.replaceChildren();
  if (planning) host.append(buildAnalysisProcessFlow({
    title: 'O01 モデルによる計画判断',
    note: '候補生成時に完了。現在の分析段階ではこのモデルを呼び出していません。',
    nodes: [
      {id: 'objective', kind: '入力', label: '分析目的', detail: String(planning.objective || '').slice(0, 70),
        terms: analysisProcessObjectiveTerms(planning.objective), state: 'complete'},
      {id: 'advisor', kind: '使用したモデル', label: analysisProcessProviderLabel(planning.provider),
        detail: planning.model || '', state: 'complete'},
      {id: 'candidate', kind: '確認順', label: analysisProcessMethodLabel(planning.primary_method),
        detail: '実行計画に記録済み', state: 'complete'}
    ]
  }));
  const phaseState = (first, last) => done || index > last ? 'complete'
    : running && index >= first && index <= last ? 'running' : 'pending';
  host.append(buildAnalysisProcessFlow({
    title: '現在の分析処理',
    note: `${current?.id || 'M0'} ${current?.title || '入力確認'} ／ サーバーの段階状態と連動`,
    nodes: [
      {id: 'source', kind: 'M0–M1', label: '発話・話者・時刻', detail: '入力と範囲を固定',
        terms: ['発話', '話者', '時刻'], state: phaseState(0, 1)},
      {id: 'methods', kind: 'M2–M4', label: '既存手法・定義', detail: '発話量と会話の時間構造',
        terms: ['参加', '交替'], state: phaseState(2, 4)},
      {id: 'package', kind: 'M5–M7', label: '結果の保存・公開', detail: '根拠と成果物を確定',
        state: phaseState(5, 7)},
      {id: 'result', kind: '結果', label: done ? '分析完了' : '結果待ち', detail: '',
        state: done ? 'complete' : 'pending'}
    ]
  }));
}

function analysisExecutionPublicationEvidence() {
  const settings = analysisExecutionState.settings || {};
  const attempts = settings.resultRun?.publication_attempts || [];
  const latest = attempts.at(-1);
  const roles = ['research', 'input', 'orchestrator', 'visualization'];
  const records = Object.fromEntries((settings.publications || []).map(row => [row.target_role, row]));
  const notSelected = roles.every(role => records[role]?.status === 'not_selected');
  const blocked = latest?.status === 'blocked' && Array.isArray(latest.executed) && latest.executed.length === 0;
  const complete = latest?.status === 'completed' && roles.every(role => latest.effective?.includes(role)
    && latest.executed?.includes(role) && latest.outcomes?.[role]?.status === 'published' && records[role]?.status === 'published');
  return {attempts, latest, roles, records, notSelected, blocked, complete};
}
function analysisExecutionRetryAction() {
  const settings = analysisExecutionState.settings || {};
  if (settings.recovery?.mode === 'blocked' || analysisExecutionPublicationEvidence().blocked) return '';
  return ['resume', 'retry_publication', 'retry_failed'].find(action => settings.allowedActions?.includes(action)) || '';
}
function analysisExecutionHeadline() {
  return {idle: '分析の開始準備', accepted: '分析を受け付けました', running: '分析を実行しています',
    waiting: '分析は確認・回復を待っています', failed: '分析が失敗しました',
    cancelling: '分析の中止を待っています', cancelled: '分析を中止しました', completed: '分析処理が完了しました'}[analysisExecutionState.status]
    || `分析状態を確認できません（${analysisExecutionState.status || '不明'}）`;
}
function renderAnalysisPublicationEvidence() {
  const host = document.querySelector('#analysis-execution-publications');
  if (!host) return;
  host.replaceChildren();
  const evidence = analysisExecutionPublicationEvidence();
  const heading = document.createElement('p');
  heading.textContent = evidence.notSelected ? 'Vault保存は選択されていません。本体成果物のみが対象です。'
    : evidence.blocked ? '保存済み固定packageの欠落・不整合により公開を停止しました。再計算や再生成で置き換えません。'
      : evidence.complete ? '4つのVaultへの書出し成功を今回の試行記録で確認しました。'
        : evidence.latest ? 'Vault保存は未完了です。保存先ごとの結果を確認してください。' : '4保存先の実行記録は不明です。旧履歴や記録未取得を保存成功とは判定しません。';
  host.append(heading);
  const list = document.createElement('ul');
  const names = {research:'ResearchVault', input:'InputVault', orchestrator:'OrchestratorVault', visualization:'VisualizationVault'};
  const statuses = {published:'書出し成功',publishing:'書出し中',not_selected:'対象外',pending:'待機',failed:'失敗',conflict:'競合',unknown:'不明',missing:'欠落',blocked:'停止'};
  for (const role of evidence.roles) {
    const record = evidence.records[role], outcome = evidence.latest?.outcomes?.[role];
    const state = record?.status || 'unknown';
    const row = document.createElement('li');
    const hasExecutionRecord = Array.isArray(evidence.latest?.executed);
    const executed = hasExecutionRecord ? (evidence.latest.executed.includes(role) ? '今回のwriter実行あり' : '今回のwriter実行なし') : 'writer実行記録不明';
    const writerConfirmed = hasExecutionRecord && evidence.latest.executed.includes(role) && outcome?.status === 'published';
    const label = state === 'published' && !writerConfirmed ? '台帳上published（書出し未確認）' : statuses[state] || `不明な状態 (${state})`;
    row.textContent = `${names[role]}: ${label} / ${executed}${record?.error || outcome?.error ? ` / ${record?.error || outcome?.error}` : ''}`;
    list.append(row);
  }
  host.append(list);
  if (evidence.latest) { const note = document.createElement('p');note.textContent = `公開試行 ${evidence.latest.attempt_id} / 状態 ${evidence.latest.status} / package ${evidence.latest.package_hash || '不明'}`;host.append(note); }
  const recovery = analysisExecutionState.settings?.recovery;
  if (recovery?.mode === 'blocked' || recovery?.pending) {
    const note = document.createElement('p');note.textContent = recovery.mode === 'blocked'
      ? `再開できません（${recovery.reason_code || '理由未取得'}）。確定済みの成果物を保持しています。新しい分析を開始してください。`
      : 'アプリの再起動により中断しました。「固定入力から分析を再開」で続けられます。確定済みの成果物を保持しています。';host.append(note);
  }
}

function renderAnalysisExecution() {
  if (analysisState.itemId === analysisExecutionState.itemId && analysisExecutionView && !analysisExecutionView.hidden) analysisExecutionSetWorkspaceVisibility(true);
  const stagesHost = document.querySelector('#analysis-execution-stages');
  if (stagesHost) {
    stagesHost.replaceChildren();
    analysisExecutionState.stages.forEach(stage => {
      const item = document.createElement('li');
      const css = stage.status === 'committed' ? 'completed'
        : stage.status === 'active' ? 'running'
          : stage.status === 'pending' ? 'skipped' : stage.status;
      item.className = `analysis-execution-stage ${css}`;
      item.dataset.executionStage = stage.id;
      const strong = document.createElement('strong'); strong.textContent = `${stage.id} ${stage.title}`;
      const small = document.createElement('small'); small.textContent = analysisExecutionStatusLabel(stage.status);
      item.append(strong, small);
      (stage.steps || []).filter(step => step.status === 'reused').forEach(step => {
        const reused = document.createElement('small');
        reused.dataset.reusedStep = step.step_id;
        const sourceTime = step.reused_at && new Date(step.reused_at);
        reused.textContent = `${analysisProcessMethodLabel(step.step_id)}：再利用（元の実行 ${sourceTime && Number.isFinite(sourceTime.getTime()) ? sourceTime.toLocaleString('ja-JP') : '日時不明'}）`;
        item.append(reused);
      });
      stagesHost.append(item);
    });
  }
  const percent = analysisExecutionPercent();
  const percentText = document.querySelector('#analysis-execution-percent');
  const track = document.querySelector('#analysis-execution-track');
  if (percentText) percentText.textContent = `${percent}%`;
  if (track) {
    track.setAttribute('aria-valuenow', String(percent));
    const bar = track.querySelector('i'); if (bar) bar.style.width = `${percent}%`;
  }
  const current = analysisExecutionState.stages[analysisExecutionState.currentIndex]
    || analysisExecutionState.stages.find(value => ['failed', 'waiting', 'cancelled'].includes(value.status))
    || analysisExecutionState.stages.at(-1);
  renderAnalysisExecutionFlow(current);
  const stateLabel = document.querySelector('#analysis-execution-state-label');
  const title = document.querySelector('#analysis-execution-current-title');
  const message = document.querySelector('#analysis-execution-message');
  if (stateLabel) stateLabel.textContent = current ? `${current.id} ${analysisExecutionStatusLabel(current.status)}` : '開始準備';
  if (title) title.textContent = current?.title || '入力と設定を確認しています';
  if (message) {
    const failed = current?.steps?.find(value => value.error);
    const publications = analysisExecutionState.settings?.publications || [];
    const publicationFailure = publications.find(value => !['published', 'not_selected', 'pending'].includes(value.status));
    message.textContent = failed?.error || publicationFailure?.error || analysisExecutionState.settings?.error
      || (analysisExecutionState.status === 'completed' ? '本体の分析処理が完了しました。Vault保存の確認は下の実行記録を参照してください。' : analysisExecutionState.status === 'waiting' ? '停止理由と利用可能な操作を確認してください。' : analysisExecutionHeadline());
  }
  const heading = document.querySelector('#analysis-execution-title');
  if (heading) heading.textContent = analysisExecutionHeadline();
  renderAnalysisPublicationEvidence();
  const summary = document.querySelector('#analysis-execution-summary');
  if (summary) summary.textContent = 'M0〜M7をサーバー側の永続ゲートで管理します。完了済み成果物は再試行時も保持されます。';
  const elapsed = document.querySelector('#analysis-execution-elapsed');
  const mode = document.querySelector('#analysis-execution-mode');
  const external = document.querySelector('#analysis-execution-external');
  if (elapsed) elapsed.textContent = analysisExecutionElapsedText();
  if (mode) mode.textContent = analysisExecutionState.mode === 'manual' ? '手入力定義' : '自動計画';
  if (external) {
    const provider = analysisExecutionState.settings?.planning?.provider;
    external.textContent = ['openai', 'google'].includes(provider)
      ? `計画時: ${analysisProcessProviderLabel(provider)} ／ 実行中: なし` : 'なし（ローカル）';
  }
  const log = document.querySelector('#analysis-execution-log');
  if (log) log.textContent = analysisExecutionState.logs.join('\n');
  const orbit = document.querySelector('#analysis-execution-orbit');
  if (orbit) orbit.classList.toggle('is-idle', !analysisExecutionState.active);
  const cancel = document.querySelector('#analysis-execution-cancel');
  const results = document.querySelector('#analysis-execution-results');
  const review = document.querySelector('#analysis-execution-review');
  const background = document.querySelector('#analysis-execution-background');
  if (background) background.textContent = analysisExecutionState.settings?.recovery?.pending
    ? '分析の画面に戻る' : 'バックグラウンドで続ける';
  if (cancel) {
    cancel.hidden = !analysisExecutionState.settings?.allowedActions?.includes('cancel');
    cancel.disabled = analysisExecutionState.cancelRequested;
    cancel.textContent = analysisExecutionState.cancelRequested ? '中止を待っています…' : '分析を中止';
  }
  if (results) results.hidden = !analysisExecutionState.settings?.resultRun?.id
    || analysisExecutionState.settings.resultRun.status !== 'completed';
  if (review) {
    const action = analysisExecutionRetryAction();
    review.hidden = !action;
    review.disabled = analysisRunOperations.has('retry');
    review.textContent = action === 'resume' ? '固定入力から分析を再開'
      : action === 'retry_publication' ? '保存済みpackageから4保存先への公開だけ再試行' : '失敗した処理を再試行';
  }
  if (analysisRunButton) analysisRunButton.textContent = analysisExecutionState.active ? '実行状況を見る' : '分析を実行';
  if (analysisExecutionChip) {
    analysisExecutionChip.hidden = analysisExecutionState.status === 'idle';
    analysisExecutionChip.classList.toggle('is-active', analysisExecutionState.active);
    analysisExecutionChip.classList.toggle('is-complete', analysisExecutionState.status === 'completed');
    analysisExecutionChip.classList.toggle('has-error', ['waiting', 'failed'].includes(analysisExecutionState.status));
  }
  if (analysisExecutionChipLabel) analysisExecutionChipLabel.textContent = analysisExecutionState.active
    ? `${current?.id || 'M0'} ${analysisExecutionStatusLabel(analysisExecutionState.status)}` : analysisExecutionStatusLabel(analysisExecutionState.status);
}

function analysisExecutionSetWorkspaceVisibility(showExecution) {
  if (analysisExecutionView) analysisExecutionView.hidden = !showExecution;
  const shell = document.querySelector('#analysis-shell');
  const empty = document.querySelector('#analysis-empty');
  const loading = document.querySelector('#analysis-loading');
  const comparison = document.querySelector('#interview-comparison-details');
  if (showExecution) {
    if (shell) shell.hidden = true;
    if (empty) empty.hidden = true;
    if (loading) loading.hidden = true;
    if (comparison) comparison.hidden = true;
  } else {
    if (shell) shell.hidden = !analysisState.data;
    if (empty) empty.hidden = Boolean(analysisState.data);
    if (loading) loading.hidden = true;
    if (comparison) comparison.hidden = false;
  }
}

function showAnalysisExecutionView({updateRoute = true} = {}) {
  if (!analysisExecutionState.itemId) return;
  if (analysisState.itemId !== analysisExecutionState.itemId || analysisCard?.hidden) {
    showView('analysis', {analysisItemId: analysisExecutionState.itemId});
  }
  analysisExecutionSetWorkspaceVisibility(true);
  renderAnalysisExecution();
  if (updateRoute) syncRouteHash(`${routeHash('analysis', analysisExecutionState.itemId)}/run`);
  if (analysisExecutionState.id && ['accepted', 'running', 'waiting', 'cancelling'].includes(analysisExecutionState.status)) {
    analysisExecutionPoll();
  }
}

function hideAnalysisExecutionView({updateRoute = true} = {}) {
  analysisExecutionSetWorkspaceVisibility(false);
  if (analysisState.data) renderAnalysisWorkspace();
  if (updateRoute && analysisExecutionState.itemId) syncRouteHash(routeHash('analysis', analysisExecutionState.itemId));
}

async function analysisExecutionRequestJson(input, options = {}) {
  const response = await apiFetch(input, options);
  const data = await readJsonResponse(response);
  if (!response.ok) { const error = new Error(data.error || `HTTP ${response.status}`); error.status = response.status;error.code = data.reason_code || data.code;throw error; }
  return data;
}

async function analysisExecutionPoll() {
  if (!analysisExecutionState.id || analysisRunOperations.has('poll')) return;
  const request = captureAnalysisRun('poll');
  try {
    const data = await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(request.itemId)}/analysis/pipelines/${encodeURIComponent(request.id)}`);
    if (!request.current()) return;
    analysisExecutionApplyResponse(data);
  } catch (error) {
    if (!request.current()) return;
    analysisExecutionState.logs.push(`状態取得失敗：${error.message}`);
    renderAnalysisExecution();
  } finally { request.release(); }
  if (request.id === analysisExecutionState.id && request.itemId === analysisExecutionState.itemId
      && ['accepted', 'running', 'cancelling'].includes(analysisExecutionState.status)) {
    window.clearTimeout(analysisExecutionState.pollTimer);
    analysisExecutionState.pollTimer = window.setTimeout(analysisExecutionPoll, 350);
  }
}

async function analysisExecutionPrepareDefinition() {
  if (analysisExecutionMode() !== 'manual') return [];
  if (analysisExecutionValidatePlan()) throw new Error(analysisExecutionValidatePlan());
  return [analysisMeasurement.adopted.definition_id];
}

async function startAnalysisExecution(event) {
  event?.preventDefault();
  if (analysisStartOwner) return;
  analysisExecutionUpdatePlanSummary();
  if (analysisExecutionValidatePlan()) return;
  const dialog = captureAnalysisDialog();
  const token = {}; analysisStartOwner = token;
  const planGeneration = analysisPlanGeneration;
  const owns = () => analysisStartOwner === token && dialog.current() && planGeneration === analysisPlanGeneration;
  const itemId = dialog.context.itemId, item = dialog.context.data.item;
  const payload = {
    request_id: typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : createSubmissionId(),
    source_revision: item.revision_count, analysis_revision: item.analysis_revision,
    mode: analysisExecutionMode(), definition_ids: [],
    provider_policy: ['openai', 'google'].includes(analysisPlanningProposal?.provider) ? 'cloud_allowed' : 'local_only',
    ...(analysisPlanningProposal && analysisPlanningItemId === itemId ? {planning_proposal: structuredClone(analysisPlanningProposal)} : {}),
    publication_targets: document.querySelector('#analysis-run-publish')?.checked ? ['input', 'orchestrator', 'visualization'] : [],
    research_protocol: {classification: 'exploratory', data_viewed: true}
  };
  if (analysisRunStartButton) analysisRunStartButton.disabled = true;
  try {
    payload.definition_ids = await analysisExecutionPrepareDefinition();
    if (!owns()) return;
    if (payload.mode === 'manual') {
      payload.expected_definition_versions = {[analysisMeasurement.adopted.definition_id]: analysisMeasurement.adopted.version};
      payload.expected_input_hash = analysisMeasurement.trial.input_hash;
      payload.source_revision = analysisMeasurement.trial.source_revision;
      payload.analysis_revision = analysisMeasurement.trial.analysis_revision;
    }
    if (!owns()) return;
    await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(itemId)}/analysis/plans/preview`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    if (!owns()) return;
    const response = await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(itemId)}/analysis/pipelines`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    // A submitted request remains owned by A even if its dialog has since closed.
    ++analysisRunOwner; analysisRunOperations.clear();
    Object.assign(analysisExecutionState, {id: response.pipeline_id, itemId,
      itemName: item.source_name || '分析対象', mode: payload.mode, startedAt: Date.now(), restored: false, generation: response.generation ?? 0});
    analysisExecutionApplyResponse(response);
    if (owns()) { closeAnalysisExecutionDialog(); showAnalysisExecutionView(); }
    else analysisExecutionPoll();
  } catch (error) {
    if (owns()) analysisExecutionSetDialogMessage(error.message || '分析計画を開始できませんでした。', true);
  } finally {
    if (analysisStartOwner === token) analysisStartOwner = null;
    if (dialog.current() && analysisRunStartButton) analysisRunStartButton.disabled = Boolean(analysisExecutionValidatePlan());
  }
}

async function cancelAnalysisExecution() {
  if (!analysisExecutionState.active || analysisExecutionState.cancelRequested) return;
  if (!window.confirm('現在の分析を中止しますか？ 完了済みの結果は保持されます。')) return;
  analysisExecutionState.cancelRequested = true;
  renderAnalysisExecution();
  const request = captureAnalysisRun('cancel');
  try {
    const response = await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(request.itemId)}/analysis/pipelines/${encodeURIComponent(request.id)}/cancel`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'
    });
    if (!request.current()) return;
    ++analysisRunOwner; analysisRunOperations.clear();
    analysisExecutionApplyResponse(response);
    analysisExecutionPoll();
  } catch (error) {
    if (!request.current()) return;
    analysisExecutionState.cancelRequested = false;
    analysisExecutionState.logs.push(`中止要求失敗：${error.message}`);
    renderAnalysisExecution();
  } finally { request.release(); }
}

async function analysisExecutionReviewPlan() {
  const retry = analysisExecutionRetryAction();
  if (!retry || analysisRunOperations.has('retry')) return;
  const request = captureAnalysisRun('retry');
  try {
    renderAnalysisExecution();
    const response = await analysisExecutionRequestJson(`/api/library/${encodeURIComponent(request.itemId)}/analysis/pipelines/${encodeURIComponent(request.id)}/${retry === 'resume' ? 'resume' : 'retry'}`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'
    });
    if (!request.current()) return;
    ++analysisRunOwner; analysisRunOperations.clear();
    analysisExecutionApplyResponse(response);
    analysisExecutionPoll();
  } catch (error) {
    if (!request.current()) return;
    analysisExecutionState.logs.push(`${retry === 'resume' ? '再開' : '再試行'}失敗：${error.message}`);
    renderAnalysisExecution();
  } finally {
    const current = request.current();
    request.release();
    if (current) renderAnalysisExecution();
  }
}

async function analysisExecutionOpenResults() {
  const context = captureAnalysisContext(), request = captureAnalysisRun('results');
  const runId = analysisExecutionState.settings?.resultRun?.id;
  try {
    if (!runId || analysisExecutionState.settings?.resultRun?.status !== 'completed' || !request.itemId || !request.current() || !isAnalysisContextCurrent(context)) return;
    if (typeof openFixedAnalysisRun === 'function') await openFixedAnalysisRun(request.itemId, runId);
  } finally { request.release(); }
}

function analysisExecutionBind() {
  listen(analysisRunButton, 'click', () => analysisExecutionState.active ? showAnalysisExecutionView() : openAnalysisExecutionDialog());
  listen(analysisRunSettingsButton, 'click', () => openAnalysisExecutionDialog({mode: 'manual', showDetails: true}));
  listen(document.querySelector('#close-analysis-run-dialog'), 'click', closeAnalysisExecutionDialog);
  listen(analysisRunDialog, 'close', () => { if (!analysisRunDialog.open) invalidateAnalysisDialog(); });
  listen(analysisRunDialog, 'cancel', invalidateAnalysisDialog);
  listen(analysisRunForm, 'submit', startAnalysisExecution);
  for (const action of ['save', 'trial', 'adopt']) listen(document.querySelector(`#analysis-definition-${action}`), 'click', () => analysisMeasurementAction(action));
  listen(document.querySelector('#analysis-definition-confirm'), 'change', analysisMeasurementRender);
  listen(document.querySelector('#analysis-definition-inspect'), 'click', analysisMeasurementInspect);
  document.querySelectorAll('#analysis-manual-definition input:not([type="checkbox"]), #analysis-definition-preset').forEach(control => listen(control, 'input', analysisMeasurementInvalidate));
  document.querySelectorAll('input[name="analysis_display_mode"]').forEach(control => listen(control, 'change', analysisExecutionSyncDisplay));
  listen(analysisAdvisorProposeButton, 'click', analysisAdvisorPropose);
  listen(analysisAdvisorEngine, 'change', analysisAdvisorSyncEngine);
  listen(analysisAdvisorObjective, 'input', analysisAdvisorClearProposal);
  listen(analysisAdvisorModel, 'input', analysisAdvisorClearProposal);
  document.querySelectorAll('input[name="analysis_run_mode"], #analysis-manual-definition input, #analysis-manual-definition select, #analysis-run-publish')
    .forEach(control => listen(control, 'input', () => { ++analysisPlanGeneration; analysisExecutionUpdatePlanSummary(); }));
  listen(document.querySelector('#analysis-execution-background'), 'click', () => hideAnalysisExecutionView());
  listen(document.querySelector('#analysis-execution-results'), 'click', analysisExecutionOpenResults);
  listen(document.querySelector('#analysis-execution-review'), 'click', analysisExecutionReviewPlan);
  listen(document.querySelector('#analysis-execution-cancel'), 'click', cancelAnalysisExecution);
  listen(analysisExecutionChip, 'click', showAnalysisExecutionView);
  window.addEventListener('popstate', () => window.setTimeout(() => {
    const wantsRun = /#\/analysis\/[^/]+\/run$/.test(window.location.hash);
    if (wantsRun && analysisExecutionState.itemId) showAnalysisExecutionView({updateRoute: false});
    else if (analysisExecutionView && !analysisExecutionView.hidden) hideAnalysisExecutionView({updateRoute: false});
  }, 0));
}

window.addEventListener('DOMContentLoaded', () => {
  analysisExecutionBind();
  analysisExecutionRestore();
  renderAnalysisExecution();
  if (analysisExecutionElapsedTimer !== null) window.clearInterval(analysisExecutionElapsedTimer);
  analysisExecutionElapsedTimer = window.setInterval(() => {
    if (analysisExecutionState.status !== 'idle') renderAnalysisExecution();
  }, 1000);
  if (analysisExecutionState.restored) analysisExecutionPoll();
  if (/#\/analysis\/[^/]+\/run$/.test(window.location.hash) && analysisExecutionState.itemId) {
    showAnalysisExecutionView({updateRoute: false});
  }
});
