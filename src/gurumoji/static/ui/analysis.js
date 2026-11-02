/* 公開版の画面処理: analysis。共有状態はapp.jsで管理する。 */
function safeAnalysisColor(value, fallback = '#1C6B50') {
  const color = String(value || '').toUpperCase();
  return /^#[0-9A-F]{6}$/.test(color) ? color : fallback;
}

function boundedAnalysisPercent(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(100, Math.max(0, number)) : 0;
}

function analysisNumberText(value, digits = 1, suffix = '') {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)}${suffix}` : '—';
}

function analysisObservedTimeText(metric, key = 'speaking_seconds', formatter = formatTime) {
  const value = metric?.[key];
  const missing = Number.isInteger(metric?.missing_time_turn_count) ? metric.missing_time_turn_count : null;
  const timed = Number.isInteger(metric?.timed_turn_count) ? metric.timed_turn_count : null;
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) || Number(value) < 0) {
    if (metric?.role_aggregation_status === 'mixed') return '役割混在で算出不可';
    return missing > 0 ? `時刻不明${missing}発話` : '時刻不明';
  }
  const text = formatter(value);
  return missing > 0 && timed !== null
    ? `時刻あり${text}（${timed}/${timed + missing}発話、時刻不明${missing}発話）` : text;
}

function analysisExportLink(label, dataset, className = 'analysis-export-link') {
  const exports = analysisState.data && analysisState.data.exports;
  const href = (exports && exports[dataset]) || (
    dataset === 'report' && analysisState.itemId
      ? `/api/library/${encodeURIComponent(analysisState.itemId)}/analysis/export.md`
      : ''
  );
  if (!href || !String(href).startsWith('/api/')) return null;
  const link = analysisElement('a', className, label);
  link.href = href;
  link.download = '';
  link.setAttribute('aria-label', `${label}をダウンロード`);
  return link;
}

function analysisExportDirectory(title, classification, datasets) {
  const section = analysisCardPanel(title, classification, '', true);
  const links = analysisElement('div', 'analysis-export-directory');
  datasets.forEach(([dataset, label]) => {
    const link = analysisExportLink(label, dataset, 'analysis-data-export');
    if (link) links.append(link);
  });
  if (links.childNodes.length) section.body.append(links);
  else section.body.append(analysisElement('p', 'analysis-no-data', '出力できる集計データがありません。'));
  return section.panel;
}

function setAnalysisLoading(loading) {
  const loadingView = document.querySelector('#analysis-loading');
  const shell = document.querySelector('#analysis-shell');
  const empty = document.querySelector('#analysis-empty');
  if (loadingView) loadingView.hidden = !loading;
  if (shell) shell.hidden = loading || !analysisState.data;
  if (empty) empty.hidden = loading || Boolean(analysisState.data);
  if (analysisItemSelect) analysisItemSelect.disabled = loading;
}

function updateAnalysisTarget() {
  const selected = analysisCatalog.find(item => item.id === analysisState.itemId);
  const name = document.querySelector('#analysis-target-name');
  const meta = document.querySelector('#analysis-target-meta');
  if (name) name.textContent = selected ? selected.source_name : '未選択';
  const openButton = document.querySelector('#analysis-open-item-button');
  if (openButton) openButton.hidden = !selected;
  if (meta) {
    meta.textContent = selected
      ? `発話 ${selected.segment_count || 0}件 / 最終時刻 ${analysisEndpointText(selected.duration, selected.timed_turn_count, selected.missing_time_turn_count)} / 更新 ${formatDate(selected.updated_at)}`
      : '処理済みデータを選択してください';
  }
  const exportLink = document.querySelector('#analysis-json-export');
  const jsonHref = analysisState.data && analysisState.data.exports && analysisState.data.exports.json;
  if (exportLink) {
    exportLink.hidden = !jsonHref;
    if (jsonHref && String(jsonHref).startsWith('/api/')) exportLink.href = jsonHref;
  }
  const xlsxLink = document.querySelector('#analysis-xlsx-export');
  const xlsxHref = analysisState.data && analysisState.data.exports && analysisState.data.exports.xlsx;
  if (xlsxLink) {
    xlsxLink.hidden = !xlsxHref;
    if (xlsxHref && String(xlsxHref).startsWith('/api/')) xlsxLink.href = xlsxHref;
  }
}

async function loadAnalysisCatalog(force = false) {
  if (analysisCatalogLoaded && !force) {
    if (analysisState.itemId && !analysisState.data) loadAnalysisItem(analysisState.itemId);
    return;
  }
  setAlert(document.querySelector('#analysis-message'), '');
  if (analysisItemSelect) {
    analysisItemSelect.disabled = true;
    analysisItemSelect.replaceChildren(new Option('処理済みデータを読み込んでいます…', ''));
  }
  try {
    const response = await apiFetch('/api/library?sort=updated_desc', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '分析対象を取得できませんでした。');
    analysisCatalog = Array.isArray(data.items) ? data.items : [];
    analysisCatalogLoaded = true;
    if (analysisItemSelect) {
      analysisItemSelect.replaceChildren();
      if (!analysisCatalog.length) {
        analysisItemSelect.add(new Option('分析できる処理済みデータがありません', ''));
      } else {
        analysisCatalog.forEach(item => {
          const label = `${item.source_name}（発話 ${item.segment_count || 0}件）`;
          analysisItemSelect.add(new Option(label, item.id));
        });
      }
    }
    const currentExists = analysisCatalog.some(item => item.id === analysisState.itemId);
    const resultExists = analysisCatalog.some(item => item.id === currentJobId);
    const linkedItem = !analysisLinkedItemApplied ? new URLSearchParams(location.search).get('item') : '';
    analysisLinkedItemApplied = true;
    const nextId = linkedItem || (currentExists
      ? analysisState.itemId
      : resultExists ? currentJobId : (analysisCatalog[0] || {}).id || '');
    if (analysisItemSelect) analysisItemSelect.value = nextId;
    if (nextId) await loadAnalysisItem(nextId, {discardDirty: force});
    else {
      analysisState.itemId = '';
      analysisState.data = null;
      updateAnalysisTarget();
      setAnalysisLoading(false);
    }
  } catch (error) {
    setAlert(document.querySelector('#analysis-message'), error.message, true);
    analysisState.data = null;
    setAnalysisLoading(false);
  } finally {
    if (analysisItemSelect) analysisItemSelect.disabled = false;
  }
}

async function loadAnalysisItem(itemId, {discardDirty = false, execute = false} = {}) {
  const nextId = String(itemId || '');
  if (!nextId) return;
  if (!discardDirty && hasUnsavedAnalysisChanges()) {
    const leave = window.confirm('分析設定・手動コード・準備記録に未保存の変更があります。破棄してデータを読み込みますか？');
    if (!leave) {
      if (analysisItemSelect) analysisItemSelect.value = analysisState.itemId;
      return;
    }
  }
  const closedFixedViewer = typeof closeFixedAnalysisViewer === 'function' && closeFixedAnalysisViewer();
  const closedAnalysisDialog = typeof closeAnalysisExecutionDialog === 'function' && closeAnalysisExecutionDialog();
  if ((closedFixedViewer || closedAnalysisDialog) && analysisItemSelect?.isConnected && !analysisItemSelect.closest('[hidden]')) analysisItemSelect.focus();
  if (analysisRequestController) analysisRequestController.abort();
  analysisRequestController = new AbortController();
  analysisNavigationGeneration += 1;
  // The former view's request may finish, but it no longer owns these controls.
  analysisSaveOwner = null;
  analysisSaveInProgress = false;
  analysisTermRunRequested = false;
  const requestId = ++analysisRequestSequence;
  const executionView = document.querySelector('#analysis-execution-view');
  if (executionView) executionView.hidden = true;
  analysisState.itemId = nextId;
  analysisState.data = null;
  if (analysisItemSelect) analysisItemSelect.value = nextId;
  updateAnalysisTarget();
  if (analysisCard && !analysisCard.hidden) syncRouteHash(routeHash('analysis', nextId), {replace: true});
  setAnalysisLoading(true);
  setAlert(document.querySelector('#analysis-message'), '');
  try {
    const query = execute ? '?execute=1' : '';
    const response = await apiFetch(`/api/library/${encodeURIComponent(nextId)}/analysis${query}`, {
      cache: 'no-store', signal: analysisRequestController.signal
    });
    const payload = await readJsonResponse(response);
    if (requestId !== analysisRequestSequence) return;
    if (!response.ok) throw new Error(payload.error || '分析データを取得できませんでした。');
    const data = payload.analysis && typeof payload.analysis === 'object' ? payload.analysis : payload;
    analysisState.data = data;
    invalidateAnalysisMethodOverview();
    analysisState.config = deepCopy(data.config || {});
    analysisState.annotations = deepCopy(data.annotations || {});
    preparationDraft = null;
    preparationDirty = false;
    analysisState.segmentQuery = '';
    analysisState.annotatedOnly = false;
    analysisState.speakerAttributeFilter = '';
    analysisState.selectedSpeaker = '';
    setAnalysisDirty(false);
    renderAnalysisWorkspace();
    onContentAnalysisLoaded();
  } catch (error) {
    if (error.name === 'AbortError') return;
    if (requestId !== analysisRequestSequence) return;
    analysisState.data = null;
    setAlert(document.querySelector('#analysis-message'), error.message, true);
  } finally {
    if (requestId === analysisRequestSequence) setAnalysisLoading(false);
  }
}

function setAnalysisMode(mode) {
  analysisState.mode = ['manual', 'methods'].includes(mode) ? mode : 'automatic';
  renderAnalysisWorkspace();
}

function analysisModeContent(compact) {
  if (analysisState.mode === 'manual') return renderManualAnalysis(compact);
  if (analysisState.mode === 'methods') return renderMethodAnalysis(compact);
  return renderAutomaticAnalysis(compact);
}

function renderAnalysisWorkspace() {
  if (!analysisState.data) return;
  const shell = document.querySelector('#analysis-shell');
  const empty = document.querySelector('#analysis-empty');
  if (analysisState.data.executed === false && analysisState.mode === 'automatic') {
    if (shell) shell.hidden = true;
    if (empty) {
      empty.hidden = false;
      const title = empty.querySelector('strong');
      const desc = empty.querySelector('p');
      if (title) title.textContent = '分析はまだ実行されていません';
      if (desc) desc.textContent = '右上の［分析を実行］ボタンを押すと、発話量・会話構造・形態素・共起・統計検定の分析を開始します。';
      let history = empty.querySelector('.analysis-empty-history');
      if (!history) {
        history = analysisElement('div', 'analysis-empty-history');
        empty.append(history);
      }
      history.replaceChildren(buildAnalysisStorage({readOnly: true}));
    }
    setAnalysisDirty(analysisState.dirty, false);
    if (!ANALYSIS_COMING_SOON) refreshAnalysisStorage();
    return;
  }
  document.querySelectorAll('[data-analysis-mode]').forEach(button => {
    const active = button.dataset.analysisMode === analysisState.mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  updateAnalysisTarget();
  if (analysisDesktopContent) {
    analysisDesktopContent.replaceChildren();
    analysisDesktopContent.append(analysisModeContent(false));
  }
  if (analysisMobileContent) {
    analysisMobileContent.replaceChildren();
    analysisMobileContent.append(analysisModeContent(true));
  }
  if (shell) shell.hidden = false;
  if (empty) empty.hidden = true;
  setAnalysisDirty(analysisState.dirty, false);
  renderKwicResults();
  if (!ANALYSIS_COMING_SOON) refreshInsightControls();
  if (!ANALYSIS_COMING_SOON) refreshAnalysisStorage();
  restoreAnalysisEvidencePosition();
  scheduleAnalysisNavigationSync();
  if (!analysisInitialSectionApplied && requestedAnalysisSection) {
    analysisInitialSectionApplied = true;
    requestAnimationFrame(() => {
      const content = window.matchMedia('(max-width: 959px)').matches
        ? analysisMobileContent : analysisDesktopContent;
      const target = content && content.querySelector(`[data-analysis-anchor="${requestedAnalysisSection}"]`);
      const jump = content && content.querySelector(`[data-analysis-jump="${requestedAnalysisSection}"]`);
      selectAnalysisPage(requestedAnalysisSection);
      if (jump) {
        content.querySelectorAll('[data-analysis-jump]').forEach(button => button.classList.toggle('active', button === jump));
      }
      if (target) target.scrollIntoView({block: 'start'});
    });
  }
}

function appendResearchAnalysis(grid, compact) {
  const research = (analysisState.data && analysisState.data.research) || {};
  const linguistics = research.linguistics || {};
  const statistics = research.statistics || {};
  const engine = linguistics.engine || {};
  const coverage = linguistics.coverage || {};

  const morphologyPanel = analysisCardPanel('使われた言葉の種類（形態素・品詞）', 'automatic', 'morphemes', true, 'morphology');
  const engineNotice = analysisElement('div', `analysis-engine-notice ${engine.status || 'fallback'}`);
  engineNotice.append(
    analysisElement('strong', '', `${engine.morphology || '解析器未確認'} / ${engine.syntax || '構文解析未確認'}`),
    analysisElement('p', '', engine.message || '解析状態を確認できませんでした。')
  );
  morphologyPanel.body.append(engineNotice);
  const morphologyMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(morphologyMetrics, '形態素', `${coverage.token_count || 0}件`);
  appendAnalysisMetric(morphologyMetrics, '内容語', `${coverage.content_token_count || 0}件`);
  appendAnalysisMetric(morphologyMetrics, '文', `${coverage.sentence_count || 0}件`);
  appendAnalysisMetric(morphologyMetrics, '係り受け', `${coverage.dependency_count || 0}件`);
  morphologyPanel.body.append(morphologyMetrics);
  const posRows = Array.isArray(linguistics.pos_frequency) ? linguistics.pos_frequency : [];
  const maxPos = Math.max(1, ...posRows.map(item => Number(item.count) || 0));
  posRows.slice(0, compact ? 7 : 12).forEach(item => appendAnalysisBar(
    morphologyPanel.body,
    [item.upos, item.pos_detail].filter(Boolean).join(' / '),
    100 * (Number(item.count) || 0) / maxPos,
    `${item.count || 0}件 / ${analysisNumberText(item.percent, 1, '%')}`,
    '#2F80ED'
  ));
  const morphologyExports = analysisElement('div', 'analysis-inline-exports');
  [
    ['dependencies', '係り受けCSV'],
    ['pos_frequency', '品詞頻度CSV']
  ].forEach(([dataset, label]) => {
    const link = analysisExportLink(label, dataset, 'analysis-inline-export');
    if (link) morphologyExports.append(link);
  });
  morphologyPanel.body.append(morphologyExports);
  grid.append(morphologyPanel.panel);

  const termsPanel = analysisCardPanel('よく使われた言葉（TF・DF）', 'automatic', 'term_frequency', false, 'lexical_frequency');
  const terms = Array.isArray(linguistics.term_frequency) ? linguistics.term_frequency : [];
  const maxTerm = Math.max(1, ...terms.map(item => Number(item.term_frequency) || 0));
  terms.slice(0, compact ? 10 : 15).forEach(item => appendSearchableTermBar(
    termsPanel.body,
    item.term,
    100 * (Number(item.term_frequency) || 0) / maxTerm,
    `TF ${item.term_frequency || 0} / DF ${item.document_frequency || 0} / ${item.upos || '—'}`,
    '#6C8B3C'
  ));
  if (!terms.length) termsPanel.body.append(analysisElement('p', 'analysis-no-data', '内容語を抽出できませんでした。解析器の状態と原文を確認してください。'));
  termsPanel.body.append(analysisElement('p', 'analysis-caption', 'TFは総出現回数、DFはその語を含む発話数です。頻度は重要性を意味しません。'));
  grid.append(termsPanel.panel);

  const cooccurrencePanel = analysisCardPanel('一緒に使われる言葉のつながり（共起）', 'automatic', 'cooccurrence', true, 'cooccurrence');
  const cooccurrence = Array.isArray(linguistics.cooccurrence) ? linguistics.cooccurrence : [];
  if (cooccurrence.length) {
    cooccurrencePanel.body.append(buildAnalysisCooccurrenceExplorer(cooccurrence));
  } else {
    cooccurrencePanel.body.append(analysisElement('p', 'analysis-no-data', `同じ発話で${coverage.cooccurrence_min_count || 2}回以上共起する語の組み合わせがありません。`));
  }
  cooccurrencePanel.body.append(analysisElement('p', 'analysis-caption', `発話を文書単位とし、上位${coverage.cooccurrence_top_terms || 60}語からJaccard係数を計算しています。関係の意味は原文で確認してください。`));
  grid.append(cooccurrencePanel.panel);

  const dependencies = Array.isArray(linguistics.dependency_preview) ? linguistics.dependency_preview : [];
  const syntaxPanel = analysisCardPanel('文章内の言葉のつながり（係り受け）', 'automatic', 'dependencies', true, 'syntax');
  if (dependencies.length) {
    syntaxPanel.body.append(buildAnalysisDependencyExplorer(dependencies, compact));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', '係り受けの表データを確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['発話', '語', '原形', '品詞', '関係', '係り先'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    dependencies.slice(0, compact ? 12 : 30).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.segment_id),
        analysisElement('td', '', item.surface),
        analysisElement('td', '', item.lemma),
        analysisElement('td', '', item.upos),
        analysisElement('td', '', item.dependency),
        analysisElement('td', '', item.head_token_id ? `${item.head_surface} (#${item.head_token_id})` : 'ROOT')
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    syntaxPanel.body.append(details);
  } else {
    syntaxPanel.body.append(analysisElement('p', 'analysis-no-data', '係り受けデータがありません。GiNZAとja-ginzaの導入状態を確認してください。'));
  }
  grid.append(syntaxPanel.panel);

  grid.append(analysisSectionHeading(
    'statistics', '03 / STATISTICS', '統計で比較する',
    '発話単位の分布、変数間の関連、群間差を順に確認します。p値だけでなく効果量・標本数・前提条件も併記します。'
  ));

  const correlations = Array.isArray(statistics.correlations) ? statistics.correlations : [];
  const computedCorrelations = correlations.filter(item => item.status === 'computed');
  const correlationPanel = analysisCardPanel('指標どうしの関係（相関）', 'automatic', 'correlations', true, 'correlation');
  if (computedCorrelations.length) {
    correlationPanel.body.append(buildAnalysisCorrelationExplorer(correlations));
  } else {
    correlationPanel.body.append(analysisElement('p', 'analysis-no-data', '相関を計算できる変数または標本数が不足しています。'));
  }
  grid.append(correlationPanel.panel);

  const descriptives = (Array.isArray(statistics.descriptives) ? statistics.descriptives : [])
    .filter(item => item.scope === 'overall');
  const statsPanel = analysisCardPanel('会話データの基本統計', 'automatic', 'descriptives', true, 'descriptive_statistics');
  if (descriptives.length) {
    statsPanel.body.append(buildAnalysisDescriptiveChart(descriptives));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', '記述統計の数値表を確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['変数', '分析単位・測定単位', 'N', '欠測', '平均', '標準偏差', '中央値', '最小', '最大'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    descriptives.forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.label || item.variable),
        analysisElement('td', '', `${item.analysis_unit || statistics.analysis_unit || '発話'} / ${item.unit || '—'}`),
        analysisElement('td', '', item.n || 0),
        analysisElement('td', '', item.missing ?? '—'),
        analysisElement('td', '', analysisNumberText(item.mean, 3)),
        analysisElement('td', '', analysisNumberText(item.standard_deviation, 3)),
        analysisElement('td', '', analysisNumberText(item.median, 3)),
        analysisElement('td', '', analysisNumberText(item.minimum, 3)),
        analysisElement('td', '', analysisNumberText(item.maximum, 3))
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    statsPanel.body.append(details);
  } else statsPanel.body.append(analysisElement('p', 'analysis-no-data', '記述統計を計算できる発話がありません。'));
  statsPanel.body.append(analysisElement('p', 'analysis-caption', `分析単位: ${statistics.analysis_unit || '発話'} / 比較軸: ${statistics.group_variable === 'role' ? '役割' : '話者'}。欠損値は変数ごとに除外します。`));
  grid.append(statsPanel.panel);

  const frequencies = Array.isArray(statistics.frequencies) ? statistics.frequencies : [];
  const frequencyPanel = analysisCardPanel('カテゴリ別の件数と割合', 'automatic', 'frequencies', true, 'descriptive_statistics');
  if (frequencies.length) {
    frequencyPanel.body.append(buildAnalysisFrequencyExplorer(frequencies, compact));
  } else {
    frequencyPanel.body.append(analysisElement('p', 'analysis-no-data', '割合を可視化できるカテゴリデータがありません。'));
  }
  grid.append(frequencyPanel.panel);

  const tests = Array.isArray(statistics.tests) ? statistics.tests : [];
  const crosstabs = Array.isArray(statistics.crosstabs) ? statistics.crosstabs : [];
  const selectedTerms = Array.isArray(statistics.selected_terms) ? statistics.selected_terms : [];
  const selectedTermPanel = analysisCardPanel('手動選択単語のクロス集計＋カイ二乗検定', 'configured', 'crosstabs', true, 'group_statistics');
  if (selectedTerms.length) {
    selectedTerms.slice(0, compact ? 8 : 20).forEach(term => {
      const columnVariable = `selected_term:${term}`;
      const rows = crosstabs.filter(item => item.column_variable === columnVariable);
      const test = tests.find(item => item.family === 'クロス集計' && (item.term === term || item.outcome === rows[0]?.table_id || item.outcome === columnVariable));
      const matchMode = rows[0]?.match_mode || statistics.crosstab_match_mode || 'normalized';
      const article = analysisElement('article', 'analysis-selected-term-result');
      article.append(analysisElement('h4', '', `「${term}」 × ${statistics.group_variable === 'role' ? '役割' : '話者'} / ${analysisMatchModeLabel(matchMode)}`));
      const evidence = analysisElement('button', 'secondary-button', '同じ一致条件で文脈を確認');
      evidence.type = 'button';
      evidence.addEventListener('click', () => {
        selectAnalysisPage('content');
        if (typeof runKwicSearch === 'function') runKwicSearch({query: term, matchMode, offset: 0});
      });
      article.append(evidence);
      if (rows.length) {
        const wrap = analysisElement('div', 'analysis-table-wrap');
        const table = analysisElement('table', 'analysis-table');
        const head = analysisElement('thead');
        const headRow = analysisElement('tr');
        ['比較群', '出現', '度数', '行%', '列%'].forEach(value => headRow.append(analysisElement('th', '', value)));
        head.append(headRow);
        const body = analysisElement('tbody');
        rows.forEach(item => {
          const row = analysisElement('tr');
          row.append(
            analysisElement('td', '', item.row_value),
            analysisElement('td', '', item.column_value),
            analysisElement('td', '', item.count || 0),
            analysisElement('td', '', analysisNumberText(item.row_percent, 1, '%')),
            analysisElement('td', '', analysisNumberText(item.column_percent, 1, '%'))
          );
          body.append(row);
        });
        table.append(head, body);
        wrap.append(table);
        article.append(wrap);
      }
      if (test && test.status === 'computed') {
        article.append(analysisElement(
          'p',
          'analysis-term-test-summary',
          `Pearson χ²(${test.df1}) = ${analysisNumberText(test.statistic, 3)}, ${analysisPValueText(test.p_value)}, Cramér's V = ${analysisNumberText(test.effect_size, 3)}, N = ${test.n || 0}`
        ));
      } else {
        article.append(analysisElement('p', 'analysis-term-test-summary unavailable', '比較群または「あり／なし」の一方が不足しているため検定は未計算です。'));
      }
      selectedTermPanel.body.append(article);
    });
  } else {
    selectedTermPanel.body.append(analysisElement('p', 'analysis-no-data', '「設定・手動」画面で単語を選び、検定を実行してください。'));
  }
  selectedTermPanel.body.append(analysisElement('p', 'analysis-caption', '発話単位の探索的検定です。同じ話者の発話は独立でない可能性があり、多重検定補正も行っていません。'));
  grid.append(selectedTermPanel.panel);

  const testsPanel = analysisCardPanel('グループ間の違いと効果の大きさ', 'automatic', 'statistical_tests', true, 'group_statistics');
  const computedTests = tests.filter(item => item.status === 'computed');
  if (computedTests.length) {
    testsPanel.body.append(buildAnalysisEffectChart(computedTests, compact));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', '統計検定の数値表を確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table analysis-stat-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['検定', '対象', '分析単位・測定単位', 'N', '欠測', '統計量', 'p値（未補正）', '効果量'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    computedTests.slice(0, compact ? 10 : 24).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.test),
        analysisElement('td', '', item.outcome_label || item.outcome),
        analysisElement('td', '', `${item.analysis_unit || '発話'} / ${item.unit || '—'}`),
        analysisElement('td', '', item.n || 0),
        analysisElement('td', '', item.missing ?? '—'),
        analysisElement('td', '', analysisNumberText(item.statistic, 3)),
        analysisElement('td', '', analysisPValueText(item.p_value)),
        analysisElement('td', '', item.effect_name ? `${item.effect_name} = ${analysisNumberText(item.effect_size, 3)}` : '—')
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    testsPanel.body.append(details);
  } else testsPanel.body.append(analysisElement('p', 'analysis-no-data', '比較群または標本数が不足しているため、推測統計を計算していません。'));
  const unavailableCount = tests.filter(item => item.status !== 'computed').length;
  testsPanel.body.append(analysisElement('p', 'analysis-caption', `発話単位の探索的検定・p値は多重検定未補正です。同じ話者の発話は独立ではない可能性があります。p値だけで結論を出さず、効果量・標本数・欠測と前提条件を確認してください。未計算 ${unavailableCount}件。`));
  grid.append(testsPanel.panel);

  const crosstabsPanel = analysisCardPanel('項目の組み合わせ比較（クロス集計）', 'automatic', 'crosstabs', true, 'group_statistics');
  if (crosstabs.length) {
    crosstabsPanel.body.append(buildAnalysisCrosstabExplorer(crosstabs, compact));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', 'クロス集計の数値表を確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['表', '行', '列', '度数', '行%', '列%'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    crosstabs.slice(0, compact ? 16 : 40).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.table_label),
        analysisElement('td', '', item.row_value),
        analysisElement('td', '', item.column_value),
        analysisElement('td', '', item.count || 0),
        analysisElement('td', '', analysisNumberText(item.row_percent, 1, '%')),
        analysisElement('td', '', analysisNumberText(item.column_percent, 1, '%'))
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    crosstabsPanel.body.append(details);
  } else crosstabsPanel.body.append(analysisElement('p', 'analysis-no-data', 'クロス集計できるデータがありません。'));
  grid.append(crosstabsPanel.panel);

  grid.append(analysisSectionHeading(
    'exports', '04 / OUTPUT & REVIEW', '出力して検証する',
    '標準出力のExcel、再分析用CSV、手法と限界をまとめています。論文利用前に原文・欠損・解析器の状態を確認してください。'
  ));

  const rowLimits = (analysisState.data?.research || {}).row_limits || {};
  const truncatedRows = Object.entries(rowLimits).filter(([, value]) => value.truncated);
  if (truncatedRows.length) grid.append(analysisElement('p', 'analysis-limit-note', `画面用プレビュー: ${truncatedRows.map(([key, value]) => `${key} ${value.returned_rows}/${value.total_rows}行`).join('、')}。全件はCSV/Excel出力で確認してください。`));
  if (coverage.cooccurrence_truncated) grid.append(analysisElement('p', 'analysis-limit-note', `共起の候補集合: 上位${coverage.cooccurrence_top_terms}語 / 最小${coverage.cooccurrence_min_count}発話。共起行 ${coverage.cooccurrence_returned_rows}/${coverage.cooccurrence_total_rows}件。候補制限により会話全体の全関係を表しません。`));
  grid.append(analysisExportDirectory('研究分析データの出力', 'automatic', [
    ['xlsx', 'Excelブック（標準出力）'],
    ['transformer_topics', 'Transformerテーマ CSV'],
    ['transformer_assignments', 'Transformer発話分類 CSV'],
    ['transformer_speakers', 'Transformer話者比較 CSV'],
    ['transformer_timeline', 'Transformer時間推移 CSV'],
    ['transformer_outliers', 'Transformer例外候補 CSV'],
    ['segments_all', '発話データ CSV'],
    ['morphemes', '形態素 CSV'],
    ['dependencies', '構文・係り受け CSV'],
    ['pos_frequency', '品詞頻度 CSV'],
    ['term_frequency', '語彙頻度 CSV'],
    ['cooccurrence', '共起 CSV'],
    ['descriptives', '記述統計 CSV'],
    ['frequencies', '度数分布 CSV'],
    ['crosstabs', 'クロス集計 CSV'],
    ['statistical_tests', '統計検定 CSV'],
    ['correlations', '相関 CSV'],
    ['analysis_methods', '分析手法・出典 CSV']
  ]));

  const methodsPanel = analysisCardPanel('分析方法と結果を見るときの注意', 'automatic', 'analysis_methods', true);
  const methods = Array.isArray(research.methods) ? research.methods : [];
  methods.forEach(item => {
    const article = analysisElement('article', 'analysis-method-item');
    article.append(
      analysisElement('strong', '', `${item.category}: ${item.method}`),
      analysisElement('p', '', `${item.engine || '内蔵'} ${item.engine_version || ''} / ${item.description || ''}`)
    );
    if (item.source_url && String(item.source_url).startsWith('https://')) {
      const link = analysisElement('a', '', item.source_title || '公式資料');
      link.href = item.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      article.append(link);
    }
    methodsPanel.body.append(article);
  });
  const limitations = Array.isArray(research.limitations) ? research.limitations : [];
  if (limitations.length) {
    const details = analysisElement('details', 'analysis-cautions');
    details.append(analysisElement('summary', '', '論文利用前に確認する限界'));
    const list = analysisElement('ul');
    limitations.forEach(value => list.append(analysisElement('li', '', value)));
    details.append(list);
    methodsPanel.body.append(details);
  }
  grid.append(methodsPanel.panel);
}

function buildAnalysisScopeSwitch() {
  const switcher = analysisElement('section', 'analysis-scope-switch');
  switcher.setAttribute('aria-label', '分析対象の単位');
  [
    ['overall', 'インタビュー全体', '会話全体の流れ・構造・統計を確認'],
    ['speakers', '話者ごと', '個人の発話量・語彙・属性を確認']
  ].forEach(([scope, titleText, description]) => {
    const active = analysisState.automaticScope === scope;
    const button = analysisElement('button', active ? 'active' : '');
    button.type = 'button';
    button.dataset.analysisScope = scope;
    button.setAttribute('aria-pressed', String(active));
    button.append(
      analysisElement('strong', '', titleText),
      analysisElement('span', '', description)
    );
    switcher.append(button);
  });
  return switcher;
}

function analysisSpeakerRoleText(metric) {
  const label = role => Object.hasOwn(speakerRoleLabels, role) ? speakerRoleLabels[role] : String(role || '役割未設定');
  if (metric?.role_status === 'mixed') {
    const roles = Array.isArray(metric.observed_roles) ? metric.observed_roles.map(label).join('・') : '';
    return roles ? `役割混在（${roles}）` : '役割混在';
  }
  return label(metric?.role);
}

function analysisSpeakerAttributeValue(metric, key) {
  const profile = metric && typeof metric.profile === 'object' ? metric.profile : {};
  if (key === 'role') return analysisSpeakerRoleText(metric);
  if (key === 'tags') return (Array.isArray(profile.tags) ? profile.tags : []).join('・');
  if (key.startsWith('custom:')) {
    const attributes = profile.attributes && typeof profile.attributes === 'object' ? profile.attributes : {};
    return String(attributes[key.slice(7)] || '').trim();
  }
  return String(profile[key] || '').trim();
}

function analysisSpeakerAttributeDimensions(speakers) {
  const fixed = [
    ['role', '役割'],
    ['organization', '組織'],
    ['department', '部署'],
    ['job_title', '役職'],
    ['conditions', '会話固有条件'],
    ['tags', 'タグ']
  ];
  const customKeys = new Set();
  speakers.forEach(metric => {
    const profile = metric && typeof metric.profile === 'object' ? metric.profile : {};
    const attributes = profile.attributes && typeof profile.attributes === 'object' ? profile.attributes : {};
    Object.keys(attributes).forEach(key => customKeys.add(key));
  });
  const candidates = [
    ...fixed,
    ...[...customKeys].sort((a, b) => a.localeCompare(b, 'ja')).map(key => [`custom:${key}`, key])
  ];
  return candidates
    .map(([key, label]) => ({
      key,
      label,
      values: [...new Set(speakers.map(metric => analysisSpeakerAttributeValue(metric, key)).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b, 'ja', {numeric: true, sensitivity: 'base'}))
    }))
    .filter(dimension => dimension.values.length);
}

function sortedAnalysisSpeakers(speakers, sortKey) {
  const values = [...speakers];
  const nameCompare = (a, b) => String(a.speaker_name || a.speaker).localeCompare(
    String(b.speaker_name || b.speaker), 'ja', {numeric: true, sensitivity: 'base'}
  );
  if (sortKey === 'speaker_name') return values.sort(nameCompare);
  if (sortKey === 'speaker_label') {
    return values.sort((a, b) => String(a.speaker).localeCompare(String(b.speaker), 'ja', {numeric: true}));
  }
  if (sortKey.startsWith('attribute:')) {
    const attributeKey = sortKey.slice(10);
    return values.sort((a, b) => {
      const valueA = analysisSpeakerAttributeValue(a, attributeKey);
      const valueB = analysisSpeakerAttributeValue(b, attributeKey);
      if (!valueA && valueB) return 1;
      if (valueA && !valueB) return -1;
      return valueA.localeCompare(valueB, 'ja', {numeric: true, sensitivity: 'base'}) || nameCompare(a, b);
    });
  }
  return values.sort((a, b) => Number(a.speaking_seconds == null) - Number(b.speaking_seconds == null)
    || Number(b.speaking_seconds || 0) - Number(a.speaking_seconds || 0) || nameCompare(a, b));
}

function buildAnalysisSpeakerTimelineChart(metric, bins) {
  const module = analysisElement('div', 'analysis-chart-module');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', `${metric.speaker_name || metric.speaker}の発話タイミング`),
    analysisElement('span', '', '各時間帯にこの話者が発話した秒数を示します。')
  );
  if (metric.timed_turn_count === 0 && metric.missing_time_turn_count > 0) {
    module.append(explanation, analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため、この話者の時間推移は表示できません。'));
    return module;
  }
  const stage = analysisElement('div', 'analysis-chart-stage');
  stage.append(buildAnalysisLineSvg([{
    id: metric.speaker,
    label: metric.speaker_name || metric.speaker,
    color: safeAnalysisColor(metric.color),
    values: bins.map(bin => Number(((bin.speakers || []).find(item => String(item.speaker) === String(metric.speaker)) || {}).seconds) || 0)
  }], bins));
  const legend = analysisElement('div', 'analysis-chart-legend');
  const entry = analysisElement('span');
  const marker = analysisElement('i');
  marker.style.backgroundColor = safeAnalysisColor(metric.color);
  entry.append(marker, document.createTextNode(metric.speaker_name || metric.speaker));
  legend.append(entry);
  module.append(explanation, stage, legend, analysisElement('p', 'analysis-chart-note', `${analysisObservedTimeText(metric)}。時刻あり発話だけを集計しています。時刻不明の発話は時間帯へ配置できません。`));
  return module;
}

function analysisMedian(values) {
  const sorted = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function analysisDurationSummary(segments) {
  const durations = segments
    .filter(item => item.valid_time === true && item.duration != null && item.duration !== '')
    .map(item => Number(item.duration))
    .filter(value => Number.isFinite(value) && value >= 0);
  return {
    median: analysisMedian(durations),
    longest: durations.length ? Math.max(...durations) : null
  };
}

function renderSpeakerAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const data = analysisState.data || {};
  const automatic = data.automatic || {};
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  if (!speakers.length) {
    fragment.append(analysisElement('p', 'analysis-no-data analysis-speaker-empty', '話者ごとの分析に利用できる発話データがありません。'));
    return fragment;
  }

  const dimensions = analysisSpeakerAttributeDimensions(speakers);
  const allowedSorts = new Set(['speaking_desc', 'speaker_name', 'speaker_label', ...dimensions.map(item => `attribute:${item.key}`)]);
  if (!allowedSorts.has(analysisState.speakerSort)) analysisState.speakerSort = 'speaking_desc';
  const activeDimension = analysisState.speakerSort.startsWith('attribute:')
    ? dimensions.find(item => item.key === analysisState.speakerSort.slice(10)) : null;
  if (analysisState.speakerAttributeFilter && (!activeDimension || !activeDimension.values.includes(analysisState.speakerAttributeFilter))) {
    analysisState.speakerAttributeFilter = '';
  }
  const sortedSpeakers = sortedAnalysisSpeakers(speakers, analysisState.speakerSort);
  const visibleSpeakers = analysisState.speakerAttributeFilter && activeDimension
    ? sortedSpeakers.filter(item => analysisSpeakerAttributeValue(item, activeDimension.key) === analysisState.speakerAttributeFilter)
    : sortedSpeakers;
  const selected = visibleSpeakers.find(item => String(item.speaker) === String(analysisState.selectedSpeaker))
    || visibleSpeakers[0];
  if (selected) analysisState.selectedSpeaker = String(selected.speaker);

  const toolbar = analysisElement('section', 'analysis-speaker-toolbar');
  const toolbarIntro = analysisElement('div', 'analysis-speaker-toolbar-intro');
  toolbarIntro.append(
    analysisElement('span', '', 'SPEAKER ANALYSIS'),
    analysisElement('h2', '', '話者を並べ替えて個別に確認'),
    analysisElement('p', '', dimensions.length
      ? `登録済み属性 ${dimensions.length}項目を利用できます。属性順では同じ値の話者をまとめて表示します。`
      : '話者名・ラベル・発話量で並べ替えられます。話者管理で属性を付けると属性順も選択できます。')
  );
  const controls = analysisElement('div', 'analysis-speaker-sort-controls');
  const sortLabel = analysisElement('label');
  sortLabel.append(analysisElement('span', '', '並べ替え'));
  const sortSelect = document.createElement('select');
  [
    ['speaking_desc', '発話時間が長い順'],
    ['speaker_name', '話者名順'],
    ['speaker_label', '話者ラベル順']
  ].forEach(([value, label]) => sortSelect.add(new Option(label, value)));
  dimensions.forEach(item => sortSelect.add(new Option(`属性：${item.label}`, `attribute:${item.key}`)));
  sortSelect.value = analysisState.speakerSort;
  sortSelect.addEventListener('change', () => {
    analysisState.speakerSort = sortSelect.value;
    analysisState.speakerAttributeFilter = '';
    renderAnalysisWorkspace();
  });
  sortLabel.append(sortSelect);
  controls.append(sortLabel);
  if (activeDimension) {
    const filterLabel = analysisElement('label');
    filterLabel.append(analysisElement('span', '', `${activeDimension.label}で絞り込み`));
    const filterSelect = document.createElement('select');
    filterSelect.add(new Option('すべての属性値', ''));
    activeDimension.values.forEach(value => filterSelect.add(new Option(`${value}（${speakers.filter(item => analysisSpeakerAttributeValue(item, activeDimension.key) === value).length}人）`, value)));
    filterSelect.value = analysisState.speakerAttributeFilter;
    filterSelect.addEventListener('change', () => {
      analysisState.speakerAttributeFilter = filterSelect.value;
      analysisState.selectedSpeaker = '';
      renderAnalysisWorkspace();
    });
    filterLabel.append(filterSelect);
    controls.append(filterLabel);
  }
  const exportLink = analysisExportLink('話者別集計CSV', 'speakers', 'analysis-inline-export');
  if (exportLink) controls.append(exportLink);
  toolbar.append(toolbarIntro, controls);
  fragment.append(toolbar);

  const workspace = analysisElement('div', 'analysis-speaker-dashboard');
  const browser = analysisElement('aside', 'analysis-speaker-browser');
  const browserHeading = analysisElement('header');
  browserHeading.append(
    analysisElement('strong', '', `話者 ${visibleSpeakers.length} / ${speakers.length}人`),
    analysisElement('span', '', activeDimension ? `${activeDimension.label}順` : 'クリックして個別分析を表示')
  );
  browser.append(browserHeading);
  const list = analysisElement('div', 'analysis-speaker-list');
  let previousGroup = null;
  visibleSpeakers.forEach(metric => {
    const groupValue = activeDimension
      ? analysisSpeakerAttributeValue(metric, activeDimension.key) || '未設定' : '';
    if (activeDimension && groupValue !== previousGroup) {
      list.append(analysisElement('div', 'analysis-speaker-group-label', `${activeDimension.label}：${groupValue}`));
      previousGroup = groupValue;
    }
    const active = selected && String(metric.speaker) === String(selected.speaker);
    const button = analysisElement('button', active ? 'active' : '');
    button.type = 'button';
    button.dataset.analysisSpeakerId = metric.speaker;
    button.setAttribute('aria-pressed', String(active));
    button.style.setProperty('--speaker-color', safeAnalysisColor(metric.color));
    const identity = analysisElement('span', 'analysis-speaker-list-identity');
    identity.append(
      analysisElement('i'),
      analysisElement('strong', '', metric.speaker_name || metric.speaker)
    );
    const detail = activeDimension
      ? `${groupValue} / ${analysisObservedTimeText(metric)}`
      : `${analysisSpeakerRoleText(metric)} / ${analysisObservedTimeText(metric)}`;
    button.append(identity, analysisElement('small', '', detail));
    list.append(button);
  });
  if (!visibleSpeakers.length) list.append(analysisElement('p', 'analysis-no-data', 'この属性値に該当する話者はいません。'));
  browser.append(list);
  workspace.append(browser);

  const detail = analysisElement('section', 'analysis-speaker-detail');
  detail.setAttribute('aria-label', '選択した話者の分析');
  if (!selected) {
    detail.append(analysisElement('p', 'analysis-no-data', '左の一覧から話者を選択してください。'));
    workspace.append(detail);
    fragment.append(workspace);
    return fragment;
  }
  const detailHeader = analysisElement('section', 'analysis-speaker-detail-header');
  detailHeader.style.setProperty('--speaker-color', safeAnalysisColor(selected.color));
  const titleGroup = analysisElement('div');
  titleGroup.append(
    analysisElement('span', '', selected.speaker),
    analysisElement('h2', '', selected.speaker_name || selected.speaker),
    analysisElement('p', '', `${analysisSpeakerRoleText(selected)}の発話を、インタビュー全体との比率を保ったまま表示しています。`)
  );
  const profileAttributes = analysisElement('div', 'analysis-speaker-attributes');
  dimensions.forEach(dimension => {
    const value = analysisSpeakerAttributeValue(selected, dimension.key);
    if (!value) return;
    const chip = analysisElement('span');
    chip.append(analysisElement('small', '', dimension.label), document.createTextNode(value));
    profileAttributes.append(chip);
  });
  if (!profileAttributes.childNodes.length) profileAttributes.append(analysisElement('span', 'empty', '登録属性なし'));
  detailHeader.append(titleGroup, profileAttributes);
  detail.append(detailHeader);

  const metrics = analysisElement('div', 'analysis-overview analysis-speaker-overview');
  appendAnalysisMetric(metrics, '発話時間', analysisObservedTimeText(selected), analysisNumberText(selected.speaking_percent, 1, '%'));
  appendAnalysisMetric(metrics, '発話回数', `${selected.turn_count || 0}回`, `平均 ${analysisNumberText(selected.average_turn_seconds, 1, '秒')}`);
  appendAnalysisMetric(metrics, '文字数', `${selected.characters || 0}字`, `${analysisNumberText(selected.characters_per_minute, 1)}字/分`);
  appendAnalysisMetric(metrics, '質問候補', `${selected.question_candidates || 0}件`);
  appendAnalysisMetric(metrics, '最初の発話', selected.first_start == null ? '—' : formatTime(selected.first_start));
  appendAnalysisMetric(metrics, '最後の発話', selected.last_end == null ? '—' : formatTime(selected.last_end));
  detail.append(metrics);

  const detailGrid = analysisElement('div', 'analysis-grid analysis-speaker-detail-grid');
  const bins = Array.isArray(automatic.time_bins) ? automatic.time_bins : [];
  const timelinePanel = analysisCardPanel('この話者の時間推移', 'automatic', '', true);
  if (bins.length) timelinePanel.body.append(buildAnalysisSpeakerTimelineChart(selected, bins));
  else timelinePanel.body.append(analysisElement('p', 'analysis-no-data', '時間推移を表示できません。'));
  detailGrid.append(timelinePanel.panel);

  const research = data.research || {};
  const linguistics = research.linguistics || {};
  const speakerTermRows = Array.isArray(linguistics.speaker_term_frequency) ? linguistics.speaker_term_frequency : [];
  const speakerTerms = speakerTermRows.find(item => String(item.speaker) === String(selected.speaker)) || {};
  const termsPanel = analysisCardPanel('この話者の内容語', 'automatic');
  const terms = Array.isArray(speakerTerms.terms) ? speakerTerms.terms : [];
  const maxTerm = Math.max(1, ...terms.map(item => Number(item.term_frequency) || 0));
  terms.slice(0, compact ? 10 : 15).forEach(item => appendSearchableTermBar(
    termsPanel.body,
    item.term,
    100 * (Number(item.term_frequency) || 0) / maxTerm,
    `TF ${item.term_frequency || 0} / DF ${item.document_frequency || 0} / ${item.upos || '—'}`,
    selected.color,
    selected.speaker
  ));
  if (!terms.length) termsPanel.body.append(analysisElement('p', 'analysis-no-data', 'この話者の内容語を抽出できませんでした。'));
  termsPanel.body.append(analysisElement('p', 'analysis-caption', `内容語 ${speakerTerms.content_token_count || 0}件 / 異なり語 ${speakerTerms.unique_term_count || 0}件。GiNZA/Sudachiの解析結果を話者内で再集計しています。`));
  detailGrid.append(termsPanel.panel);

  const distributionPanel = analysisCardPanel('話者内の発話分布', 'automatic');
  const speakerSegments = (Array.isArray(data.segments) ? data.segments : [])
    .filter(item => String(item.speaker) === String(selected.speaker) && !item.excluded);
  const durationSummary = analysisDurationSummary(speakerSegments);
  const distributionMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(distributionMetrics, '中央値', analysisNumberText(durationSummary.median, 2, '秒'));
  appendAnalysisMetric(distributionMetrics, '最長発話', analysisNumberText(durationSummary.longest, 2, '秒'));
  appendAnalysisMetric(distributionMetrics, '質問候補率', analysisNumberText(100 * speakerSegments.filter(item => item.question_candidate).length / Math.max(1, speakerSegments.length), 1, '%'));
  appendAnalysisMetric(distributionMetrics, '内容語多様性', speakerTerms.content_token_count
    ? analysisNumberText(100 * Number(speakerTerms.unique_term_count || 0) / Number(speakerTerms.content_token_count), 1, '%') : '—');
  distributionPanel.body.append(distributionMetrics, analysisElement('p', 'analysis-caption', '話者内の記述値です。話者間の優劣や発言の重要性を示すものではありません。'));
  detailGrid.append(distributionPanel.panel);

  const emotionPanel = analysisCardPanel('感情推定・手動コード', 'automatic');
  const emotionCounts = selected.emotion_counts && typeof selected.emotion_counts === 'object' ? selected.emotion_counts : {};
  const codeCounts = selected.code_counts && typeof selected.code_counts === 'object' ? selected.code_counts : {};
  const codeLabels = new Map(((data.manual || {}).codebook || []).map(item => [String(item.id), item.label || item.id]));
  const summaryRows = [
    ...Object.entries(emotionCounts).map(([label, count]) => [`感情推定 / ${label}`, count]),
    ...Object.entries(codeCounts).map(([id, count]) => [`手動コード / ${codeLabels.get(String(id)) || id}`, count])
  ].sort((a, b) => Number(b[1]) - Number(a[1]));
  summaryRows.forEach(([label, count]) => {
    const row = analysisElement('div', 'analysis-list-row');
    row.append(analysisElement('strong', '', label), analysisElement('span', '', `${count}件`));
    emotionPanel.body.append(row);
  });
  if (!summaryRows.length) emotionPanel.body.append(analysisElement('p', 'analysis-no-data', '感情推定または手動コードの集計はありません。'));
  emotionPanel.body.append(analysisElement('p', 'analysis-caption', '感情はモデル推定、コードは研究者による付与です。両者を同じ尺度として比較しないでください。'));
  detailGrid.append(emotionPanel.panel);

  const transitionPanel = analysisCardPanel('この話者との話者交替', 'automatic', '', true);
  const transitions = (Array.isArray(automatic.transitions) ? automatic.transitions : [])
    .filter(item => String(item.from_speaker) === String(selected.speaker) || String(item.to_speaker) === String(selected.speaker))
    .sort((a, b) => Number(b.count || 0) - Number(a.count || 0));
  if (transitions.length) {
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['方向', '相手話者', '回数', '平均間隔', '重なり候補'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    transitions.slice(0, compact ? 10 : 20).forEach(item => {
      const outgoing = String(item.from_speaker) === String(selected.speaker);
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', outgoing ? 'この話者 → 相手' : '相手 → この話者'),
        analysisElement('td', '', outgoing ? item.to_name || item.to_speaker : item.from_name || item.from_speaker),
        analysisElement('td', '', item.count || 0),
        analysisElement('td', '', analysisNumberText(item.average_gap_seconds, 2, '秒')),
        analysisElement('td', '', item.overlap_candidates || 0)
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    transitionPanel.body.append(wrap);
  } else transitionPanel.body.append(analysisElement('p', 'analysis-no-data', '他の話者との交替データがありません。'));
  transitionPanel.body.append(analysisElement('p', 'analysis-caption', '話者交替の回数は影響・同意・対立を意味しません。前後の発話を確認してください。'));
  detailGrid.append(transitionPanel.panel);

  const utterancePanel = analysisCardPanel('この話者の発話一覧', 'automatic', '', true);
  const utteranceList = analysisElement('div', 'analysis-speaker-utterances');
  speakerSegments.slice(0, compact ? 12 : 30).forEach(item => {
    const article = analysisElement('article', 'analysis-speaker-utterance');
    article.append(
      analysisElement('time', '', `${formatTime(item.start || 0)}–${formatTime(item.end || 0)}`),
      analysisElement('p', '', item.text || '（本文なし）')
    );
    utteranceList.append(article);
  });
  if (!speakerSegments.length) utteranceList.append(analysisElement('p', 'analysis-no-data', '表示できる発話がありません。'));
  utterancePanel.body.append(utteranceList);
  if (speakerSegments.length > (compact ? 12 : 30)) {
    utterancePanel.body.append(analysisElement('p', 'analysis-limit-note', `表示負荷を抑えるため先頭${compact ? 12 : 30}件を表示しています。全件は発話データCSVまたはExcelで確認できます。`));
  }
  detailGrid.append(utterancePanel.panel);
  detail.append(detailGrid);
  workspace.append(detail);
  fragment.append(workspace);
  return fragment;
}

function renderAutomaticAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const data = analysisState.data || {};
  const automatic = data.automatic || {};
  const overview = automatic.overview || {};
  const speakerScope = analysisState.automaticScope === 'speakers';
  const intro = analysisElement('div', 'analysis-result-intro');
  intro.dataset.analysisAnchor = 'overview';
  intro.append(
    analysisElement('span', 'analysis-kind automatic', '自動集計'),
    analysisElement('h2', '', speakerScope
      ? '話者ごとの会話データ分析'
      : '会話全体の分析結果'),
    analysisElement('p', '', speakerScope
      ? '話者を選び、発話量・時間推移・内容語・話者交替・登録属性を個別に確認します。属性は比較や並べ替えのための記述情報です。'
      : '概要から傾向をつかみ、気になる項目を選んで根拠の発話を確認できます。')
  );
  fragment.append(intro, buildAnalysisScopeSwitch());

  if (speakerScope) {
    fragment.append(renderSpeakerAnalysis(compact));
    return fragment;
  }

  const metrics = analysisElement('div', 'analysis-overview');
  appendAnalysisMetric(metrics, '時刻ありの最終終了位置', analysisEndpointText(overview.session_duration, overview.session_timed_turn_count, overview.session_missing_time_turn_count), '除外を含む全発話の時刻。録音ファイルの全長ではありません');
  appendAnalysisMetric(metrics, '対象発話', `${overview.included_segment_count || 0}件`, `全${overview.segment_count || 0}件`);
  appendAnalysisMetric(metrics, '話者', `${overview.speaker_count || 0}人`);
  appendAnalysisMetric(metrics, '実際の参加者', overview.participant_count === null || overview.participant_count === undefined ? '未登録' : `${overview.participant_count}人`, '研究者が準備画面で登録した人数');
  appendAnalysisMetric(metrics, '観測された参加発言者', overview.observed_participant_count == null ? '不明' : `${overview.observed_participant_count}人`, overview.mixed_role_speaker_count > 0 ? '同じ話者の役割が混在するため人数を確定できません' : 'UNKNOWNを除外・実参加人数とは別');
  appendAnalysisMetric(metrics, '発話時間（時刻あり）', analysisObservedTimeText(overview, 'total_speaking_seconds'));
  fragment.append(metrics);

  const observations = Array.isArray(automatic.observations) ? automatic.observations : [];
  if (observations.length) {
    const box = analysisElement('section', 'analysis-observations');
    box.append(analysisElement('h3', '', '確認候補'));
    observations.forEach(item => {
      const row = analysisElement('article', item.level === 'attention' ? 'attention' : 'info');
      row.append(analysisElement('strong', '', item.label || '確認候補'), analysisElement('p', '', item.message || ''));
      box.append(row);
    });
    fragment.append(box);
  }

  const summary = analysisElement('section', 'analysis-page');
  summary.dataset.analysisPage = 'overview';
  summary.setAttribute('aria-label', '概要');
  const observationsBox = fragment.querySelector('.analysis-observations');
  if (observationsBox) summary.append(observationsBox);
  summary.append(buildInsightSummary());
  const contentPage = analysisElement('section', 'analysis-page');
  contentPage.dataset.analysisPage = 'content';
  contentPage.setAttribute('aria-label', '内容・文脈検索');
  contentPage.append(buildContentExplorer(), buildSegmentClassificationPanel(compact), buildTransformerAnalysisPanel());
  fragment.append(buildAnalysisNavigation(), summary, contentPage);

  const grid = analysisElement('div', 'analysis-grid');
  grid.append(analysisSectionHeading(
    'conversation', '01 / CONVERSATION FLOW', '会話の流れを見る',
    'まず時間推移と話者別の参加量を見て、次に話者交替・無音・重なりの候補を確認します。'
  ));
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  const timelinePanel = analysisCardPanel('発話量の変化（時間別）', 'automatic', 'timeline', true, 'participation');
  const bins = Array.isArray(automatic.time_bins) ? automatic.time_bins : [];
  const allTimeMissing = overview.timed_turn_count === 0 && overview.missing_time_turn_count > 0;
  if (bins.length && !allTimeMissing) timelinePanel.body.append(buildAnalysisTimelineChart(bins, speakers));
  else timelinePanel.body.append(analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため、時間推移を表示できません。'));
  grid.append(timelinePanel.panel);

  const excitementPanel = analysisCardPanel('盛り上がりと議題・話題（時間別）', 'automatic', '', true, 'conversation_dynamics');
  if (allTimeMissing) excitementPanel.body.append(analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため、活発度は算出できません。'));
  else excitementPanel.body.append(buildAnalysisExcitementChart(bins, data.session_outline));
  grid.append(excitementPanel.panel);

  const speakerPanel = analysisCardPanel('話者ごとの発話量', 'automatic', 'speakers', true, 'participation');
  if (!speakers.length) {
    speakerPanel.body.append(analysisElement('p', 'analysis-no-data', '発話データがありません。'));
  } else {
    speakers.forEach(item => {
      appendAnalysisBar(
        speakerPanel.body,
        item.speaker_name || item.speaker || '話者',
        item.speaking_percent,
        `${analysisNumberText(item.speaking_percent, 1, '%')} / ${analysisObservedTimeText(item)} / ${item.turn_count || 0}回`,
        item.color
      );
    });
  }
  grid.append(speakerPanel.panel);

  const balance = automatic.balance || {};
  const balancePanel = analysisCardPanel(balance.denominator === 'observed_speakers' ? '全観測話者の発言バランス' : '参加者の発言バランス', 'automatic', '', false, 'participation');
  const balanceMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(balanceMetrics, '均等度', balance.normalized_evenness == null ? '未計算' : analysisNumberText(Number(balance.normalized_evenness) * 100, 1, '%'), '観測発言者内で100%に近いほど均等');
  appendAnalysisMetric(balanceMetrics, '最大比率', analysisNumberText(balance.max_participant_percent, 1, '%'), balance.max_participant_name || '—');
  appendAnalysisMetric(balanceMetrics, 'Gini係数', analysisNumberText(balance.gini, 3), '0に近いほど均等');
  balancePanel.body.append(balanceMetrics, analysisElement('p', 'analysis-caption', `${balance.denominator_label || '観測された発言者内'} / 分母 ${balance.balance_speaker_count ?? '—'}人。${balance.denominator_note || ''} 時刻欠測 ${balance.missing_time_turn_count ?? '—'}発話。発言量の偏りを示す記述値で、発言の重要性や影響力ではありません。`));
  if (balance.unavailable_reason === 'mixed_roles') balancePanel.body.append(analysisElement('p', 'content-inline-notice', '同じ話者の役割が混在するため、参加者内の割合・均等度は算出できません。全体時間は保持しています。'));
  grid.append(balancePanel.panel);

  const moderatorPanel = analysisCardPanel('司会者と参加者の発言関係', 'automatic', '', false, 'participation');
  const moderator = automatic.moderator || {};
  const moderatorMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(moderatorMetrics, '司会発話比率', moderator.role_aggregation_status === 'mixed' ? '役割混在で算出不可' : moderator.assigned ? analysisNumberText(moderator.speaking_percent, 1, '%') : '役割未設定');
  appendAnalysisMetric(moderatorMetrics, '質問候補', moderator.role_aggregation_status === 'mixed' ? '役割混在で算出不可' : analysisNumberText(moderator.question_candidates, 0, '件'));
  appendAnalysisMetric(moderatorMetrics, '参加者応答', `${moderator.participant_responses || 0}件`);
  appendAnalysisMetric(moderatorMetrics, '参加者間遷移', `${moderator.participant_to_participant_transitions || 0}件`);
  moderatorPanel.body.append(moderatorMetrics, analysisElement('p', 'analysis-caption', '質問・応答は表記と話者遷移からの候補です。進行品質の評価ではありません。'));
  grid.append(moderatorPanel.panel);

  const transitionsPanel = analysisCardPanel('発言者の交替パターン', 'automatic', 'transitions', true, 'conversation_dynamics');
  const transitions = Array.isArray(automatic.transitions) ? automatic.transitions : [];
  if (transitions.length) {
    const tableWrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['前の話者', '次の話者', '回数', '平均間隔', '重なり候補'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    transitions.slice(0, compact ? 8 : 20).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.from_name || item.from_speaker),
        analysisElement('td', '', item.to_name || item.to_speaker),
        analysisElement('td', '', item.count || 0),
        analysisElement('td', '', analysisNumberText(item.average_gap_seconds, 2, '秒')),
        analysisElement('td', '', item.overlap_candidates || 0)
      );
      body.append(row);
    });
    table.append(head, body);
    tableWrap.append(table);
    transitionsPanel.body.append(tableWrap, analysisElement('p', 'analysis-caption', '遷移回数は影響関係や同意を意味しません。'));
  } else transitionsPanel.body.append(analysisElement('p', 'analysis-no-data', '話者交替のデータがありません。'));
  grid.append(transitionsPanel.panel);

  const gapsPanel = analysisCardPanel('沈黙・同時発話の候補', 'automatic', 'gaps', false, 'conversation_dynamics');
  const longGaps = Array.isArray(automatic.long_gaps) ? automatic.long_gaps : [];
  const overlaps = Array.isArray(automatic.overlap_candidates) ? automatic.overlap_candidates : [];
  const gapSummary = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(gapSummary, '長い無音候補', `${longGaps.length}件`);
  appendAnalysisMetric(gapSummary, '重なり候補', `${overlaps.length}件`);
  gapsPanel.body.append(gapSummary);
  const overlapExport = analysisExportLink('重なりCSV', 'overlaps', 'analysis-inline-export');
  if (overlapExport) gapsPanel.body.append(overlapExport);
  gapsPanel.body.append(analysisElement('p', 'analysis-caption', '沈黙・遮り・熱意などの意味は音声と文脈を確認して判断してください。'));
  grid.append(gapsPanel.panel);

  const emotionPanel = analysisCardPanel('声から推定した感情の分布', 'automatic', 'emotions', false, 'audio_emotion');
  const emotions = Array.isArray(automatic.emotions) ? automatic.emotions : [];
  if (emotions.length) {
    emotions.slice(0, compact ? 10 : 20).forEach(item => {
      const row = analysisElement('div', 'analysis-list-row');
      const emotionLabel = [
        item.speaker_name || item.speaker,
        item.model_name || item.model || '感情モデル',
        item.label || item.emotion
      ].filter(Boolean).join(' / ');
      row.append(
        analysisElement('strong', '', emotionLabel),
        analysisElement('span', '', `${item.count || 0}件 / ${analysisObservedTimeText(item, 'seconds')}`)
      );
      emotionPanel.body.append(row);
    });
  } else emotionPanel.body.append(analysisElement('p', 'analysis-no-data', '音声感情分析が未実行、または利用できる推定値がありません。'));
  emotionPanel.body.append(analysisElement('p', 'analysis-caption', 'モデル推定は本人の感情を確定するものではありません。'));
  grid.append(emotionPanel.panel);

  const groups = Array.isArray(automatic.groups) ? automatic.groups : [];
  if (groups.length) {
    const groupsPanel = analysisCardPanel('話者グループの比較', 'configured', 'groups', false, 'participation');
    groups.forEach(item => appendAnalysisBar(
      groupsPanel.body, item.group || '未設定', item.speaking_percent,
      `${item.speaker_count || 0}人 / ${item.turn_count || 0}回 / ${analysisObservedTimeText(item)}`,
      '#9B51E0'
    ));
    grid.append(groupsPanel.panel);
  }

  grid.append(analysisSectionHeading(
    'language', '02 / LANGUAGE STRUCTURE', '語と構文を探索する',
    '特徴語から全体像をつかみ、形態素・共起関係・文ごとの係り受けへ段階的に掘り下げます。'
  ));
  const keywordsPanel = analysisCardPanel('会話でよく使われた特徴語', 'automatic', 'keywords', false, 'lexical_frequency');
  const keywords = Array.isArray(automatic.keywords) ? automatic.keywords : [];
  const maxKeyword = Math.max(1, ...keywords.map(item => Number(item.count) || 0));
  if (keywords.length) {
    keywords.slice(0, compact ? 10 : 15).forEach(item => appendAnalysisBar(
      keywordsPanel.body, item.term, 100 * (Number(item.count) || 0) / maxKeyword, `${item.count || 0}回`, '#6C8B3C'
    ));
  } else keywordsPanel.body.append(analysisElement('p', 'analysis-no-data', '特徴語候補を抽出できませんでした。'));
  keywordsPanel.body.append(analysisElement('p', 'analysis-caption', '出現頻度による簡易候補で、研究テーマを自動決定するものではありません。'));
  grid.append(keywordsPanel.panel);

  appendResearchAnalysis(grid, compact);

  const qualityPanel = analysisCardPanel('分析に使ったデータの確認', 'automatic');
  const quality = automatic.data_quality || {};
  const qualityList = analysisElement('div', 'analysis-quality-list');
  [
    ['話者未判定の発話', `${quality.unknown_speaker_segments || 0}件`],
    ['本文が空の発話', `${quality.empty_text_segments || 0}件`],
    ['時間が0秒の発話', `${quality.zero_duration_segments || 0}件`],
    ['時刻が不正な発話', `${quality.invalid_time_segments || 0}件`],
    ['感情データ範囲', analysisNumberText(quality.emotion_coverage_percent, 1, '%')],
    ['分析から除外', `${quality.excluded_segments || 0}件`]
  ].forEach(([label, value]) => {
    const row = analysisElement('div', 'analysis-list-row');
    row.append(analysisElement('span', '', label), analysisElement('strong', '', value));
    qualityList.append(row);
  });
  qualityPanel.body.append(qualityList);
  grid.append(qualityPanel.panel);
  grid.append(analysisExportDirectory('自動分析データの出力', 'automatic', [
    ['summary', '概要 CSV'],
    ['observations', '確認候補 CSV'],
    ['speakers', '話者別発話量 CSV'],
    ['transitions', '話者遷移 CSV'],
    ['gaps', '無音候補 CSV'],
    ['overlaps', '重なり候補 CSV'],
    ['keywords', '特徴語候補 CSV'],
    ['emotions', '感情推定 CSV'],
    ['timeline', '時間推移 CSV'],
    ['groups', '属性比較 CSV']
  ]));
  // Keep existing panels and controls mounted when switching sections. This
  // preserves search input, running-job status, and the method view's panels.
  let page;
  [...grid.children].forEach(node => {
    if (node.dataset.analysisAnchor) {
      page = analysisElement('section', 'analysis-page analysis-grid');
      page.dataset.analysisPage = node.dataset.analysisAnchor;
      page.setAttribute('aria-label', node.querySelector('h2')?.textContent || '分析結果');
      fragment.append(page);
    }
    if (page) page.append(node);
  });
  fragment.querySelector('[data-analysis-page="exports"]')?.append(buildAnalysisStorage());
  applyAnalysisPage(fragment, analysisState.automaticPage);

  const cautions = Array.isArray(data.cautions) ? data.cautions : [];
  if (cautions.length) {
    const details = analysisElement('details', 'analysis-cautions');
    details.append(analysisElement('summary', '', '分析値を読むときの注意'));
    const list = analysisElement('ul');
    cautions.forEach(value => list.append(analysisElement('li', '', value)));
    details.append(list);
    fragment.append(details);
  }
  return fragment;
}

function analysisField(labelText, control, noteText = '') {
  const label = analysisElement('label', 'field analysis-field');
  label.append(analysisElement('span', '', labelText), control);
  if (noteText) label.append(analysisElement('small', '', noteText));
  return label;
}

function analysisGroupByOptions() {
  const options = {
    none: '比較しない',
    role: '会話役割',
    organization: '組織',
    department: '部署',
    job_title: '役職'
  };
  const automatic = analysisState.data && analysisState.data.automatic || {};
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  analysisSpeakerAttributeDimensions(speakers)
    .filter(dimension => dimension.key.startsWith('custom:'))
    .forEach(dimension => {
      const key = dimension.key.slice('custom:'.length);
      options[`attribute:${key}`] = `事前アンケート：${dimension.label}`;
    });
  const current = String(analysisState.config.group_by || '');
  if (current.startsWith('attribute:') && !options[current]) {
    options[current] = `事前アンケート：${current.slice('attribute:'.length)}`;
  }
  return options;
}

function analysisConfigControl(field, type = 'text', options = null) {
  const value = analysisState.config[field];
  let control;
  if (type === 'textarea') {
    control = document.createElement('textarea');
    control.rows = field === 'research_question' || field === 'analyst_memo' ? 4 : 2;
    control.value = value || '';
  } else if (type === 'select') {
    control = document.createElement('select');
    Object.entries(options || {}).forEach(([optionValue, label]) => control.add(new Option(label, optionValue)));
    control.value = value === undefined || value === null ? '' : String(value);
  } else {
    control = document.createElement('input');
    control.type = type;
    if (type === 'checkbox') control.checked = Boolean(value);
    else control.value = value === undefined || value === null ? '' : String(value);
  }
  control.dataset.analysisConfig = field;
  return control;
}

function analysisMatchModeLabel(mode) {
  return ({normalized: '正規化語の完全一致', surface: '表層語の完全一致', literal: '本文の部分一致（大文字小文字を区別）'})[mode] || '一致条件未確認';
}

function analysisTermCrosstabSelector(compact) {
  const container = analysisElement('div', 'analysis-term-selector');
  const selected = Array.isArray(analysisState.config.crosstab_terms)
    ? analysisState.config.crosstab_terms
    : [];
  const input = analysisConfigControl('crosstab_terms', 'text');
  input.placeholder = '例：改善, 価格, 使いやすい';
  container.append(
    analysisField(
      'クロス集計＋カイ二乗検定をする単語',
      input,
      'カンマ・読点・改行区切り。最大30語。発話ごとの「あり／なし」と統計の比較軸を集計します。'
    )
  );

  container.append(analysisField('語の一致条件（文脈検索と共通）', analysisConfigControl('crosstab_match_mode', 'select', {normalized: analysisMatchModeLabel('normalized'), surface: analysisMatchModeLabel('surface'), literal: analysisMatchModeLabel('literal')})));
  const candidates = (((analysisState.data || {}).research || {}).linguistics || {}).term_frequency || [];
  const candidateWrap = analysisElement('div', 'analysis-term-candidates');
  candidateWrap.append(analysisElement('span', '', '頻出語から選択'));
  candidates.slice(0, compact ? 16 : 30).forEach(item => {
    const term = String(item.term || '').trim();
    if (!term) return;
    const button = analysisElement('button', selected.includes(term) ? 'active' : '', term);
    button.type = 'button';
    button.dataset.analysisCrosstabTerm = term;
    button.setAttribute('aria-pressed', selected.includes(term) ? 'true' : 'false');
    candidateWrap.append(button);
  });
  if (!candidates.length) candidateWrap.append(analysisElement('small', '', '候補語は分析実行後に表示されます。'));

  const action = analysisElement('button', 'primary-button small analysis-run-term-test', '選択した単語で検定を実行');
  action.type = 'button';
  action.dataset.analysisRunTermCrosstab = 'true';
  container.append(candidateWrap, action);
  return container;
}

function analysisCodebookEditor(compact) {
  const container = analysisElement('div', 'analysis-codebook');
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  if (!codebook.length) {
    container.append(analysisElement('p', 'analysis-no-data', 'コードはまだありません。研究質問に沿ってコード名と定義を追加してください。'));
  }
  codebook.forEach((code, index) => {
    const card = analysisElement(compact ? 'details' : 'article', 'analysis-code-card');
    if (compact) {
      const summary = analysisElement('summary');
      const swatch = analysisElement('i');
      swatch.style.backgroundColor = safeAnalysisColor(code.color, speakerThemeColors[index % speakerThemeColors.length]);
      summary.append(swatch, analysisElement('strong', '', code.label || `コード ${index + 1}`));
      card.append(summary);
    }
    const body = analysisElement('div', 'analysis-code-body');
    const top = analysisElement('div', 'analysis-code-top');
    const color = document.createElement('input');
    color.type = 'color';
    color.value = safeAnalysisColor(code.color, speakerThemeColors[index % speakerThemeColors.length]);
    color.dataset.analysisCodeId = code.id;
    color.dataset.analysisCodeField = 'color';
    color.setAttribute('aria-label', `${code.label || `コード ${index + 1}`}の色`);
    const label = document.createElement('input');
    label.type = 'text';
    label.maxLength = 120;
    label.value = code.label || '';
    label.placeholder = 'コード名';
    label.dataset.analysisCodeId = code.id;
    label.dataset.analysisCodeField = 'label';
    const remove = analysisElement('button', 'analysis-remove-code', '削除');
    remove.type = 'button';
    remove.dataset.analysisRemoveCode = code.id;
    remove.setAttribute('aria-label', `${code.label || `コード ${index + 1}`}を削除`);
    top.append(color, label, remove);
    body.append(top);
    [
      ['category', 'カテゴリー', '例：利用上の課題'],
      ['theme', 'テーマ', '例：導入を阻む負担']
    ].forEach(([field, caption, placeholder]) => {
      const input = document.createElement('input');
      input.type = 'text';
      input.maxLength = 160;
      input.value = code[field] || '';
      input.placeholder = placeholder;
      input.dataset.analysisCodeId = code.id;
      input.dataset.analysisCodeField = field;
      body.append(analysisField(caption, input));
    });
    [
      ['description', '定義', 'このコードに含める意味・判断基準'],
      ['include_example', '含める例', '該当する発話の例'],
      ['exclude_example', '含めない例', '似ているが除外する発話の例']
    ].forEach(([field, caption, placeholder]) => {
      const textarea = document.createElement('textarea');
      textarea.rows = field === 'description' ? 3 : 2;
      textarea.maxLength = field === 'description' ? 4000 : 2000;
      textarea.value = code[field] || '';
      textarea.placeholder = placeholder;
      textarea.dataset.analysisCodeId = code.id;
      textarea.dataset.analysisCodeField = field;
      body.append(analysisField(caption, textarea));
    });
    card.append(body);
    container.append(card);
  });
  const add = analysisElement('button', 'secondary-button analysis-add-code', '＋ コードを追加');
  add.type = 'button';
  add.dataset.analysisAddCode = 'true';
  container.append(add);
  return container;
}

function analysisAnnotation(segmentId) {
  if (!analysisState.annotations[segmentId] || typeof analysisState.annotations[segmentId] !== 'object') {
    analysisState.annotations[segmentId] = {
      codes: [], interaction_tags: [], elicitation: 'unknown', interaction_links: [],
      dialogue_act: '', importance_score: null, review_score: null, sensitivity_score: null,
      classification_status: 'unreviewed', classification_note: '',
      memo: '', important: false, excluded: false
    };
  }
  return analysisState.annotations[segmentId];
}

function analysisSegmentMatches(segment) {
  const query = analysisState.segmentQuery.trim().toLocaleLowerCase();
  const annotation = analysisState.annotations[segment.id] || {};
  const annotated = Boolean(
    (annotation.codes || []).length
    || (annotation.interaction_tags || []).length
    || annotation.elicitation && annotation.elicitation !== 'unknown'
    || (annotation.interaction_links || []).length
    || annotation.memo
    || annotation.dialogue_act
    || annotation.importance_score !== undefined && annotation.importance_score !== null
    || annotation.review_score !== undefined && annotation.review_score !== null
    || annotation.sensitivity_score !== undefined && annotation.sensitivity_score !== null
    || annotation.classification_status && annotation.classification_status !== 'unreviewed'
    || annotation.classification_note
    || annotation.important
    || annotation.excluded
  );
  if (analysisState.annotatedOnly && !annotated) return false;
  if (!query) return true;
  return `${segment.speaker_name || ''} ${segment.speaker || ''} ${segment.text || ''}`
    .toLocaleLowerCase().includes(query);
}

function renderAnalysisSegmentItems(list, compact) {
  list.replaceChildren();
  const segments = Array.isArray(analysisState.data.segments) ? analysisState.data.segments : [];
  const visible = segments.filter(analysisSegmentMatches);
  const limit = compact ? 100 : 200;
  const count = analysisElement('p', 'analysis-segment-count', `表示 ${Math.min(visible.length, limit)} / 該当 ${visible.length} / 全 ${segments.length}発話`);
  list.append(count);
  if (!visible.length) {
    list.append(analysisElement('p', 'analysis-no-data', '条件に一致する発話がありません。'));
    return;
  }
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  const interactionTags = ((analysisState.data.manual || {}).interaction_tags || []);
  const classificationResult = ((analysisState.data.segment_classification || {}).result || {});
  const proposalById = new Map((classificationResult.segments || []).map(row => [String(row.segment_id), row]));
  visible.slice(0, limit).forEach(segment => {
    const annotation = analysisState.annotations[segment.id] || {
      codes: [], interaction_tags: [], elicitation: 'unknown', interaction_links: [],
      dialogue_act: '', importance_score: null, review_score: null, sensitivity_score: null,
      classification_status: 'unreviewed', classification_note: '',
      memo: '', important: false, excluded: false
    };
    const card = analysisElement('article', 'analysis-segment-card');
    card.dataset.analysisSegmentCard = segment.id;
    const header = analysisElement('header');
    const meta = analysisElement('div');
    const speaker = analysisElement('strong', '', segment.speaker_name || segment.speaker || '話者未判定');
    speaker.style.borderColor = safeAnalysisColor(segment.color);
    meta.append(
      analysisElement('span', 'analysis-segment-time', `#${segment.utterance_order || '—'}`),
      analysisElement('span', 'analysis-segment-time', `${formatTime(segment.start || 0)}–${formatTime(segment.end || 0)}`),
      speaker
    );
    const status = analysisElement('div', 'analysis-segment-status');
    if (annotation.important) status.append(analysisElement('span', 'important', '重要引用'));
    if (annotation.excluded) status.append(analysisElement('span', 'excluded', '分析除外'));
    header.append(meta, status);
    const quote = analysisElement('p', 'analysis-segment-text', segment.text || '（本文なし）');
    card.append(header, quote);

    const proposal = proposalById.get(String(segment.id));
    if (proposal) {
      const proposalGrid = analysisElement('div', 'segment-proposal-grid');
      const proposalCard = (label, value, source) => {
        const item = analysisElement('article');
        item.append(analysisElement('strong', '', label), analysisElement('span', '', value || '提案なし'));
        if (source && source.dialogue_act) {
          const apply = analysisElement('button', 'secondary-button small', '手動欄へ反映');
          apply.type = 'button';
          apply.dataset.applyClassificationProposal = source === proposal.llm ? 'llm' : 'template';
          apply.dataset.analysisSegmentId = segment.id;
          item.append(apply);
        }
        return item;
      };
      const scoreText = source => source && source.dialogue_act_label
        ? `${source.dialogue_act_label} / 重要${source.importance_score ?? '—'}・要確認${source.review_score ?? '—'}・機密${source.sensitivity_score ?? '—'}`
        : '';
      proposalGrid.append(
        proposalCard('テンプレート', scoreText(proposal.template), proposal.template),
        proposalCard('Jev', scoreText(proposal.llm), proposal.llm),
        proposalCard('Transformer話題', (proposal.transformer || {}).topic_label || '', null)
      );
      card.append(proposalGrid);
    }

    const classificationControls = analysisElement('div', 'segment-manual-classification');
    const dialogueAct = document.createElement('select');
    dialogueAct.add(new Option('未確定', ''));
    Object.entries(dialogueActLabels).forEach(([value, label]) => dialogueAct.add(new Option(label, value)));
    dialogueAct.value = annotation.dialogue_act || '';
    dialogueAct.dataset.analysisSegmentId = segment.id;
    dialogueAct.dataset.analysisAnnotationField = 'dialogue_act';
    classificationControls.append(analysisField('手動：発話種別', dialogueAct));
    [
      ['importance_score', '手動：重要度'],
      ['review_score', '手動：要確認度'],
      ['sensitivity_score', '手動：機密らしさ']
    ].forEach(([field, label]) => {
      const input = document.createElement('input');
      input.type = 'number'; input.min = '0'; input.max = '100'; input.step = '1';
      input.value = annotation[field] === undefined || annotation[field] === null ? '' : String(annotation[field]);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = field;
      classificationControls.append(analysisField(label, input, '0〜100。空欄は未確定。'));
    });
    const classificationStatus = document.createElement('select');
    [['unreviewed', '未確認'], ['draft', '確認途中'], ['reviewed', '確認済み']]
      .forEach(([value, label]) => classificationStatus.add(new Option(label, value)));
    classificationStatus.value = annotation.classification_status || 'unreviewed';
    classificationStatus.dataset.analysisSegmentId = segment.id;
    classificationStatus.dataset.analysisAnnotationField = 'classification_status';
    classificationControls.append(analysisField('判定状態', classificationStatus));
    card.append(classificationControls);

    const classificationNote = document.createElement('textarea');
    classificationNote.rows = 2;
    classificationNote.maxLength = 5000;
    classificationNote.value = annotation.classification_note || '';
    classificationNote.placeholder = '自動提案を採用・修正・保留した根拠';
    classificationNote.dataset.analysisSegmentId = segment.id;
    classificationNote.dataset.analysisAnnotationField = 'classification_note';
    card.append(analysisField('分類確認メモ', classificationNote));

    const codeGroup = analysisElement('fieldset', 'analysis-chip-group');
    codeGroup.append(analysisElement('legend', '', 'テーマコード'));
    if (!codebook.length) codeGroup.append(analysisElement('p', 'analysis-inline-note', '先にコードブックへコードを追加してください。'));
    codebook.forEach(code => {
      const label = analysisElement('label', 'analysis-code-chip');
      label.style.setProperty('--code-color', safeAnalysisColor(code.color));
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = (annotation.codes || []).includes(code.id);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = 'codes';
      input.dataset.analysisAnnotationValue = code.id;
      label.append(input, analysisElement('span', '', code.label));
      codeGroup.append(label);
    });
    card.append(codeGroup);

    const interactionGroup = analysisElement('details', 'analysis-interaction-group');
    interactionGroup.append(analysisElement('summary', '', '相互作用タグを確認・設定'));
    const chips = analysisElement('div', 'analysis-chip-group inline');
    interactionTags.forEach(tag => {
      const label = analysisElement('label', 'analysis-interaction-chip');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = (annotation.interaction_tags || []).includes(tag.id);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = 'interaction_tags';
      input.dataset.analysisAnnotationValue = tag.id;
      label.append(input, analysisElement('span', '', tag.label));
      chips.append(label);
    });
    interactionGroup.append(chips);
    card.append(interactionGroup);

    const elicitation = document.createElement('select');
    [
      ['unknown', '不明・未確認'], ['spontaneous', '自発的な発言'],
      ['moderator_prompted', '司会者の質問・働きかけを受けた発言'],
      ['participant_prompted', '他の参加者の働きかけを受けた発言'],
      ['other_prompted', 'その他の働きかけを受けた発言']
    ].forEach(([value, label]) => elicitation.add(new Option(label, value)));
    elicitation.value = annotation.elicitation || 'unknown';
    elicitation.dataset.analysisSegmentId = segment.id;
    elicitation.dataset.analysisAnnotationField = 'elicitation';
    card.append(analysisField('発話のきっかけ', elicitation, '自発か、誰の働きかけを受けたかを記録します。不明は推測で選びません。'));

    const evidenceGroup = analysisElement('details', 'analysis-interaction-group');
    evidenceGroup.append(analysisElement('summary', '', '根拠発話との相互作用リンク'));
    evidenceGroup.append(analysisElement('p', 'analysis-inline-note', '同意・反論・補足・変化は、対象となる発話を選び、根拠メモとともに結びます。単独タグだけからは意見形成を結論づけません。'));
    const linkControls = analysisElement('div', 'analysis-link-controls');
    const target = document.createElement('select');
    target.dataset.analysisInteractionTarget = segment.id;
    target.add(new Option('対象発話を選択', ''));
    const currentIndex = segments.findIndex(item => item.id === segment.id);
    segments.slice(Math.max(0, currentIndex - 12), currentIndex + 13)
      .filter(item => item.id !== segment.id)
      .forEach(item => target.add(new Option(
        `#${item.utterance_order || '—'} ${item.speaker_name || item.speaker}: ${String(item.text || '').slice(0, 42)}`,
        item.id
      )));
    const relation = document.createElement('select');
    relation.dataset.analysisInteractionRelation = segment.id;
    [
      ['response', '応答'], ['agreement', '同意・賛同'], ['disagreement', '不一致・反対'],
      ['differentiation', '立場の差異化'], ['change', '意見の変化'], ['word_use', '言葉の意味の違い'],
      ['repetition', '反復・強調'], ['engagement', '補足・発展']
    ].forEach(([value, label]) => relation.add(new Option(label, value)));
    const evidenceMemo = document.createElement('input');
    evidenceMemo.type = 'text';
    evidenceMemo.maxLength = 2000;
    evidenceMemo.placeholder = '根拠メモ（任意）';
    evidenceMemo.dataset.analysisInteractionMemo = segment.id;
    const addLink = analysisElement('button', 'secondary-button small', 'リンクを追加');
    addLink.type = 'button';
    addLink.dataset.analysisAddInteractionLink = segment.id;
    linkControls.append(target, relation, evidenceMemo, addLink);
    evidenceGroup.append(linkControls);
    const links = Array.isArray(annotation.interaction_links) ? annotation.interaction_links : [];
    if (links.length) {
      const list = analysisElement('ul', 'analysis-link-list');
      const relationLabels = {
        response: '応答', agreement: '同意・賛同', disagreement: '不一致・反対',
        differentiation: '立場の差異化', change: '意見の変化', word_use: '言葉の意味の違い',
        repetition: '反復・強調', engagement: '補足・発展'
      };
      links.forEach((link, index) => {
        const targetSegment = segments.find(item => item.id === link.target_segment_id) || {};
        const label = analysisElement('span', '', `${relationLabels[link.relation] || link.relation}：#${targetSegment.utterance_order || '—'} ${targetSegment.speaker_name || targetSegment.speaker || link.target_segment_id}`);
        const removeLink = analysisElement('button', 'secondary-button small', '削除');
        removeLink.type = 'button';
        removeLink.dataset.analysisRemoveInteractionLink = 'true';
        removeLink.dataset.analysisInteractionSource = segment.id;
        removeLink.dataset.analysisInteractionIndex = String(index);
        const row = analysisElement('li');
        row.append(label, removeLink);
        if (link.evidence_memo) row.append(analysisElement('small', '', link.evidence_memo));
        list.append(row);
      });
      evidenceGroup.append(list);
    }
    card.append(evidenceGroup);

    const flags = analysisElement('div', 'analysis-annotation-flags');
    [
      ['important', '重要引用として残す'],
      ['excluded', 'この発話を自動集計から除外']
    ].forEach(([field, labelText]) => {
      const label = analysisElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = Boolean(annotation[field]);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = field;
      label.append(input, analysisElement('span', '', labelText));
      flags.append(label);
    });
    card.append(flags);
    const memo = document.createElement('textarea');
    memo.rows = compact ? 2 : 3;
    memo.maxLength = 5000;
    memo.value = annotation.memo || '';
    memo.placeholder = 'この発話の意味、文脈、例外、解釈メモ';
    memo.dataset.analysisSegmentId = segment.id;
    memo.dataset.analysisAnnotationField = 'memo';
    card.append(analysisField('発話メモ', memo));
    list.append(card);
  });
  if (visible.length > limit) {
    list.append(analysisElement('p', 'analysis-limit-note', `表示負荷を抑えるため先頭${limit}件を表示しています。検索で対象を絞り込んでください。`));
  }
}

function analysisCodingWorkspace(compact) {
  const container = analysisElement('div', 'analysis-coding-workspace');
  const toolbar = analysisElement('div', 'analysis-coding-toolbar');
  const search = document.createElement('input');
  search.type = 'search';
  search.value = analysisState.segmentQuery;
  search.placeholder = '発話本文・話者を検索';
  search.dataset.analysisSegmentQuery = 'true';
  const annotatedLabel = analysisElement('label', 'mini-check');
  const annotated = document.createElement('input');
  annotated.type = 'checkbox';
  annotated.checked = analysisState.annotatedOnly;
  annotated.dataset.analysisAnnotatedOnly = 'true';
  annotatedLabel.append(annotated, analysisElement('span', '', '設定済みだけ'));
  toolbar.append(analysisField('発話を検索', search), annotatedLabel);
  const list = analysisElement('div', 'analysis-segment-list');
  list.dataset.analysisSegmentList = compact ? 'mobile' : 'desktop';
  renderAnalysisSegmentItems(list, compact);
  container.append(toolbar, list);
  return container;
}

function renderTranscriptPreparation() {
  const prepared = analysisState.data.manual?.preparation;
  const panel = analysisCardPanel('文字起こしを分析用データに整える', 'manual', 'prepared_turns', true);
  if (!prepared) return panel.panel;
  const key = `${analysisState.itemId}:${prepared.revision}:${prepared.source_hash}`;
  if (preparationDraft && preparationDirty && preparationDraft.source_hash === prepared.source_hash
      && preparationDraft.key.startsWith(`${analysisState.itemId}:`)) {
    preparationDraft.key = key;
    preparationDraft.revision = prepared.revision;
  }
  if (!preparationDraft || preparationDraft.key !== key) {
    preparationDraft = {key, revision: prepared.revision, source_hash: prepared.source_hash,
      order_verified: prepared.order_verified, participant_count: prepared.participant_count,
      metadata_sources: prepared.metadata_sources || '', review_analysis: false, records: {}};
    prepared.rows.forEach(row => {
      preparationDraft.records[row.segment_id] = Object.fromEntries(
        ['text_status', 'role', 'speaker_verified', 'boundary_verified', 'source_locator', 'source_segment_ids']
          .map(field => [field, deepCopy(row[field])])
      );
    });
  }
  const statusLabels = {draft: '確認途中', confirmed: '本文・区切り確認済みの版', needs_review: '入力変更後・要再確認'};
  panel.body.append(analysisElement('p', '',
    `入力版 ${prepared.input_version ?? '未固定'} / ${statusLabels[prepared.status]}。内容分析の準備: ${prepared.content_ready_count}/${prepared.rows.length}発言、相互作用の準備: ${prepared.interaction_ready_count}/${prepared.rows.length}発言。`));
  panel.body.append(analysisElement('p', 'analysis-section-help',
    '取込原本は上書きしません。本文・話者・区切りは既存の文字起こし編集画面で修正してください。以下は修正した版の確認記録です。音声未照合や話者不明を確認済みとみなさず、資料がない人数は空欄にします。'));
  if (prepared.analysis_needs_review) panel.body.append(analysisElement('p', 'analysis-orphan-warning',
    '既存のコード・相互作用は要再確認です。入力版または確認状態が変わりました。保存するだけでは解除されません。'));
  const exportLink = analysisElement('a', 'analysis-export-link', '原本・全入力版・確認履歴 JSON');
  exportLink.href = `/api/library/${encodeURIComponent(analysisState.itemId)}/preparation/export.json`;
  exportLink.download = '';
  panel.body.append(exportLink);
  const edit = analysisElement('button', 'secondary-button', '文字起こし編集を開く');
  edit.type = 'button';
  edit.addEventListener('click', () => {
    if (preparationDirty || analysisState.dirty) {
      setAlert(document.querySelector('#analysis-message'), '先に準備記録と分析設定を保存してください。', true);
      return;
    }
    openLibraryItem(analysisState.itemId);
  });
  panel.body.append(edit);
  const control = (label, field, options, sid = null) => {
    const object = sid ? preparationDraft.records[sid] : preparationDraft;
    const input = document.createElement(options && typeof options === 'object' ? 'select' : options === 'textarea' ? 'textarea' : 'input');
    if (input.tagName === 'SELECT') Object.entries(options).forEach(([value, text]) => input.append(new Option(text, value)));
    else if (input.tagName === 'INPUT') input.type = options || 'text';
    const value = object[field];
    if (input.type === 'checkbox') input.checked = Boolean(value);
    else input.value = Array.isArray(value) ? value.join(', ') : value ?? '';
    input.dataset.preparationKey = `${sid || 'session'}:${field}`;
    input.addEventListener('input', () => {
      object[field] = input.type === 'checkbox' ? input.checked
        : field === 'participant_count' ? (input.value === '' ? null : Number(input.value))
        : field === 'source_segment_ids' ? input.value.split(',').map(v => v.trim()).filter(Boolean) : input.value;
      preparationDirty = true;
      analysisMutationGeneration += 1;
      document.querySelectorAll('[data-preparation-key]').forEach(peer => {
        if (peer === input || peer.dataset.preparationKey !== input.dataset.preparationKey) return;
        if (input.type === 'checkbox') peer.checked = input.checked;
        else peer.value = input.value;
      });
    });
    return analysisField(label, input);
  };
  panel.body.append(
    control('資料・確認根拠（研究目的・質問票・参加者名簿等の資料名と位置。実名は不要）', 'metadata_sources', 'textarea'),
    control('実際の参加人数（不明は空欄。発言者数とは別）', 'participant_count', 'number'),
    control('保存されている発言の順序を原資料と確認した', 'order_verified', 'checkbox')
  );
  const turns = analysisElement('details');
  turns.append(analysisElement('summary', '', `発言ごとの確認（${prepared.rows.length}件）`));
  prepared.rows.forEach(row => {
    const detail = analysisElement('details', 'analysis-segment-card');
    detail.append(analysisElement('summary', '', `#${row.order} ${row.speaker_id || '話者不明'} / ${row.segment_id}`));
    const text = analysisElement('p', 'analysis-segment-text', row.text);
    text.style.whiteSpace = 'pre-wrap';
    detail.append(text, analysisElement('p', 'analysis-section-help',
      `取込本文: ${row.original_text ?? '対応する取込本文なし'} / 時刻: ${row.start ?? '不明'}–${row.end ?? '不明'}`));
    const fields = analysisElement('div', 'analysis-settings-grid');
    fields.append(
      control('本文確認', 'text_status', {unreviewed: '未確認', transcript_checked: '逐語録を確認（音声未照合）', audio_verified: '音声・動画と照合済み', unclear: '聞き取り不明・要確認'}, row.segment_id),
      control('役割（初期値は不明）', 'role', {unknown: '不明', participant: '参加者', moderator: '司会者', observer: '観察者'}, row.segment_id),
      control('発言者を確認した', 'speaker_verified', 'checkbox', row.segment_id),
      control('一人の発言として区切りを確認した', 'boundary_verified', 'checkbox', row.segment_id),
      control('元資料の位置（行・ページ等）', 'source_locator', 'text', row.segment_id),
      control('分割・結合元の発言ID（カンマ区切り。不明は空欄）', 'source_segment_ids', 'text', row.segment_id)
    );
    detail.append(fields);
    turns.append(detail);
  });
  panel.body.append(turns);
  if (prepared.analysis_needs_review) panel.body.append(control(
    '現在の版で既存のコード・相互作用を研究者が再確認した（明示的に解除）', 'review_analysis', 'checkbox'));
  const message = analysisElement('p', 'analysis-section-help');
  message.setAttribute('role', 'status');
  for (const [label, confirm] of [['確認途中として保存', false], ['本文・区切りを確認して版を確定', true]]) {
    const button = analysisElement('button', 'secondary-button', label);
    button.type = 'button';
    button.dataset.preparationSave = String(confirm);
    button.addEventListener('click', async () => {
      if (preparationSaving) return;
      if (analysisState.dirty) {
        message.textContent = '先に未保存の分析設定・コードを保存してください。';
        return;
      }
      const itemId = analysisState.itemId;
      const payload = {...deepCopy(preparationDraft), confirm};
      const sent = JSON.stringify(preparationDraft);
      preparationSaving = true;
      message.textContent = '保存中…';
      try {
        const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/preparation`, {
          method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
        });
        const result = await readJsonResponse(response);
        if (!response.ok) throw new Error(result.error || '準備記録を保存できませんでした。');
        if (analysisState.itemId !== itemId) return;
        if (JSON.stringify(preparationDraft) !== sent) {
          preparationDraft.revision = result.revision;
          message.textContent = '保存しました。保存中の追加編集があるため、もう一度保存してください。';
          return;
        }
        preparationDirty = false;
        await loadAnalysisItem(itemId, {discardDirty: true});
        setAlert(document.querySelector('#analysis-message'), '準備記録を保存しました。話者・順序の不足は別途表示されます。');
      } catch (error) {
        message.textContent = error.message;
      } finally {
        preparationSaving = false;
      }
    });
    panel.body.append(button);
  }
  panel.body.append(message);
  return panel.panel;
}

function qualitativeCount(value) {
  const count = Number(value);
  return Number.isFinite(count) ? Math.max(0, Math.floor(count)) : 0;
}

function qualitativeEvidenceDetails(segments, {continuous = false} = {}) {
  const details = analysisElement('details', 'qualitative-evidence');
  details.append(analysisElement('summary', '', continuous
    ? `根拠の連続発言を開く（${segments.length}発言・両端とその間）`
    : `該当発言を開く（${segments.length}発言・連続ではない抜粋）`));
  const list = analysisElement('div', 'qualitative-evidence-list');
  const reviews = new Map((analysisState.data.manual?.preparation?.rows || []).map(row => [row.segment_id, row]));
  const codes = new Map((analysisState.data.manual?.codebook || []).map(code => [code.id, code]));
  let offset = 0;
  const more = contentButton('次の40発言を表示', appendNext);
  function appendNext() {
    const batch = segments.slice(offset, offset + 40);
    offset += batch.length;
    batch.forEach(segment => {
      const review = reviews.get(segment.id);
      const textStatus = {unreviewed: '未確認', transcript_checked: '逐語録確認済み・音声未照合',
        audio_verified: '音声照合済み', unclear: '聞き取り不明'}[review?.text_status] || '不明';
      const role = {participant: '参加者', moderator: '司会者', observer: '観察者'}[review?.role] || '役割不明';
      const article = analysisElement('blockquote', 'qualitative-quote');
      article.dataset.qualitativeEvidenceId = segment.id;
      article.append(analysisElement('p', 'qualitative-exact-text', segment.text || '（本文なし）'));
      article.append(analysisElement('p', 'analysis-caption',
        `#${segment.utterance_order ?? '不明'} / ${segment.speaker_name || segment.speaker || '話者不明'} / ${role} / ${segment.id}`));
      article.append(analysisElement('p', 'analysis-caption',
        `本文確認: ${textStatus} / 話者・役割・順序: ${review?.interaction_ready ? '準備記録で確認済み' : '未確認項目あり'}${segment.excluded ? ' / 集計から除外（文脈として表示）' : ''}`));
      const labels = (segment.annotation?.codes || []).map(id => codes.get(id)).filter(Boolean)
        .map(code => [code.label, code.category && `カテゴリー: ${code.category}`, code.theme && `テーマ: ${code.theme}`].filter(Boolean).join(' / '));
      if (labels.length) article.append(analysisElement('p', 'analysis-caption', `内容のコード: ${labels.join('；')}`));
      if (segment.valid_time) article.append(contentButton('元の発言・音声を確認', () => openInsightMedia(segment)));
      else article.append(analysisElement('p', 'analysis-caption', '時刻不明のため音声位置への移動はできません。'));
      list.insertBefore(article, more);
    });
    more.hidden = offset >= segments.length;
  }
  list.append(more);
  details.append(list);
  details.addEventListener('toggle', () => { if (details.open && !offset) appendNext(); });
  return details;
}

function renderInteractionTimeline() {
  const panel = analysisCardPanel('相互作用と意見変化の発言順タイムライン', 'manual', 'interaction_links', true, 'qualitative_coding');
  panel.panel.dataset.interactionTimeline = '';
  const data = analysisState.data;
  const manual = data.manual || {};
  const segments = data.segments || [];
  const lookup = new Map(segments.map((segment, index) => [segment.id, {segment, index}]));
  const links = (manual.interaction_links || []).slice().sort((a, b) =>
    (lookup.get(a.source_segment_id)?.index ?? Infinity) - (lookup.get(b.source_segment_id)?.index ?? Infinity));
  const stale = Boolean(manual.preparation?.analysis_needs_review);
  panel.body.append(analysisElement('p', 'analysis-section-help',
    '保存済みの手動リンクを、応答した発言の順で表示します。矢印は「参照先 → 応答発言」で、因果関係や同調圧力を示しません。間隔は経過時間を表しません。'));
  panel.body.append(analysisElement('p', 'analysis-caption',
    `入力版: ${manual.preparation?.input_version ?? '未固定'} / ${links.length}リンク。リンク件数は支持人数ではありません。意見変更などの判定は研究者の解釈です。`));
  if (stale) panel.body.append(analysisElement('p', 'analysis-orphan-warning',
    '要再確認：根拠の版が変わっています。旧リンクのIDのみ表示し、現在の本文を旧解釈の根拠として結びません。'));
  if (!links.length) {
    panel.body.append(analysisElement('p', 'analysis-no-data', '相互作用リンクは未登録です。「発話ごとのコード・相互作用・メモ」で対象発言と関係を指定して保存すると表示されます。'));
    return panel.panel;
  }
  const filter = document.createElement('select');
  filter.dataset.interactionFilter = '';
  filter.append(new Option('すべての関係', ''));
  const relations = new Map(links.map(link => [link.relation, link.relation_label || link.relation]));
  relations.forEach((label, id) => filter.append(new Option(label, id)));
  panel.body.append(analysisField('関係の種類で絞り込み', filter));
  const count = analysisElement('p', 'analysis-caption');
  count.setAttribute('aria-live', 'polite');
  const list = analysisElement('ol', 'qualitative-timeline');
  let offset = 0;
  let filtered = links;
  const more = contentButton('次の30リンクを表示', appendNext);
  more.dataset.interactionMore = '';
  function appendNext() {
    const batch = filtered.slice(offset, offset + 30);
    offset += batch.length;
    batch.forEach(link => {
      const from = lookup.get(link.target_segment_id);
      const to = lookup.get(link.source_segment_id);
      const unavailable = stale || link.analysis_needs_review || link.status === 'missing_target' || !from || !to;
      const event = analysisElement('li', `qualitative-event${unavailable ? ' needs-review' : ''}`);
      event.dataset.interactionSource = link.source_segment_id;
      event.dataset.interactionRelation = link.relation;
      event.append(analysisElement('strong', 'qualitative-relation', link.relation_label || link.relation));
      if (unavailable) {
        event.append(analysisElement('p', '', `${link.target_segment_id} → ${link.source_segment_id}`));
        event.append(analysisElement('p', 'analysis-caption', !from || !to || link.status === 'missing_target'
          ? '参照先の発言がありません。履歴・JSONを確認してください。'
          : '根拠が要再確認です。準備画面で現在の版との対応を確認してください。'));
      } else {
        const pair = analysisElement('div', 'qualitative-response-pair');
        [from.segment, to.segment].forEach((segment, index) => {
          if (index) pair.append(analysisElement('span', 'qualitative-direction', '応答'));
          const endpoint = analysisElement('div', 'qualitative-endpoint');
          endpoint.append(analysisElement('strong', '', `#${segment.utterance_order ?? '不明'} ${segment.speaker_name || segment.speaker || '話者不明'}`));
          const excerpt = segment.text || '';
          endpoint.append(analysisElement('p', 'qualitative-exact-text', excerpt.length > 160 ? `${excerpt.slice(0, 160)}…（全文は下の根拠）` : excerpt));
          pair.append(endpoint);
        });
        event.append(pair);
        const first = Math.min(from.index, to.index), last = Math.max(from.index, to.index);
        event.append(qualitativeEvidenceDetails(segments.slice(first, last + 1), {continuous: true}));
      }
      if (link.evidence_memo) event.append(analysisElement('p', 'qualitative-interpretation', `研究者の解釈メモ: ${link.evidence_memo}`));
      list.append(event);
    });
    count.textContent = `${filtered.length}リンク中 ${offset}リンクを表示（全体 ${links.length}リンク）`;
    more.hidden = offset >= filtered.length;
  }
  filter.addEventListener('change', () => {
    filtered = links.filter(link => !filter.value || link.relation === filter.value);
    offset = 0;
    list.replaceChildren();
    appendNext();
  });
  panel.body.append(count, list, more);
  appendNext();
  return panel.panel;
}

function renderManualSummary(container, compact) {
  const manual = analysisState.data.manual || {};
  container.append(analysisElement('p', 'analysis-caption qualitative-snapshot-notice',
    manual.preparation?.analysis_needs_review
      ? '要再確認：以下のコード集計・比較表には以前の解釈が含まれます。現在の入力に対する確定結果ではありません。'
      : '図表は保存済みの分析記録です。未保存のコード・リンクの編集は、保存後に反映されます。'));
  const checks = Array.isArray(manual.context_checks) ? manual.context_checks : [];
  const readiness = analysisCardPanel('分析前の確認', 'configured', 'context');
  const checkGrid = analysisElement('div', 'analysis-check-grid');
  checks.forEach(item => {
    const row = analysisElement('div', item.ready ? 'ready' : 'missing');
    row.append(
      analysisElement('span', '', item.ready ? '✓' : '!'),
      analysisElement('strong', '', item.label),
      analysisElement('small', '', item.ready ? '設定済み' : '要設定')
    );
    checkGrid.append(row);
  });
  readiness.body.append(checkGrid);
  container.append(readiness.panel);

  const plan = manual.focus_group_plan || {};
  if (plan && Object.keys(plan).length) {
    const planPanel = analysisCardPanel('対象データの確認と分析方針', 'configured', 'analysis_plan', true);
    planPanel.body.append(
      analysisElement('p', 'analysis-section-help', `${plan.status || '不明'}：${plan.provisional_assumption || ''}`)
    );
    const inventory = Array.isArray(plan.data_inventory) ? plan.data_inventory : [];
    const missing = inventory.filter(item => item.status === '不明' || item.status === '一部');
    if (missing.length) {
      const list = analysisElement('ul', 'analysis-inline-list');
      missing.forEach(item => list.append(analysisElement('li', '', `${item.item}: ${item.value}`)));
      planPanel.body.append(analysisElement('strong', '', '要確認'), list);
    }
    const methods = Array.isArray(plan.methods) ? plan.methods : [];
    methods.forEach(item => planPanel.body.append(analysisElement(
      'p', 'analysis-list-row', `${item.role}：${item.method}（データ充足: ${item.data_sufficiency}）`
    )));
    const expertBlock = analysisState.data.experts || {};
    if (expertBlock.status === 'unavailable') {
      planPanel.body.append(analysisElement('p', 'analysis-section-help', expertBlock.message || '専門家定義を読み込めません。'));
    }
    (Array.isArray(expertBlock.experts) ? expertBlock.experts : []).forEach(expert => {
      planPanel.body.append(buildExpertDetails(expert));
    });
    if (expertBlock.ai && expertBlock.ai.mode === 'blocked') {
      planPanel.body.append(analysisElement('p', 'analysis-section-help', `AI見解：${expertBlock.ai.reason}`));
    }
    container.append(planPanel.panel);
  }

  const codeMetrics = Array.isArray(manual.code_metrics) ? manual.code_metrics : [];
  const interactionSummary = Array.isArray(manual.interaction_summary) ? manual.interaction_summary : [];
  if (codeMetrics.length || interactionSummary.some(item => item.count)) {
    const summary = analysisCardPanel('手動コードの集計', 'manual', 'codes', true, 'qualitative_coding');
    if (codeMetrics.length) {
      const maximum = codeMetrics.reduce((max, item) => Math.max(max, qualitativeCount(item.segment_count)), 0);
      summary.body.append(analysisElement('p', 'analysis-caption',
        `棒の共通尺度: 0～${maximum}発言（最長の棒＝最大件数）。割合・重要性・支持人数を表しません。同一発言への同一コードは1件、複数コードはそれぞれに計上します。`));
      codeMetrics.forEach(item => {
        const value = qualitativeCount(item.segment_count);
        const row = appendAnalysisBar(summary.body, item.label, maximum ? 100 * value / maximum : 0,
          `${value}発言 / ${qualitativeCount(item.speaker_count)}話者ラベル / ${item.group_count ?? '不明'}グループ / 重要引用 ${qualitativeCount(item.important_count)}件 / ${analysisObservedTimeText(item)}`, item.color);
        row.dataset.qualitativeCode = item.id;
        row.querySelector('.analysis-bar-track').setAttribute('aria-label', `${item.label}: ${value}発言。共通尺度0～${maximum}発言`);
        row.querySelector('.analysis-bar-track i').style.minWidth = '0';
      });
    }
    const tags = analysisElement('div', 'analysis-interaction-summary');
    interactionSummary.filter(item => item.count).forEach(item => {
      const chip = analysisElement('span', '', `${item.label} ${item.count}件`);
      tags.append(chip);
    });
    if (tags.childNodes.length) summary.body.append(tags);
    container.append(summary.panel);
  }

  const matrix = Array.isArray(manual.case_code_matrix) ? manual.case_code_matrix : [];
  const codebook = Array.isArray(manual.codebook) ? manual.codebook : [];
  if (matrix.length && codebook.length) {
    const matrixPanel = analysisCardPanel('話者×コード（発言件数）', 'manual', 'case_matrix', true, 'qualitative_coding');
    const wrap = analysisElement('div', 'analysis-table-wrap');
    wrap.tabIndex = 0;
    wrap.setAttribute('role', 'region');
    wrap.setAttribute('aria-label', '話者×コード比較表。列が多い場合は横にスクロールできます。');
    const table = analysisElement('table', 'analysis-table analysis-matrix');
    const maximum = matrix.reduce((max, row) => (row.codes || []).reduce(
      (value, code) => Math.max(value, qualitativeCount(code.count)), max), 0);
    matrixPanel.body.append(analysisElement('p', 'analysis-caption', `色の共通尺度: 0～${maximum}発言。件数を押すと該当する発言を開けます。話者ラベルと実際の人数は別です。`));
    const evidence = analysisElement('div', 'qualitative-matrix-evidence');
    evidence.setAttribute('aria-live', 'polite');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    headRow.append(analysisElement('th', '', '話者'));
    codebook.forEach(code => {
      const cell = analysisElement('th', '', code.label);
      cell.scope = 'col';
      headRow.append(cell);
    });
    head.append(headRow);
    const body = analysisElement('tbody');
    matrix.forEach(rowData => {
      const row = analysisElement('tr');
      row.append(analysisElement('th', '', rowData.speaker_name || rowData.speaker));
      const counts = new Map((rowData.codes || []).map(item => [item.code_id, item.count]));
      codebook.forEach(code => {
        const value = qualitativeCount(counts.get(code.id));
        const cell = analysisElement('td', value ? 'has-value' : '');
        cell.style.setProperty('--matrix-strength', String(maximum ? value / maximum : 0));
        if (value) {
          const button = contentButton(String(value), () => {
            evidence.replaceChildren(analysisElement('strong', '', `${rowData.speaker_name || rowData.speaker} × ${code.label}`));
            if (manual.preparation?.analysis_needs_review) {
              evidence.append(analysisElement('p', '', '要再確認：現在の本文を旧コードの根拠として表示できません。'));
              return;
            }
            const matching = (analysisState.data.segments || []).filter(segment => !segment.excluded
              && segment.speaker === rowData.speaker && (segment.annotation?.codes || []).includes(code.id));
            const details = qualitativeEvidenceDetails(matching);
            evidence.append(details);
            details.open = true;
            details.querySelector('summary').focus();
          }, 'qualitative-matrix-button');
          button.setAttribute('aria-label', `${rowData.speaker_name || rowData.speaker}、${code.label}、${value}発言の根拠を開く`);
          cell.append(button);
        } else cell.textContent = '0';
        row.append(cell);
      });
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    matrixPanel.body.append(wrap, evidence);
    container.append(matrixPanel.panel);
  }
  container.append(renderInteractionTimeline());
}

function renderManualAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const manual = (analysisState.data && analysisState.data.manual) || {};
  const intro = analysisElement('div', 'analysis-result-intro manual');
  intro.append(
    analysisElement('span', 'analysis-kind manual', '要設定・要確認'),
    analysisElement('h2', '', compact ? '設定・手動分析' : '研究目的に沿った設定と手動コーディング'),
    analysisElement('p', '', 'テーマ、合意・対立、沈黙の意味は自動確定できません。定義を作り、発話を読み、根拠と解釈を保存してください。')
  );
  fragment.append(intro);
  fragment.append(renderTranscriptPreparation());
  const orphanedCount = Number(manual.orphaned_annotation_count) || 0;
  if (orphanedCount > 0) {
    const warning = analysisElement('div', 'analysis-orphan-warning');
    warning.setAttribute('role', 'status');
    warning.append(
      analysisElement('strong', '', '参照先のない注釈があります'),
      analysisElement('p', '', `文字起こし編集で参照先がなくなった注釈が${orphanedCount}件あります。JSONには復旧用に保持されています。`)
    );
    fragment.append(warning);
  }

  const summaryGrid = analysisElement('div', 'analysis-grid manual-summary-grid');
  renderManualSummary(summaryGrid, compact);
  const importantQuotes = (analysisState.data.segments || []).filter(segment => {
    const annotation = analysisState.annotations[segment.id] || {};
    return annotation.important && !annotation.excluded;
  });
  if (importantQuotes.length) {
    const quotesPanel = analysisCardPanel('重要引用', 'manual', 'important_quotes', true, 'qualitative_coding');
    importantQuotes.slice(0, compact ? 5 : 12).forEach(segment => {
      const quote = analysisElement('blockquote', 'analysis-important-quote');
      quote.append(
        analysisElement('p', '', segment.text || '（本文なし）'),
        analysisElement('footer', '', `${segment.speaker_name || segment.speaker} / ${formatTime(segment.start || 0)}–${formatTime(segment.end || 0)}`)
      );
      quotesPanel.body.append(quote);
    });
    summaryGrid.append(quotesPanel.panel);
  }
  summaryGrid.append(analysisExportDirectory('手動分析データの出力', 'manual', [
    ['report', '分析レポート（Markdown）'],
    ['analysis_plan', '分析方針・データ確認 CSV'],
    ['analysis_units', '発言と分析結果の対応表 CSV'],
    ['context', '入力・確認状況 CSV'],
    ['codes', 'コード集計 CSV'],
    ['codebook_history', 'コードブック変更履歴 CSV'],
    ['coded_segments', 'コード済み発話 CSV'],
    ['interactions', '相互作用タグ CSV'],
    ['interaction_links', '相互作用の根拠発話 CSV'],
    ['case_matrix', '話者×コード CSV'],
    ['important_quotes', '重要引用 CSV']
  ]));
  fragment.append(summaryGrid);

  const settingsPanel = analysisCardPanel('分析条件', 'configured', '', true);
  const settingsGrid = analysisElement('div', 'analysis-settings-grid');
  settingsGrid.append(
    analysisField('研究質問', analysisConfigControl('research_question', 'textarea'), '分析で明らかにしたい問いを記録します。'),
    analysisField('主となる分析手法', analysisConfigControl('analysis_method', 'select', {
      auto: '資料に応じて暫定選定', qualitative_content: '質的内容分析', thematic: 'テーマ分析',
      framework: 'フレームワーク分析', scat: 'SCAT', mgta: 'M-GTA', kj: 'KJ法',
      quantitative_text: '計量テキスト分析（補助）', interaction: '相互作用分析'
    }), '分析方針・データ確認CSVで、必要な手順と不足資料を確認できます。'),
    analysisField('手法選定の理由', analysisConfigControl('method_rationale', 'textarea'), '研究目的・データとの対応、得たい結果、限界を研究者が記録します。'),
    analysisField('分析単位', analysisConfigControl('analysis_unit', 'select', {
      turn: '発話単位'
    })),
    analysisField(
      '比較軸',
      analysisConfigControl('group_by', 'select', analysisGroupByOptions()),
      '話者管理とリンク済みの事前アンケート項目も回答群ごとの比較に使えます。'
    ),
    analysisField('長い無音の基準（秒）', analysisConfigControl('long_gap_seconds', 'number')),
    analysisField('重なり候補の基準（秒）', analysisConfigControl('overlap_seconds', 'number')),
    analysisField('低参加候補の基準（%）', analysisConfigControl('low_participation_percent', 'number')),
    analysisField('時間帯の幅（秒）', analysisConfigControl('time_bin_seconds', 'number')),
    analysisField('特徴語から除外する語', analysisConfigControl('stop_words', 'text'), 'カンマ区切りで入力します。'),
    analysisField('Sudachi分割単位', analysisConfigControl('morph_split_mode', 'select', {
      A: 'A（短単位）', B: 'B（中間）', C: 'C（長単位・既定）'
    }), 'GiNZA利用時はモデル側の設定を記録します。'),
    analysisField('共起の最小発話数', analysisConfigControl('cooccurrence_min_count', 'number')),
    analysisField('共起へ使う上位語数', analysisConfigControl('cooccurrence_top_terms', 'number')),
    analysisField('統計の比較軸', analysisConfigControl('statistics_group_by', 'select', {
      speaker: '話者', role: '会話役割'
    }), '同一会話内の発話は独立でない可能性があります。')
  );
  const excludeModerator = analysisElement('label', 'check-row analysis-setting-check');
  excludeModerator.append(
    analysisConfigControl('exclude_moderator', 'checkbox'),
    analysisElement('span', '', '参加バランスから司会・観察役を除外する')
  );
  settingsGrid.append(excludeModerator);
  settingsPanel.body.append(settingsGrid, analysisTermCrosstabSelector(compact));

  const speakerExclusions = analysisElement('fieldset', 'analysis-speaker-exclusions');
  speakerExclusions.append(analysisElement('legend', '', '分析から除外する話者'));
  const uniqueSpeakers = new Map();
  (analysisState.data.segments || []).forEach(segment => {
    if (!uniqueSpeakers.has(segment.speaker)) uniqueSpeakers.set(segment.speaker, segment.speaker_name || segment.speaker);
  });
  uniqueSpeakers.forEach((name, speaker) => {
    const label = analysisElement('label');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = (analysisState.config.excluded_speakers || []).includes(speaker);
    input.dataset.analysisExcludedSpeaker = speaker;
    label.append(input, analysisElement('span', '', name));
    speakerExclusions.append(label);
  });
  settingsPanel.body.append(speakerExclusions);
  fragment.append(settingsPanel.panel);

  const codebookPanel = analysisCardPanel('コードブック', 'configured', '', true, 'qualitative_coding');
  codebookPanel.body.append(
    analysisElement('p', 'analysis-section-help', 'コードの意味と含む／含まない例、カテゴリー、テーマを先に定義すると、複数人でも判断を揃えやすくなります。'),
    analysisField('今回のコードブック変更理由', analysisConfigControl('codebook_change_reason', 'textarea'), '追加・修正・削除の理由を記入します。変更時に履歴へ保存されます。'),
    analysisCodebookEditor(compact)
  );
  fragment.append(codebookPanel.panel);

  const codingPanel = analysisCardPanel('発話ごとのコード・相互作用・メモ', 'manual', 'coded_segments', true, 'qualitative_coding');
  codingPanel.body.append(
    analysisElement('p', 'analysis-section-help', 'タグは観察記録です。合意や発言抑制などの意味は、前後の発話や音声を確認して設定してください。'),
    analysisCodingWorkspace(compact)
  );
  fragment.append(codingPanel.panel);

  const interpretationPanel = analysisCardPanel('研究者の解釈', 'manual', '', true);
  const interpretationGrid = analysisElement('div', 'analysis-interpretation-grid');
  interpretationGrid.append(
    analysisField('分析メモ', analysisConfigControl('analyst_memo', 'textarea'), 'テーマ、例外事例、少数意見、次に確認する点を記録します。'),
    analysisField('確認状態', analysisConfigControl('interpretation_status', 'select', {
      draft: '下書き・要確認', reviewed: '確認済み'
    }))
  );
  interpretationPanel.body.append(interpretationGrid);
  fragment.append(interpretationPanel.panel);

  const saveBar = analysisElement('div', 'analysis-save-bar');
  const saveText = analysisElement('div');
  saveText.append(
    analysisElement('strong', '', analysisState.dirty ? '未保存の変更があります' : '分析設定は保存済みです'),
    analysisElement('span', '', '保存すると自動集計とExcel・CSV・JSONも更新されます。')
  );
  saveText.firstElementChild.dataset.analysisSaveState = 'true';
  const save = analysisElement('button', 'primary-button small', analysisState.dirty ? '設定とコードを保存' : '保存済み');
  save.type = 'button';
  save.dataset.analysisSave = 'true';
  save.disabled = !analysisState.dirty;
  saveBar.append(saveText, save);
  fragment.append(saveBar);
  return fragment;
}

function syncAnalysisControls(source, selector, predicate) {
  document.querySelectorAll(selector).forEach(control => {
    if (control === source || !predicate(control)) return;
    if (source.type === 'checkbox') control.checked = source.checked;
    else control.value = source.value;
  });
}

function updateAnalysisConfigFromControl(control) {
  const field = control.dataset.analysisConfig;
  if (!field) return false;
  let value;
  if (control.type === 'checkbox') value = control.checked;
  else if (control.type === 'number') {
    const number = Number(control.value);
    value = Number.isFinite(number) ? number : analysisState.config[field];
  } else if (field === 'stop_words' || field === 'crosstab_terms') {
    value = control.value.split(/[,、\n]/).map(item => item.trim()).filter(Boolean);
  } else value = control.value;
  analysisState.config[field] = value;
  syncAnalysisControls(control, '[data-analysis-config]', peer => peer.dataset.analysisConfig === field);
  setAnalysisDirty(true);
  return true;
}

function updateAnalysisCodeFromControl(control) {
  const codeId = control.dataset.analysisCodeId;
  const field = control.dataset.analysisCodeField;
  if (!codeId || !field) return false;
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  const code = codebook.find(item => item.id === codeId);
  if (!code) return false;
  code[field] = field === 'color' ? safeAnalysisColor(control.value) : control.value;
  syncAnalysisControls(control, '[data-analysis-code-id]', peer => (
    peer.dataset.analysisCodeId === codeId && peer.dataset.analysisCodeField === field
  ));
  setAnalysisDirty(true);
  return true;
}

function updateAnalysisAnnotationFromControl(control) {
  const segmentId = control.dataset.analysisSegmentId;
  const field = control.dataset.analysisAnnotationField;
  if (!segmentId || !field) return false;
  const annotation = analysisAnnotation(segmentId);
  const itemValue = control.dataset.analysisAnnotationValue;
  if (field === 'codes' || field === 'interaction_tags') {
    const values = Array.isArray(annotation[field]) ? annotation[field] : [];
    annotation[field] = control.checked
      ? [...new Set([...values, itemValue])]
      : values.filter(value => value !== itemValue);
  } else if (field === 'important' || field === 'excluded') annotation[field] = control.checked;
  else if (['importance_score', 'review_score', 'sensitivity_score'].includes(field)) {
    const number = control.value === '' ? null : Number(control.value);
    annotation[field] = Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : null;
  }
  else annotation[field] = control.value;
  syncAnalysisControls(control, '[data-analysis-annotation-field]', peer => (
    peer.dataset.analysisSegmentId === segmentId
    && peer.dataset.analysisAnnotationField === field
    && peer.dataset.analysisAnnotationValue === itemValue
  ));
  setAnalysisDirty(true);
  return true;
}

function refreshAnalysisSegmentLists() {
  document.querySelectorAll('[data-analysis-segment-list]').forEach(list => {
    renderAnalysisSegmentItems(list, list.dataset.analysisSegmentList === 'mobile');
  });
}

async function saveAnalysis() {
  if (!analysisState.itemId || !analysisState.data || analysisSaveInProgress) return;
  const saveContext = captureAnalysisContext();
  analysisSaveOwner = saveContext;
  // Preserve later edits only within this same data/navigation/revision owner.
  const ownsSave = () => analysisSaveOwner === saveContext
    && isAnalysisContextCurrent({...saveContext, mutation: analysisMutationGeneration});
  analysisSaveInProgress = true;
  setAnalysisDirty(true, false);
  setAlert(document.querySelector('#analysis-message'), '');
  const savedItemId = analysisState.itemId;
  const saveGeneration = analysisMutationGeneration;
  try {
    const item = analysisState.data.item || {};
    const response = await apiFetch(`/api/library/${encodeURIComponent(savedItemId)}/analysis`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        source_revision: Number(item.revision_count || 0),
        analysis_revision: Number(item.analysis_revision || 0),
        config: analysisState.config,
        annotations: analysisState.annotations
      })
    });
    const payload = await readJsonResponse(response);
    if (!ownsSave()) return;
    if (!response.ok) throw new Error(payload.error || '分析設定を保存できませんでした。');
    const data = payload.analysis && typeof payload.analysis === 'object' ? payload.analysis : payload;
    analysisSaveInProgress = false;
    const hasLaterChanges = analysisState.itemId === savedItemId
      && analysisMutationGeneration !== saveGeneration;
    if (analysisState.itemId === savedItemId && !hasLaterChanges) {
      analysisState.data = data;
      invalidateAnalysisMethodOverview();
      analysisState.config = deepCopy(data.config || {});
      analysisState.annotations = deepCopy(data.annotations || {});
      if (analysisTermRunRequested) analysisState.mode = 'automatic';
      analysisTermRunRequested = false;
      setAnalysisDirty(false);
      renderAnalysisWorkspace();
      onContentAnalysisLoaded();
      setAlert(document.querySelector('#analysis-message'), '分析設定、手動コード、解釈メモを保存し、集計と出力データを更新しました。');
    } else if (analysisState.itemId === savedItemId) {
      if (analysisState.data && analysisState.data.item && data.item) {
        analysisState.data.item.revision_count = data.item.revision_count;
        analysisState.data.item.analysis_revision = data.item.analysis_revision;
        analysisState.data.item.analysis_updated_at = data.item.analysis_updated_at;
      }
      setAnalysisDirty(true, false);
      setAlert(document.querySelector('#analysis-message'), '保存開始後の追加変更が残っています。内容を確認して、もう一度保存してください。', true);
    }
    if (typeof analysisMeasurementRefreshContext === 'function') analysisMeasurementRefreshContext();
  } catch (error) {
    if (!ownsSave()) return;
    analysisSaveInProgress = false;
    analysisTermRunRequested = false;
    setAnalysisDirty(true, false);
    setAlert(document.querySelector('#analysis-message'), error.message, true);
  } finally {
    // An old completion must not release a newer view's save operation.
    if (analysisSaveOwner === saveContext) {
      analysisSaveOwner = null;
      analysisSaveInProgress = false;
      analysisTermRunRequested = false;
      setAnalysisDirty(analysisState.dirty, false);
    }
  }
}
