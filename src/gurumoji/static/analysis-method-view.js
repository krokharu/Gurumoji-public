// Method-specific analysis view and classification controls.
// The expert's own account of a method: scope, conditions, procedure and literature.
function buildExpertDetails(expert, {open = false} = {}) {
  const box = analysisElement('details', 'analysis-expert');
  box.open = open;
  box.append(analysisElement('summary', '',
    `${expert.role || ''}の専門家：${expert.title || expert.method_id || '不明'}（${expert.status_label || ''}・${expert.selection_label || ''}）`));
  const school = (expert.school || {}).default || {};
  if (school.label) {
    box.append(analysisElement('p', 'analysis-caption', `採用する流派：${school.label} / 分析単位：${expert.analysis_unit || '—'}`));
  }
  const appendList = (heading, rows, ordered) => {
    if (!rows.length) return;
    const list = analysisElement(ordered ? 'ol' : 'ul', 'analysis-inline-list');
    rows.forEach(text => list.append(analysisElement('li', '', text)));
    box.append(analysisElement('strong', '', heading), list);
  };
  appendList('この手法で扱う範囲', expert.scope || []);
  appendList('担当外（引き継ぎ先）', (expert.out_of_scope || [])
    .map(item => item.handoff ? `${item.text}（${item.handoff}）` : item.text));
  appendList('満たさない・判定できない条件', (expert.checks || [])
    .filter(check => check.result === 'fail' || check.result === 'not_evaluable')
    .map(check => `${check.severity === 'block' && check.result === 'fail' ? '分析を始めない' : '要確認'}：${check.message}`));
  appendList('研究者が確認する項目', (expert.quality_checks || [])
    .filter(check => check.result === 'human').map(check => check.message));
  appendList('手順と担当', (expert.procedure || []).map(step => `${step.title}（${step.actor_label}）`), true);
  appendList('示してはいけない結論', expert.prohibited_conclusions || []);
  const references = (expert.references || []).map(item => item.id).join('、');
  if (references) {
    box.append(analysisElement('p', 'analysis-caption',
      `方法論の根拠：${references}（${expert.definition_note} 第${expert.definition_version}版、知識の確認日 ${expert.knowledge_verified}）`));
  }
  if ((expert.missing_references || []).length) {
    box.append(analysisElement('p', 'analysis-caption', `見つからない文献ノート：${expert.missing_references.join('、')}`));
  }
  if ((expert.open_issues || []).length) {
    box.append(analysisElement('p', 'analysis-caption', `専門家定義の未解決事項：${expert.open_issues.length}件`));
  }
  return box;
}

// Result panels are built by the existing views and tagged with their method, so the
// method view shows the same panels without a second implementation.
const METHOD_PANEL_SOURCES = {qualitative_coding: 'manual'};
const METHOD_EXTERNAL_NOTES = {
  outline: '議題・アウトラインの作成と編集は文字起こし画面で行います。',
  ai_finishing: 'AI仕上げの実行と変更記録の確認は文字起こし画面で行います。',
  kwic: '「自動分析」の文脈検索で語を検索すると、この手法の結果が出ます。'
};

function analysisMethodState() {
  if (!analysisState.methods || !isAnalysisContextCurrent(analysisState.methods.context)) {
    analysisState.methods = {context: captureAnalysisContext(), itemId: analysisState.itemId, loading: false, error: '', data: null, selected: ''};
  }
  return analysisState.methods;
}

function invalidateAnalysisMethodOverview() {
  analysisState.methods = null;
}

async function loadAnalysisMethodOverview() {
  const state = analysisMethodState();
  const itemId = analysisState.itemId;
  const owns = () => analysisState.methods === state && isAnalysisContextCurrent(state.context);
  if (!itemId || state.loading || state.data) return;
  state.loading = true;
  state.error = '';
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/methods`, {cache: 'no-store'});
    const payload = await readJsonResponse(response);
    if (!response.ok) throw new Error(payload.error || '手法別の分析状態を取得できませんでした。');
    if (!owns()) return;
    state.data = payload;
    const methods = Array.isArray(payload.methods) ? payload.methods : [];
    if (!methods.some(method => method.method_id === state.selected)) {
      state.selected = ((methods.find(method => method.produced) || methods[0] || {}).method_id) || '';
    }
  } catch (error) {
    if (!owns()) return;
    state.error = error.message;
  } finally {
    if (!owns()) return;
    state.loading = false;
    if (analysisState.itemId === itemId && analysisState.mode === 'methods') renderAnalysisWorkspace();
  }
}

function methodResultPanels(methodId, compact) {
  const scope = analysisState.automaticScope;
  analysisState.automaticScope = 'overall';
  try {
    const source = METHOD_PANEL_SOURCES[methodId] === 'manual'
      ? renderManualAnalysis(compact)
      : renderAutomaticAnalysis(compact);
    return [...source.querySelectorAll(`[data-analysis-method~="${methodId}"]`)];
  } finally {
    analysisState.automaticScope = scope;
  }
}

function localMethodPanels(method) {
  const result = method.details || {};
  const panel = analysisCardPanel(method.title, 'automatic', method.method_id, true, method.method_id);
  (method.summaries || []).forEach(row => panel.body.append(
    analysisElement('p', 'analysis-caption', `${row.title}：${row.text}`)));
  (method.limitations || []).forEach(text => panel.body.append(analysisElement('p', 'content-inline-notice', text)));
  panel.body.append(analysisElement('p', 'analysis-caption', `手法版：${method.method_version || '不明'}`));
  const labels = {
    speaker_name: '話者', incoming: '受取回数', outgoing: '受渡回数', reciprocity: '相互性',
    outgoing_bias: '受渡先の偏り', strength_centrality: '重み付き中心性',
    from_speaker: '渡した話者', to_speaker: '受けた話者', weight: '回数',
    speaker_count: '話者数', transition_count: '交替回数', missing_time_count: '時刻不明の発話数',
    unknown_speaker_count: '話者未確認の発話数', term: '語', term_a: '語A', term_b: '語B',
    community: 'まとまり', degree: '接続語数', strength: '共起回数の合計', terms: '語の一覧', term_count: '語数',
    label: 'コード・確認候補', segment_count: '発話数', mean_similarity: '平均類似度', unscorable_count: '算出不能数',
    segment_id: '発話ID', code_ids: '現在のコード', nearest_other_code: '近い別コード',
    own_similarity: '自コード類似度', other_similarity: '別コード類似度', max_similarity: '最大類似度', text: '本文'
  };
  const names = {response_nodes: '話者ごとの指標', response_edges: '発話の受け渡し', response_summary: '対象と分母',
    cooccurrence_nodes: '中心語', cooccurrence_edges: '語の共起', cooccurrence_communities: '語のまとまり',
    consistency_codes: 'コードごとのまとまり', coding_consistency: '要確認の発話'};
  const flags = {closer_other_code: '別コードにより近い', far_from_all_codes: 'すべてのコードから遠い'};
  for (const [name, rows] of Object.entries(result.tables || {})) {
    const section = analysisElement('section', 'analysis-panel');
    section.append(analysisElement('h3', '', `${names[name] || name}（${rows.length}件）`));
    if (!rows.length) section.append(analysisElement('p', 'analysis-no-data',
      result.status === 'completed' ? '該当する行はありません。' : '適用条件を満たす結果はありません。'));
    if (rows.length) {
      const fields = (result.card?.output_fields?.[name] || Object.keys(rows[0])).filter(key => key in labels);
      const box = analysisElement('div', 'analysis-table-scroll');
      const table = analysisElement('table', 'analysis-table');
      const head = analysisElement('tr');
      [...fields.map(key => labels[key]), '原文'].forEach(label => head.append(analysisElement('th', '', label)));
      const thead = analysisElement('thead');
      thead.append(head);
      const body = analysisElement('tbody');
      let count = 0;
      const more = contentButton('さらに10件を表示', appendNext);
      function appendNext() {
        rows.slice(count, count + 10).forEach(row => {
          const tr = analysisElement('tr');
          fields.forEach(key => {
            let value = row[key];
            if (key === 'label') value = String(value || '').split(';').map(v => flags[v] || v).join('・');
            if (Array.isArray(value)) value = value.join('、');
            if (typeof value === 'number' && !Number.isInteger(value)) value = value.toFixed(4);
            tr.append(analysisElement('td', '', value == null ? '算出不能' : String(value)));
          });
          const evidence = analysisElement('td');
          const ids = row.segment_ids || row.evidence_segment_ids || [];
          if (ids.length) evidence.append(evidenceDetails(ids));
          tr.append(evidence);
          body.append(tr);
        });
        count += 10;
        more.hidden = count >= rows.length;
      }
      table.append(thead, body);
      box.append(table);
      section.append(box, more);
      appendNext();
    }
    panel.body.append(section);
  }
  if (result.engine?.parser?.status === 'fallback') panel.body.append(analysisElement('p', 'content-inline-notice',
    '簡易解析による語の分割を使用しています。正式解析の結果とは分けて確認してください。'));
  if (result.coverage?.cooccurrence_truncated) panel.body.append(analysisElement('p', 'content-inline-notice',
    `共起表は上位${result.coverage.cooccurrence_returned_rows}辺に限定されています（候補${result.coverage.cooccurrence_total_rows}辺）。`));
  if (result.coverage?.unscorable_segment_count) panel.body.append(analysisElement('p', 'content-inline-notice',
    `重心がゼロで比較できない発話：${result.coverage.unscorable_segment_count}件。確認候補なしとは扱いません。`));
  return [panel.panel];
}

function buildMethodDetail(method, overview, compact) {
  const nodes = [];
  const header = analysisElement('div', `analysis-method-header ${method.verdict}`);
  header.append(
    analysisElement('h3', '', method.title),
    analysisElement('p', 'analysis-method-verdict', `${method.verdict_label}（結果の状態：${method.status_label}）`)
  );
  if (method.verdict_reason) header.append(analysisElement('p', 'analysis-section-help', method.verdict_reason));
  const counts = Object.entries(method.result_counts || {});
  if (counts.length) {
    const metrics = analysisElement('div', 'analysis-mini-metrics');
    counts.forEach(([dataset, total]) => appendAnalysisMetric(metrics, dataset, `${total}件`));
    header.append(metrics);
  }
  header.append(analysisElement('p', 'analysis-caption', `分析単位：${method.analysis_unit || '—'}`));
  nodes.push(header);

  const expert = (overview.experts || {})[method.expert_id];
  if (expert) {
    if (method.expert_scope === 'preconditions') {
      nodes.push(analysisElement('p', 'analysis-section-help',
        'この手法の結果がないため、結果に対する判定ではなく、実行前に満たす条件を表示しています。'));
    }
    nodes.push(buildExpertDetails(expert));
  } else if (method.expert_note) {
    nodes.push(analysisElement('p', 'analysis-section-help', method.expert_note));
  }
  if (METHOD_EXTERNAL_NOTES[method.method_id]) {
    nodes.push(analysisElement('p', 'analysis-section-help', METHOD_EXTERNAL_NOTES[method.method_id]));
  }

  const panels = ['response_network', 'cooccurrence_network', 'coding_consistency'].includes(method.method_id)
    ? localMethodPanels(method) : methodResultPanels(method.method_id, compact);
  if (panels.length) nodes.push(...panels);
  else if (method.produced) nodes.push(analysisElement('p', 'analysis-no-data', 'この手法の結果は保存記録とCSVで確認します。'));
  else nodes.push(analysisElement('p', 'analysis-no-data', 'まだ結果がありません。上の条件を確認してから実行してください。'));

  if ((method.limitations || []).length) {
    const details = analysisElement('details', 'analysis-cautions');
    details.append(analysisElement('summary', '', '限界と追加確認'));
    const list = analysisElement('ul');
    method.limitations.forEach(value => list.append(analysisElement('li', '', value)));
    details.append(list);
    nodes.push(details);
  }
  const exportBox = analysisElement('div', 'analysis-inline-exports');
  (method.datasets || []).forEach(dataset => {
    const link = analysisExportLink(`${dataset} CSV`, dataset, 'analysis-inline-export');
    if (link) exportBox.append(link);
  });
  if (exportBox.childNodes.length) nodes.push(exportBox);
  return nodes;
}

function renderMethodAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const state = analysisMethodState();
  const intro = analysisElement('div', 'analysis-result-intro');
  intro.append(
    analysisElement('span', 'analysis-kind automatic', '手法別'),
    analysisElement('h2', '', '分析手法ごとの結果と担当専門家'),
    analysisElement('p', '', '手法ごとに、結果が出ているか、担当の専門家が示す適用条件を満たしているかを確認します。判定は保存済みのデータに対するもので、解釈の妥当性を保証しません。')
  );
  const refresh = analysisElement('button', 'secondary-button compact-button', '↻ 手法別の状態を再取得');
  refresh.type = 'button';
  refresh.dataset.analysisMethodsRefresh = 'true';
  intro.append(refresh);
  fragment.append(intro);

  if (state.error) {
    fragment.append(analysisElement('p', 'content-inline-notice', state.error));
    return fragment;
  }
  if (!state.data) {
    loadAnalysisMethodOverview();
    fragment.append(analysisElement('p', 'analysis-section-help', '手法別の状態を読み込んでいます…'));
    return fragment;
  }

  const overview = state.data;
  const methods = new Map((overview.methods || []).map(method => [method.method_id, method]));
  const summary = analysisElement('div', 'analysis-method-summary');
  [
    ['ok', '結果あり・条件を満たす'], ['check', '結果あり・要確認'], ['stop', '結果あり・この条件では使わない'],
    ['no_expert', '結果あり・担当専門家なし'], ['none', '結果なし']
  ].forEach(([key, label]) => {
    const chip = analysisElement('span', `analysis-method-chip ${key}`);
    chip.append(
      analysisElement('strong', '', String((overview.summary || {})[key] || 0)),
      analysisElement('small', '', label)
    );
    summary.append(chip);
  });
  fragment.append(summary);

  const layout = analysisElement('div', 'analysis-method-layout');
  const list = analysisElement('nav', 'analysis-method-list');
  list.setAttribute('aria-label', '分析手法の選択');
  (overview.groups || []).forEach(group => {
    const section = analysisElement('section', 'analysis-method-group');
    section.append(analysisElement('h3', '', group.title));
    (group.method_ids || []).forEach(methodId => {
      const method = methods.get(methodId);
      if (!method) return;
      const button = analysisElement('button', `analysis-method-button ${method.verdict}`);
      button.type = 'button';
      button.dataset.analysisMethodSelect = methodId;
      if (methodId === state.selected) {
        button.classList.add('active');
        button.setAttribute('aria-current', 'true');
      }
      button.append(
        analysisElement('strong', '', method.title),
        analysisElement('span', 'analysis-method-verdict', method.verdict_label),
        analysisElement('small', '', method.verdict_reason || method.status_label)
      );
      section.append(button);
    });
    list.append(section);
  });
  layout.append(list);

  const detail = analysisElement('div', 'analysis-method-detail');
  const selected = methods.get(state.selected) || (overview.methods || [])[0];
  if (selected) buildMethodDetail(selected, overview, compact).forEach(node => detail.append(node));
  else detail.append(analysisElement('p', 'analysis-no-data', '表示できる手法がありません。'));
  layout.append(detail);
  fragment.append(layout);
  return fragment;
}

function buildSegmentClassificationPanel(compact) {
  const state = (analysisState.data || {}).segment_classification || {};
  const result = state.result || null;
  const summary = state.summary || {};
  const panel = analysisCardPanel(
    '発話種別・重要度・要確認・機密らしさ', 'automatic',
    'segment_classifications', true, 'segment_classification'
  );
  panel.body.append(analysisElement(
    'p', 'analysis-section-help',
    'テンプレート規則、Jev（LLM）、既存Transformer話題を別々の提案として比較します。自動値は手動確定値を上書きしません。'
  ));
  if (state.stale) panel.body.append(analysisElement(
    'p', 'analysis-orphan-warning', '文字起こし、コードブック、手動分析、またはTransformer結果が変わったため再実行が必要です。'
  ));
  const metrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(metrics, '対象', `${summary.segment_count || 0}発話`);
  appendAnalysisMetric(metrics, '手動確認済み', `${summary.manual_reviewed_count || 0}件`);
  appendAnalysisMetric(metrics, 'Jev重要度 高', `${summary.high_importance_count || 0}件`);
  appendAnalysisMetric(metrics, 'Jev要確認 高', `${summary.high_review_count || 0}件`);
  appendAnalysisMetric(metrics, 'Jev機密らしさ 高', `${summary.high_sensitivity_count || 0}件`);
  panel.body.append(metrics);

  const actions = analysisElement('div', 'segment-classification-actions');
  const run = analysisElement(
    'button', 'primary-button small',
    segmentClassificationBusy() ? 'Jevで判定中…' : 'テンプレート＋Jev＋Transformerで判定'
  );
  run.type = 'button';
  run.disabled = segmentClassificationBusy() || hasUnsavedAnalysisChanges();
  run.dataset.runSegmentClassification = 'true';
  actions.append(run);
  if (hasUnsavedAnalysisChanges()) actions.append(analysisElement('small', '', '設定・手動変更・準備記録を保存してから実行してください。'));
  panel.body.append(actions);

  const rows = result && Array.isArray(result.segments) ? result.segments : [];
  if (!rows.length) {
    panel.body.append(analysisElement('p', 'analysis-no-data', `分類結果はまだありません。この欄の「テンプレート＋Jev＋Transformerで判定」から${summary.segment_count || 0}発話を一括判定できます。`));
  } else {
    const ranked = [...rows].sort((a, b) => {
      const score = row => Math.max(
        Number((row.llm || {}).importance_score) || 0,
        Number((row.llm || {}).review_score) || 0,
        Number((row.llm || {}).sensitivity_score) || 0
      );
      return score(b) - score(a) || Number(a.utterance_order || 0) - Number(b.utterance_order || 0);
    }).slice(0, compact ? 8 : 20);
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['発話', '話者', 'テンプレート', 'Jev', 'Transformer話題', '重要', '要確認', '機密'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    ranked.forEach(value => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', `#${value.utterance_order || '—'}`),
        analysisElement('td', '', value.speaker_name || value.speaker || '—'),
        analysisElement('td', '', (value.template || {}).dialogue_act_label || '—'),
        analysisElement('td', '', (value.llm || {}).dialogue_act_label || '—'),
        analysisElement('td', '', (value.transformer || {}).topic_label || '—'),
        analysisElement('td', '', (value.llm || {}).importance_score ?? '—'),
        analysisElement('td', '', (value.llm || {}).review_score ?? '—'),
        analysisElement('td', '', (value.llm || {}).sensitivity_score ?? '—')
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    panel.body.append(wrap, analysisElement('p', 'analysis-caption', '表は3スコアの高い順に表示。全件とクロス集計はCSVで出力できます。'));
  }
  const exports = analysisElement('div', 'segment-classification-actions');
  const rowsLink = analysisExportLink('全発話の比較CSV', 'segment_classifications', 'analysis-inline-export');
  const crossLink = analysisExportLink('クロス集計CSV', 'segment_classification_crosstabs', 'analysis-inline-export');
  if (rowsLink) exports.append(rowsLink);
  if (crossLink) exports.append(crossLink);
  panel.body.append(exports);
  return panel.panel;
}

async function runSegmentClassification({useJev = true, quiet = false} = {}) {
  if (!analysisState.itemId || !analysisState.data || segmentClassificationBusy() || hasUnsavedAnalysisChanges()) return;
  const context = captureAnalysisContext();
  const token = {};
  segmentClassificationRequests.set(context.itemId, token);
  const owns = () => segmentClassificationRequests.get(context.itemId) === token;
  const current = () => owns() && isAnalysisContextCurrent(context);
  renderAnalysisWorkspace();
  if (!quiet) setAlert(
    document.querySelector('#analysis-message'),
    useJev
      ? 'Jevへ発話本文と短い前後文脈を送り、分類候補を作成しています。'
      : 'テンプレートと保存済みTransformer結果から分類候補を作成しています。'
  );
  try {
    const item = context.data.item || {};
    const response = await apiFetch(`/api/library/${encodeURIComponent(context.itemId)}/analysis/classifications`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        request_id: createSubmissionId(),
        source_revision: Number(item.revision_count || 0),
        analysis_revision: Number(item.analysis_revision || 0),
        use_jev: Boolean(useJev)
      })
    });
    const payload = await readJsonResponse(response);
    if (!response.ok) throw new Error(payload.error || '発話分類を実行できませんでした。');
    if (!current()) return;
    context.data.segment_classification = payload.segment_classification;
    invalidateAnalysisMethodOverview();
    const warning = payload.archive_warning ? ` ${payload.archive_warning}` : '';
    if (!quiet) setAlert(document.querySelector('#analysis-message'), `発話分類を保存しました。${warning}`, Boolean(payload.archive_warning));
    return {ok: true, payload};
  } catch (error) {
    if (current() && !quiet) setAlert(document.querySelector('#analysis-message'), error.message, true);
    return {ok: false, error: error.message};
  } finally {
    const refresh = owns() && analysisState.itemId === context.itemId;
    if (owns()) segmentClassificationRequests.delete(context.itemId);
    if (refresh) renderAnalysisWorkspace();
  }
}
