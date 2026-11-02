/* Content exploration shares the existing analysis workspace and saved revisions. */
const contentAnalysisStates = new Map();
let contentAnalysisPollTimer = null;
let contentAnalysisPollSequence = 0;
let transformerAnalysisPollTimer = null;
let transformerAnalysisPollSequence = 0;
let analysisEvidenceReturn = null;
let analysisEvidenceRequest = 0;
const insightCategoryLabels = {
  overview: '総合的な見解', themes: '主要テーマ', shared: '共通する意見',
  differences: '異なる意見・少数意見', questions: '追加で確認する点'
};

function contentAnalysisState() {
  const id = analysisState.itemId;
  if (!contentAnalysisStates.has(id) || !isAnalysisContextCurrent(contentAnalysisStates.get(id).context)) {
    const previous = contentAnalysisStates.get(id);
    const preferences = {};
    for (const key of ['query', 'mode', 'speaker', 'provider', 'maxTopics', 'minTopicSize', 'topicCount', 'transformerMode', 'manualMinSimilarity', 'semanticQuery']) {
      if (previous && Object.prototype.hasOwnProperty.call(previous, key)) preferences[key] = previous[key];
    }
    contentAnalysisStates.set(id, {context: captureAnalysisContext(),
      query: '', mode: 'normalized', speaker: '', offset: 0, result: null,
      loading: false, error: '', sequence: 0, controller: null,
      provider: 'openai', run: null, aiError: '', pollError: '', starting: false, fingerprint: '',
      transformerRun: null, transformerStarting: false, transformerError: '', transformerPollError: '',
      maxTopics: 8, minTopicSize: 2, topicCount: 0, transformerMode: 'auto',
      manualMinSimilarity: 0, semanticQuery: '', semanticHits: null,
      semanticLoading: false, semanticError: '', ...preferences
    });
  }
  return contentAnalysisStates.get(id);
}

function contentButton(label, action, className = 'secondary-button compact-button') {
  const button = analysisElement('button', className, label);
  button.type = 'button';
  button.addEventListener('click', action);
  return button;
}

function currentAnalysisContent() {
  return window.matchMedia('(max-width: 959px)').matches ? analysisMobileContent : analysisDesktopContent;
}

function jumpToContentSearch() {
  selectAnalysisPage('content');
  currentAnalysisContent()?.querySelector('[data-analysis-anchor="content"]')?.scrollIntoView({block: 'start'});
}

function analysisEvidenceTimeValid(segment) {
  return Boolean(segment && !segment.time_unknown
    && typeof segment.start === 'number' && Number.isFinite(segment.start)
    && typeof segment.end === 'number' && Number.isFinite(segment.end)
    && segment.start >= 0 && segment.end >= segment.start);
}

function evidenceDetails(ids, {snapshot = null, stale = false} = {}) {
  const lookup = snapshot || Object.fromEntries((analysisState.data?.segments || [])
    .filter(s => !s.excluded).map(s => [s.id, s]));
  const details = analysisElement('details', 'content-evidence');
  details.append(analysisElement('summary', '', `根拠の発話を確認（${ids.length}件）`));
  const body = analysisElement('div', 'content-evidence-list');
  let count = 0;
  const more = contentButton('さらに10件を表示', appendNext);
  function appendNext() {
    const next = ids.slice(count, count + 10);
    count += next.length;
    next.forEach(id => {
      const segment = lookup[id];
      if (!segment) { body.insertBefore(analysisElement('p', 'content-inline-notice', `根拠発話 ${id} は保存資料にありません。`), more); return; }
      const article = analysisElement('blockquote', 'analysis-important-quote');
      article.append(analysisElement('p', '', segment.text || '（本文なし）'));
      const footer = analysisElement('footer', '',
        `${segment.speaker_name || segment.speaker} / ${analysisEvidenceTimeValid(segment) ? `${formatTime(segment.start)}–${formatTime(segment.end)}` : '時刻不明'}`);
      if (stale) footer.append(analysisElement('span', '', ' / 生成時点の引用'));
      else if (analysisEvidenceTimeValid(segment)) footer.append(contentButton('音声で確認', () => openInsightMedia(segment)));
      else footer.append(analysisElement('span', '', ' / 音声再生不可：有効な開始・終了時刻がありません。'));
      article.append(footer);
      body.insertBefore(article, more);
    });
    more.hidden = count >= ids.length;
  }
  body.append(more);
  details.append(body);
  details.addEventListener('toggle', () => { if (details.open && !count) appendNext(); });
  return details;
}

async function openInsightMedia(segment) {
  const itemId = analysisState.itemId;
  const context = captureAnalysisContext();
  const request = ++analysisEvidenceRequest;
  const isCurrent = () => request === analysisEvidenceRequest && isAnalysisContextCurrent(context);
  analysisEvidenceReturn = {itemId, scroll: window.scrollY, mode: analysisState.mode,
    scope: analysisState.automaticScope, selectedSpeaker: analysisState.selectedSpeaker,
    catalog: analysisCatalog.slice()};
  try {
    if (!analysisEvidenceTimeValid(segment)) throw new Error('音声再生不可：保存された根拠の時刻が不明または不正です。');
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}`);
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '元データを取得できませんでした。');
    if (!isCurrent()) return;
    const current = (data.segments || []).find(s => s.id === segment.id);
    if (!analysisEvidenceTimeValid(current)) throw new Error('音声再生不可：現在の発話の時刻が不明または不正です。');
    if (!current || String(current.text || '') !== String(segment.text || '')
      || String(current.speaker || 'UNKNOWN') !== String(segment.speaker || 'UNKNOWN')
      || Math.abs(Number(current.start) - Number(segment.start)) > .001
      || Math.abs(Number(current.end) - Number(segment.end)) > .001) {
      throw new Error('この発話は更新されています。分析を再集計してから確認してください。');
    }
    renderResult(data);
    const back = document.querySelector('#return-to-analysis-evidence');
    if (back) back.hidden = false;
    selectedSegmentId = segment.id;
    document.querySelector('#segment-keyword').value = '';
    document.querySelector('#segment-speaker-filter').value = '';
    document.querySelector('#segment-emotion-filter').value = '';
    renderSegments();
    if (mediaPlayer) playSegment(segment.id);
    else {
      const row = [...document.querySelectorAll('.segment')].find(el => el.dataset.segmentId === segment.id);
      row?.scrollIntoView({block: 'center'});
      setAlert(document.querySelector('#save-message'), '元の音声・動画が利用できないため、発話本文を表示しています。');
    }
  } catch (error) {
    if (!isCurrent()) return;
    setAlert(document.querySelector('#analysis-message'), error.message, true);
  }
}

function restoreAnalysisEvidencePosition() {
  const saved = analysisEvidenceReturn;
  if (!saved || saved.itemId !== analysisState.itemId || analysisCard.hidden) return;
  const changed = analysisState.mode !== saved.mode || analysisState.automaticScope !== saved.scope
    || analysisState.selectedSpeaker !== saved.selectedSpeaker;
  analysisState.mode = saved.mode;
  analysisState.automaticScope = saved.scope;
  analysisState.selectedSpeaker = saved.selectedSpeaker;
  analysisEvidenceReturn = null;
  if (changed) renderAnalysisWorkspace();
  requestAnimationFrame(() => window.scrollTo({top: saved.scroll, behavior: 'instant'}));
}

function returnToAnalysisEvidence() {
  if (analysisEvidenceReturn) openAnalysisForItem(analysisEvidenceReturn.itemId);
}

function contentTermButton(term, speaker = '') {
  const button = contentButton(term, () => {
    const state = contentAnalysisState();
    Object.assign(state, {query: term, mode: 'normalized', speaker, offset: 0});
    analysisState.mode = 'automatic';
    analysisState.automaticScope = 'overall';
    renderAnalysisWorkspace();
    searchContentKwic();
    jumpToContentSearch();
  }, 'content-term-button');
  button.setAttribute('aria-label', `「${term}」を文脈検索`);
  return button;
}

function appendSearchableTermBar(container, term, value, detail, color = '#1C6B50', speaker = '') {
  appendAnalysisBar(container, term, value, detail, color);
  const label = container.lastElementChild?.querySelector('strong');
  if (label) label.replaceWith(contentTermButton(term, speaker));
}

function buildInsightSummary() {
  const panel = analysisCardPanel('分析結果の見解', 'automatic', 'insights', true, 'local_insights ai_insights');
  panel.panel.classList.add('content-insight-summary');
  const local = analysisState.data?.insights?.local || [];
  panel.body.append(analysisElement('p', 'analysis-caption',
    '保存済みデータから読み取れる傾向です。根拠を開き、発話の文脈を確認できます。'));
  if (analysisState.data?.research?.linguistics?.engine?.status === 'fallback') {
    panel.body.append(analysisElement('p', 'content-inline-notice', '簡易分割による参考表示です。ひらがなだけの断片は見解・特徴語の対象外です。語の区切りは原文で確認してください。'));
  }
  if (!local.length) panel.body.append(analysisElement('p', 'analysis-no-data', '見解をまとめられる内容語や保存済みコード・重要引用がありません。文脈検索から原文を確認できます。'));
  local.slice(0, 5).forEach(finding => {
    const article = analysisElement('article', 'content-finding');
    article.append(analysisElement('h3', '', finding.title), analysisElement('p', '', finding.text));
    const names = (finding.speakers || []).map(id => (analysisState.data.segments || []).find(s => s.speaker === id)?.speaker_name || id);
    article.append(analysisElement('small', 'content-finding-meta', `${finding.count}発話 / ${names.join('、')}`));
    if (finding.term) article.append(contentTermButton(finding.term, finding.speaker || ''));
    article.append(evidenceDetails(finding.segment_ids || []));
    panel.body.append(article);
  });
  const ai = analysisElement('details', 'content-ai-section');
  ai.append(analysisElement('summary', '', 'AIで内容・意見を整理'));
  const toolbar = analysisElement('div', 'content-ai-toolbar');
  const label = analysisElement('label', 'field');
  label.append(analysisElement('span', '', '見解を生成するAI'));
  const select = analysisElement('select');
  select.dataset.insightProvider = 'true';
  select.add(new Option('OpenAI', 'openai'));
  select.add(new Option('Google Gemini', 'google'));
  select.add(new Option('LM Studio（ローカル）', 'lmstudio'));
  select.value = contentAnalysisState().provider;
  select.addEventListener('change', () => {
    contentAnalysisState().provider = select.value;
    document.querySelectorAll('[data-insight-provider]').forEach(peer => { peer.value = select.value; });
  });
  label.append(select);
  const generate = contentButton('AIで見解を作成', startContentInsights, 'primary-button small');
  generate.dataset.insightGenerate = 'true';
  const cancel = contentButton('生成を中止', cancelContentInsights);
  cancel.dataset.insightCancel = 'true';
  toolbar.append(label, generate, cancel);
  const status = analysisElement('p', 'content-ai-status');
  status.dataset.insightStatus = 'true';
  status.setAttribute('role', 'status');
  const output = analysisElement('div', 'content-ai-output');
  output.dataset.insightOutput = 'true';
  ai.append(toolbar, analysisElement('p', 'analysis-caption', '保存済みの発話本文・話者名／役割・研究質問・コード・重要フラグを選択したAIへ送信します。設定時は専門家の短い説明・手順情報も含みます。LM Studioは設定された接続先で処理します。生成した見解は下書きです。'));
  panel.body.append(ai, status, output);
  // Render after the panel is attached by renderAnalysisWorkspace.
  return panel.panel;
}

function buildContentExplorer() {
  const container = analysisElement('section', 'content-explorer');
  container.dataset.analysisAnchor = 'content';
  const panel = analysisCardPanel('言葉を前後の文脈で読む', 'automatic', '', true, 'kwic');
  const state = contentAnalysisState();
  const form = analysisElement('form', 'content-kwic-form');
  const queryLabel = analysisElement('label', 'field');
  queryLabel.append(analysisElement('span', '', '気になる語・表現'));
  const query = analysisElement('input');
  query.type = 'search'; query.maxLength = 200; query.value = state.query;
  query.placeholder = '例：改善、使いにくい'; query.dataset.kwicQuery = 'true';
  query.addEventListener('input', () => {
    const state = contentAnalysisState();
    state.query = query.value;
    document.querySelectorAll('[data-kwic-query]').forEach(peer => { peer.value = query.value; });
  });
  queryLabel.append(query);
  const modeLabel = analysisElement('label', 'field');
  modeLabel.append(analysisElement('span', '', '一致条件'));
  const matchMode = analysisElement('select');
  matchMode.dataset.kwicMode = 'true';
  [['normalized', '正規化語の完全一致'], ['surface', '表層語の完全一致'], ['literal', '部分文字列']]
    .forEach(([value, label]) => matchMode.add(new Option(label, value)));
  matchMode.value = state.mode;
  matchMode.addEventListener('change', () => {
    const state = contentAnalysisState();
    state.mode = matchMode.value;
    document.querySelectorAll('[data-kwic-mode]').forEach(peer => { peer.value = state.mode; });
  });
  modeLabel.append(matchMode);
  const speakerLabel = analysisElement('label', 'field');
  speakerLabel.append(analysisElement('span', '', '話者で絞り込む'));
  const speaker = analysisElement('select');
  speaker.dataset.kwicSpeaker = 'true'; speaker.add(new Option('すべての話者', ''));
  const speakers = new Map((analysisState.data?.segments || []).filter(s => !s.excluded).map(s => [s.speaker, s.speaker_name || s.speaker]));
  speakers.forEach((name, id) => speaker.add(new Option(name, id)));
  speaker.value = state.speaker;
  speaker.addEventListener('change', () => {
    const state = contentAnalysisState();
    state.speaker = speaker.value;
    document.querySelectorAll('[data-kwic-speaker]').forEach(peer => { peer.value = speaker.value; });
  });
  speakerLabel.append(speaker);
  const submit = analysisElement('button', 'primary-button small', '文脈を検索');
  submit.type = 'submit';
  form.append(queryLabel, modeLabel, speakerLabel, submit);
  form.addEventListener('submit', event => { event.preventDefault(); contentAnalysisState().offset = 0; searchContentKwic(); });
  const results = analysisElement('div', 'content-kwic-results');
  results.dataset.kwicResults = 'true';
  panel.body.append(form, results);
  container.append(panel.panel);

  const comparison = analysisCardPanel('話者別の特徴語比較', 'automatic', 'characteristic_terms', true, 'speaker_characteristics');
  comparison.body.append(analysisElement('p', 'analysis-caption', 'その話者と他の話者の「語を含む発話の割合」の差を比較します。分母は本文のある対象発話です。少数の発話では差が大きく出るため、件数と原文も確認してください。'));
  const rows = analysisState.data?.research?.content?.characteristic_terms || [];
  if (!rows.length) comparison.body.append(analysisElement('p', 'analysis-no-data', '比較できる話者や、出現率に差のある語がありません。'));
  const groups = new Map();
  rows.forEach(row => {
    if (!groups.has(row.speaker)) groups.set(row.speaker, []);
    groups.get(row.speaker).push(row);
  });
  groups.forEach(values => {
    const details = analysisElement('details', 'content-speaker-terms');
    details.open = groups.size === 1;
    details.append(analysisElement('summary', '', `${values[0].speaker_name} / ${values[0].total}発話`));
    values.forEach(row => {
      const line = analysisElement('div', 'content-comparison-row');
      line.append(contentTermButton(row.term, row.speaker),
        analysisElement('span', '', `本人 ${row.count}/${row.total}（${Number(row.percent).toFixed(1)}%） / 他 ${row.other_count}/${row.other_total}（${Number(row.other_percent).toFixed(1)}%）`),
        analysisElement('strong', '', `+${Number(row.difference_pp).toFixed(1)}ポイント`));
      details.append(line);
    });
    comparison.body.append(details);
  });
  container.append(comparison.panel);
  return container;
}

function transformerRunActive(run) {
  return run && ['queued', 'running', 'cancelling'].includes(run.status);
}

function transformerPendingKey(itemId) { return `gurumoji.transformerRequest.${itemId}`; }

function transformerExportLinks() {
  const wrap = analysisElement('div', 'analysis-inline-exports');
  [
    ['transformer_topics', 'テーマCSV'],
    ['transformer_assignments', '発話分類CSV'],
    ['transformer_speakers', '話者比較CSV'],
    ['transformer_timeline', '時間推移CSV'],
    ['transformer_input_coverage', '入力・切詰め範囲CSV'],
    ['transformer_outliers', '例外候補CSV'],
    ['transformer_backchannels', '相づち対応CSV'],
    ['transformer_backchannel_speakers', '相づち集計CSV'],
    ['transformer_backchannel_rates', '相づち応答率CSV'],
    ['transformer_backchannel_tests', '相づち統計検定CSV'],
    ['transformer_speaker_results', '話者別リザルトCSV']
  ].forEach(([dataset, label]) => {
    const link = analysisExportLink(label, dataset, 'analysis-inline-export');
    if (link) wrap.append(link);
  });
  return wrap;
}

function transformerModeValue(state) {
  return ['auto', 'candidate', 'manual'].includes(state.transformerMode) ? state.transformerMode : 'auto';
}

function transformerCandidates(result) {
  const rows = result && result.quality ? result.quality.cluster_candidates : null;
  return Array.isArray(rows) ? rows.filter(row => row && Number(row.topic_count) >= 2) : [];
}

function suggestedCandidateCount(result) {
  const rows = transformerCandidates(result);
  if (!rows.length) return 0;
  return Number(result?.coverage?.topic_count) || Number(rows[0].topic_count) || 0;
}

// The researcher's own theme definitions live in the saved analysis config.
function manualTransformerTopics(fromServer = false) {
  const source = fromServer ? analysisState.data?.config : analysisState.config;
  const rows = source ? source.transformer_topics : null;
  return Array.isArray(rows) ? rows : [];
}

function buildTransformerCandidateList(result, state) {
  const box = analysisElement('div', 'transformer-candidates');
  const rows = transformerCandidates(result);
  if (!rows.length) {
    box.append(analysisElement('p', 'analysis-caption',
      '候補一覧はまだありません。画面上部の「分析を実行」からテーマ分析を行うと、テーマ数ごとのsilhouetteが出ます。候補モードでは、指定した件数で作り直したうえで候補一覧も作ります。'));
    return box;
  }
  const validRows = rows.filter(row => row.status !== 'invalid_topic_count' && row.silhouette_cosine != null);
  const best = validRows.reduce(
    (left, right) => (!left || Number(right.silhouette_cosine) > Number(left.silhouette_cosine) ? right : left),
    null);
  box.append(analysisElement('p', 'analysis-caption',
    'テーマ数ごとのsilhouette（cosine）です。まとまりの幾何的な指標であり、テーマの意味の妥当性ではありません。選んで実行すると、保存済みの意味ベクトルを再利用して作り直します。'));
  const wrap = analysisElement('div', 'analysis-table-wrap');
  const table = analysisElement('table', 'analysis-table');
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  ['テーマ数', 'silhouette', '選択'].forEach(label => headRow.append(analysisElement('th', '', label)));
  head.append(headRow);
  const body = document.createElement('tbody');
  rows.forEach(row => {
    const count = Number(row.topic_count);
    const line = document.createElement('tr');
    line.dataset.transformerCandidate = String(count);
    if (count === Number(state.topicCount)) line.classList.add('selected');
    const invalid = row.status === 'invalid_topic_count';
    const countCell = analysisElement('td', '', `${count}件${invalid ? ` / 不成立（実際${row.actual_topic_count}件）` : ''}`);
    if (best && count === Number(best.topic_count)) countCell.append(analysisElement('small', '', ' / 自動の選択'));
    const scoreCell = analysisElement('td', '',
      row.silhouette_cosine == null ? '—' : Number(row.silhouette_cosine).toFixed(3));
    const pickCell = analysisElement('td');
    const pick = contentButton('選ぶ', () => {
      if (analysisState.data?.transformer?.result !== result) return;
      const state = contentAnalysisState();
      state.topicCount = count;
      document.querySelectorAll('[data-transformer-topic-count]').forEach(peer => { peer.value = String(count); });
      document.querySelectorAll('[data-transformer-candidate]').forEach(peer => {
        peer.classList.toggle('selected', Number(peer.dataset.transformerCandidate) === count);
      });
      refreshTransformerControls();
    });
    pick.dataset.transformerCandidatePick = String(count);
    pick.disabled = invalid;
    pickCell.append(pick);
    line.append(countCell, scoreCell, pickCell);
    body.append(line);
  });
  table.append(head, body);
  wrap.append(table);
  box.append(wrap);
  return box;
}

function buildTransformerManualTopics(state) {
  const box = analysisElement('div', 'transformer-manual-topics');
  box.append(analysisElement('p', 'analysis-caption',
    '研究者が定義したテーマへ、意味が最も近い発話を割り当てます。テーマ名だけでも実行できますが、手がかり語やシード発話IDを使うと、定義した意味に近い発話を探索できます。安定性は別途検証が必要です。編集後は「設定とコードを保存」を押してから実行します。割り当ては候補であり、テーマの妥当性を確かめた結果ではありません。'));
  const topics = manualTransformerTopics();
  if (!topics.length) {
    box.append(analysisElement('p', 'analysis-no-data', 'テーマが定義されていません。2件以上を追加してください。'));
  }
  topics.forEach((topic, index) => {
    const row = analysisElement('article', 'transformer-manual-topic');
    const labelField = analysisElement('label', 'field');
    labelField.append(analysisElement('span', '', `テーマ${index + 1}の名前`));
    const label = analysisElement('input');
    label.type = 'text';
    label.maxLength = 120;
    label.value = topic.label || '';
    label.addEventListener('input', () => {
      topic.label = label.value;
      setAnalysisDirty(true);
      refreshTransformerControls();
    });
    labelField.append(label);
    const cueField = analysisElement('label', 'field');
    cueField.append(analysisElement('span', '', '手がかり語（読点・カンマ区切り）'));
    const cues = analysisElement('input');
    cues.type = 'text';
    cues.maxLength = 400;
    cues.value = (topic.cues || []).join('、');
    cues.placeholder = '例：価格、費用、予算';
    cues.addEventListener('input', () => {
      topic.cues = cues.value.split(/[,、;\s]+/).map(value => value.trim()).filter(Boolean).slice(0, 20);
      setAnalysisDirty(true);
      refreshTransformerControls();
    });
    cueField.append(cues);
    const seedField = analysisElement('label', 'field');
    seedField.append(analysisElement('span', '', 'シード発話ID（任意・区切り入力）'));
    const seeds = analysisElement('input');
    seeds.type = 'text';
    seeds.maxLength = 800;
    seeds.value = (topic.seed_segment_ids || []).join(' ');
    seeds.placeholder = '根拠の発話IDを貼り付け';
    seeds.addEventListener('input', () => {
      topic.seed_segment_ids = seeds.value.split(/[,、;\s]+/)
        .map(value => value.trim()).filter(Boolean).slice(0, 50);
      setAnalysisDirty(true);
      refreshTransformerControls();
    });
    seedField.append(seeds);
    const remove = contentButton('このテーマを削除', () => {
      analysisState.config.transformer_topics = manualTransformerTopics()
        .filter((_, position) => position !== index);
      setAnalysisDirty(true);
      renderAnalysisWorkspace();
    });
    row.append(labelField, cueField, seedField, remove);
    box.append(row);
  });
  const planned = Array.isArray(analysisState.data?.plan_items) ? analysisState.data.plan_items : [];
  if (planned.length) {
    const labels = new Set(topics.map(topic => String(topic.label || '').trim()));
    const missing = planned.filter(item => !labels.has(String(item.text || '').trim()));
    const importPlan = contentButton(
      `質問ガイドから取り込む（未取り込み ${missing.length}／${planned.length}項目）`,
      () => {
        const rows = manualTransformerTopics();
        missing.slice(0, Math.max(0, 12 - rows.length)).forEach(item => {
          const id = self.crypto && self.crypto.randomUUID
            ? `topic_${self.crypto.randomUUID().replaceAll('-', '').slice(0, 16)}`
            : `topic_${Date.now()}_${Math.random().toString(16).slice(2, 6)}`;
          rows.push({id, label: item.text, cues: [], seed_segment_ids: [], memo: '質問ガイドから取り込み'});
        });
        analysisState.config.transformer_topics = rows;
        setAnalysisDirty(true);
        renderAnalysisWorkspace();
      }, 'secondary-button small');
    importPlan.disabled = !missing.length || topics.length >= 12;
    box.append(importPlan);
    box.append(analysisElement('p', 'analysis-caption',
      '予定した議題をそのままテーマにすると、項目ごとに「話された発話数」が出ます。見出しだけでも実行できますが、手がかり語を足すほど割り当ては安定します。'));
  }
  const add = contentButton('テーマを追加', () => {
    const rows = manualTransformerTopics();
    if (rows.length >= 12) return;
    const id = self.crypto && self.crypto.randomUUID
      ? `topic_${self.crypto.randomUUID().replaceAll('-', '').slice(0, 16)}`
      : `topic_${Date.now()}_${Math.random().toString(16).slice(2, 6)}`;
    rows.push({id, label: `テーマ ${rows.length + 1}`, cues: [], seed_segment_ids: [], memo: ''});
    analysisState.config.transformer_topics = rows;
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
  }, 'secondary-button small');
  add.disabled = topics.length >= 12;
  box.append(add);
  return box;
}

function buildTransformerAnalysisPanel() {
  const panel = analysisCardPanel('Transformerテーマ分析', 'configured', 'transformer_topics', true, 'transformer_topics');
  panel.panel.classList.add('transformer-analysis-panel');
  const state = contentAnalysisState();
  const transformer = analysisState.data?.transformer || {};
  const result = transformer.result;
  panel.body.append(analysisElement('p', 'analysis-caption',
    '短い相づちを除き、前後の文脈と話者量の偏りを補正して、多言語E5で発話をまとめます。テーマの決め方は、自動・候補から選ぶ・研究者が定義したテーマへの割り当ての3つです。初回はモデルをダウンロードします。意味の近さは賛否・合意・重要性を示しません。'));

  const toolbar = analysisElement('div', 'transformer-toolbar');
  const modeLabel = analysisElement('label', 'field');
  modeLabel.append(analysisElement('span', '', 'テーマの決め方'));
  const modeSelect = analysisElement('select');
  [['auto', '自動でまとめる'], ['candidate', '候補から選ぶ'], ['manual', '手動で定義する']]
    .forEach(([value, label]) => modeSelect.add(new Option(label, value)));
  modeSelect.value = transformerModeValue(state);
  modeSelect.dataset.transformerMode = 'true';
  modeSelect.addEventListener('change', () => {
    const state = contentAnalysisState();
    state.transformerMode = modeSelect.value;
    if (state.transformerMode === 'candidate' && !state.topicCount) {
      state.topicCount = suggestedCandidateCount(result) || 4;
    }
    if (state.transformerMode !== 'candidate') state.topicCount = 0;
    renderAnalysisWorkspace();
  });
  modeLabel.append(modeSelect);
  toolbar.append(modeLabel);
  const countLabel = analysisElement('label', 'field');
  countLabel.append(analysisElement('span', '', 'テーマ数'));
  const countSelect = analysisElement('select');
  // Every count the candidate list can offer is selectable here as well.
  Array.from({length: 11}, (_, index) => index + 2)
    .forEach(value => countSelect.add(new Option(`${value}件`, String(value))));
  countSelect.value = String(state.topicCount || 4);
  // Keep the request in step with what the control shows.
  if (transformerModeValue(state) === 'candidate') state.topicCount = Number(countSelect.value);
  countSelect.dataset.transformerTopicCount = 'true';
  countSelect.addEventListener('change', () => {
    const state = contentAnalysisState();
    state.topicCount = Number(countSelect.value);
    document.querySelectorAll('[data-transformer-topic-count]').forEach(peer => { peer.value = countSelect.value; });
    document.querySelectorAll('[data-transformer-candidate]').forEach(row => {
      row.classList.toggle('selected', Number(row.dataset.transformerCandidate) === state.topicCount);
    });
    refreshTransformerControls();
  });
  countLabel.append(countSelect);
  const maxLabel = analysisElement('label', 'field');
  maxLabel.append(analysisElement('span', '', '自動選択時の上限'));
  const maxSelect = analysisElement('select');
  [4, 6, 8, 10, 12].forEach(value => maxSelect.add(new Option(`${value}件`, String(value))));
  maxSelect.value = String(state.maxTopics);
  maxSelect.dataset.transformerMaxTopics = 'true';
  maxSelect.addEventListener('change', () => {
    const state = contentAnalysisState();
    state.maxTopics = Number(maxSelect.value);
    document.querySelectorAll('[data-transformer-max-topics]').forEach(peer => { peer.value = maxSelect.value; });
  });
  maxLabel.append(maxSelect);
  const minLabel = analysisElement('label', 'field');
  minLabel.append(analysisElement('span', '', 'テーマの最小発話数'));
  const minSelect = analysisElement('select');
  [2, 3, 4, 5, 8, 10].forEach(value => minSelect.add(new Option(`${value}発話`, String(value))));
  minSelect.value = String(state.minTopicSize);
  minSelect.dataset.transformerMinTopicSize = 'true';
  minSelect.addEventListener('change', () => {
    const state = contentAnalysisState();
    state.minTopicSize = Number(minSelect.value);
    document.querySelectorAll('[data-transformer-min-topic-size]').forEach(peer => { peer.value = minSelect.value; });
  });
  minLabel.append(minSelect);
  const similarityLabel = analysisElement('label', 'field');
  similarityLabel.append(analysisElement('span', '', '未割当のしきい値'));
  const similaritySelect = analysisElement('select');
  [[0, 'なし（最も近いテーマへ）'], [0.7, '0.70'], [0.75, '0.75'], [0.8, '0.80'], [0.85, '0.85']]
    .forEach(([value, label]) => similaritySelect.add(new Option(label, String(value))));
  similaritySelect.value = String(state.manualMinSimilarity);
  similaritySelect.dataset.transformerMinSimilarity = 'true';
  similaritySelect.addEventListener('change', () => {
    const state = contentAnalysisState();
    state.manualMinSimilarity = Number(similaritySelect.value);
    document.querySelectorAll('[data-transformer-min-similarity]').forEach(peer => {
      peer.value = similaritySelect.value;
    });
  });
  similarityLabel.append(similaritySelect);
  const mode = transformerModeValue(state);
  const runLabels = {
    auto: result ? 'テーマ分析を再実行' : 'テーマ分析を実行',
    candidate: 'このテーマ数で作り直す',
    manual: '定義したテーマへ割り当てる'
  };
  const run = contentButton(runLabels[mode], startTransformerAnalysis, 'primary-button small');
  run.dataset.transformerRun = 'true';
  const cancel = contentButton('分析を中止', cancelTransformerAnalysis);
  cancel.dataset.transformerCancel = 'true';
  if (mode === 'auto') toolbar.append(maxLabel, minLabel);
  if (mode === 'candidate') toolbar.append(countLabel);
  if (mode === 'manual') toolbar.append(similarityLabel);
  toolbar.append(run, cancel);
  panel.body.append(toolbar);
  if (mode === 'candidate') panel.body.append(buildTransformerCandidateList(result, state));
  if (mode === 'manual') panel.body.append(buildTransformerManualTopics(state));
  const status = analysisElement('p', 'content-ai-status');
  status.dataset.transformerStatus = 'true';
  status.setAttribute('role', 'status');
  panel.body.append(status);
  const processFlow = analysisElement('div');
  processFlow.dataset.transformerProcessFlow = 'true';
  processFlow.hidden = true;
  panel.body.append(processFlow);

  const output = analysisElement('div', 'transformer-output');
  output.dataset.transformerOutput = 'true';
  if (result) {
    if (transformer.stale) output.append(analysisElement('p', 'content-inline-notice',
      '更新が必要：本文・話者・分析条件または処理版が変わっています。以下は実行時点の入力と設定による結果です。'));
    const engine = result.engine || {};
    const coverage = result.coverage || {};
    const quality = result.quality || {};
    const analyzedCount = coverage.segment_count || 0;
    const sourceCount = coverage.source_segment_count || analyzedCount;
    const modeLabels = {auto: '自動', candidate: '候補から選択', manual: '手動で定義'};
    const resultMode = (result.parameters || {}).mode || quality.topic_mode || 'auto';
    output.append(analysisElement('p', 'content-ai-meta',
      `テーマの決め方：${modeLabels[resultMode] || resultMode}`
      + `${resultMode === 'candidate' ? `（${(result.parameters || {}).topic_count || coverage.topic_count || 0}件を指定）` : ''}`
      + ` / ${engine.name || 'Transformer'}`
      + `${engine.revision ? ` @${String(engine.revision).slice(0, 12)}` : ''}`
      + `${engine.dimensions ? ` / ${engine.dimensions}次元` : ''}`
      + ` / ${engine.device || '実行装置不明'} / seed 42`
      + ` / ${analyzedCount}/${sourceCount}発話を分析 / ${coverage.topic_count || 0}テーマ`
      + `${quality.silhouette_cosine == null ? '' : ` / silhouette ${Number(quality.silhouette_cosine).toFixed(3)}`}`));
    output.append(analysisElement('p', 'content-inline-notice',
      '自動結果は未確認の候補です。意味の近さ・語句の一致・根拠IDの存在は、主張の真偽や本人の変化を保証しません。研究者による原文・前後文脈の照合が必要です。'));
    if (coverage.token_measurement_status !== 'measured') {
      output.append(analysisElement('p', 'analysis-caption', 'token切詰めは未計測です。切詰めなしを意味しません。'));
    } else {
      output.append(analysisElement('p', 'analysis-caption',
        `文字上限で切詰め ${coverage.character_truncated_segment_count || 0}件 / token上限で切詰め ${coverage.token_truncated_segment_count || 0}件。`));
    }
    const truncatedIds = coverage.truncated_segment_ids || [];
    if (truncatedIds.length) output.append(evidenceDetails(truncatedIds, {snapshot: result.evidence, stale: Boolean(transformer.stale)}));
    if ((coverage.target_truncated_segment_ids || []).length) output.append(analysisElement('p', 'content-inline-notice',
      `文脈追加後、対象発話の本文が一部または全部落ちた発話ID: ${coverage.target_truncated_segment_ids.join('、')}`));
    if (coverage.reused_embeddings) output.append(analysisElement('p', 'analysis-caption',
      '保存済みの意味ベクトル（int8）を再利用しました。埋め込みの再計算はしていません。'));
    if (resultMode === 'manual') {
      const threshold = (result.parameters || {}).manual_min_similarity;
      output.append(analysisElement('p', 'analysis-caption',
        `研究者が定義した${((result.parameters || {}).manual_topics || []).length}テーマへの割り当てです。`
        + `未割当 ${coverage.unassigned_segment_count || 0}件`
        + `（しきい値 ${threshold ? Number(threshold).toFixed(2) : 'なし'}）。`
        + '割り当ては意味の近さによる候補で、テーマの妥当性を検証した結果ではありません。'));
    }
    if (coverage.low_margin_segment_count) output.append(analysisElement('p', 'analysis-caption',
      `上位2テーマの差が小さい境界例が${coverage.low_margin_segment_count}件あります。どちらのテーマにも入りうる発話です。`));
    if (coverage.context_expanded_segment_count) output.append(analysisElement('p', 'analysis-caption',
      `短い発話${coverage.context_expanded_segment_count}件は、同じ話者の隣接発話を文脈として足して意味ベクトル化しました。`));
    if (coverage.small_cluster_segment_count && resultMode !== 'manual') output.append(
      analysisElement('p', 'analysis-caption',
        `最小発話数に満たないまとまりの${coverage.small_cluster_segment_count}件は、テーマに含めていません。`));
    if (coverage.ignored_noise_segment_count) output.append(analysisElement('p', 'analysis-caption',
      `記号・短い認識断片 ${coverage.ignored_noise_segment_count}件をテーマ分類と意味検索から除外しました。`));
    if (coverage.backchannel_segment_count) output.append(analysisElement('p', 'analysis-caption',
      `相づち ${coverage.backchannel_segment_count}件を別集計し、${coverage.linked_backchannel_segment_count || 0}件を応答対象のテーマへ紐付けました。`));
    if (coverage.speaker_result_count) output.append(analysisElement('p', 'analysis-caption',
      `話者別リザルトは${coverage.speaker_result_count}話者分を作成し、うち${coverage.candidate_speaker_result_count ?? coverage.explicit_speaker_result_count ?? 0}話者に変化・気づき・選好の未確認表現候補があります。`));
    if (quality.silhouette_cosine != null && Number(quality.silhouette_cosine) < 0.25) {
      output.append(analysisElement('p', 'content-inline-notice',
        'テーマ間の分離は弱めです。固定テーマ数も試し、代表発言を確認して解釈してください。'));
    }
    if (quality.dominant_speaker && Number(quality.dominant_speaker_percent) >= 35) {
      output.append(analysisElement('p', 'analysis-caption',
        `発話時間が多い話者（${Number(quality.dominant_speaker_percent).toFixed(1)}%）があります。発話量だけで進行役扱い・参加者除外はしません。${result.parameters?.speaker_balancing ? " 話者別の発話件数による重み付けを適用しています。" : ""}`));
    }
    const overallBackchannelRates = (Array.isArray(result.backchannel_rates) ? result.backchannel_rates : [])
      .filter(row => row.scope === 'overall' && row.speaker_group === 'participant')
      .sort((left, right) => Number(right.response_rate_percent || 0) - Number(left.response_rate_percent || 0));
    const backchannelTests = Array.isArray(result.backchannel_tests) ? result.backchannel_tests : [];
    if (overallBackchannelRates.length) {
      const section = analysisElement('section', 'transformer-speaker-results');
      section.append(analysisElement('h3', '', '相づちの統計分析'),
        analysisElement('p', 'analysis-caption',
          '分母は、本人以外の有意味発話を「反応機会」とした代理値です。応答率は相づちを返した異なる対象発話数÷反応機会数で、参加時間や聞いていた事実を直接測定した値ではありません。相づちの種類は辞書上の分類であり、同意や進行品質の得点ではありません。'));
      const wrap = analysisElement('div', 'analysis-table-wrap');
      const table = analysisElement('table', 'analysis-table');
      const head = document.createElement('thead');
      const headRow = document.createElement('tr');
      ['話者', '反応機会', '応答した発話', '応答率', '相づち総数', '100機会あたり'].forEach(label => {
        headRow.append(analysisElement('th', '', label));
      });
      head.append(headRow); table.append(head);
      const body = document.createElement('tbody');
      overallBackchannelRates.forEach(row => {
        const line = document.createElement('tr');
        [row.speaker_name, row.opportunity_count, row.responded_target_count,
          row.response_rate_percent == null ? '—' : `${Number(row.response_rate_percent).toFixed(2)}%`,
          row.backchannel_count,
          row.backchannels_per_100_opportunities == null ? '—' : Number(row.backchannels_per_100_opportunities).toFixed(2)
        ].forEach(value => line.append(analysisElement('td', '', String(value))));
        body.append(line);
      });
      table.append(body); wrap.append(table); section.append(wrap);
      if (backchannelTests.length) {
        const tests = analysisElement('details', 'transformer-outliers');
        tests.append(analysisElement('summary', '', `探索的な統計検定 ${backchannelTests.length}件`));
        backchannelTests.forEach(row => {
          const sparse = row.status === 'computed_sparse' ? ' / 期待度数が小さいためp値から差を判定しない' : '';
          const resultText = row.p_value == null
            ? row.interpretation
            : `χ²=${Number(row.statistic).toFixed(3)}, df=${row.df}, p=${(Number(row.p_value) > 0 && Number(row.p_value) < 0.0001 ? Number(row.p_value).toExponential(2) : Number(row.p_value).toFixed(4))}, Cramér\'s V=${Number(row.effect_size).toFixed(3)}${sparse}`;
          const item = analysisElement('article');
          item.append(analysisElement('strong', '', row.test), analysisElement('p', '', resultText),
            analysisElement('p', 'analysis-caption', row.assumption_note || ''));
          tests.append(item);
        });
        section.append(tests);
      }
      output.append(section);
    }
    const speakerResults = Array.isArray(result.speaker_results) ? result.speaker_results : [];
    if (speakerResults.length) {
      const section = analysisElement('section', 'transformer-speaker-results');
      section.append(analysisElement('h3', '', '話者別の表現候補（未確認）'),
        analysisElement('p', 'analysis-caption',
          '語句から「意見の変化・維持」「新しい気づき」「支持・選好」の候補を探します。否定・引用・主語の検出は限定的です。本人の変化として確定せず、原文と文脈を研究者が確認してください。会議前調査との比較ではありません。'));
      const resultGroups = new Map();
      speakerResults.forEach(row => {
        if (!resultGroups.has(row.speaker)) resultGroups.set(row.speaker, []);
        resultGroups.get(row.speaker).push(row);
      });
      resultGroups.forEach(rows => {
        const details = analysisElement('details', 'transformer-outliers');
        const labels = [...new Set(rows.map(row => row.result_label || '未判定'))];
        details.open = resultGroups.size <= 4;
        details.append(analysisElement('summary', '', `${rows[0].speaker_name} / ${labels.join('・')}`));
        rows.forEach(row => {
          const item = analysisElement('article');
          const candidate = ['unverified_candidate', 'explicit'].includes(row.confidence);
          const topicPrefix = candidate ? '候補の話題' : '主な話題';
          item.append(analysisElement('strong', '', row.result_label || '未判定'),
            analysisElement('p', 'transformer-topic-meta',
              `${topicPrefix}: ${row.topic_label || '紐付けなし'}${candidate ? ' / 未確認・研究者の照合が必要' : ''}`),
            analysisElement('p', '', row.basis || ''),
            evidenceDetails(row.evidence_segment_ids || [], {
              snapshot: result.evidence || null, stale: Boolean(transformer.stale)
            }));
          details.append(item);
        });
        section.append(details);
      });
      output.append(section);
    }
    const topics = Array.isArray(result.topics) ? result.topics : [];
    if (!topics.length) output.append(analysisElement('p', 'analysis-no-data', 'まとまりとして表示できるテーマ候補がありません。'));
    topics.forEach(topic => {
      const article = analysisElement('article', 'transformer-topic');
      const heading = analysisElement('header');
      heading.append(analysisElement('span', 'transformer-topic-id', topic.topic_id),
        analysisElement('h3', '', topic.label || topic.topic_id));
      const roleBreakdown = topic.facilitator_segment_count == null ? ''
        : ` / 参加者 ${topic.participant_segment_count || 0}・進行役 ${topic.facilitator_segment_count || 0}`;
      const backchannelBreakdown = topic.backchannel_count == null ? '' : ` / 相づち ${topic.backchannel_count || 0}`;
      const originNote = topic.origin === 'manual'
        ? `研究者が定義${topic.seed_segment_count ? `・シード${topic.seed_segment_count}件` : ''} / ` : '';
      article.append(heading, analysisElement('p', 'transformer-topic-meta',
        `${originNote}${topic.segment_count}発話${roleBreakdown}${backchannelBreakdown} / ${topic.speaker_count}人 / ${formatTime(topic.speaking_seconds || 0)}`
        + ` / 中心類似度 ${topic.average_similarity == null ? '—' : Number(topic.average_similarity).toFixed(3)}`));
      if (topic.origin === 'manual' && (topic.auto_keywords || []).length) {
        article.append(analysisElement('p', 'analysis-caption',
          `このテーマに集まった発話の特徴語：${topic.auto_keywords.join('・')}`));
      }
      if (!topic.segment_count) {
        article.append(analysisElement('p', 'analysis-no-data',
          'このテーマに割り当てられた発話はありません。手がかり語やシード発話、しきい値を見直してください。'));
      }
      const speakerRows = (result.speaker_topics || []).filter(row => row.topic_id === topic.topic_id);
      if (speakerRows.length) {
        const distribution = analysisElement('div', 'transformer-speaker-distribution');
        speakerRows.forEach(row => distribution.append(analysisElement('span', '',
          `${row.speaker_name} ${row.segment_count}件（${Number(row.topic_percent).toFixed(1)}%）`)));
        article.append(distribution);
      }
      const backchannelRows = (result.speaker_backchannels || []).filter(row => row.topic_id === topic.topic_id);
      if (backchannelRows.length) {
        const distribution = analysisElement('div', 'transformer-speaker-distribution');
        distribution.append(analysisElement('strong', '', 'この話題への相づち'));
        backchannelRows.forEach(row => distribution.append(analysisElement('span', '',
          `${row.speaker_name} ${row.backchannel_count}件`)));
        article.append(distribution);
      }
      article.append(evidenceDetails(topic.representative_segment_ids || [], {
        snapshot: result.evidence || null, stale: Boolean(transformer.stale)
      }));
      output.append(article);
    });
    const outliers = Array.isArray(result.outliers) ? result.outliers : [];
    if (outliers.length) {
      const details = analysisElement('details', 'transformer-outliers');
      details.append(analysisElement('summary', '', `他の発話と意味が離れた例外候補 ${outliers.length}件`),
        analysisElement('p', 'analysis-caption', '少数意見とは限りません。原文と前後関係を確認してください。'));
      outliers.forEach(row => {
        const item = analysisElement('article');
        item.append(analysisElement('strong', '', `${row.speaker_name} / 類似度 ${Number(row.nearest_similarity).toFixed(3)}`),
          analysisElement('p', '', row.text), evidenceDetails([row.segment_id], {
            snapshot: result.evidence || null, stale: Boolean(transformer.stale)
          }));
        details.append(item);
      });
      output.append(details);
    }
    const backchannels = Array.isArray(result.backchannels) ? result.backchannels : [];
    if (backchannels.length) {
      const kindLabels = {agreement: '同意表現候補（辞書）', continuer: '継続表現候補（辞書）', courtesy: '謝意表現候補（辞書）',
        confirmation: '確認表現候補（辞書）', acknowledgement: '応答候補（辞書）'};
      const details = analysisElement('details', 'transformer-outliers');
      details.append(analysisElement('summary', '', `相づちの対応関係 ${backchannels.length}件`),
        analysisElement('p', 'analysis-caption',
          '直前の別話者の発話を優先し、ない場合は後続の発話へ対応を推定します。相づちは賛成を意味するとは限りません。'));
      backchannels.forEach(row => {
        const item = analysisElement('article');
        item.append(analysisElement('strong', '',
          `${row.speaker_name} / ${kindLabels[row.kind] || '応答'} / ${row.topic_label || '紐付けなし'}`),
          analysisElement('p', 'analysis-caption', `対応方法: ${{previous_other_speaker: '前の別話者発話', next_other_speaker: '後の別話者発話', unassigned: '未割当'}[row.link_method] || row.link_method || '不明'}`),
          analysisElement('p', '', row.text), evidenceDetails(
            [row.segment_id, row.responds_to_segment_id].filter(Boolean), {
              snapshot: result.evidence || null, stale: Boolean(transformer.stale)
            }));
        details.append(item);
      });
      output.append(details);
    }
    output.append(transformerExportLinks());

    const search = analysisElement('form', 'transformer-semantic-form');
    const queryLabel = analysisElement('label', 'field');
    queryLabel.append(analysisElement('span', '', '意味で発話を検索'));
    const query = analysisElement('input');
    query.type = 'search'; query.maxLength = 500; query.value = state.semanticQuery;
    query.placeholder = '例：価格への不満、導入をためらう理由'; query.dataset.semanticQuery = 'true';
    query.addEventListener('input', () => {
      const state = contentAnalysisState();
      state.semanticQuery = query.value;
      document.querySelectorAll('[data-semantic-query]').forEach(peer => { peer.value = query.value; });
    });
    queryLabel.append(query);
    const submit = analysisElement('button', 'secondary-button small', '意味検索'); submit.type = 'submit';
    search.append(queryLabel, submit);
    search.addEventListener('submit', event => { event.preventDefault(); searchTransformerSemantics(); });
    const searchResults = analysisElement('div', 'transformer-search-results');
    searchResults.dataset.semanticResults = 'true';
    output.append(search, searchResults);
  }
  panel.body.append(output);
  requestAnimationFrame(() => { refreshTransformerControls(); renderTransformerSearchResults(); });
  return panel.panel;
}

function refreshTransformerControls() {
  if (!analysisState.data) return;
  const state = contentAnalysisState();
  const busy = state.transformerStarting || transformerRunActive(state.transformerRun);
  const mode = transformerModeValue(state);
  const savedTopics = manualTransformerTopics(true);
  const manualBlocked = mode === 'manual' && savedTopics.length < 2;
  const runLabels = {
    auto: analysisState.data.transformer?.result ? 'テーマ分析を再実行' : 'テーマ分析を実行',
    candidate: 'このテーマ数で作り直す',
    manual: '定義したテーマへ割り当てる'
  };
  document.querySelectorAll('[data-transformer-run]').forEach(button => {
    button.disabled = Boolean(busy || hasUnsavedAnalysisChanges() || analysisSaveInProgress || manualBlocked);
    button.textContent = state.transformerStarting ? '開始しています…' : runLabels[mode];
  });
  document.querySelectorAll('[data-transformer-cancel]').forEach(button => {
    button.hidden = !transformerRunActive(state.transformerRun);
    button.disabled = state.transformerRun?.status === 'cancelling';
  });
  document.querySelectorAll(
    '[data-transformer-mode], [data-transformer-topic-count], [data-transformer-min-topic-size],'
    + ' [data-transformer-min-similarity]'
  ).forEach(select => { select.disabled = Boolean(busy); });
  document.querySelectorAll('[data-transformer-max-topics]').forEach(select => {
    select.disabled = Boolean(busy || mode !== 'auto');
  });
  const modeHints = {
    auto: 'silhouetteを目安に、差が小さい場合は少ないテーマ数を選びます。ボタンを押したときだけローカルで実行します。会話本文を外部AI APIへ送信しません。',
    candidate: '選んだテーマ数で作り直します。保存済みの意味ベクトルがあれば再利用し、モデルの再実行はしません。',
    manual: '定義したテーマへ、意味が最も近い発話を割り当てます。テーマの妥当性を確かめた結果ではありません。'
  };
  document.querySelectorAll('[data-transformer-status]').forEach(host => {
    host.textContent = hasUnsavedAnalysisChanges() ? '未保存の変更があります。保存してから実行してください。'
      : manualBlocked
        ? '手動で割り当てるには、テーマを2件以上定義して保存してください。'
        : state.transformerError || state.transformerPollError
          || (state.transformerRun ? `${state.transformerRun.message} ${state.transformerRun.progress}%`
            : modeHints[mode]);
  });
  document.querySelectorAll('[data-transformer-process-flow]').forEach(host => {
    const run = state.transformerRun;
    host.hidden = !run && !state.transformerStarting;
    if (host.hidden) { host.replaceChildren(); delete host.dataset.flowSignature; return; }
    const progress = Math.max(0, Math.min(100, Number(run?.progress) || 0));
    const completed = run?.status === 'completed';
    const running = run?.status === 'running';
    const failed = ['failed', 'stale', 'cancelled'].includes(run?.status);
    const sourceTerms = (analysisState.data.automatic?.keywords || [])
      .map(item => String(item.term || '')).filter(Boolean).slice(0, 3);
    const title = `Transformerテーマ分析 ${completed ? '完了' : failed ? '停止' : `${progress}%`}`;
    const note = run?.message || 'サーバーの進捗に連動。モデル内部の単語間計算は表示しません。';
    const phase = progress < 5 ? 'prepare' : progress < 60 ? 'embedding'
      : progress < 90 ? 'topics' : 'evidence';
    const signature = JSON.stringify([run?.status, phase, run?.model, sourceTerms]);
    if (host.dataset.flowSignature === signature) {
      const heading = host.querySelector('.analysis-process-flow-heading');
      if (heading) {
        heading.querySelector('strong').textContent = title;
        heading.querySelector('small').textContent = note;
      }
      return;
    }
    host.dataset.flowSignature = signature;
    const stepState = (first, last) => completed || progress > last ? 'complete'
      : failed && progress >= first && progress <= last ? 'failed'
        : running && progress >= first && progress <= last ? 'running' : 'pending';
    host.replaceChildren(buildAnalysisProcessFlow({
      title, note,
      nodes: [
        {id: 'prepare', kind: '入力', label: '発話と内容語', detail: '分析する発話を準備',
          terms: sourceTerms.length ? sourceTerms : ['発話', '内容語', '話者'], state: stepState(0, 4)},
        {id: 'embedding', kind: 'Transformer', label: 'E5意味ベクトル',
          detail: run?.model || '保存済みベクトルを再利用する場合あり', state: stepState(5, 59)},
        {id: 'topics', kind: 'テーマ', label: '分類・割り当て', detail: '意味の近さから候補を形成',
          state: stepState(60, 89)},
        {id: 'evidence', kind: '結果', label: '根拠発話と保存', detail: '',
          state: stepState(90, 100)}
      ]
    }));
  });
}

async function startTransformerAnalysis() {
  const itemId = analysisState.itemId;
  const state = contentAnalysisState();
  if (state.transformerStarting || transformerRunActive(state.transformerRun) || hasUnsavedAnalysisChanges()) return;
  const operation = 'startTransformerAnalysis';
  const token = {};
  state.operations ||= {};
  state.operations[operation] = token;
  const owns = () => isAnalysisContextCurrent(state.context) && state.operations[operation] === token;
  const item = analysisState.data.item;
  let pending = null;
  try { pending = JSON.parse(sessionStorage.getItem(transformerPendingKey(itemId)) || 'null'); } catch (_) { /* unavailable */ }
  const mode = transformerModeValue(state);
  const topicCount = mode === 'candidate' ? Number(state.topicCount) || 0 : 0;
  const minSimilarity = mode === 'manual' ? Number(state.manualMinSimilarity) || 0 : 0;
  if (!pending || pending.source_revision !== item.revision_count || pending.analysis_revision !== item.analysis_revision
    || pending.max_topics !== state.maxTopics || pending.min_topic_size !== state.minTopicSize
    || pending.topic_count !== topicCount || pending.mode !== mode
    || pending.min_similarity !== minSimilarity) {
    pending = {request_id: crypto.randomUUID(), source_revision: item.revision_count,
      analysis_revision: item.analysis_revision, max_topics: state.maxTopics,
      min_topic_size: state.minTopicSize, topic_count: topicCount,
      mode, min_similarity: minSimilarity};
  }
  try { sessionStorage.setItem(transformerPendingKey(itemId), JSON.stringify(pending)); } catch (_) { /* in memory only */ }
  state.transformerStarting = true; state.transformerError = ''; refreshTransformerControls();
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/transformer`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(pending)
    });
    const data = await readJsonResponse(response);
    if (!owns()) return;
    if (data.run) state.transformerRun = data.run;
    if (!response.ok && !data.run) throw new Error(data.error || 'Transformer分析を開始できませんでした。');
    try { sessionStorage.removeItem(transformerPendingKey(itemId)); } catch (_) { /* unavailable */ }
  } catch (error) { if (!owns()) return;
    state.transformerError = `${error.message} 必要な場合はもう一度実行してください。`;
  } finally {
    if (!owns()) return;
    state.transformerStarting = false;
    if (itemId === analysisState.itemId) { refreshTransformerControls(); pollTransformerAnalysis(); }
  }
}

async function cancelTransformerAnalysis() {
  const itemId = analysisState.itemId;
  const state = contentAnalysisState();
  const operation = 'cancelTransformerAnalysis';
  if (!state.transformerRun) return;
  const runId = state.transformerRun.request_id;
  state.cancellations ||= new Set();
  const key = `${operation}:${runId}`;
  if (state.cancellations.has(key)) return;
  state.cancellations.add(key);
  const token = {};
  state.operations ||= {};
  state.operations[operation] = token;
  const owns = () => isAnalysisContextCurrent(state.context) && state.operations[operation] === token && state.transformerRun?.request_id === runId;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/transformer/cancel`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({request_id: runId})
    });
    const data = await readJsonResponse(response);
    if (!owns()) return;
    if (!response.ok) throw new Error(data.error || '中止できませんでした。');
    pollTransformerAnalysis();
  } catch (error) { if (!owns()) return; state.transformerError = error.message; refreshTransformerControls(); } finally { state.cancellations.delete(key); }
}

async function pollTransformerAnalysis() {
  clearTimeout(transformerAnalysisPollTimer);
  if (!analysisState.data) return;
  const itemId = analysisState.itemId;
  const state = contentAnalysisState();
  const operation = 'pollTransformerAnalysis';
  const token = {};
  state.operations ||= {};
  state.operations[operation] = token;
  const owns = () => isAnalysisContextCurrent(state.context) && state.operations[operation] === token;
  const sequence = ++transformerAnalysisPollSequence;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/transformer`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!owns()) return;
    if (sequence !== transformerAnalysisPollSequence || itemId !== analysisState.itemId || !analysisState.data) return;
    if (!response.ok) throw new Error(data.error || 'Transformer分析の状態を取得できませんでした。');
    const previousRequest = analysisState.data.transformer?.result?.request_id;
    state.transformerPollError = ''; state.transformerRun = data.run;
    analysisState.data.transformer = data.transformer || {result: null, stale: false};
    refreshTransformerControls();
    const currentRequest = analysisState.data.transformer?.result?.request_id;
    if (currentRequest && currentRequest !== previousRequest) {
      state.semanticHits = null; renderAnalysisWorkspace(); loadAnalysisStorage();
    }
    if (transformerRunActive(state.transformerRun)) {
      transformerAnalysisPollTimer = setTimeout(pollTransformerAnalysis, 1800);
    }
  } catch (error) { if (!owns()) return;
    if (sequence !== transformerAnalysisPollSequence || itemId !== analysisState.itemId) return;
    state.transformerPollError = error.message; refreshTransformerControls();
    if (transformerRunActive(state.transformerRun)) transformerAnalysisPollTimer = setTimeout(pollTransformerAnalysis, 5000);
  }
}

function renderTransformerSearchResults() {
  const state = contentAnalysisState();
  document.querySelectorAll('[data-semantic-results]').forEach(host => {
    host.replaceChildren();
    if (state.semanticLoading) host.append(analysisElement('p', 'analysis-caption', '意味検索を実行しています…'));
    if (state.semanticError) host.append(analysisElement('p', 'content-inline-notice', state.semanticError));
    if (!state.semanticHits) return;
    if (!state.semanticHits.length) host.append(analysisElement('p', 'analysis-no-data', '関連する発話を表示できませんでした。'));
    state.semanticHits.forEach(hit => {
      const article = analysisElement('article', 'transformer-search-hit');
      article.append(analysisElement('strong', '', `${hit.speaker_name} / 類似度 ${Number(hit.score).toFixed(3)}`),
        analysisElement('small', '', `${formatTime(hit.start)}–${formatTime(hit.end)} / ${hit.topic_label || 'テーマ未割当'}`),
        analysisElement('p', '', hit.text), evidenceDetails([hit.segment_id]));
      host.append(article);
    });
  });
}

async function searchTransformerSemantics() {
  const itemId = analysisState.itemId;
  const state = contentAnalysisState();
  if (!state.semanticQuery.trim() || state.semanticLoading) return;
  const operation = 'searchTransformerSemantics';
  const requestedQuery = state.semanticQuery;
  const token = {};
  state.operations ||= {};
  state.operations[operation] = token;
  const owns = () => isAnalysisContextCurrent(state.context) && state.operations[operation] === token;
  state.semanticLoading = true; state.semanticError = ''; state.semanticHits = null;
  renderTransformerSearchResults();
  try {
    const params = new URLSearchParams({q: state.semanticQuery, limit: '20'});
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/semantic-search?${params}`);
    const data = await readJsonResponse(response);
    if (!owns()) return;
    if (!response.ok) throw new Error(data.error || '意味検索を実行できませんでした。');
    if (itemId !== analysisState.itemId) return;
    if (requestedQuery !== state.semanticQuery) return;
    state.semanticHits = data.hits || [];
  } catch (error) { if (!owns() || requestedQuery !== state.semanticQuery) return; state.semanticError = error.message; }
  finally { if (!owns()) return; state.semanticLoading = false; if (itemId === analysisState.itemId) renderTransformerSearchResults(); }
}

function renderKwicResults() {
  if (!analysisState.data) return;
  const state = contentAnalysisState();
  document.querySelectorAll('[data-kwic-results]').forEach(host => {
    host.replaceChildren();
    if (state.loading) host.append(analysisElement('p', 'analysis-caption', '文脈を検索しています…'));
    if (state.error) host.append(analysisElement('p', 'content-inline-notice', state.error));
    const result = state.result;
    if (!result) {
      if (!state.loading && !state.error) host.append(analysisElement('p', 'analysis-caption', '語を入力するか、見解・頻出語・特徴語から選んでください。'));
      return;
    }
    const header = analysisElement('div', 'content-kwic-heading');
    header.append(analysisElement('p', '', `「${result.query}」${({normalized: '（正規化語の完全一致）', surface: '（表層語の完全一致）', literal: '（部分文字列）'})[result.mode] || ''}：${result.total}件 / ${result.total ? result.offset + 1 : 0}–${result.offset + result.hits.length}件を表示`));
    const link = analysisElement('a', 'analysis-export-link', '検索結果すべてをCSV出力');
    const params = new URLSearchParams({q: result.query, mode: result.mode, speaker: result.speaker, format: 'csv'});
    link.href = `/api/library/${encodeURIComponent(analysisState.itemId)}/analysis/kwic?${params}`;
    link.download = '';
    const save = contentButton('この検索をObsidianに保存', () => saveAnalysisPackage({q: result.query, mode: result.mode, speaker: result.speaker}));
    save.dataset.archiveKwic = 'true';
    save.disabled = Boolean(analysisState.dirty || analysisStorageState().busy);
    header.append(link, save); host.append(header);
    result.hits.forEach(hit => {
      const article = analysisElement('article', 'content-kwic-hit');
      article.append(analysisElement('small', '', `${hit.speaker_name} / ${formatTime(hit.start)}–${formatTime(hit.end)}`));
      const text = analysisElement('p', 'content-kwic-line');
      text.append(analysisElement('span', 'content-kwic-left', hit.left), analysisElement('mark', '', hit.match), analysisElement('span', '', hit.right));
      article.append(text, evidenceDetails(hit.context_ids || [hit.segment_id]));
      host.append(article);
    });
    const pager = analysisElement('div', 'content-kwic-pager');
    const turnPage = offset => {
      const current = contentAnalysisState();
      if (current.result !== result) return;
      current.offset = offset;
      searchContentKwic(true);
    };
    const previous = contentButton('前の50件', () => turnPage(Math.max(0, result.offset - 50)));
    previous.disabled = state.loading || result.offset === 0;
    const next = contentButton('次の50件', () => turnPage(result.offset + 50));
    next.disabled = state.loading || result.offset + result.hits.length >= result.total;
    pager.append(previous, next); host.append(pager);
  });
}

function runKwicSearch({query, matchMode = 'normalized', speaker = '', offset = 0} = {}) {
  const state = contentAnalysisState();
  state.query = String(query || ''); state.mode = matchMode; state.speaker = speaker; state.offset = offset;
  jumpToContentSearch();
  document.querySelectorAll('[data-kwic-query]').forEach(input => { input.value = state.query; });
  document.querySelectorAll('[data-kwic-mode]').forEach(select => { select.value = state.mode; });
  document.querySelectorAll('[data-kwic-speaker]').forEach(select => { select.value = state.speaker; });
  return searchContentKwic();
}

async function searchContentKwic(page = false) {
  const itemId = analysisState.itemId;
  const state = contentAnalysisState();
  const operation = 'searchContentKwic';
  const token = {};
  state.operations ||= {};
  state.operations[operation] = token;
  const owns = () => isAnalysisContextCurrent(state.context) && state.operations[operation] === token;
  if (page && state.result) {
    state.query = state.result.query; state.mode = state.result.mode; state.speaker = state.result.speaker;
    document.querySelectorAll('[data-kwic-mode]').forEach(select => { select.value = state.mode; });
    document.querySelectorAll('[data-kwic-query]').forEach(input => { input.value = state.query; });
    document.querySelectorAll('[data-kwic-speaker]').forEach(select => { select.value = state.speaker; });
  }
  state.controller?.abort();
  const controller = new AbortController(); state.controller = controller;
  const sequence = ++state.sequence;
  const requestedQuery = JSON.stringify([state.query, state.mode, state.speaker, state.offset]);
  state.loading = true; state.error = ''; state.result = null;
  renderKwicResults();
  try {
    const params = new URLSearchParams({q: state.query, mode: state.mode, speaker: state.speaker, offset: String(state.offset), limit: '50'});
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/kwic?${params}`, {signal: controller.signal});
    const data = await readJsonResponse(response);
    if (!owns()) return;
    if (!response.ok) throw new Error(data.error || '文脈検索に失敗しました。');
    if (sequence !== state.sequence || itemId !== analysisState.itemId) return;
    if (data.fingerprint !== analysisState.data?.insights?.fingerprint) throw new Error('分析対象が更新されています。「再集計」を押してから検索してください。');
    if (requestedQuery !== JSON.stringify([state.query, state.mode, state.speaker, state.offset])) return;
    state.result = data;
  } catch (error) { if (!owns()) return;
    if (error.name !== 'AbortError' && sequence === state.sequence && requestedQuery === JSON.stringify([state.query, state.mode, state.speaker, state.offset])) state.error = error.message;
  } finally {
    if (!owns()) return;
    if (sequence === state.sequence) state.loading = false;
    if (itemId === analysisState.itemId) renderKwicResults();
  }
}

function insightRunActive(run) {
  return run && ['queued', 'running', 'cancelling'].includes(run.status);
}

function refreshInsightControls() {
  if (!analysisState.data) return;
  const state = contentAnalysisState();
  const busy = state.starting || insightRunActive(state.run);
  document.querySelectorAll('[data-insight-generate]').forEach(button => {
    button.disabled = Boolean(busy || hasUnsavedAnalysisChanges() || analysisSaveInProgress);
    button.textContent = state.starting ? '開始しています…' : analysisState.data.insights?.ai ? 'AI見解を再生成' : 'AIで見解を作成';
  });
  document.querySelectorAll('[data-insight-cancel]').forEach(button => {
    button.hidden = !insightRunActive(state.run);
    button.disabled = state.run?.status === 'cancelling';
  });
  document.querySelectorAll('[data-insight-provider]').forEach(select => { select.disabled = Boolean(busy); });
  document.querySelectorAll('[data-insight-status]').forEach(host => {
    const usage = state.run?.usage;
    const tokenText = usage?.request_count ? ` / ${usage.request_count}回・${Number(usage.total_tokens || 0).toLocaleString()}トークン` : '';
    host.textContent = hasUnsavedAnalysisChanges() ? '未保存の変更があります。設定・コード・準備記録を保存してから生成してください。'
      : state.aiError || state.pollError || (state.run ? `${state.run.message} ${state.run.progress}%${tokenText}` : 'AI見解は「内容・文脈検索」の「AIで内容・意見を整理」から個別に生成します。');
  });
  document.querySelectorAll('[data-insight-output]').forEach(host => {
    const insights = analysisState.data.insights || {};
    const ai = insights.ai;
    const key = `${analysisState.itemId}:${ai?.request_id || ''}:${Boolean(insights.stale)}`;
    if (host.dataset.renderKey === key) return;
    host.dataset.renderKey = key; host.replaceChildren();
    if (!ai) return;
    const providerLabel = {
      openai: 'OpenAI', google: 'Google Gemini', lmstudio: 'LM Studio（ローカル）'
    }[ai.provider] || 'AI';
    host.append(analysisElement('p', 'content-ai-meta', `AI見解・下書き / ${providerLabel} / ${ai.model} / ${formatDate(ai.generated_at)}`));
    host.append(analysisElement('p', 'content-inline-notice',
      '未確認の解釈候補です。根拠IDの検査は、本文が主張を支持するか、真偽や「全員」の範囲を検証するものではありません。研究者が原文と対象者集合を照合してください。'));
    if (insights.stale) host.append(analysisElement('p', 'content-inline-notice', '更新が必要：元データまたは分析条件が変わっています。以下は生成時点の見解です。'));
    if (!(ai.findings || []).length) host.append(analysisElement('p', 'analysis-no-data', '根拠付きでまとめられる見解は見つかりませんでした。'));
    (ai.findings || []).forEach(finding => {
      const article = analysisElement('article', 'content-finding ai');
      article.append(analysisElement('small', 'content-finding-meta', insightCategoryLabels[finding.category] || ''),
        analysisElement('h4', '', finding.title), analysisElement('p', '', finding.text),
        analysisElement('p', 'analysis-caption', finding.validation_note || '未確認の候補・研究者レビューが必要'),
        evidenceDetails(finding.segment_ids || [], {snapshot: ai.evidence, stale: insights.stale}));
      host.append(article);
    });
  });
}

function insightPendingKey(itemId) { return `gurumoji.insightRequest.${itemId}`; }

async function startContentInsights() {
  const itemId = analysisState.itemId;
  const state = contentAnalysisState();
  if (state.starting || insightRunActive(state.run) || hasUnsavedAnalysisChanges()) return;
  const operation = 'startContentInsights';
  const token = {};
  state.operations ||= {};
  state.operations[operation] = token;
  const owns = () => isAnalysisContextCurrent(state.context) && state.operations[operation] === token;
  const item = analysisState.data.item;
  let pending = state.pending || null;
  try { pending = JSON.parse(sessionStorage.getItem(insightPendingKey(itemId)) || 'null') || pending; } catch (_) { /* storage unavailable */ }
  if (!pending || pending.provider !== state.provider || pending.source_revision !== item.revision_count
    || pending.analysis_revision !== item.analysis_revision) {
    pending = {provider: state.provider, source_revision: item.revision_count,
      analysis_revision: item.analysis_revision, request_id: crypto.randomUUID(),
      ai_efforts: typeof readAiEfforts === 'function' ? readAiEfforts() : undefined};
  }
  state.pending = pending;
  try { sessionStorage.setItem(insightPendingKey(itemId), JSON.stringify(pending)); } catch (_) { /* request stays in memory */ }
  state.starting = true; state.aiError = ''; refreshInsightControls();
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/insights`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(pending)
    });
    const data = await readJsonResponse(response);
    if (!owns()) return;
    if (data.run) state.run = data.run;
    if (!response.ok && !data.run) {
      try { sessionStorage.removeItem(insightPendingKey(itemId)); } catch (_) { /* storage unavailable */ }
      state.pending = null;
      throw new Error(data.error || 'AI見解の生成を開始できませんでした。');
    }
    try { sessionStorage.removeItem(insightPendingKey(itemId)); } catch (_) { /* storage unavailable */ }
    state.pending = null;
  } catch (error) { if (!owns()) return;
    state.aiError = `${error.message} 必要な場合はもう一度生成ボタンを押してください。`;
  } finally {
    if (!owns()) return;
    state.starting = false;
    if (itemId === analysisState.itemId) {
      refreshInsightControls(); pollContentInsights();
    }
  }
}

async function cancelContentInsights() {
  const itemId = analysisState.itemId;
  const state = contentAnalysisState();
  const operation = 'cancelContentInsights';
  if (!state.run) return;
  const runId = state.run.request_id;
  state.cancellations ||= new Set();
  const key = `${operation}:${runId}`;
  if (state.cancellations.has(key)) return;
  state.cancellations.add(key);
  const token = {};
  state.operations ||= {};
  state.operations[operation] = token;
  const owns = () => isAnalysisContextCurrent(state.context) && state.operations[operation] === token && state.run?.request_id === runId;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/insights/cancel`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({request_id: runId})
    });
    const data = await readJsonResponse(response);
    if (!owns()) return;
    if (!response.ok) throw new Error(data.error || '中止できませんでした。');
    state.aiError = '';
    if (itemId === analysisState.itemId) pollContentInsights();
  } catch (error) { if (!owns()) return; state.aiError = error.message; refreshInsightControls(); } finally { state.cancellations.delete(key); }
}

async function pollContentInsights() {
  clearTimeout(contentAnalysisPollTimer);
  if (!analysisState.data) return;
  const itemId = analysisState.itemId;
  const state = contentAnalysisState();
  const operation = 'pollContentInsights';
  const token = {};
  state.operations ||= {};
  state.operations[operation] = token;
  const owns = () => isAnalysisContextCurrent(state.context) && state.operations[operation] === token;
  const sequence = ++contentAnalysisPollSequence;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/analysis/insights`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!owns()) return;
    if (sequence !== contentAnalysisPollSequence || itemId !== analysisState.itemId || !analysisState.data) return;
    if (!response.ok) throw new Error(data.error || '生成状態を取得できませんでした。');
    state.pollError = '';
    const previousArchive = analysisState.data.insights?.ai?.archive_id;
    state.run = data.run;
    // A poll must never mix freshly generated text with a different transcript.
    const current = analysisState.data.insights || {};
    if (data.insights?.fingerprint === current.fingerprint) analysisState.data.insights = data.insights;
    else if (current.ai) current.stale = true;
    if (state.pending?.request_id === data.run?.request_id) {
      state.pending = null; state.aiError = '';
      try { sessionStorage.removeItem(insightPendingKey(itemId)); } catch (_) { /* storage unavailable */ }
    }
    refreshInsightControls();
    if (analysisState.data.insights?.ai?.archive_id !== previousArchive) loadAnalysisStorage();
    if (insightRunActive(state.run)) contentAnalysisPollTimer = setTimeout(pollContentInsights, 1800);
  } catch (error) { if (!owns()) return;
    if (sequence !== contentAnalysisPollSequence || itemId !== analysisState.itemId) return;
    state.pollError = error.message; refreshInsightControls();
    if (insightRunActive(state.run)) contentAnalysisPollTimer = setTimeout(pollContentInsights, 5000);
  }
}

function onContentAnalysisLoaded() {
  ++contentAnalysisPollSequence; ++transformerAnalysisPollSequence;
  clearTimeout(contentAnalysisPollTimer); clearTimeout(transformerAnalysisPollTimer);
  loadAnalysisStorage();
  if (analysisState.data?.executed === false) return;
  openLinkedAnalysisEvidence();
  const state = contentAnalysisState();
  if (!state.pending) {
    try { state.pending = JSON.parse(sessionStorage.getItem(insightPendingKey(analysisState.itemId)) || 'null'); } catch (_) { /* storage unavailable */ }
  }
  const fingerprint = analysisState.data?.insights?.fingerprint || '';
  if (state.fingerprint !== fingerprint) {
    state.controller?.abort(); state.sequence++;
    state.loading = false; state.result = null; state.error = ''; state.offset = 0;
    state.fingerprint = fingerprint;
  }
  if (state.query.trim() && !state.result) searchContentKwic();
  pollContentInsights();
  pollTransformerAnalysis();
}
