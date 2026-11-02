/* Cross-session comparison deliberately lives beside, rather than inside, a
 * single transcript's analysis state.  It is read-only: opening or comparing
 * sessions never changes their annotations or analysis settings. */
(() => {
  const card = document.querySelector('#interview-comparison-card');
  if (!card) return;

  const baseSelect = document.querySelector('#interview-comparison-base');
  const dataGroupSelect = document.querySelector('#interview-comparison-data-group');
  let dataGroups = [];
  const allowDifferent = document.querySelector('#interview-comparison-allow-different');
  const targets = document.querySelector('#interview-comparison-targets');
  const targetStatus = document.querySelector('#interview-comparison-target-status');
  const runButton = document.querySelector('#interview-comparison-run');
  const selectionStatus = document.querySelector('#interview-comparison-selection');
  const message = document.querySelector('#interview-comparison-message');
  const result = document.querySelector('#interview-comparison-result');
  const refreshButton = document.querySelector('#interview-comparison-refresh');
  const historyStatus = document.querySelector('#interview-comparison-history-status');
  const historyList = document.querySelector('#interview-comparison-history-list');
  const historyRefresh = document.querySelector('#interview-comparison-history-refresh');
  let catalog = [];
  let savedRuns = [];
  let baseId = '';
  let selectedIds = new Set();
  let running = false;
  let catalogLoading = false;
  let historyLoading = false;
  let historySequence = 0;
  let retryingRunId = '';
  let historyMessage = '';

  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  };

  const setMessage = (text, error = false) => {
    message.hidden = !text;
    message.textContent = text || '';
    message.classList.toggle('error', Boolean(text && error));
  };

  const itemFor = id => catalog.find(item => item.id === id);
  const sameContent = (base, candidate) => Boolean(
    base && candidate && base.comparison_key && base.comparison_key === candidate.comparison_key
  );
  const timeText = seconds => {
    const value = Math.max(0, Math.round(Number(seconds) || 0));
    const minutes = Math.floor(value / 60);
    return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
  };
  const number = value => new Intl.NumberFormat('ja-JP', {maximumFractionDigits: 1}).format(Number(value) || 0);
  const dateText = value => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value || '') : date.toLocaleString('ja-JP');
  };

  function selectedInOrder() {
    return [baseId, ...catalog.map(item => item.id).filter(id => id !== baseId && selectedIds.has(id))]
      .filter((id, index, values) => id && values.indexOf(id) === index);
  }

  function updateSelectionUi() {
    const selected = selectedInOrder();
    selectionStatus.textContent = `${selected.length}件選択（2〜8件）`;
    runButton.disabled = running || catalogLoading || selected.length < 2 || selected.length > 8;
    baseSelect.disabled = running || catalogLoading || !catalog.length;
    dataGroupSelect.disabled = running || catalogLoading;
    allowDifferent.disabled = running || catalogLoading;
    refreshButton.disabled = running || catalogLoading;
    targets.querySelectorAll('[data-comparison-target]').forEach(input => {
      input.disabled = running || catalogLoading || Boolean(dataGroupSelect.value) || input.dataset.comparisonTarget === baseId;
    });
  }

  function renderTargets() {
    targets.replaceChildren();
    const base = itemFor(baseId);
    if (!base) {
      targetStatus.textContent = '基準インタビューを選択してください。';
      updateSelectionUi();
      return;
    }
    selectedIds = new Set([...selectedIds].filter(id => id === baseId || itemFor(id)));
    selectedIds.add(baseId);
    const group = dataGroups.find(g => g.group_id === dataGroupSelect.value);
    const candidates = catalog.filter(item => item.id !== base.id && (group ? group.item_ids.includes(item.id) : allowDifferent.checked || sameContent(base, item)));
    const groupLabel = base.comparison_label || '未設定';
    if (group) {
      targetStatus.textContent = `「${group.name}」の${group.item_count}件を対象に固定します（版${group.version}）。異なる内容を含む場合は下のチェックで比較を許可してください。`;
    } else if (allowDifferent.checked) {
      targetStatus.textContent = `全${catalog.length - 1}件から選択できます。異なる内容の回には「異なる内容」と表示されます。`;
    } else if (!base.comparison_key) {
      targetStatus.textContent = '比較グループまたは質問ガイドが未設定のため、同内容の候補を表示できません。会話プロファイルで比較グループを設定してください。';
    } else {
      targetStatus.textContent = `「${groupLabel}」と一致する${candidates.length}件だけを表示しています。`;
    }
    const addTarget = (item, isBase) => {
      const label = element('label', `interview-comparison-target${isBase ? ' base' : ''}`);
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = selectedIds.has(item.id);
      input.disabled = isBase;
      input.dataset.comparisonTarget = item.id;
      const body = element('span', 'interview-comparison-target-body');
      body.append(
        element('strong', '', item.source_name || '名称未設定'),
        element('small', '', `発話 ${item.segment_count || 0}件 / ${item.comparison_label || '比較グループ未設定'}`)
      );
      const badge = element('em', sameContent(base, item) ? 'compatible' : 'different', isBase ? '基準' : sameContent(base, item) ? '同内容' : '異なる内容');
      label.append(input, body, badge);
      targets.append(label);
    };
    addTarget(base, true);
    candidates.forEach(item => addTarget(item, false));
    if (!candidates.length) {
      const empty = element('p', 'interview-comparison-empty', allowDifferent.checked
        ? '比較できる別のインタビューがありません。'
        : '同じ比較グループのインタビューがありません。比較グループを揃えるか、異なる内容も比較するを選択してください。');
      targets.append(empty);
    }
    updateSelectionUi();
  }

  function addMetricTable(parent, interviews) {
    const wrap = element('div', 'interview-comparison-table-wrap');
    const table = element('table', 'interview-comparison-table');
    const head = element('thead');
    const headRow = element('tr');
    ['インタビュー', '対象発話', '実際の参加者', '観測参加発言者', '話者', '発話時間', '抽出語数', '除外発話'].forEach(value => headRow.append(element('th', '', value)));
    head.append(headRow);
    const body = element('tbody');
    interviews.forEach(item => {
      const row = element('tr');
      [
        item.source_name,
        item.included_segment_count,
        item.participant_count == null ? '未登録' : item.participant_count,
        item.observed_participant_count ?? '—',
        item.speaker_count,
        analysisObservedTimeText(item, 'total_speaking_seconds', timeText),
        item.term_count,
        item.excluded_segment_count,
      ].forEach(value => row.append(element('td', '', value)));
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    parent.append(wrap);
  }

  function addTermList(parent, rows, kind) {
    if (!rows.length) {
      parent.append(element('p', 'interview-comparison-empty', '該当するデータがありません。2回以上出現する語のみを表示します。'));
      return;
    }
    const list = element('div', 'interview-comparison-term-list');
    rows.forEach(row => {
      const line = element('div', 'interview-comparison-term');
      if (kind === 'common') {
        line.append(element('strong', '', row.term));
        const values = element('span', '');
        row.interviews.forEach(value => {
          const source = itemFor(value.item_id);
          values.append(element('small', '', `${source ? source.source_name : value.item_id}: ${value.count}回 (${number(value.rate_per_1000_terms)}/千語)`));
        });
        line.append(values);
      } else {
        line.append(
          element('strong', '', row.term),
          element('span', '', `${row.source_name}: ${row.count}回 / ${number(row.rate_per_1000_terms)}／千語`),
          element('small', row.difference_per_1000_terms >= 0 ? 'higher' : 'lower', `他回との差 ${row.difference_per_1000_terms >= 0 ? '+' : ''}${number(row.difference_per_1000_terms)}／千語`)
        );
      }
      list.append(line);
    });
    parent.append(list);
  }

  function addCategoricalTable(parent, rows, label, interviews) {
    if (!rows.length) {
      parent.append(element('p', 'interview-comparison-empty', '記録済みの比較データがありません。'));
      return;
    }
    const wrap = element('div', 'interview-comparison-table-wrap');
    const table = element('table', 'interview-comparison-table compact');
    const head = element('thead');
    const headRow = element('tr');
    headRow.append(element('th', '', label));
    const interviewIds = interviews.map(item => item.item_id);
    interviews.forEach(item => headRow.append(element('th', '', item.source_name || item.item_id)));
    head.append(headRow);
    const body = element('tbody');
    rows.forEach(row => {
      const tableRow = element('tr');
      tableRow.append(element('th', '', row.code || row.emotion || '未設定'));
      interviewIds.forEach(id => {
        const value = (row.interviews || []).find(candidate => candidate.item_id === id) || {};
        tableRow.append(element('td', '', `${value.count || 0}件 (${number(value.rate_per_100_segments)}%)`));
      });
      body.append(tableRow);
    });
    table.append(head, body);
    wrap.append(table);
    parent.append(wrap);
  }

  function panel(title, description) {
    const section = element('section', 'interview-comparison-panel');
    section.append(element('h4', '', title));
    if (description) section.append(element('p', 'interview-comparison-caption', description));
    return section;
  }

  function renderComparisonHistory() {
    historyList.replaceChildren();
    historyRefresh.disabled = historyLoading || Boolean(retryingRunId);
    historyStatus.textContent = historyLoading
      ? '保存履歴を読み込んでいます…'
      : historyMessage || `${savedRuns.length}件の保存履歴（直近100件）`;
    historyStatus.classList.toggle('error', Boolean(historyMessage));
    if (historyLoading && !savedRuns.length) return;
    if (!savedRuns.length) {
      historyList.append(element('p', 'interview-comparison-empty', '保存済みの比較はありません。比較を集計して保存すると、ここから成果物を開けます。'));
      return;
    }
    savedRuns.forEach(run => {
      const details = element('details', 'interview-comparison-history-run');
      details.dataset.comparisonRun = run.id;
      const memberNames = (run.member_ids || []).map(id => itemFor(id)?.source_name || id);
      const state = run.status === 'writing' ? '保存中'
        : run.vault_status === 'completed' ? '保存済み'
        : 'Vault再試行が必要';
      const summary = element('summary', '', `${dateText(run.created_at)} / ${memberNames.join('、') || '比較対象不明'} / ${state}`);
      const body = element('div', 'interview-comparison-history-body');
      if (run.stale) body.append(element('p', 'interview-comparison-history-notice', '元データが更新されています。この結果は保存時点の入力に基づきます。'));
      if (run.error) body.append(element('p', 'interview-comparison-history-notice error', run.error));
      const actions = element('div', 'interview-comparison-history-actions');
      if (run.obsidian_uri) {
        const open = element('a', 'secondary-button compact-button', 'Obsidianで開く');
        open.href = run.obsidian_uri;
        actions.append(open);
      }
      if (run.status !== 'writing' && (run.status !== 'completed' || run.vault_status !== 'completed')) {
        const retry = element('button', 'secondary-button compact-button', retryingRunId === run.id ? '再試行中…' : 'Vaultへの保存を再試行');
        retry.type = 'button';
        retry.disabled = Boolean(retryingRunId);
        retry.dataset.comparisonVaultRetry = run.id;
        actions.append(retry);
      }
      if (actions.childNodes.length) body.append(actions);
      const files = element('div', 'interview-comparison-history-files');
      (run.artifacts || []).forEach(artifact => {
        const link = element('a', 'analysis-export-link', artifact.name);
        link.href = artifact.url;
        link.download = '';
        files.append(link);
      });
      body.append(files);
      details.append(summary, body);
      historyList.append(details);
    });
  }

  async function loadComparisonHistory() {
    const sequence = ++historySequence;
    historyLoading = true;
    historyMessage = '';
    renderComparisonHistory();
    try {
      const response = await apiFetch('/api/library/interview-comparison/runs', {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '保存済みの比較を取得できませんでした。');
      if (sequence !== historySequence) return;
      savedRuns = Array.isArray(data.runs) ? data.runs : [];
    } catch (error) {
      if (sequence === historySequence) historyMessage = error.message;
    } finally {
      if (sequence === historySequence) {
        historyLoading = false;
        renderComparisonHistory();
      }
    }
  }

  async function retryComparisonVault(runId) {
    if (!runId || retryingRunId) return;
    retryingRunId = runId;
    historyMessage = '';
    let retryError = '';
    renderComparisonHistory();
    try {
      const response = await apiFetch(`/api/analysis/runs/${encodeURIComponent(runId)}/vault`, {method: 'POST'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Vaultへの保存を再試行できませんでした。');
      if (data.run?.vault_status !== 'completed') retryError = data.run?.error || 'Vaultの状態を確認してください。';
    } catch (error) {
      retryError = error.message;
    } finally {
      retryingRunId = '';
      await loadComparisonHistory();
      if (retryError) {
        historyMessage = retryError;
        renderComparisonHistory();
      }
    }
  }

  // One request ID per displayed result: repeated clicks reuse the same saved run.
  let lastRequest = null;
  const requestId = () => {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return 'comparison-' + Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
  };

  async function saveComparison(button, status) {
    if (!lastRequest) return;
    button.disabled = true;
    status.textContent = '比較結果を保存しています…';
    try {
      const response = await apiFetch('/api/library/interview-comparison/runs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(lastRequest)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '比較結果を保存できませんでした。');
      status.textContent = data.run.vault_status === 'completed'
        ? '保存しました。下の保存履歴から成果物とObsidianの記録を開けます。'
        : '結果ファイルを保存しました。下の保存履歴からVaultへの書き出しを再試行してください。';
      await loadComparisonHistory();
    } catch (error) {
      status.textContent = error.message;
      button.disabled = false;
    }
  }

  function renderResult(data) {
    result.replaceChildren();
    result.hidden = false;
    const save = element('div', 'interview-comparison-save');
    const saveButton = element('button', 'secondary', '比較結果を保存');
    saveButton.type = 'button';
    const saveStatus = element('small', 'interview-comparison-save-status', '各インタビューの分析とは別の実行として保存します。');
    saveButton.addEventListener('click', () => saveComparison(saveButton, saveStatus));
    save.append(saveButton, saveStatus);
    result.append(save);
    const intro = element('div', `interview-comparison-result-intro ${data.mode || ''}`);
    intro.append(
      element('strong', '', data.same_content ? '同内容のインタビュー比較' : '異なる内容を含む探索的比較'),
      element('p', '', data.same_content
        ? '同じ比較グループとして選択された回を、発話量・語・手動コード・感情ラベルで並べています。'
        : '質問や対象条件が異なる可能性を前提に、差の説明ではなく探索の手がかりとして確認してください。')
    );
    result.append(intro);
    const cautions = element('ul', 'interview-comparison-cautions');
    (data.cautions || []).forEach(value => cautions.append(element('li', '', value)));
    result.append(cautions);
    const overview = panel('セッションの比較', '分析から除外した発話は、対象発話と語数に含めていません。');
    addMetricTable(overview, data.interviews || []);
    result.append(overview);
    const common = panel('共通して現れる語', '全ての選択回で2回以上出現した語です。テーマの確定ではありません。');
    addTermList(common, data.common_terms || [], 'common');
    result.append(common);
    const characteristics = panel('回ごとの特徴語', '各回と、残りの選択回を合算した出現率（千語あたり）の差です。');
    addTermList(characteristics, data.characteristic_terms || [], 'characteristic');
    result.append(characteristics);
    const codes = panel('手動コードの比較', '同じラベルのコードを並べます。コード定義が異なる場合は比較しないでください。');
    addCategoricalTable(codes, data.code_comparison || [], 'コード', data.interviews || []);
    result.append(codes);
    const emotions = panel('感情ラベルの比較', 'モデル名ごとの推定ラベルです。本人の感情を確定するものではありません。');
    addCategoricalTable(emotions, data.emotion_comparison || [], '感情モデル・ラベル', data.interviews || []);
    result.append(emotions);
  }

  async function loadCatalog() {
    if (running || catalogLoading) return;
    catalogLoading = true;
    result.hidden = true;
    lastRequest = null;
    setMessage('');
    updateSelectionUi();
    try {
      const response = await apiFetch('/api/library?sort=updated_desc', {cache: 'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'インタビュー一覧を取得できませんでした。');
      catalog = Array.isArray(data.items) ? data.items : [];
      dataGroups = data.data_groups || [];
      dataGroupSelect.replaceChildren(new Option('会話を個別に選択', ''));
      dataGroups.forEach(group => dataGroupSelect.add(new Option(`${group.name}（${group.item_count}件）`, group.group_id)));
      const preferred = baseId || (document.querySelector('#analysis-item-select') || {}).value;
      baseId = catalog.some(item => item.id === preferred) ? preferred : (catalog[0] || {}).id || '';
      selectedIds = new Set(baseId ? [baseId] : []);
      baseSelect.replaceChildren();
      if (!catalog.length) baseSelect.add(new Option('比較できるデータがありません', ''));
      catalog.forEach(item => baseSelect.add(new Option(item.source_name || item.id, item.id)));
      baseSelect.value = baseId;
      renderTargets();
      renderComparisonHistory();
    } catch (error) {
      catalog = [];
      baseId = '';
      selectedIds.clear();
      targets.replaceChildren();
      setMessage(error.message, true);
      updateSelectionUi();
    } finally {
      catalogLoading = false;
      updateSelectionUi();
    }
  }

  async function runComparison() {
    if (running || catalogLoading) return;
    const itemIds = selectedInOrder();
    if (itemIds.length < 2 || itemIds.length > 8) return;
    const submitted = {item_ids: itemIds, allow_different_content: allowDifferent.checked};
    if (dataGroupSelect.value) submitted.data_group_id = dataGroupSelect.value;
    running = true;
    lastRequest = null;
    setMessage('');
    updateSelectionUi();
    runButton.textContent = '比較を集計中…';
    result.hidden = true;
    try {
      const response = await apiFetch('/api/library/interview-comparison', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(submitted)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'インタビュー比較を生成できませんでした。');
      lastRequest = {...submitted, input_fingerprints: data.input_fingerprints,
        target_snapshot_hash: data.target_snapshot?.hash, request_id: requestId()};
      renderResult(data);
    } catch (error) {
      setMessage(error.message, true);
    } finally {
      running = false;
      runButton.textContent = '選択したインタビューを比較';
      updateSelectionUi();
    }
  }

  baseSelect.addEventListener('change', () => {
    if (running || catalogLoading) return;
    baseId = baseSelect.value;
    dataGroupSelect.value = '';
    selectedIds = new Set(baseId ? [baseId] : []);
    result.hidden = true;
    setMessage('');
    renderTargets();
  });
  dataGroupSelect.addEventListener('change', () => {
    if (running || catalogLoading) return;
    const group = dataGroups.find(g => g.group_id === dataGroupSelect.value);
    selectedIds = new Set(group?.item_ids || (baseId ? [baseId] : []));
    if (group) baseId = group.item_ids[0] || '';
    baseSelect.value = baseId;
    result.hidden = true; lastRequest = null; setMessage(''); renderTargets();
  });
  allowDifferent.addEventListener('change', () => {
    if (running || catalogLoading) return;
    const base = itemFor(baseId);
    if (!allowDifferent.checked && base && !dataGroupSelect.value) {
      selectedIds = new Set([...selectedIds].filter(id => id === baseId || sameContent(base, itemFor(id))));
    }
    result.hidden = true;
    setMessage('');
    renderTargets();
  });
  targets.addEventListener('change', event => {
    if (running || catalogLoading) return;
    const input = event.target.closest('[data-comparison-target]');
    if (!input) return;
    if (input.checked) {
      if (selectedInOrder().length >= 8) {
        input.checked = false;
        setMessage('比較できるインタビューは8件までです。', true);
        return;
      }
      selectedIds.add(input.dataset.comparisonTarget);
    } else selectedIds.delete(input.dataset.comparisonTarget);
    result.hidden = true;
    updateSelectionUi();
  });
  refreshButton.addEventListener('click', loadCatalog);
  historyRefresh.addEventListener('click', loadComparisonHistory);
  historyList.addEventListener('click', event => {
    const button = event.target.closest('[data-comparison-vault-retry]');
    if (button) retryComparisonVault(button.dataset.comparisonVaultRetry);
  });
  runButton.addEventListener('click', runComparison);
  loadCatalog();
  loadComparisonHistory();
})();
