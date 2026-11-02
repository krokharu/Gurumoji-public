/* Read-only visualization of durable Core/Handler snapshots. Rendering,
 * animation, reopening and polling never call an AI or start/resume a run. */
const orchestrationRoles = [
  {id: 'core', label: 'Core', subtitle: '問い・統合・終了判断', kind: 'ai'},
  {id: 'handler', label: 'Handler', subtitle: '発注・台帳・保存・停止', kind: 'code'},
  {id: 'interpretation', label: '会話解釈', subtitle: '初回のラベル・尺度設計／テーマ・別解', kind: 'ai'},
  {id: 'statistics', label: '数量・統計', subtitle: 'Python集計', kind: 'code'},
  {id: 'verification', label: '独立検証', subtitle: '原文・数値・根拠', kind: 'ai'},
  {id: 'critic', label: '批判者', subtitle: '反証・代替説明', kind: 'ai'},
  {id: 'orchestrator', label: '専門オーケストレータ', subtitle: '分野別の結果評価・批判応答・追加分析', kind: 'ai'}
];
const orchestrationState = {itemId: '', itemName: '', runId: '', run: null, epoch: 0, poll: null, timer: null,
  operation: '', submission: null, setup: null, setupEpoch: 0, viewerEpoch: 0, fetchedAt: null, error: '', lastSeq: null, resultRequest: 0, taskFingerprint: '', recoveryFingerprint: '', initialFingerprint: '', outputFingerprint: ''};
const orchestrationStorageKey = 'gurumoji.orchestration.v1';
const orchestrationNode = id => document.getElementById(`orchestration-${id}`);
const orchestrationActiveStatuses = ['accepted', 'queued', 'running', 'cancelling', 'stopping'];
const orchestrationPublicationTargets = ['input', 'orchestrator', 'visualization'];
const orchestrationVaultWriters = [['input','Input'], ['orchestrator','Orchestrator'], ['visualization','Visualization'], ['research','Research']];
function orchestrationPendingCompletion(run) {
  const stages=Array.isArray(run?.initial_stages) ? run.initial_stages : run?.initial?.stages || [];
  return Boolean(run?.tasks?.some(task=>['running','cancel_requested'].includes(task.status)) || stages.some(stage=>stage.status==='running'));
}
function isAnalysisOrchestrationActive() { return Boolean(orchestrationState.submission || orchestrationActiveStatuses.includes(orchestrationState.run?.status) || orchestrationPendingCompletion(orchestrationState.run)); }
function orchestrationLabel(status) {
  return {accepted:'受付済み', queued:'待機', idle:'待機', pending:'待機', running:'実行中', succeeded:'処理成功', completed:'処理終了',
    cancelling:'停止・完了待ち', stopping:'停止・完了待ち', cancelled:'利用者停止', stopped:'停止', interrupted:'中断・復旧待ち',
    cancel_requested:'停止要求済み', uncertain:'実行結果不明', quarantined:'結果を隔離', paused:'一時停止', recovery_required:'中断・手動復旧待ち', failed:'失敗', blocked:'実行不可', waiting:'確認待ち', skipped:'未実施', validated:'形式確認済み'}[status] || status || '状態未取得';
}
function orchestrationText(id, value) { const node = orchestrationNode(id); if (node && node.textContent !== value) node.textContent = value; }
function orchestrationElement(tag, text, className) { const element = document.createElement(tag); if (text !== undefined) element.textContent = text; if (className) element.className = className; return element; }
function orchestrationNumber(value) { return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('ja-JP') : '未計測'; }
function orchestrationBase(itemId = orchestrationState.itemId, runId = orchestrationState.runId) { return `/api/library/${encodeURIComponent(itemId)}/analysis/orchestration${runId ? `/${encodeURIComponent(runId)}` : ''}`; }
function orchestrationPersist() {
  // Only opaque identifiers are retained in browser storage; never source text/results.
  try { sessionStorage.setItem(orchestrationStorageKey, JSON.stringify({itemId:orchestrationState.itemId, runId:orchestrationState.runId})); } catch (_) { /* unavailable */ }
}
function closeAnalysisOrchestrationDialogs() {
  const closedHistory = typeof closeAnalysisHistoryViewer === 'function' && closeAnalysisHistoryViewer();
  const closed = closedHistory || ['settings', 'live'].some(name => orchestrationNode(name)?.open);
  ++orchestrationState.setupEpoch; ++orchestrationState.viewerEpoch;
  for (const name of ['settings', 'live']) if (orchestrationNode(name)?.open) orchestrationNode(name).close();
  return closed;
}
function orchestrationFormMode() { return document.querySelector('input[name="orchestration_stop"]:checked')?.value || 'auto'; }
function orchestrationRoleOverrides() {
  return Object.fromEntries(orchestrationRoles.filter(role => role.kind === 'ai').flatMap(role => {
    const provider = orchestrationNode(`provider-${role.id}`)?.value;
    const model = orchestrationNode(`model-${role.id}`)?.value.trim();
    const common = orchestrationNode('provider').value;
    return provider || model ? [[role.id, {provider: provider || common, model: model || (provider && provider !== common ? '' : orchestrationNode('model').value.trim())}]] : [];
  }));
}
function orchestrationCloudProviders() {
  const common = orchestrationNode('provider').value;
  const overrides = orchestrationRoleOverrides();
  return [...new Set(orchestrationRoles.filter(role => role.kind === 'ai').map(role => overrides[role.id]?.provider || common).filter(p => ['openai', 'google'].includes(p)))];
}
function orchestrationSyncForm() {
  const mode = orchestrationFormMode();
  orchestrationNode('time-field').hidden = !['time', 'auto'].includes(mode);
  orchestrationNode('iterations-field').hidden = !['iterations', 'auto'].includes(mode);
  orchestrationNode('importance-field').hidden = !['importance', 'auto'].includes(mode);
  orchestrationNode('time').required = mode === 'time';
  orchestrationNode('iterations').required = mode === 'iterations';
  orchestrationText('stop-explanation', {
    time:'開始からの経過時間で新規発注を止めます。進行中の呼出しを必ず期限内に終える保証ではありません。',
    iterations:'Coreの結果統合から次の実行案選択までを1巡と数えます。並列タスク数や再試行回数とは別です。',
    importance:'問いへの影響を高・中・低で暫定評価します。頻度・モデルの自信とは異なり、基準は未校正です。',
    auto:'専門側が結果と批判を検討し、Coreが分野間の統合と終了を判断します。必要な追加分析を行い、時間・回数は空欄で無上限にできます。'
  }[mode]);
  for (const role of orchestrationRoles.filter(role => role.kind === 'ai')) {
    const provider = orchestrationNode(`provider-${role.id}`)?.value;
    const input = orchestrationNode(`model-${role.id}`);
    if (input) input.placeholder = provider && provider !== orchestrationNode('provider').value ? '空欄なら実行先の設定済みモデル' : '空欄なら共通設定';
  }
  const cloud = orchestrationCloudProviders();
  orchestrationNode('cloud-disclosure').hidden = cloud.length === 0;
  orchestrationText('cloud-targets', `送信先: ${cloud.map(p => p === 'openai' ? 'OpenAI' : 'Google Gemini').join('、')}。原文や途中結果を含む固定した分析入力を送信します。`);
}
function orchestrationSetupCurrent(epoch = orchestrationState.setupEpoch) {
  return epoch === orchestrationState.setupEpoch && orchestrationNode('settings').open && orchestrationState.setup && isAnalysisContextCurrent(orchestrationState.setup);
}
function openAnalysisOrchestrationSettings() {
  if (isAnalysisOrchestrationActive() && orchestrationState.runId) { showAnalysisOrchestration(); return; }
  closeAnalysisExecutionDialog();
  const nextContext = captureAnalysisContext();
  const same = orchestrationState.setup && isAnalysisContextCurrent(orchestrationState.setup);
  orchestrationState.setup = nextContext; ++orchestrationState.setupEpoch;
  // Consent belongs to a new submission, never to a past run or a later opening.
  // An uncertain submission retains the exact choice needed for an idempotent retry.
  orchestrationNode('publication-all').checked = Boolean(orchestrationState.submission?.itemId === nextContext.itemId && orchestrationState.submission.payload.publication_targets?.length);
  if (!same) {
    orchestrationNode('question').value = String(analysisState.config?.research_question || '').slice(0, 2000);
    orchestrationNode('cloud-consent').checked = false;
    orchestrationNode('history-list').replaceChildren();
  }
  orchestrationText('settings-target', `${nextContext.data?.item?.source_name || '分析対象を選択してください'} · 入力版 ${nextContext.sourceRevision ?? '不明'} / 分析版 ${nextContext.analysisRevision ?? '不明'}`);
  const blocked = !nextContext.itemId || !nextContext.data ? '先に分析対象を読み込んでください。' : hasUnsavedAnalysisChanges() ? '未保存の変更があります。分析設定を保存してから開始してください。' : analysisExecutionState.active ? '基礎分析を実行中です。終了してから自律分析を開始してください。' : '';
  setAlert(orchestrationNode('settings-message'), blocked, Boolean(blocked));
  orchestrationNode('start').disabled = Boolean(blocked || orchestrationState.operation === 'start');
  orchestrationSyncForm();
  orchestrationNode('settings').showModal();
}
function orchestrationPayload() {
  if (!orchestrationSetupCurrent() || !orchestrationState.setup.itemId) throw Error('分析対象が変わりました。設定を開き直してください。');
  if (hasUnsavedAnalysisChanges()) throw Error('未保存の変更を保存してから開始してください。');
  if (analysisExecutionState.active) throw Error('基礎分析の終了を待ってください。');
  const mode = orchestrationFormMode(), question = orchestrationNode('question').value.trim();
  if (!question) throw Error('明らかにしたいことを入力してください。');
  const integer = (id, required, max) => {
    const raw = orchestrationNode(id).value.trim();
    if (!raw && !required) return null;
    const number = Number(raw);
    if (!Number.isInteger(number) || number < 1 || number > max) throw Error(`${orchestrationNode(id).closest('label').querySelector('span').textContent}を1〜${max}の整数で指定してください。`);
    return number;
  };
  const cloud = orchestrationCloudProviders();
  if (cloud.length && !orchestrationNode('cloud-consent').checked) throw Error('クラウドへの会話原文・途中結果の送信に同意するか、全担当をローカルに戻してください。');
  return {source_revision:orchestrationState.setup.sourceRevision, analysis_revision:orchestrationState.setup.analysisRevision,
    question, provider:orchestrationNode('provider').value, model:orchestrationNode('model').value.trim(), provider_policy:cloud.length ? 'cloud_allowed' : 'local_only', cloud_consent:cloud.length > 0 && orchestrationNode('cloud-consent').checked,
    stop_mode:mode, time_limit_seconds:['time','auto'].includes(mode) ? (integer('time', mode === 'time', 1440) ?? 0) * 60 || null : null,
    max_iterations:['iterations','auto'].includes(mode) ? integer('iterations', mode === 'iterations', 1000) : null,
    importance_threshold:orchestrationNode('importance').value, max_calls:integer('max-calls',true,1000), max_tasks:integer('max-tasks',true,2000),
    concurrency:integer('concurrency',true,4), research_mode:'exploratory', roles:orchestrationRoleOverrides(),
    model_context_version:cloud.length ? 0 : 1, context_reference_version:cloud.length ? 0 : 1,
    context_evidence_limit:24, context_text_limit:6000,
    analysis_interval_version:1, analysis_interval_seconds:300,
    publication_targets:orchestrationNode('publication-all').checked ? [...orchestrationPublicationTargets] : []};
}
async function startAnalysisOrchestration(event) {
  event?.preventDefault();
  if (orchestrationState.operation) return;
  let payload;
  try { payload = orchestrationPayload(); } catch (error) { setAlert(orchestrationNode('settings-message'), error.message, true); return; }
  const context = orchestrationState.setup, setupEpoch = orchestrationState.setupEpoch;
  const fingerprint = JSON.stringify(payload);
  // An ambiguous transport failure must not silently become a second request.
  if (orchestrationState.submission && (orchestrationState.submission.itemId !== context.itemId || orchestrationState.submission.fingerprint !== fingerprint)) {
    setAlert(orchestrationNode('settings-message'), '前の開始要求の受付状態が不明です。設定を変更して再送せず、「保存済み実行」で確認してください。', true); return;
  }
  const submission = orchestrationState.submission || {itemId:context.itemId, fingerprint, payload:{...payload, request_id: typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : createSubmissionId()}};
  orchestrationState.submission = submission; orchestrationState.operation = 'start'; orchestrationNode('start').disabled = true;
  try {
    const response = await analysisExecutionRequestJson(orchestrationBase(submission.itemId, ''), {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(submission.payload)});
    if (!response.run?.run_id) throw Error('受付IDを取得できませんでした。保存済み実行から確認してください。');
    orchestrationState.submission = null;
    orchestrationAdopt(response.run, submission.itemId, context.data?.item?.source_name);
    if (orchestrationSetupCurrent(setupEpoch)) { orchestrationNode('settings').close(); showAnalysisOrchestration(); }
    orchestrationSchedule();
  } catch (error) {
    if (error.status && error.status < 500) orchestrationState.submission = null;
    if (orchestrationSetupCurrent(setupEpoch)) setAlert(orchestrationNode('settings-message'), `${error.message}${orchestrationState.submission ? ' 受付状態は未確定です。同じ設定で再送する場合は同じ依頼IDを使います。保存済み実行も確認できます。' : ''}`, true);
  } finally {
    orchestrationState.operation = '';
    if (orchestrationState.run) renderAnalysisOrchestration();
    if (orchestrationSetupCurrent(setupEpoch)) orchestrationNode('start').disabled = false;
  }
}
function orchestrationAdopt(run, itemId, itemName = '') {
  if (run.item_id && run.item_id !== itemId) throw Error('取得した実行の対象が一致しません。');
  ++orchestrationState.epoch; orchestrationState.poll = null;
  window.clearTimeout(orchestrationState.timer);
  Object.assign(orchestrationState,{runId:run.run_id,itemId,itemName:itemName || run.item_name || run.source_name || (analysisState.itemId===itemId ? analysisState.data?.item?.source_name : '') || '',run,error:'',operation:orchestrationState.operation==='start'?'start':'',lastSeq:null,taskFingerprint:'',recoveryFingerprint:'',initialFingerprint:'',outputFingerprint:'',fetchedAt:Date.now()});
  orchestrationPersist(); renderAnalysisOrchestration();
}
function orchestrationSchedule() {
  window.clearTimeout(orchestrationState.timer);
  const run=orchestrationState.run, publication=run?.publication;
  const outputActive=run?.status==='completed' && (publication?.save_status==='saving' || ['pending','publishing'].includes(publication?.publication_status));
  if (orchestrationActiveStatuses.includes(run?.status) || !run || outputActive || orchestrationPendingCompletion(run)) orchestrationState.timer = window.setTimeout(pollAnalysisOrchestration, 1500);
}
async function pollAnalysisOrchestration() {
  if (!orchestrationState.runId || orchestrationState.poll || orchestrationState.operation) return;
  window.clearTimeout(orchestrationState.timer);
  const token = {epoch:orchestrationState.epoch,itemId:orchestrationState.itemId,runId:orchestrationState.runId}; orchestrationState.poll = token;
  const owns = () => orchestrationState.epoch === token.epoch && orchestrationState.poll === token;
  try {
    const response = await analysisExecutionRequestJson(orchestrationBase(token.itemId, token.runId));
    if (!owns()) return;
    if (response.run?.run_id !== token.runId || response.run.item_id && response.run.item_id !== token.itemId) throw Error('状態の対象IDが一致しません。');
    orchestrationState.run = response.run; orchestrationState.error = ''; orchestrationState.fetchedAt = Date.now();
  } catch (error) { if (owns()) orchestrationState.error = `状態を取得できません: ${error.message}。実行が停止したかは未確認です。`; }
  finally { if (owns()) { orchestrationState.poll = null; renderAnalysisOrchestration(); orchestrationSchedule(); } }
}
function showAnalysisOrchestration() {
  if (!orchestrationState.runId) { openAnalysisOrchestrationSettings(); return; }
  ++orchestrationState.viewerEpoch;
  orchestrationNode('result-view').hidden = true;
  renderAnalysisOrchestration();
  if (!orchestrationNode('live').open) orchestrationNode('live').showModal();
  pollAnalysisOrchestration();
}
function orchestrationRunRole(id) {
  const roles = orchestrationState.run?.roles;
  return Array.isArray(roles) ? roles.find(role => (role.id || role.role) === id) || {} : roles?.[id] || {};
}
function orchestrationRenderRole(role) {
  const run = orchestrationState.run || {}, data = orchestrationRunRole(role.id);
  const tasks = (run.tasks || []).filter(task => (task.role || task.assigned_to) === role.id);
  const status = data.status || (tasks.some(t => t.status === 'running') ? 'running' : tasks.length ? 'idle' : 'pending');
  const card = orchestrationElement('article', undefined, 'orchestration-role'); card.dataset.role = role.id; card.dataset.status = status;
  const heading = orchestrationElement('div', undefined, 'orchestration-role-heading');
  heading.append(orchestrationElement('strong', role.label), orchestrationElement('span', role.kind === 'ai' ? 'AI' : 'CODE','orchestration-kind'));
  const config = run.config?.roles?.[role.id] || {};
  const provider = data.provider || config.provider || run.config?.provider;
  const model = data.model || config.model || run.config?.model;
  const modelText = role.kind === 'code' ? (role.id === 'statistics' ? 'Python · 決定的な集計' : 'アプリ · LLM呼出しなし') : `${provider || '実行先未取得'} / ${model || 'モデル未取得'}`;
  card.append(heading,orchestrationElement('small',role.subtitle),orchestrationElement('p',modelText,'orchestration-role-model'));
  card.append(orchestrationElement('p',orchestrationLabel(status),'orchestration-role-status'));
  const assigned = data.assigned ?? (Array.isArray(run.tasks) ? tasks.length : null), completed = data.completed ?? (Array.isArray(run.tasks) ? tasks.filter(t=>['succeeded','completed'].includes(t.status)).length : null), failed = data.failed ?? (Array.isArray(run.tasks) ? tasks.filter(t=>t.status==='failed').length : null);
  card.append(orchestrationElement('p',`割当 ${orchestrationNumber(assigned)} · 成功 ${orchestrationNumber(completed)} · 失敗/要確認 ${orchestrationNumber(failed)}`,'orchestration-role-counts'));
  const current = data.current_task || tasks.find(t=>t.status==='running')?.title;
  card.append(orchestrationElement('p',typeof current === 'object' ? current.title || current.task_id : current || '進行中タスクなし','orchestration-role-task'));
  return card;
}
function renderAnalysisOrchestration() {
  const state = orchestrationState, run = state.run, live = orchestrationNode('live'); if (!live) return;
  const active = orchestrationActiveStatuses.includes(run?.status);
  const draining = !active && orchestrationPendingCompletion(run);
  orchestrationNode('chip').hidden = !state.runId;
  orchestrationNode('chip').classList.toggle('is-active', active || draining);
  orchestrationText('chip-label', `自律分析 · ${run ? orchestrationLabel(run.status) : '状態確認'}`);
  if (!run) { orchestrationText('status','保存済みの状態を確認中'); setAlert(orchestrationNode('live-message'),state.error,Boolean(state.error)); return; }
  orchestrationText('live-title',active ? '問いから、次の分析へ' : '保存された分析の状態');
  orchestrationText('live-target',`${run.item_name || run.source_name || state.itemName || state.itemId} · Run ${run.run_id} · 入力版 ${run.source_revision ?? run.config?.source_revision ?? '不明'}`);
  orchestrationText('live-question',run.config?.question || run.question || '分析目的は未取得');
  orchestrationText('status',`${orchestrationLabel(run.status)}${draining ? ' · 残処理の終了待ち' : ''}${run.phase ? ` · ${{core:'Coreの判断',label_review:'\u5c3a\u5ea6\u306e\u72ec\u7acb\u30ec\u30d3\u30e5\u30fc',specialist_review:'\u5c02\u9580\u5074\u306e\u7d50\u679c\u8a55\u4fa1',specialist_followup:'\u5c02\u9580\u5074\u306e\u8ffd\u52a0\u5206\u6790',specialists:'専門処理',initial_analysis:'全担当の初回分析・尺度要件の報告',initial_routing:'Coreによる専門家への担当指示',initial_labels:'専門家によるラベル・尺度作成',stop_review:'終了前レビュー',stopped:'停止',initial:'初期分析（コード処理）'}[run.phase] || run.phase}` : ''}`);
  orchestrationText('updated',state.fetchedAt ? `最終取得 ${new Date(state.fetchedAt).toLocaleTimeString('ja-JP')}` : '未取得');
  const notice=[state.error,run.error,run.uncertain_tasks?.length ? `実行結果が不明なタスク: ${run.uncertain_tasks.join(', ')}。二重実行を避けるため、自動再発注・通常の再開はできません。` : ''].filter(Boolean).join('\n');
  setAlert(orchestrationNode('live-message'),notice,Boolean(notice));
  const usage = run.usage || {}, tasks = run.tasks || [];
  const tokenValue = usage.total_tokens ?? usage.tokens;
  const tokenLabel = ['partial','reported'].includes(usage.measurement_status) || usage.tokens_complete === false || usage.tokens_partial || usage.partial ? 'トークン（一部計測）' : 'トークン（実測）';
  const metrics = [[run.completed_core_iterations ?? run.iteration ?? null,run.completed_core_iterations == null ? 'Core巡回' : '採用済みCore判断'],[usage.calls ?? usage.llm_calls ?? null,`AI呼出し / ${run.config?.max_calls ?? '—'}`],[Array.isArray(run.tasks) ? tasks.length : null,'登録タスク'],[tokenValue ?? null,tokenLabel]];
  orchestrationNode('metrics').replaceChildren(...metrics.map(([value,label])=>{const node=orchestrationElement('div');node.append(orchestrationElement('strong',orchestrationNumber(value)),orchestrationElement('span',label));return node;}));
  orchestrationNode('role-core').replaceChildren(orchestrationRenderRole(orchestrationRoles[0]));
  orchestrationNode('role-handler').replaceChildren(orchestrationRenderRole(orchestrationRoles[1]));
  orchestrationNode('specialists').replaceChildren(...orchestrationRoles.slice(2).map(orchestrationRenderRole));
  const events = run.events || [], latest = events.at(-1), seq = latest?.seq ?? latest?.sequence ?? null;
  // Only a new persisted event triggers a short transfer animation. No fabricated progress.
  if (active && seq !== null && seq !== state.lastSeq) {
    const link = orchestrationNode(latest.from === 'core' || latest.to === 'core' ? 'flow-decision' : 'flow-dispatch');
    link.classList.remove('has-event'); void link.offsetWidth; link.classList.add('has-event');
  }
  state.lastSeq=seq;
  orchestrationText('live-event',latest ? `最新の記録: ${latest.message || latest.type}${latest.from || latest.to ? ` · ${latest.from || '—'} → ${latest.to || '—'}` : ''}` : 'イベントはまだ記録されていません。');
  const stop = orchestrationNode('stop'), resume = orchestrationNode('resume');
  const canCancel = Array.isArray(run.allowed_actions) ? run.allowed_actions.includes('cancel') : active;
  stop.hidden = !canCancel && !['cancelling','stopping'].includes(run.status); stop.disabled = Boolean(state.operation || !canCancel || ['cancelling','stopping'].includes(run.status));
  stop.textContent = ['cancelling','stopping'].includes(run.status) ? '停止・完了を待っています' : '停止する';
  const canResume = Array.isArray(run.allowed_actions) ? run.allowed_actions.includes('resume') : run.can_resume === true;
  resume.hidden = !canResume; resume.disabled = Boolean(state.operation);
  orchestrationNode('refresh').disabled = Boolean(state.operation || state.poll);
  const reasons = {question_satisfied:'問いを充足',human_review_required:'人の確認待ち',no_new_tasks:'追加タスクなし',no_progress:'同じ判断の繰り返し・進展なし',unreviewed_results:'専門家結果の採否未完了',importance_threshold:'重要度しきい値',execution_failure:'実行障害',review_incomplete:'レビュー未完了',call_timeout:'呼出し時間上限',call_budget_limit:'AI呼出し上限',task_budget_limit:'タスク上限',source_deleted:'入力データの削除',user_cancelled:'利用者停止',user_stop:'利用者停止',time_limit:'時間上限',iteration_limit:'回数上限',call_budget:'AI呼出し上限',task_budget:'タスク上限',budget_limit:'予算上限',completed:'問いを充足',no_more_evidence:'追加の証拠なし',error:'実行障害',human_review:'人の確認待ち'};
  reasons.initial_labels_missing='初回の専門家によるラベル・尺度出力が未完了';
  reasons.initial_analysis_incomplete='初回の全担当の分析・尺度要件の報告が未完了';
  reasons.initial_routing_invalid='初回のCoreによる担当指示が未完了または不正';
  orchestrationText('stop-reason',run.stop_reason ? `停止理由: ${reasons[run.stop_reason] || run.stop_reason}。保存済みの部分結果・未実施レビューを含めて確認してください。` : '利用者停止と安全上限を最優先します。研究上の結論は未確定の探索的下書きです。');
  const config = run.config || {};
  orchestrationText('config',`実行条件: ${config.stop_mode || '未取得'} / 最低 ${config.min_iterations ?? '未取得'}回 / 時間 ${config.time_limit_seconds ?? '無上限'}${config.time_limit_seconds ? '秒' : ''} / 回数上限 ${config.max_iterations ?? '無上限'} / 呼出し上限 ${config.max_calls ?? '不明'} / タスク上限 ${config.max_tasks ?? '不明'} / 外部送信 ${config.provider_policy === 'local_only' ? 'なし（ローカル限定）' : config.provider_policy === 'cloud_allowed' ? '同意済みクラウドを許可' : '未取得'}`);
  for (const [id, suffix] of [['export-json','export.json'],['export-md','export.md']]) orchestrationNode(id).href = `${orchestrationBase()}/${suffix}`;
  orchestrationText('usage-note',`利用量の計測: ${{reported:'一部計測（全量未保証）',unavailable:'未計測'}[usage.measurement_status] || usage.measurement_status || '未取得'} · 計測済み呼出し ${orchestrationNumber(usage.measured_calls)} / ${orchestrationNumber(usage.calls)} · 費用 ${usage.cost == null ? '未計測' : `${String(usage.cost)} ${usage.currency || '通貨未取得'}`}。未計測分を0として補完しません。`);
  orchestrationText('conclusion',run.current_view?.summary || '統合結果はまだ保存されていません。');
  const notes=orchestrationNode('conclusion-notes');notes.replaceChildren();
  if(run.config?.initial_label_definitions_version){
    const catalog=run.initial_label_catalog;
    const entry=orchestrationElement('li',catalog ? `初回のラベル・尺度: 専門エージェント作成のAI下書き ${catalog.definitions.length}件` : '初回のラベル・尺度: 専門エージェントの出力待ち');
    if(catalog){const button=orchestrationElement('button','ラベル・尺度の定義を読む','link-button');button.type='button';button.addEventListener('click',()=>orchestrationReadResults(catalog.result_id));entry.append(button);}
    notes.append(entry);
  }
  for(const [key,label] of [['alternatives','代替説明'],['unresolved','未解決点']])for(const value of run.current_view?.[key] || [])notes.append(orchestrationElement('li',`${label}: ${typeof value === 'string' ? value : JSON.stringify(value)}`));
  orchestrationText('review-state',`終了前レビュー: ${{reviewed:'実施済み（研究上の結論は未確定）',pending:'待機',not_started:'未実施',not_reviewed:'未実施',incomplete:'未完了',unavailable:'実施できず'}[run.review_status] || run.review_status || '状態未取得'}${run.stale ? ' · 入力版が更新された結果です' : ''}`);
  orchestrationRenderInitial(run); orchestrationRenderOutput(run); orchestrationRenderRecovery(run); orchestrationRenderTasks(tasks); orchestrationRenderReview(run);
  orchestrationNode('events').replaceChildren(...events.slice(-100).map(event=>orchestrationElement('li',`${event.seq ?? event.sequence ?? '—'} · ${event.message || event.type}${event.task_id ? ` · ${event.task_id}` : ''}`)));
}
function orchestrationRenderInitial(run) {
  const initial=run.initial || {}, stages=Array.isArray(run.initial_stages) ? run.initial_stages : initial.stages || [];
  const available=run.phase==='initial' || Boolean(run.initial) || stages.length>0;
  orchestrationNode('initial').hidden=!available;
  if(!available)return;
  const completed=stages.filter(stage=>stage.status==='completed').length;
  const canResume=Array.isArray(run.allowed_actions) ? run.allowed_actions.includes('resume') : run.can_resume===true;
  orchestrationText('initial-summary',stages.length ? `${completed} / ${stages.length} 段階を保存済み。${initial.status==='ready' ? '初期版は保存済みです。' : run.status==='recovery_required' ? canResume ? '中断した段階は、下の再開操作から復旧できます。' : '再開は許可されていません。表示されたエラーを確認してください。' : ''}` : initial.status==='ready' ? '初期版は保存済みです。この実行には段階別の記録がありません。' : '初期分析の保存地点を確認しています。');
  const fingerprint=JSON.stringify([run.run_id,stages]);
  if(fingerprint===orchestrationState.initialFingerprint)return;
  orchestrationState.initialFingerprint=fingerprint;
  const host=orchestrationNode('initial-stages');host.replaceChildren();
  for(const stage of stages){
    const row=orchestrationElement('li');row.dataset.status=stage.status || 'unknown';
    row.append(orchestrationElement('strong',stage.label || stage.stage_id || stage.id || '段階名未取得'),orchestrationElement('span',stage.status==='completed' ? '保存済み' : orchestrationLabel(stage.status),'orchestration-checkpoint-status'));
    const attempts=stage.attempt_count ?? stage.attempts;
    row.append(orchestrationElement('small',`コード処理 · 実行回数 ${orchestrationNumber(attempts)}${stage.status==='completed' ? ' · 保存済み（再開時に再利用）' : ''}`));
    if(stage.error)row.append(orchestrationElement('p',stage.error,'orchestration-checkpoint-error'));
    if(stage.output_hash || stage.artifact_hash){const details=orchestrationElement('details');details.append(orchestrationElement('summary','保存記録'),orchestrationElement('p',`Hash: ${stage.output_hash || stage.artifact_hash}${stage.completed_at ? ` · 保存日時: ${stage.completed_at}` : ''}`));row.append(details);}
    host.append(row);
  }
}
function orchestrationPublicationSelected(publication) {
  const selected=publication?.publication_targets;
  return Array.isArray(selected) && selected.length===orchestrationPublicationTargets.length && orchestrationPublicationTargets.every(target=>selected.includes(target));
}
function orchestrationOutputLabel(status) {
  return {not_started:'未保存',saving:'保存中',saved:'保存済み',failed:'失敗',interrupted:'中断・要確認',not_selected:'未選択（OFF）',pending:'待機',publishing:'出力中',published:'出力処理成功',incomplete:'一部未完了',conflict:'競合・要確認',unknown:'結果不明',skipped:'未実施'}[status] || status || '状態未取得';
}
function orchestrationArtifactLink(artifact) {
  if(typeof artifact?.url!=='string' || !artifact.url.trim())return null;
  try { const url=new URL(artifact.url,window.location.href);if(!['http:','https:'].includes(url.protocol) || url.username || url.password)return null; } catch(_){return null;}
  const link=orchestrationElement('a',artifact.name || '保存成果物');link.setAttribute('href',artifact.url);link.setAttribute('download','');return link;
}
function orchestrationRenderOutput(run) {
  const publication=run.publication, selected=orchestrationPublicationSelected(publication), retry=orchestrationNode('publication-retry');
  retry.hidden=!(run.status==='completed' && publication?.can_retry===true);
  retry.disabled=Boolean(orchestrationState.operation);
  retry.textContent=orchestrationState.operation==='publication/retry' ? '保存・出力の応答を待っています' : selected ? '保存・4 Vault出力を再試行' : '固定成果物の保存を再試行';
  const fingerprint=JSON.stringify([run.run_id,run.status,publication]);
  if(fingerprint===orchestrationState.outputFingerprint)return;
  orchestrationState.outputFingerprint=fingerprint;
  orchestrationText('save-status',`アプリ内の固定成果物: ${publication ? orchestrationOutputLabel(publication.save_status) : '保存記録未取得'}${publication?.result_run_id ? ` · ${publication.result_run_id}` : ''}${publication?.stale ? ' · 入力更新前の固定版' : ''}`);
  orchestrationText('publication-status',`Vault出力: ${publication ? orchestrationOutputLabel(publication.publication_status) : '未選択（OFF）'}`);
  orchestrationText('publication-scope',selected ? '開始時に選択済み: Input／Orchestrator／Visualization／Researchの4つ一式。Researchには保存時点の発話本文を含みます。分析の終了と各保存先の成功は別の状態です。' : 'この実行では4 Vault出力を選択していません。保存・再開・再試行から出力先を追加することはありません。');
  const host=orchestrationNode('publication-outcomes');host.replaceChildren();
  for(const [id,label] of orchestrationVaultWriters){
    const outcome=publication?.outcomes?.[id];
    const status=outcome?.status || (selected ? 'unknown' : 'not_selected');
    const row=orchestrationElement('li');row.dataset.writer=id;row.dataset.status=status;
    row.append(orchestrationElement('strong',label),orchestrationElement('span',orchestrationOutputLabel(status)));
    if(outcome?.error)row.append(orchestrationElement('small',outcome.error));host.append(row);
  }
  setAlert(orchestrationNode('publication-error'),publication?.error || '',Boolean(publication?.error));
  const missing=publication?.result_run?.vault_notes?.missing;
  orchestrationNode('publication-note-policy').hidden=!Array.isArray(missing) || !missing.length;
  orchestrationText('publication-note-policy',Array.isArray(missing) && missing.length ? `削除済みノートの記録が${missing.length}件あります。既存の削除保護を維持します。出力処理が成功しても、全ノートの存在を保証するものではありません。` : '');
  const artifacts=orchestrationNode('output-artifacts');artifacts.replaceChildren();
  for(const artifact of publication?.result_run?.artifacts || []){
    const link=orchestrationArtifactLink(artifact);if(!link)continue;
    const row=orchestrationElement('li');row.append(link);artifacts.append(row);
  }
  orchestrationText('publication-retry-note',selected ? '再試行は同じ固定成果物・同じ承認済み範囲で4つの保存先を再訪します。失敗先だけの再試行ではありません。AI・統計の再計算は行いません。生成ノートの手動編集履歴・削除保護を使います。' : '再試行が許可された場合も、固定成果物の保存だけが対象です。AI・統計の再計算やVault出力は行いません。');
}
function orchestrationRenderTasks(tasks) {
  const fingerprint=JSON.stringify([orchestrationState.runId,tasks,orchestrationState.run?.results]);
  if(fingerprint===orchestrationState.taskFingerprint)return;
  orchestrationState.taskFingerprint=fingerprint;
  const focused=document.activeElement?.dataset?.orchestrationResult;
  const host=orchestrationNode('tasks'); host.replaceChildren(); orchestrationText('task-count',`(${tasks.length})`);
  for (const task of tasks) {
    const row=orchestrationElement('tr');
    const title=orchestrationElement('td',task.title || task.task_id || '名称未取得'); title.append(orchestrationElement('small',task.task_id || ''));
    const role=orchestrationRoles.find(r=>r.id===(task.role || task.assigned_to));
    const who=orchestrationElement('td',`${role?.label || task.role || '担当未取得'} / ${role?.kind === 'code' ? 'コード実行' : task.model || 'モデル未取得'}`);
    const result=orchestrationElement('td');
    const resultId = task.result_id || (orchestrationState.run?.results || []).find(result=>result.task_id===task.task_id)?.result_id;
    if (resultId) { const button=orchestrationElement('button','結果を読む','link-button');button.type='button';button.dataset.orchestrationResult=resultId;button.addEventListener('click',()=>orchestrationReadResults(resultId));result.append(button); }
    else result.textContent=task.error || '保存結果なし';
    row.append(title,who,orchestrationElement('td',orchestrationLabel(task.status)),result);host.append(row);
  }
  if(focused && orchestrationNode('live').open) [...host.querySelectorAll('button')].find(button=>button.dataset.orchestrationResult===focused)?.focus();
  if (!tasks.length) { const row=orchestrationElement('tr'),cell=orchestrationElement('td','タスクはまだ登録されていません。');cell.colSpan=4;row.append(cell);host.append(row); }
}
function orchestrationRenderReview(run) {
  const host=orchestrationNode('review-content');host.replaceChildren();
  const issues=run.issues || run.critic_issues || run.unresolved_issues || run.critic_findings || [];
  const decisions=run.critique_responses || run.critic_decisions || run.critic_responses || run.core_decisions || [];
  if (!issues.length && !decisions.length) host.append(orchestrationElement('p',run.review_status === 'reviewed' ? '保存済みの終了前レビューに指摘はありません。研究上の妥当性・確認分析の成功を意味しません。' : '批判レビュー・Coreの採否記録はまだ取得されていません。指摘なし・検証済みとは扱いません。'));
  for (const issue of issues) host.append(orchestrationElement('p',`${issue.issue_id || '指摘ID未取得'} · ${issue.severity || issue.importance || '重要度未取得'} · ${issue.status || '採否未取得'} · ${issue.reason || issue.message || issue.claim || issue.title || JSON.stringify(issue)}${issue.evidence_ids?.length ? ` / 根拠 ${issue.evidence_ids.join(', ')}` : ''}${issue.target_id ? ` / 対象 ${issue.target_id} 第${issue.target_version ?? '不明'}版` : ''}`));
  for (const decision of decisions) host.append(orchestrationElement('p',`Core / ${decision.issue_id || '対象指摘未取得'}: ${{adopt:'採用',reject:'棄却',defer:'保留'}[decision.disposition] || decision.disposition || decision.decision || decision.status || '判断未取得'} · ${decision.reason || decision.rationale || JSON.stringify(decision)}${decision.impact ? ` / 結論への影響: ${decision.impact}` : ''}`));
}
function orchestrationRenderRecovery(run) {
  const available=run.status==='recovery_required' && Array.isArray(run.uncertain_tasks) && run.uncertain_tasks.length>0;
  orchestrationNode('recovery').hidden=!available;
  if(!available){orchestrationState.recoveryFingerprint='';return;}
  const fingerprint=JSON.stringify([run.run_id,run.uncertain_tasks]);
  if(fingerprint!==orchestrationState.recoveryFingerprint){
    orchestrationState.recoveryFingerprint=fingerprint;
    const host=orchestrationNode('recovery-tasks');host.replaceChildren();
    for(const id of run.uncertain_tasks){
      const task=(run.tasks||[]).find(task=>task.task_id===id),label=orchestrationElement('label',undefined,'check-row'),checkbox=orchestrationElement('input');
      checkbox.type='checkbox';checkbox.value=id;checkbox.dataset.recoveryTask=id;
      label.append(checkbox,orchestrationElement('span',`${id} · ${task?.title || '名称未取得'} を放棄する（再送なし）`));host.append(label);
    }
  }
  orchestrationNode('abandon').disabled=Boolean(orchestrationState.operation) || !orchestrationNode('recovery-tasks').querySelector('input:checked');
}
function orchestrationAbandonAndResume(){
  const run=orchestrationState.run;
  if(run?.status!=='recovery_required' || orchestrationState.operation)return;
  const selected=[...orchestrationNode('recovery-tasks').querySelectorAll('input:checked')].map(input=>input.value).filter(id=>(run.uncertain_tasks||[]).includes(id));
  if(!selected.length)return;
  orchestrationAction('resume',{recovery:Object.fromEntries(selected.map(id=>[id,'abandon']))});
}
async function orchestrationAction(action, payload = {}) {
  if (!orchestrationState.runId || orchestrationState.operation) return;
  const allowed=orchestrationState.run?.allowed_actions;
  if (['cancel','resume'].includes(action) && !payload.recovery && Array.isArray(allowed) && !allowed.includes(action)) return;
  if (action === 'publication/retry' && (orchestrationState.run?.status !== 'completed' || orchestrationState.run?.publication?.can_retry !== true)) return;
  if (action === 'cancel' && !window.confirm('新規タスクの発注を止めます。完了済み結果は保持し、停止不能な呼出しは完了待ちになります。停止しますか？')) return;
  if (action === 'resume' && !window.confirm(payload.recovery ? `選択した${Object.keys(payload.recovery).length}件の結果不明な呼出しを放棄します（${Object.keys(payload.recovery).join(', ')}）。結果は採用せず再送もしません。発生済み費用は不明です。残り予算で復旧を続けますか？` : '保存済みの条件・送信先・残り予算で再開します。完了済み結果を保持します。再開しますか？')) return;
  const epoch=++orchestrationState.epoch,itemId=orchestrationState.itemId,runId=orchestrationState.runId;
  orchestrationState.poll=null;window.clearTimeout(orchestrationState.timer);
  orchestrationState.operation=action;renderAnalysisOrchestration();
  let refreshNeeded=false;
  try {
    const result=await analysisExecutionRequestJson(`${orchestrationBase(itemId,runId)}/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(action==='publication/retry' ? {} : payload)});
    if (epoch!==orchestrationState.epoch) return;
    if (result.run?.run_id!==runId || result.run.item_id && result.run.item_id!==itemId) throw Error('実行の対象IDが一致しません。');
    orchestrationState.run=result.run;orchestrationState.error='';orchestrationState.fetchedAt=Date.now();
  } catch(error) { refreshNeeded=true; if(epoch===orchestrationState.epoch) orchestrationState.error=`${action==='cancel'?'停止':action==='publication/retry'?'保存・出力の再試行':'再開'}の受付を確認できません: ${error.message}。状態を更新して確認してください。`; }
  finally { if(epoch===orchestrationState.epoch){orchestrationState.operation='';renderAnalysisOrchestration();if(refreshNeeded)pollAnalysisOrchestration();else orchestrationSchedule();} }
}
async function orchestrationReadResults(resultId = '') {
  const request=++orchestrationState.resultRequest,epoch=orchestrationState.epoch,viewer=orchestrationState.viewerEpoch,runId=orchestrationState.runId;
  const host=orchestrationNode('result-content');host.replaceChildren(orchestrationElement('p','保存済み結果を取得しています…'));orchestrationNode('result-view').hidden=false;
  try {
    const data=await analysisExecutionRequestJson(`${orchestrationBase()}/results${resultId ? `/${encodeURIComponent(resultId)}` : ''}`);
    if(request!==orchestrationState.resultRequest || epoch!==orchestrationState.epoch || viewer!==orchestrationState.viewerEpoch || runId!==orchestrationState.runId || !orchestrationNode('live').open) return;
    host.replaceChildren(orchestrationElement('p','固定された保存結果です。初期版・根拠ID・未解決点を含めて確認してください。'));
    const pre=orchestrationElement('pre',JSON.stringify(data,null,2));pre.tabIndex=0;host.append(pre);
  } catch(error) { if(request===orchestrationState.resultRequest && epoch===orchestrationState.epoch && viewer===orchestrationState.viewerEpoch && orchestrationNode('live').open)host.replaceChildren(orchestrationElement('p',`結果を取得できません: ${error.message}`)); }
}
async function orchestrationHistory() {
  if(!orchestrationSetupCurrent())return;
  const epoch=orchestrationState.setupEpoch,itemId=orchestrationState.setup.itemId,host=orchestrationNode('history-list');
  host.replaceChildren(orchestrationElement('p','保存済み実行を取得しています…'));
  try {
    const data=await analysisExecutionRequestJson(orchestrationBase(itemId,''));
    if(!orchestrationSetupCurrent(epoch))return;
    host.replaceChildren();
    for(const run of data.runs || []) {
      const button=orchestrationElement('button',`${orchestrationLabel(run.status)} · ${run.config?.question || run.run_id}`,'secondary-button');button.type='button';
      button.addEventListener('click',()=>{if(!orchestrationSetupCurrent(epoch))return;orchestrationAdopt(run,itemId);if(run.request_id===orchestrationState.submission?.payload.request_id)orchestrationState.submission=null;orchestrationNode('settings').close();showAnalysisOrchestration();});host.append(button);
    }
    if(!data.runs?.length)host.append(orchestrationElement('p','保存済み実行はありません。'));
  }catch(error){if(orchestrationSetupCurrent(epoch))host.replaceChildren(orchestrationElement('p',error.message));}
}
function bindAnalysisOrchestration() {
  const overrideHost=orchestrationNode('role-overrides');
  for(const role of orchestrationRoles.filter(r=>r.kind==='ai')) {
    const row=orchestrationElement('div',undefined,'orchestration-form-grid');
    const provider=orchestrationElement('label',undefined,'field');provider.append(orchestrationElement('span',`${role.label}の実行先`));
    const select=orchestrationElement('select');select.id=`orchestration-provider-${role.id}`;
    for(const [value,label] of [['','共通設定'],['lmstudio','LM Studio（ローカル）'],['openai','OpenAI'],['google','Google Gemini']]){const option=orchestrationElement('option',label);option.value=value;select.append(option);}provider.append(select);
    const model=orchestrationElement('label',undefined,'field');model.append(orchestrationElement('span',`${role.label}のモデルID`));const input=orchestrationElement('input');input.id=`orchestration-model-${role.id}`;input.placeholder='空欄なら共通設定';input.maxLength=200;model.append(input);row.append(provider,model);overrideHost.append(row);
  }
  listen(orchestrationNode('open'),'click',openAnalysisOrchestrationSettings);
  listen(orchestrationNode('chip'),'click',showAnalysisOrchestration);
  listen(orchestrationNode('form'),'submit',startAnalysisOrchestration);
  listen(orchestrationNode('settings-close'),'click',()=>orchestrationNode('settings').close());
  listen(orchestrationNode('settings'),'close',()=>{if(!orchestrationNode('settings').open)++orchestrationState.setupEpoch;});
  listen(orchestrationNode('live-close'),'click',()=>orchestrationNode('live').close());
  listen(orchestrationNode('live'),'close',()=>{if(!orchestrationNode('live').open)++orchestrationState.viewerEpoch;});
  listen(orchestrationNode('stop'),'click',()=>orchestrationAction('cancel'));
  listen(orchestrationNode('resume'),'click',()=>orchestrationAction('resume'));
  listen(orchestrationNode('publication-retry'),'click',()=>orchestrationAction('publication/retry'));
  listen(orchestrationNode('abandon'),'click',orchestrationAbandonAndResume);
  listen(orchestrationNode('recovery-tasks'),'change',()=>orchestrationRenderRecovery(orchestrationState.run));
  listen(orchestrationNode('refresh'),'click',pollAnalysisOrchestration);
  listen(orchestrationNode('results'),'click',()=>orchestrationReadResults());
  listen(orchestrationNode('history'),'click',orchestrationHistory);
  listen(orchestrationNode('form'),'input',event=>{if(event.target.matches('select[id^="orchestration-provider"], #orchestration-provider'))orchestrationNode('cloud-consent').checked=false;orchestrationSyncForm();});
  listen(orchestrationNode('form'),'change',event=>{if(event.target.matches('select[id^="orchestration-provider"], #orchestration-provider'))orchestrationNode('cloud-consent').checked=false;orchestrationSyncForm();});
  const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  orchestrationNode('reduced-motion').checked=motion.matches;
  listen(orchestrationNode('reduced-motion'),'change',()=>orchestrationNode('live').classList.toggle('reduce-motion',orchestrationNode('reduced-motion').checked));
  motion.addEventListener?.('change',event=>{orchestrationNode('reduced-motion').checked=event.matches;orchestrationNode('live').classList.toggle('reduce-motion',event.matches);});
  orchestrationNode('live').classList.toggle('reduce-motion',motion.matches);
  let stored;try{stored=JSON.parse(sessionStorage.getItem(orchestrationStorageKey)||'null');}catch(_){/* unavailable */}
  if(stored?.itemId && stored?.runId){orchestrationState.itemId=stored.itemId;orchestrationState.runId=stored.runId;renderAnalysisOrchestration();pollAnalysisOrchestration();}
}
window.addEventListener('DOMContentLoaded',bindAnalysisOrchestration);
