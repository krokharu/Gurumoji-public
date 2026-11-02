/* 公開版の画面処理: shared。共有状態はapp.jsで管理する。 */
let analysisEvidenceReturn = null;

let analysisFixedViewer = null;

let analysisFixedViewerGeneration = 0;

function analysisElement(tagName, className = '', textValue = '') {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (textValue !== undefined && textValue !== null && textValue !== '') {
    element.textContent = String(textValue);
  }
  return element;
}

function analysisEndpointText(value, timed, missing) {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean'
      || !Number.isFinite(Number(value)) || Number(value) < 0) {
    return missing > 0 ? `時刻不明${missing}発話` : '時刻不明';
  }
  const coverage = Number.isInteger(timed) && Number.isInteger(missing)
    ? `（時刻あり${timed}/${timed + missing}発話${missing ? `、時刻不明${missing}発話` : ''}）` : '';
  return `${formatTime(value)}${coverage}`;
}

function setAnalysisDirty(dirty, trackMutation = true) {
  analysisState.dirty = Boolean(dirty);
  if (analysisState.dirty && trackMutation) analysisMutationGeneration += 1;
  document.querySelectorAll('[data-analysis-save]').forEach(button => {
    button.disabled = !analysisState.dirty || analysisSaveInProgress;
    button.textContent = analysisSaveInProgress
      ? '保存中…'
      : analysisState.dirty ? '設定とコードを保存' : '保存済み';
  });
  document.querySelectorAll('[data-analysis-save-state]').forEach(element => {
    element.textContent = analysisState.dirty ? '未保存の変更があります' : '分析設定は保存済みです';
    element.classList.toggle('unsaved', analysisState.dirty);
  });
  const sideStatus = document.querySelector('#analysis-desktop-side-status');
  if (sideStatus) {
    sideStatus.classList.toggle('unsaved', analysisState.dirty);
    sideStatus.textContent = analysisState.dirty
      ? '設定・コードに未保存の変更があります'
      : analysisState.data ? '保存済みの分析結果を表示中' : '';
  }
  if (!ANALYSIS_COMING_SOON) refreshInsightControls();
  if (!ANALYSIS_COMING_SOON) refreshAnalysisStorage();
}

function contentButton(label, action, className = 'secondary-button compact-button') {
  const button = analysisElement('button', className, label);
  button.type = 'button';
  button.addEventListener('click', action);
  return button;
}

function analysisEvidenceTimeValid(segment) {
  return Boolean(segment && !segment.time_unknown
    && typeof segment.start === 'number' && Number.isFinite(segment.start)
    && typeof segment.end === 'number' && Number.isFinite(segment.end)
    && segment.start >= 0 && segment.end >= segment.start);
}

function returnToAnalysisEvidence() {
  if (analysisEvidenceReturn) openAnalysisForItem(analysisEvidenceReturn.itemId);
}

function closeFixedAnalysisViewer() {
  // Invalidate synchronously: native close events may arrive after another open.
  ++analysisFixedViewerGeneration;
  if (!analysisFixedViewer?.dialog.open) return false;
  analysisFixedViewer.dialog.close();
  analysisFixedViewer.body.replaceChildren();
  return true;
}

function fallbackSpeaker(label) {
  if (!label || label === 'UNKNOWN') return '話者（未判定）';
  const match = String(label).match(/_(\d+)$/);
  return match ? `話者 ${Number(match[1]) + 1}` : label;
}

function captureAnalysisContext() {
  return {itemId: analysisState.itemId, data: analysisState.data, navigation: analysisNavigationGeneration,
    mutation: analysisMutationGeneration, sourceRevision: analysisState.data?.item?.revision_count,
    analysisRevision: analysisState.data?.item?.analysis_revision};
}

function isAnalysisContextCurrent(context) {
  return context.itemId === analysisState.itemId && context.data === analysisState.data
    && context.navigation === analysisNavigationGeneration && context.mutation === analysisMutationGeneration
    && context.sourceRevision === analysisState.data?.item?.revision_count
    && context.analysisRevision === analysisState.data?.item?.analysis_revision;
}

function segmentClassificationBusy() { return segmentClassificationRequests.has(analysisState.itemId); }

function setAlert(element, message, error = false) {
  if (!element) return;
  element.setAttribute('role', error ? 'alert' : 'status');
  element.setAttribute('aria-live', error ? 'assertive' : 'polite');
  element.setAttribute('aria-atomic', 'true');
  element.textContent = message || '';
  element.hidden = !message;
  element.classList.toggle('error', error);
}

function listen(element, eventName, handler) {
  if (element) element.addEventListener(eventName, handler);
}

function apiFetch(input, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    return window.fetch(input, options);
  }
  const headers = new Headers(options.headers || {});
  headers.set('X-Gurumoji-Request', '1');
  return window.fetch(input, {...options, headers});
}

function deepCopy(value) {
  return JSON.parse(JSON.stringify(value));
}

function setCurrentJobDirty(dirty = true, trackMutation = true) {
  currentJobDirty = Boolean(dirty);
  if (currentJobDirty && trackMutation) currentJobMutationGeneration += 1;
  if (resultCard) resultCard.classList.toggle('has-unsaved', currentJobDirty);
  if (saveButton) saveButton.classList.toggle('unsaved', currentJobDirty);
}

async function readJsonResponse(response) {
  const body = await response.text();
  if (!body) return {};
  try {
    return JSON.parse(body);
  } catch (error) {
    const status = `${response.status} ${response.statusText}`.trim();
    const looksLikeHtml = body.trimStart().startsWith('<')
      || (response.headers.get('content-type') || '').includes('text/html');
    if (looksLikeHtml) {
      throw new Error(
        `サーバーからHTMLエラーが返されました（${status}）。アプリを再起動してページを再読み込みしてください。`
      );
    }
    throw new Error(`サーバー応答を読み取れませんでした（${status}）。`);
  }
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value.toFixed(unit ? 1 : 0)} ${units[unit]}`;
}

function formatTime(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h
    ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value || '' : new Intl.DateTimeFormat('ja-JP', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  }).format(date);
}

function selectedOptionText(select) {
  return select && select.selectedOptions && select.selectedOptions[0]
    ? select.selectedOptions[0].textContent.trim()
    : '';
}

function scrollBehavior() {
  return reducedMotionMedia.matches ? 'auto' : 'smooth';
}

function downloadUnsavedDraft(kind) {
  if (kind === 'transcript') captureSessionProfile();
  const data = kind === 'transcript'
    ? {schema: 'gurumoji.unsaved-transcript.v1', item_id: currentJobId, base_revision: currentJob?.revision_count, draft: deepCopy(currentJob)}
    : {schema: 'gurumoji.unsaved-speakers.v1', base_revision: speakerRegistryRevision, speakers: deepCopy(speakerRegistry), delete_ids: [...speakerRegistryDeletedIds]};
  const blob = new Blob([JSON.stringify({...data, exported_at: new Date().toISOString()}, null, 2)], {type: 'application/json;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `gurumoji-unsaved-${kind}-${Date.now()}.json`;
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function showDraftRecovery(kind) {
  const panel = document.querySelector(kind === 'transcript' ? '#result-draft-recovery' : '#speaker-draft-recovery');
  if (!panel) return;
  panel.hidden = false;
  const count = kind === 'transcript'
    ? (currentJob?.segments || []).filter(segment => JSON.stringify(segment) !== JSON.stringify((currentJobBaseline?.segments || []).find(item => item.id === segment.id))).length
    : speakerRegistry.filter(record => JSON.stringify(record) !== JSON.stringify(speakerRegistryBaseline.find(item => item.id === record.id))).length;
  const deleted = kind === 'transcript' ? (currentJobBaseline?.segments || []).filter(item => !(currentJob?.segments || []).some(segment => segment.id === item.id)).length : speakerRegistryDeletedIds.size;
  panel.querySelector('[data-draft-count]').textContent = `追加・変更 ${count}件 / 削除 ${deleted}件。会話設定も含む未保存内容全体をJSONで退避できます。退避後に再読み込みし、最新の内容と照合してください。自動上書きはしません。`;
  panel.querySelector('button')?.focus();
}
