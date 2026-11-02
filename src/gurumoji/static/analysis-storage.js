/* Saved analysis packages are separate from live computation and researcher notes. */
const analysisStorageStates = new Map();
let analysisLinkedItemApplied = false;
let analysisLinkedEvidenceApplied = false;

function analysisStorageState() {
  const key = analysisState.itemId;
  if (!analysisStorageStates.has(key)) analysisStorageStates.set(key, {runs: [], busy: false, error: '', sequence: 0, pending: null, pagination: null});
  return analysisStorageStates.get(key);
}

function buildAnalysisStorage({readOnly = false} = {}) {
  const panel = analysisCardPanel('分析を保存して読み返す', 'automatic', '', true);
  panel.panel.classList.add('analysis-storage');
  panel.body.append(analysisElement('p', 'analysis-caption',
    readOnly ? '保存済みの結果は、現在の会話を再分析せずに読み返せます。'
      : '見解・原文へのリンクを分析用Vaultに、全件データと条件をCSV／JSONに保存します。過去の結果も読み返せます。'));
  const button = contentButton('分析結果をObsidianに保存', () => saveAnalysisPackage(), 'primary-button small');
  button.dataset.archiveSave = 'true';
  const reload = contentButton('保存履歴を更新', () => loadAnalysisStorage());
  const more = contentButton('さらに前の履歴を表示', () => loadAnalysisStorage(true));
  more.dataset.archiveMore = 'true'; more.hidden = true;
  const bar = analysisElement('div', 'content-ai-toolbar');
  if (!readOnly) bar.append(button);
  bar.append(reload, more);
  const status = analysisElement('p', 'content-ai-status'); status.dataset.archiveStatus = 'true'; status.setAttribute('role', 'status');
  const history = analysisElement('div'); history.dataset.archiveHistory = 'true';
  const lookup = analysisElement('form', 'analysis-fixed-lookup');
  const label = analysisElement('label', '', 'run IDで過去の保存結果を開く');
  const input = analysisElement('input'); input.type = 'text'; input.required = true; input.maxLength = 100;
  label.append(input); const open = analysisElement('button', 'secondary-button compact-button', '保存済みrunを開く'); open.type = 'submit';
  lookup.append(label, open);
  lookup.addEventListener('submit', event => { event.preventDefault(); openFixedAnalysisRun(analysisState.itemId, input.value.trim()); });
  panel.body.append(bar, status, history, lookup);
  return panel.panel;
}

// History metadata is data, not a trusted navigation destination.
function savedAnalysisObsidianUri(value) {
  if (typeof value !== 'string' || value !== value.trim() || /[\u0000-\u001f\u007f]/.test(value)
      || /%(?![0-9a-f]{2})/i.test(value)) return '';
  try {
    const uri = new URL(value);
    const entries = [...uri.searchParams];
    if (uri.protocol !== 'obsidian:' || uri.host !== 'open' || uri.username || uri.password
        || uri.pathname || uri.hash || entries.length !== 1 || entries[0][0] !== 'path') return '';
    decodeURIComponent(uri.search); // Reject malformed encoded text rather than repairing it.
    const path = entries[0][1];
    return path.trim() && !/[\u0000-\u001f\u007f]/.test(path) ? value : '';
  } catch (_) { return ''; }
}

function savedAnalysisArtifactUrl(id) {
  if (typeof id !== 'string' || !id || id !== id.trim() || id === '.' || id === '..'
      || /[\u0000-\u001f\u007f]/.test(id)) return '';
  try { return `/api/analysis/artifacts/${encodeURIComponent(id)}`; }
  catch (_) { return ''; }
}

function refreshAnalysisStorage() {
  if (!analysisState.data) return;
  const state = analysisStorageState();
  document.querySelectorAll('[data-archive-more]').forEach(button => {
    button.hidden = !state.pagination?.has_more;
    button.disabled = state.busy;
  });
  document.querySelectorAll('[data-archive-save], [data-archive-kwic]').forEach(button => {
    button.disabled = Boolean(state.busy || analysisState.dirty || analysisSaveInProgress);
  });
  document.querySelectorAll('[data-archive-status]').forEach(host => {
    host.textContent = state.busy ? '分析結果とVaultを保存しています…'
      : analysisState.dirty ? '設定・コードを保存してから分析結果を保存してください。'
      : state.error || `${state.runs.length}件の保存履歴 / AI仕上げ・AI見解は成功時に自動で記録します。`;
  });
  document.querySelectorAll('[data-archive-history]').forEach(host => {
    const key = JSON.stringify(state.runs.map(r => [r.id, r.status, r.vault_status, r.stale, r.error, r.vault_outputs, r.publication_attempts, r.publication_records, r.kind, r.created_at, r.obsidian_uri, r.artifacts]));
    if (host.dataset.renderKey === key) return;
    host.dataset.renderKey = key; host.replaceChildren();
    const labels = {__proto__: null, text_analysis: '文章分析', ai_insights: 'AI見解', ai_finishing: 'AI仕上げ', kwic: '文脈検索'};
    state.runs.forEach(run => {
      const details = analysisElement('details', 'analysis-archive-run');
      const summary = analysisElement('summary', '', `${labels[run.kind] || run.kind} / ${formatDate(run.created_at)}${run.stale ? ' / 現在入力は保存時と異なります' : ''}`);
      const body = analysisElement('div', 'analysis-archive-body');
      body.append(analysisElement('p', 'analysis-caption', `元データ ${run.source_revision}版 / 分析 ${run.analysis_revision}版${run.model ? ` / ${run.model}` : ''}`));
      if (run.error) body.append(analysisElement('p', 'content-inline-notice', run.error));
      body.append(analysisElement('p', 'analysis-caption', `固定run ${run.id} / 本体保存: ${run.status}`));
      body.append(buildSavedPublicationEvidence(run));
      body.append(contentButton('この保存済み結果を読む', () => openFixedAnalysisRun(run.item_id, run.id)));
      if (run.obsidian_uri) {
        const uri = savedAnalysisObsidianUri(run.obsidian_uri);
        if (uri) {
          const open = analysisElement('a', 'secondary-button compact-button', 'Obsidianで開く');
          open.href = uri; body.append(open);
        } else body.append(analysisElement('p', 'content-inline-notice', 'Obsidianのリンクを確認できません。'));
      }
      if (analysisSavedPublicationEvidence(run).retryable) {
        body.append(contentButton('保存時の範囲でVault書出しを再試行', () => retrySavedVault(run.id)));
      }
      const files = analysisElement('div', 'analysis-archive-files');
      if (run.status === 'completed') {
        const bundle = analysisElement('a', 'analysis-export-link', 'export.zip');
        bundle.href = `/api/analysis/runs/${encodeURIComponent(run.id)}/export.zip`;
        bundle.download = '';
        files.append(bundle);
        for (const format of ['xlsx', 'sav']) {
          const link = analysisElement('a', 'analysis-export-link', format === 'sav' ? 'SAV＋型付きJSON（ZIP）' : 'Excel');
          link.href = `/api/analysis/runs/${encodeURIComponent(run.id)}/export.${format}`;
          link.download = ''; files.append(link);
        }
      }
      (run.artifacts || []).forEach(artifact => {
        const url = savedAnalysisArtifactUrl(artifact.id);
        if (url) {
          const link = analysisElement('a', 'analysis-export-link', artifact.name);
          link.href = url; link.download = ''; files.append(link);
        } else files.append(analysisElement('span', 'content-inline-notice', `${artifact.name || '保存ファイル'}: ファイルIDを確認できないためダウンロードできません。`));
      });
      body.append(files); details.append(summary, body); host.append(details);
    });
  });
}

async function loadAnalysisStorage(append = false) {
  if (!analysisState.data) return;
  const itemId = analysisState.itemId;
  const state = analysisStorageState(); const sequence = ++state.sequence;
  const context = captureAnalysisContext();
  try {
    const offset = append ? state.runs.length : 0;
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/runs?limit=100&offset=${offset}`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '保存履歴を取得できませんでした。');
    if (sequence !== state.sequence) return;
    state.error = '';
    const rows = data.runs || [];
    state.runs = append ? [...new Map([...state.runs, ...rows].map(run => [run.id, run])).values()] : rows;
    state.pagination = data.pagination || null;
  } catch (error) { if (sequence === state.sequence) state.error = error.message; }
  if (isAnalysisContextCurrent(context)) refreshAnalysisStorage();
}

async function saveAnalysisPackage(kwic = null) {
  if (!analysisState.data || analysisState.dirty || analysisSaveInProgress) return;
  const itemId = analysisState.itemId;
  const state = analysisStorageState();
  if (state.busy) return;
  const item = analysisState.data.item;
  const identity = JSON.stringify([itemId, item.revision_count, item.analysis_revision, kwic]);
  const storageKey = `gurumoji.analysisSave.${itemId}`;
  let pending = state.pending;
  try { pending = JSON.parse(sessionStorage.getItem(storageKey) || 'null') || pending; } catch (_) { /* optional storage */ }
  if (!pending || pending.identity !== identity) pending = {identity, request_id: crypto.randomUUID()};
  state.pending = pending; state.busy = true; state.error = ''; refreshAnalysisStorage();
  try { sessionStorage.setItem(storageKey, JSON.stringify(pending)); } catch (_) { /* keep in memory */ }
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/runs`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
        request_id: pending.request_id, source_revision: item.revision_count,
        analysis_revision: item.analysis_revision, ...(kwic ? {kwic} : {})
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '分析結果を保存できませんでした。');
    state.pending = null;
    try { sessionStorage.removeItem(storageKey); } catch (_) { /* optional storage */ }
    state.error = generatedVaultProblems(data.run) + vaultNotesMessage(data.run);
  } catch (error) { state.error = error.message; }
  finally {
    state.busy = false;
    if (itemId === analysisState.itemId) { await loadAnalysisStorage(); refreshAnalysisStorage(); }
  }
}

// OBS-04: say which researcher-touched notes the shared Vault note policy handled.
function vaultNotesMessage(run) {
  const notes = run && run.vault_notes && typeof run.vault_notes === 'object' ? run.vault_notes : {};
  const count = key => (Array.isArray(notes[key]) ? notes[key].length : 0);
  const parts = [];
  if (count('edit_saved')) parts.push(`Obsidianで編集されていたノート${count('edit_saved')}件は、編集した版を履歴に保存してから最新版に更新しました。`);
  if (count('missing')) parts.push(`削除されていたノート${count('missing')}件は作り直していません。`);
  return parts.length ? ` ${parts.join(' ')}詳しくはResearchVaultの「90-運用/同期状況」を確認してください。` : '';
}

// Publication is separate from immutable package storage; legacy flags are not evidence.
function analysisSavedPublicationEvidence(run) {
  const roles = ['research', 'input', 'orchestrator', 'visualization'];
  const latest = run?.publication_attempts?.at(-1);
  const records = Object.fromEntries((run?.publication_records || []).map(row => [row.target_role, row]));
  const requested = latest?.requested, effective = latest?.effective;
  const validRequested = Array.isArray(requested) && (requested.length === 0
    || (requested.length === 3 && ['input','orchestrator','visualization'].every(role => requested.includes(role))));
  const scopeKnown = validRequested && Array.isArray(effective);
  const samePackage = typeof run?.fingerprint === 'string' && run.fingerprint.length > 0
    && latest?.package_hash === run.fingerprint;
  const scopeEmpty = Array.isArray(run?.saved_publication_targets) && run.saved_publication_targets.length === 0;
  const recordedNotSelected = !latest && Boolean(run?.id && run?.fingerprint) && roles.every(role => records[role]?.status === 'not_selected'
    && records[role]?.result_run_id === run?.id && records[role]?.package_hash === run?.fingerprint);
  const notSelected = (!latest && scopeEmpty) || recordedNotSelected || (samePackage && scopeKnown
    && latest.requested.length === 0 && latest.effective.length === 0
    && latest.status === 'not_selected' && latest.executed?.length === 0);
  const confirmed = role => samePackage
    && latest?.effective?.includes(role) && latest?.executed?.includes(role)
    && latest?.outcomes?.[role]?.status === 'published';
  const complete = run?.status === 'completed' && scopeKnown && requested.length === 3 && effective.length === 4
    && latest.executed?.length === 4 && latest.status === 'completed' && roles.every(confirmed);
  const workflowDisagrees = Boolean(latest) && Object.keys(records).length > 0 && roles.some(role =>
    records[role]?.status !== latest?.outcomes?.[role]?.status || records[role]?.result_run_id !== run.id
    || records[role]?.package_hash !== run.fingerprint);
  const blocked = latest?.status === 'blocked';
  const retryable = run?.status === 'completed' && samePackage && scopeKnown && latest.requested.length > 0
    && !complete && !blocked && latest.status !== 'publishing';
  return {roles, latest, records, scopeKnown, notSelected, confirmed, complete, workflowDisagrees, recordedNotSelected, scopeEmpty, blocked, retryable};
}

function generatedVaultProblems(run) {
  const evidence = analysisSavedPublicationEvidence(run);
  const saved = run?.status === 'completed' ? '本体の保存記録があります。' : '本体の保存は未完了です。';
  return saved + (evidence.notSelected ? (evidence.recordedNotSelected && !evidence.scopeEmpty ? '台帳上、Vault書出しは対象外です。公開試行の記録はありません。' : '保存時の範囲ではVault書出しは対象外です。')
    : evidence.complete ? '4つのVaultへの書出しを今回の実行記録で確認しました。'
    : evidence.blocked ? '固定packageの不整合によりVault書出しを停止しました。再試行はできません。'
    : evidence.latest ? 'Vault書出しは未完了または未確認です。4保存先の記録を確認してください。'
    : 'Vault書出しの実行記録がなく、成功を確認できません。');
}

function buildSavedPublicationEvidence(run) {
  const evidence = analysisSavedPublicationEvidence(run);
  const host = analysisElement('div', 'analysis-saved-publication');
  host.append(analysisElement('p', 'analysis-caption', generatedVaultProblems(run)));
  const details = analysisElement('details');
  details.append(analysisElement('summary', '', '4保存先の実行記録'));
  const names = {research:'ResearchVault', input:'InputVault', orchestrator:'OrchestratorVault', visualization:'VisualizationVault'};
  const labels = {__proto__: null, published:'published（成功未確認）', not_selected:'対象外', pending:'待機', failed:'失敗', conflict:'競合', unknown:'不明', missing:'欠落', publishing:'実行中'};
  const list = analysisElement('ul');
  for (const role of evidence.roles) {
    const outcome = evidence.latest?.outcomes?.[role];
    const executed = Array.isArray(evidence.latest?.executed)
      ? evidence.latest.executed.includes(role) ? 'writer実行あり' : 'writer実行なし' : 'writer実行不明';
    const label = evidence.confirmed(role) ? '書出し成功' : evidence.notSelected ? '対象外' : labels[outcome?.status] || (outcome?.status ? `不明（${outcome.status}）` : '不明');
    const record = evidence.records[role];
    list.append(analysisElement('li', '', `${names[role]}: ${label} / ${executed}`
      + (record ? ` / 台帳: ${record.status}` : '') + (outcome?.error ? ` / ${outcome.error}` : '')));
  }
  details.append(list);
  if (evidence.workflowDisagrees) details.append(analysisElement('p', 'content-inline-notice', '最新の書出し試行とpipeline台帳の状態が一致していません。writerの実行結果と処理進行の台帳を分けて表示しています。台帳を自動で修復しません。'));
  const show = value => Array.isArray(value) ? value.length ? value.join(', ') : 'なし' : '不明';
  details.append(analysisElement('p', 'analysis-caption',
    `要求: ${show(evidence.latest?.requested)} / 実効範囲: ${show(evidence.latest?.effective)} / 実行: ${show(evidence.latest?.executed)}`));
  if (evidence.latest) details.append(analysisElement('p', 'analysis-caption',
    `試行 ${evidence.latest.attempt_id} / ${evidence.latest.status} / package ${evidence.latest.package_hash || '不明'}`));
  host.append(details); return host;
}

async function retrySavedVault(runId) {
  const itemId = analysisState.itemId;
  const state = analysisStorageState();
  if (state.busy || !analysisSavedPublicationEvidence(state.runs.find(run => run.id === runId)).retryable) return;
  state.busy = true; state.error = ''; refreshAnalysisStorage();
  try {
    const response = await apiFetch(`/api/analysis/runs/${encodeURIComponent(runId)}/vault`, {method: 'POST'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'Vaultを保存できませんでした。');
    state.error = generatedVaultProblems(data.run) + vaultNotesMessage(data.run);
  } catch (error) { state.error = error.message; }
  finally {
    state.busy = false;
    if (itemId === analysisState.itemId) { await loadAnalysisStorage(); refreshAnalysisStorage(); }
  }
}

async function openLinkedAnalysisEvidence() {
  if (analysisLinkedEvidenceApplied || !analysisState.data) return;
  const params = new URLSearchParams(location.search);
  const sid = params.get('segment');
  if (!sid || params.get('item') !== analysisState.itemId) return;
  analysisLinkedEvidenceApplied = true;
  const itemId = analysisState.itemId;
  const segment = analysisState.data.segments.find(s => s.id === sid);
  if (!segment) { setAlert(document.querySelector('#analysis-message'), '引用された発話は現在のデータにはありません。Vaultの保存済み原文を確認してください。', true); return; }
  if (params.get('text_hash')) {
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(segment.text))), b => b.toString(16).padStart(2, '0')).join('');
    if (analysisState.itemId !== itemId) return;
    if (hash !== params.get('text_hash') || Math.abs(Number(params.get('start')) - segment.start) > .001
      || Math.abs(Number(params.get('end')) - segment.end) > .001 || params.get('speaker') !== segment.speaker) {
      setAlert(document.querySelector('#analysis-message'), '引用の保存後に発話が更新されています。過去の原文はVaultで確認できます。現在の発話は分析画面から確認してください。', true);
      return;
    }
  }
  await openInsightMedia(segment);
}

// One read-only modal owns its item/run, navigation generation and request tokens.
// It never invokes live analysis, pipeline status/recovery or publication.
let analysisFixedViewer = null;
let analysisFixedViewerGeneration = 0;
function analysisFixedViewerElements() {
  if (analysisFixedViewer) return analysisFixedViewer;
  const dialog = analysisElement('dialog', 'app-dialog analysis-fixed-dialog');
  dialog.setAttribute('aria-labelledby', 'analysis-fixed-title');
  const header = analysisElement('div', 'analysis-fixed-header');
  const title = analysisElement('h2', '', '保存済み結果'); title.id = 'analysis-fixed-title';
  const close = contentButton('閉じる', () => closeFixedAnalysisViewer());
  const identity = analysisElement('p', 'analysis-caption');
  const status = analysisElement('p', 'content-ai-status'); status.setAttribute('role', 'status');
  const body = analysisElement('div', 'analysis-fixed-body');
  header.append(title, close, identity, status); dialog.append(header, body);
  dialog.addEventListener('close', () => { if (!dialog.open) ++analysisFixedViewerGeneration; });
  dialog.addEventListener('cancel', () => { ++analysisFixedViewerGeneration; });
  document.body.append(dialog);
  analysisFixedViewer = {dialog, identity, status, body, close};
  return analysisFixedViewer;
}

function closeFixedAnalysisViewer() {
  // Invalidate synchronously: native close events may arrive after another open.
  ++analysisFixedViewerGeneration;
  if (!analysisFixedViewer?.dialog.open) return false;
  analysisFixedViewer.dialog.close();
  analysisFixedViewer.body.replaceChildren();
  return true;
}

async function openFixedAnalysisRun(itemId, runId) {
  if (!itemId || !runId) return;
  const context = captureAnalysisContext();
  const elements = analysisFixedViewerElements();
  const owner = ++analysisFixedViewerGeneration;
  // The immutable run belongs to this navigation, not the live editor's data object.
  const current = () => owner === analysisFixedViewerGeneration && elements.dialog.open
    && context.itemId === analysisState.itemId && context.navigation === analysisNavigationGeneration;
  elements.identity.textContent = `会話 ${itemId} / 固定run ${runId}`;
  elements.status.textContent = '保存済みpackageを検証しています…';
  elements.body.replaceChildren();
  if (!elements.dialog.open) elements.dialog.showModal();
  elements.close.focus();
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/runs/${encodeURIComponent(runId)}`, {cache:'no-store'});
    const data = await readJsonResponse(response);
    if (!current()) return;
    if (!response.ok) throw new Error(data.error || '保存済み結果を読み取れません。');
    if (data.run?.id !== runId || data.run?.item_id !== itemId || !['verified','missing_reference'].includes(data.integrity)) throw new Error('保存結果の対象または完全性を確認できません。');
    elements.status.textContent = data.integrity === 'verified' ? '保存済みの結果を開きました。'
      : '保存した参照先を確認しています。';
    renderFixedAnalysisRun(elements.body, data, {itemId, runId, current, status:elements.status});
  } catch (error) {
    if (current()) { elements.status.textContent = error.message; elements.body.replaceChildren(); }
  }
}

function renderFixedAnalysisRun(host, data, owner) {
  const run = data.run, unknown = value => value === null || value === undefined || value === '' ? '不明' : String(value);
  if (data.integrity === 'missing_reference') {
    host.append(analysisElement('p', 'content-inline-notice', data.recovery_status === 'rebuilding'
      ? '参照先の行を作り直しています…' : data.error || '参照先の行がありません（作り直しても一致しません）。'));
    if (data.recovery_status === 'rebuilding') setTimeout(async () => {
      if (!owner.current()) return;
      try {
        const response = await apiFetch(`/api/library/${encodeURIComponent(owner.itemId)}/analysis/runs/${encodeURIComponent(owner.runId)}`, {cache:'no-store'});
        const next = await readJsonResponse(response);
        if (!owner.current()) return;
        if (!response.ok || next.run?.id !== owner.runId || next.run?.item_id !== owner.itemId
          || !['verified','missing_reference'].includes(next.integrity)) throw new Error('復旧した参照の対象が一致しません。');
        if (owner.status && next.integrity === 'verified') owner.status.textContent = '参照先を復旧し、保存したhashとの一致を確認しました。';
        host.replaceChildren(); renderFixedAnalysisRun(host, next, owner);
      } catch (_) { if (owner.current()) host.append(analysisElement('p', 'content-inline-notice', '復旧状態を取得できません。')); }
    }, 1000);
    return;
  }
  host.append(analysisElement('p', '', `保存日時 ${unknown(run.created_at)} / 元データ ${unknown(run.source_revision)}版 / 分析 ${unknown(run.analysis_revision)}版`));
  host.append(analysisElement('p', 'analysis-caption', typeof data.current_input?.stale !== 'boolean'
    ? '取得時点の入力比較が不明なため、現在入力との一致は確認できません。' : data.current_input?.stale
    ? '取得時点の現在入力は保存時と異なります。ここでは保存済みの本文・話者・role・時刻だけを表示します。'
    : '取得時点では保存済み入力と一致しています。現在の編集内容を保存行へ補っていません。'));
  host.append(buildSavedPublicationEvidence(run));
  host.append(buildFixedAnalysisSummary(data.saved_summary));
  const provenance = analysisElement('details');
  provenance.append(analysisElement('summary', '', '保存した入力版・条件・来歴'));
  provenance.append(analysisElement('p', 'analysis-caption', '保存ファイルのhashと構成を確認しました。科学的妥当性や研究者の確認を示すものではありません。'));
  const fields = [['input fingerprint',data.provenance?.input_fingerprint],['snapshot ID',data.provenance?.input_snapshot_id],
    ['package fingerprint',data.provenance?.fingerprint],['保存形式',data.provenance?.schema_version],['手法registry版',data.provenance?.method_version]];
  for (const [label,value] of fields) provenance.append(analysisElement('p','analysis-caption',`${label}: ${unknown(value)}`));
  provenance.append(analysisElement('p','analysis-caption','保存時の定義版・条件はparameters.json、本文・話者などの来歴はinput.json、測定結果はresult.jsonまたは保存表で確認できます。未記録の値は不明です。'));
  host.append(provenance);
  host.append(buildFixedStatisticsTools(owner, run));
  const download = analysisElement('a', 'analysis-export-link', 'このrunの全ファイルをZIPでダウンロード');
  download.href = `/api/analysis/runs/${encodeURIComponent(owner.runId)}/export.zip`; download.download = '';
  host.append(download, analysisElement('p', 'analysis-caption', 'ダウンロードは保存済み全件です。previewの範囲や現在のfilterでは縮めません。'));
  const files = analysisElement('div', 'analysis-fixed-files');
  const preview = analysisElement('section', 'analysis-fixed-preview'); preview.setAttribute('aria-label', '保存ファイルのpreview');
  const artifacts = run.artifacts || [];
  let page = 0, previewSequence = 0;
  const showPreview = async artifact => {
    if (!owner.current()) return;
    const sequence = ++previewSequence;
    preview.replaceChildren(analysisElement('p', '', `${artifact.name} を読み取っています…`));
    try {
      const response = await apiFetch(`/api/library/${encodeURIComponent(owner.itemId)}/analysis/runs/${encodeURIComponent(owner.runId)}/previews/${encodeURIComponent(artifact.id)}`, {cache:'no-store'});
      const result = await readJsonResponse(response);
      if (!owner.current() || sequence !== previewSequence) return;
      if (!response.ok) throw new Error(result.error || 'previewを読み取れません。');
      if (result.preview?.run_id !== owner.runId || result.preview?.artifact_id !== artifact.id) throw new Error('previewの対象が一致しません。');
      renderFixedAnalysisPreview(preview, artifact, result.preview);
    } catch (error) {
      if (owner.current() && sequence === previewSequence) preview.replaceChildren(analysisElement('p', 'content-inline-notice', error.message));
    }
  };
  const showFiles = () => {
    const heading = analysisElement('h3', '', '保存ファイル'); heading.tabIndex = -1;
    files.replaceChildren(heading);
    const begin = page * 20;
    files.append(analysisElement('p', 'analysis-caption', `全${artifacts.length}ファイル / ${artifacts.length ? begin + 1 : 0}–${Math.min(begin+20,artifacts.length)}件を表示`));
    for (const artifact of artifacts.slice(begin, begin + 20)) {
      const row = analysisElement('div', 'analysis-fixed-file');
      row.append(contentButton(`${artifact.name} を読む`, () => showPreview(artifact)));
      const link = analysisElement('a', 'analysis-export-link', '全件ダウンロード');
      const table = /^tables\/([a-z_]+)\.csv$/.exec(artifact.name);
      const generated = table && artifact.id === `${owner.runId}.${table[1]}`;
      if (table) {
        for (const format of ['svg', 'png']) {
          const image = analysisElement('a', 'analysis-export-link', format.toUpperCase());
          image.href = `/api/analysis/runs/${encodeURIComponent(owner.runId)}/export.${format}?dataset=${encodeURIComponent(table[1])}`;
          image.download = ''; row.append(image);
        }
      }
      link.href = generated
        ? `/api/analysis/runs/${encodeURIComponent(owner.runId)}/tables/${table[1]}.csv`
        : `/api/analysis/artifacts/${encodeURIComponent(artifact.id)}`; link.download = '';
      row.append(link, analysisElement('p', 'analysis-caption', `${generated ? '取得時に生成' : unknown(artifact.bytes) + ' bytes'} / 全件数 ${unknown(artifact.rows)} / ID ${artifact.id} / ${generated ? '行hash' : 'sha256'} ${unknown(artifact.sha256)}`));
      files.append(row);
    }
    const previous = contentButton('前のファイル', () => { if (!owner.current()) return; --page; showFiles(); files.querySelector('h3')?.focus(); }); previous.disabled = page === 0;
    const next = contentButton('次のファイル', () => { if (!owner.current()) return; ++page; showFiles(); files.querySelector('h3')?.focus(); }); next.disabled = begin + 20 >= artifacts.length;
    if (artifacts.length > 20) files.append(previous, next);
  };
  const inspector = analysisElement('details'); inspector.append(analysisElement('summary', '', '全ファイル・JSONの詳細'));
  showFiles(); inspector.append(files); host.append(preview, inspector);
  const initial = artifacts.find(artifact => artifact.name === 'tables/measurements.csv')
    || artifacts.find(artifact => artifact.media_type === 'text/csv' || artifact.name.endsWith('.csv'));
  if (initial) showPreview(initial);
}

function buildFixedStatisticsTools(owner, run) {
  const panel = analysisElement('details');
  panel.append(analysisElement('summary', '', '保存した表から統計を実行する'));
  const form = analysisElement('form', 'analysis-config-grid');
  const controls = {};
  const field = (key, label, element) => {
    const host = analysisElement('label', 'field'); host.append(analysisElement('span', '', label), element);
    controls[key] = element; form.append(host); return element;
  };
  const select = (key, label, values) => {
    const control = analysisElement('select');
    for (const [value, title] of values) {
      const option = analysisElement('option', '', title); option.value = value; control.append(option);
    }
    return field(key, label, control);
  };
  const names = [...new Set((run.artifacts || []).map(a => /^tables\/([a-z_]+)\.csv$/.exec(a.name)?.[1]).filter(Boolean))];
  const dataset = select('dataset', '固定データ表', names.map(name => [name, name]));
  select('outcome', '目的変数', []);
  select('predictor', '説明変数（相関・回帰）', [['', '指定なし']]);
  select('group', '群・条件', [['', '指定なし']]);
  select('unit_column', '話者・参加者を識別する列', [['', '指定なし']]);
  select('pair', '対応ID', [['', '指定なし']]);
  select('method', '手法', [['auto','尺度とデザインから選択'],['descriptive','記述統計'],['welch','Welchのt検定'],
    ['mann_whitney','Mann–Whitney'],['welch_anova','Welchの分散分析'],['kruskal','Kruskal–Wallis'],
    ['paired_t','対応t検定'],['wilcoxon','Wilcoxon'],['repeated_anova','反復測定（GG補正）'],['friedman','Friedman'],
    ['chi_square','カイ二乗・Fisher'],['pearson','Pearson相関'],['spearman','Spearman相関'],['kendall','Kendall相関'],
    ['linear','線形回帰（HC3）'],['logistic','二値ロジスティック回帰'],['gee_binary','二値GEE'],['gee_count','計数GEE'],['mixed_linear','線形混合モデル']]);
  select('cluster', 'クラスターID', [['','指定なし']]);
  select('analysis_unit', '分析単位', [['speaker','話者'],['participant','参加者'],['conversation','会話'],['row','独立した行'],['utterance','発話（対応手法のみ）']]);
  select('correction', '多重比較補正', [['holm','Holm'],['fdr_bh','Benjamini–Hochberg'],['none','補正なし（探索）']]);
  const confirm = field('confirmed', '尺度・分析単位・変数の出所を確認しました', analysisElement('input'));
  confirm.type = 'checkbox'; confirm.required = true;
  const variableFields = analysisElement('div'); form.append(variableFields);
  let definitions = new Map(), generation = 0, columnTypes = new Map();
  const selectedColumns = () => [...new Set(['outcome','predictor','group','unit_column','pair','cluster'].map(key=>controls[key].value).filter(Boolean))];
  const drawDefinitions = () => {
    variableFields.replaceChildren(); confirm.checked = false;
    for (const column of selectedColumns()) {
      const definition = definitions.get(column) || {column,measurement_level:'nominal',source:'',validation_status:'unvalidated',definition_version:1};
      definitions.set(column,definition);
      const group = analysisElement('fieldset'); group.append(analysisElement('legend','',`変数：${column}`));
      for (const [key,label,choices] of [
        ['measurement_level','尺度',[['nominal','名義'],['ordinal','順序'],['interval','間隔'],['ratio','比率']]],
        ['source','値の出所',[['','選択してください'],['researcher','研究者の記録'],['rule','規則・集計'],['ai','AI生成']]],
        ['validation_status','検証状態',[['unvalidated','未検証'],['reviewed','研究者が内容確認'],['validated','妥当性検証済み']]]]) {
        const labelNode=analysisElement('label','field'); labelNode.append(analysisElement('span','',label));
        const control=analysisElement('select'); control.required=true;
        for(const [value,title] of choices) {const option=analysisElement('option','',title); option.value=value; control.append(option);}
        control.value=definition[key]; control.addEventListener('change',()=>{definition[key]=control.value;confirm.checked=false;});
        labelNode.append(control);group.append(labelNode);
      }
      const orderLabel=analysisElement('label','field'); orderLabel.append(analysisElement('span','','順序尺度の値（小さい順に1行ずつ）'));
      const order=analysisElement('textarea'); order.rows=2; order.value=(definition.levels||[]).join('\n');
      order.addEventListener('input',()=>{const types=columnTypes.get(column)||[];const numeric=types.some(type=>['integer','number'].includes(type)) && !types.includes('string');definition.levels=order.value.split('\n').map(value=>value.trim()).filter(Boolean).map(value=>numeric ? Number(value) : value);confirm.checked=false;});
      orderLabel.append(order);group.append(orderLabel);variableFields.append(group);
    }
  };
  for(const key of ['outcome','predictor','group','unit_column','pair','cluster']) controls[key].addEventListener('change',drawDefinitions);
  const message = analysisElement('p', 'content-ai-status'); message.setAttribute('role','status');
  const button = analysisElement('button', 'primary-button small', '統計を実行して別の固定結果に保存'); button.type = 'submit';
  form.append(analysisElement('p','analysis-caption','探索的分析です。数値は分析単位ごとに平均し、欠測行を除外します。発話を独立標本として検定しません。'),button,message);
  const load = async () => {
    const sequence=++generation, datasetName=dataset.value; button.disabled=true;
    try {
      const response = await apiFetch(`/api/library/${encodeURIComponent(owner.itemId)}/analysis/runs/${encodeURIComponent(owner.runId)}/tables/${encodeURIComponent(datasetName)}/schema`);
      const data = await readJsonResponse(response);
      if (!owner.current() || sequence!==generation || dataset.value!==datasetName) return;
      if (!response.ok) throw new Error(data.error || '列を取得できません。');
      for (const key of ['outcome','predictor','group','unit_column','pair','cluster']) {
        controls[key].replaceChildren();
        for (const value of key === 'outcome' ? data.fields : ['',...data.fields]) {
          const option=analysisElement('option','',value || '指定なし'); option.value=value; controls[key].append(option);
        }
      }
      message.textContent=`全${data.row_count}行。列の意味と尺度を確認してください。`;
      columnTypes=new Map((data.columns||[]).map(column=>[column.name,column.observed_types]));
      definitions=new Map(); drawDefinitions(); button.disabled=false;
    } catch(error) {if(owner.current() && sequence===generation) message.textContent=error.message;}
  };
  dataset.addEventListener('change',load); if(names.length) load(); else button.disabled=true;
  form.addEventListener('submit',async event => {
    event.preventDefault(); if(!owner.current() || button.disabled || !confirm.checked) return;
    const plan={method:controls.method.value,outcome:controls.outcome.value,analysis_unit:controls.analysis_unit.value,
      correction:controls.correction.value,mode:'exploratory',min_n:5,predictors:controls.predictor.value ? [controls.predictor.value] : []};
    for(const key of ['group','unit_column','pair','cluster']) if(controls[key].value) plan[key]=controls[key].value;
    const columns=[...new Set([plan.outcome,...plan.predictors,...['group','unit_column','pair','cluster'].map(k=>plan[k]).filter(Boolean)])];
    const variables=columns.map(column=>({...definitions.get(column),unit:plan.analysis_unit}));
    const sequence=++generation, datasetName=dataset.value;
    button.disabled=true;
    try {
      const response=await apiFetch(`/api/library/${encodeURIComponent(owner.itemId)}/analysis/runs/${encodeURIComponent(owner.runId)}/statistics`,{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset:datasetName,variables,plan})});
      const data=await readJsonResponse(response); if(!owner.current() || sequence!==generation || dataset.value!==datasetName) return;
      if(!response.ok) throw new Error(data.error || '統計を実行できません。');
      message.textContent=data.statistics.results[0].report;
      panel.append(contentButton('保存した統計結果を開く',()=>openFixedAnalysisRun(owner.itemId,data.run.id)));
      loadAnalysisStorage();
    } catch(error) {if(owner.current() && sequence===generation) message.textContent=error.message;}
    finally {if(owner.current() && sequence===generation) button.disabled=false;}
  });
  panel.append(form); return panel;
}

function buildFixedAnalysisSummary(summary) {
  const host = analysisElement('section', 'analysis-fixed-summary');
  host.setAttribute('aria-label', '保存時の結果要約');
  host.append(analysisElement('h3', '', '保存時の結果要約'));
  const methods = summary?.methods || [];
  if (!methods.length) host.append(analysisElement('p', 'analysis-caption', 'この保存結果には表示できる要約がありません。保存表または全ファイルの詳細を確認してください。'));
  const statuses = {__proto__: null, completed:'計算済み',not_run:'未実行',failed:'失敗',partial:'一部のみ',unavailable:'利用不可',skipped:'省略'};
  const unknown = value => value === null || value === undefined || value === '' ? '不明' : String(value);
  const versionText = (value, status) => {
    if (status === 'unsupported') return '表示できない形式';
    if (status === 'missing') return '記録なし';
    if (status === 'recorded') return value === null || value === undefined || String(value).trim() === ''
      ? '省略（全ファイルで確認）' : String(value);
    // Compatibility with older summary responses: never fill from another record.
    if (value === null || value === undefined || typeof value === 'string' && !value.trim()) return '記録なし';
    return typeof value === 'string' || typeof value === 'number' && Number.isFinite(value) ? String(value) : '表示できない形式';
  };
  for (const method of methods) {
    const card = analysisElement('article', 'analysis-fixed-method');
    card.append(analysisElement('h4', '', method.title || method.method_id || '名称不明の保存手法'));
    card.append(analysisElement('p', 'analysis-caption', `保存時の状態: ${statuses[method.status] || unknown(method.status)} / 分析単位: ${unknown(method.analysis_unit)}`));
    card.append(analysisElement('p', 'analysis-caption', `保存した計算版: ${versionText(method.engine_version, method.engine_version_status)}`));
    card.append(analysisElement('p', 'analysis-caption', `手法registry版: ${versionText(method.method_version, method.method_version_status)}`));
    for (const row of method.summaries || []) card.append(analysisElement('p', '', `${row.title || '保存集計'}: ${unknown(row.text)}`));
    for (const row of method.findings || []) card.append(analysisElement('p', '', `${row.title || '保存された見解'}: ${unknown(row.text)}`));
    if (!method.summaries?.length && !method.findings?.length) card.append(analysisElement('p', 'analysis-caption', '要約本文は未記録です。保存表を確認してください。'));
    for (const note of method.limitations || []) card.append(analysisElement('p', 'content-inline-notice', `制約: ${unknown(note)}`));
    host.append(card);
  }
  const algorithms = analysisElement('section', 'analysis-fixed-algorithms');
  algorithms.append(analysisElement('h4', '', '保存した算法一覧'));
  const savedAlgorithms = Array.isArray(summary?.algorithms) ? summary.algorithms : [];
  for (const record of savedAlgorithms) algorithms.append(analysisElement('p', 'analysis-caption',
    `${record.name || '名称省略'}: ${versionText(record.version, record.status)}`));
  if (!savedAlgorithms.length) algorithms.append(analysisElement('p', 'analysis-caption', summary?.algorithms_status === 'unsupported' ? '表示できない形式' : '記録なし'));
  algorithms.append(analysisElement('p', 'analysis-caption', '手法ごとの計算版・registry版とは別の保存記録です。欠けた版を他の記録や現在の版で補っていません。'));
  host.append(algorithms);
  if (summary?.definitions?.length) {
    const definitions = analysisElement('details'); definitions.append(analysisElement('summary', '', '保存時の測定定義'));
    for (const definition of summary.definitions) definitions.append(analysisElement('p', 'analysis-caption',
      `${unknown(definition.name)} / ID ${unknown(definition.definition_id)} / ${unknown(definition.version)}版 / 列 ${unknown(definition.output_column)} / 規則 ${unknown(definition.measurement_rule)} / 手法 ${unknown(definition.method)}`));
    host.append(definitions);
  }
  if (summary?.truncated) host.append(analysisElement('p', 'content-inline-notice',
    '要約の一部を省略しています（最大12手法・各5項目・算法20件・本文16 KiB）。制約を含む全文はresult.json、条件はparameters.jsonで確認してください。'));
  host.append(analysisElement('p', 'analysis-caption', '保存時の集計・見解をそのまま表示しています。previewから新しい指標を計算していません。'));
  return host;
}

function renderFixedAnalysisPreview(host, artifact, preview) {
  host.replaceChildren(analysisElement('h3', '', `${artifact.name} / 固定run ${preview.run_id}`));
  host.append(analysisElement('p', 'analysis-caption', preview.truncated
    ? '一部を省略しています。全件はダウンロードで確認してください。省略部分から集計していません。'
    : 'このファイルのpreview範囲を表示しています。'));
  if (preview.format === 'table') {
    host.append(analysisElement('p', 'analysis-caption', `全${preview.total_rows}行中${preview.shown_rows}行 / 全${preview.total_columns}列中${preview.columns.length}列。上限20行・24列・各セル256文字・本文16 KiB。空欄はnullと空文字を区別できません。保存JSONやmissing_reason列を確認してください。`));
    const scroll = analysisElement('div', 'analysis-fixed-table'); scroll.tabIndex = 0;
    scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', `${artifact.name}の保存表`);
    const table = analysisElement('table'), head = analysisElement('thead'), line = analysisElement('tr');
    for (const field of preview.columns) { const cell = analysisElement('th', '', field); cell.scope = 'col'; line.append(cell); }
    head.append(line); table.append(head); const body = analysisElement('tbody');
    for (const row of preview.rows) { const line = analysisElement('tr'); for (const value of row) line.append(analysisElement('td', '', value)); body.append(line); }
    table.append(body); scroll.append(table); host.append(scroll);
  } else {
    host.append(analysisElement('p', 'analysis-caption', 'JSON本文は最大16 KiBの抜粋です。null・0・空文字を変換せず示します。省略時は完全なJSONではありません。'));
    host.append(analysisElement('pre', 'analysis-fixed-json', preview.text));
  }
}
