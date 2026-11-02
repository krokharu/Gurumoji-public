/* 公開版の画面処理: speakers。共有状態はapp.jsで管理する。 */
function newLocalSpeakerId() {
  return self.crypto && self.crypto.randomUUID
    ? self.crypto.randomUUID().replaceAll('-', '')
    : `speaker_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function blankSpeakerRecord() {
  return {
    id: newLocalSpeakerId(),
    participant_code: '',
    display_name: '',
    pseudonym: '',
    default_role: 'participant',
    organization: '',
    department: '',
    job_title: '',
    confidentiality_status: 'unknown',
    tags: [],
    attributes: {},
    notes: '',
    active: true
  };
}

function attributesToText(attributes) {
  return Object.entries(attributes || {}).map(([key, value]) => `${key}=${value}`).join('; ');
}

function textToAttributes(value) {
  const attributes = {};
  String(value || '').split(/[;\n]+/).forEach(part => {
    const separator = part.includes('=') ? '=' : ':';
    const index = part.indexOf(separator);
    if (index <= 0) return;
    const key = part.slice(0, index).trim();
    const itemValue = part.slice(index + 1).trim();
    if (key) attributes[key] = itemValue;
  });
  return attributes;
}

function speakerSurveyQuestionKeys(records = speakerRegistry) {
  const keys = new Set();
  records.forEach(record => {
    const attributes = record && typeof record.attributes === 'object' ? record.attributes : {};
    Object.keys(attributes || {}).forEach(key => {
      const clean = String(key || '').trim();
      if (clean) keys.add(clean);
    });
  });
  return [...keys].sort((a, b) => a.localeCompare(b, 'ja', {numeric: true, sensitivity: 'base'}));
}

function speakerSurveyAnswer(record, question) {
  const attributes = record && typeof record.attributes === 'object' ? record.attributes : {};
  return String((attributes || {})[question] ?? '').trim();
}

function speakerSurveyQuestionSummary(records, question) {
  const counts = new Map();
  const answeredRecords = [];
  records.forEach(record => {
    const answer = speakerSurveyAnswer(record, question);
    if (!answer) return;
    answeredRecords.push(record);
    counts.set(answer, (counts.get(answer) || 0) + 1);
  });
  const values = [...counts.entries()]
    .map(([value, count]) => ({value, count}))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value, 'ja', {numeric: true}));
  return {
    question,
    answeredRecords,
    answered: answeredRecords.length,
    missing: Math.max(0, records.length - answeredRecords.length),
    values
  };
}

function speakerSurveyNumericValue(value) {
  const normalized = String(value || '').trim().normalize('NFKC').replaceAll(',', '');
  if (/^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(normalized)) return Number(normalized);
  const scale = normalized.match(/^([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*[:：]/);
  return scale ? Number(scale[1]) : null;
}

function speakerSurveyNumericSummary(records, question) {
  const values = records
    .map(record => speakerSurveyNumericValue(speakerSurveyAnswer(record, question)))
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  const answered = records.filter(record => speakerSurveyAnswer(record, question)).length;
  if (values.length < 2 || values.length < answered * 0.8) return null;
  const middle = Math.floor(values.length / 2);
  const median = values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
  return {
    count: values.length,
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    median,
    minimum: values[0],
    maximum: values[values.length - 1]
  };
}

function speakerSurveyCorrelation(records, questionA, questionB) {
  const pairs = records.map(record => [
    speakerSurveyNumericValue(speakerSurveyAnswer(record, questionA)),
    speakerSurveyNumericValue(speakerSurveyAnswer(record, questionB))
  ]).filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b));
  if (pairs.length < 3) return null;
  const meanA = pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length;
  const meanB = pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length;
  const numerator = pairs.reduce((sum, pair) => sum + (pair[0] - meanA) * (pair[1] - meanB), 0);
  const denominatorA = pairs.reduce((sum, pair) => sum + (pair[0] - meanA) ** 2, 0);
  const denominatorB = pairs.reduce((sum, pair) => sum + (pair[1] - meanB) ** 2, 0);
  const denominator = Math.sqrt(denominatorA * denominatorB);
  if (!denominator) return null;
  return {count: pairs.length, coefficient: numerator / denominator};
}

function scheduleSpeakerSurveyAnalysis() {
  window.clearTimeout(speakerSurveyAnalysisTimer);
  speakerSurveyAnalysisTimer = window.setTimeout(renderSpeakerSurveyAnalysis, 160);
}

function appendSpeakerSurveyBar(container, label, count, total, maximum) {
  const row = analysisElement('div', 'speaker-survey-bar');
  const heading = analysisElement('div');
  heading.append(
    analysisElement('strong', '', label),
    analysisElement('span', '', `${count}人 / ${total ? (100 * count / total).toFixed(1) : '0.0'}%`)
  );
  const track = analysisElement('div', 'speaker-survey-bar-track');
  const fill = analysisElement('i');
  fill.style.width = `${maximum ? (100 * count / maximum).toFixed(2) : 0}%`;
  track.append(fill);
  row.append(heading, track);
  container.append(row);
}

function buildSpeakerSurveyCompleteness(records, questions) {
  const panel = analysisElement('section', 'speaker-survey-panel');
  panel.append(
    analysisElement('h4', '', '質問別の回答率'),
    analysisElement('p', 'speaker-survey-help', '')
  );
  panel.lastChild.textContent = '回答漏れの確認と、分析対象にする質問の選択ができます。';
  const list = analysisElement('div', 'speaker-survey-completeness');
  questions
    .map(question => speakerSurveyQuestionSummary(records, question))
    .sort((a, b) => b.answered - a.answered || a.question.localeCompare(b.question, 'ja'))
    .forEach(summary => {
      const button = analysisElement('button', summary.question === speakerSurveyAnalysisState.primaryQuestion ? 'active' : '');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(summary.question === speakerSurveyAnalysisState.primaryQuestion));
      const text = analysisElement('span');
      text.append(
        analysisElement('strong', '', summary.question),
        analysisElement('small', '', `${summary.answered} / ${records.length}人`)
      );
      const track = analysisElement('i');
      const fill = analysisElement('b');
      fill.style.width = `${records.length ? (100 * summary.answered / records.length).toFixed(2) : 0}%`;
      track.append(fill);
      button.append(text, track);
      button.addEventListener('click', () => {
        speakerSurveyAnalysisState.primaryQuestion = summary.question;
        speakerSurveyAnalysisState.answerFilter = '';
        if (speakerSurveyAnalysisState.secondaryQuestion === summary.question) {
          speakerSurveyAnalysisState.secondaryQuestion = questions.find(item => item !== summary.question) || '';
        }
        renderSpeakerSurveyAnalysis();
      });
      list.append(button);
    });
  panel.append(list);
  return panel;
}

function buildSpeakerSurveyCrosstab(records, primaryQuestion, secondaryQuestion) {
  const panel = analysisElement('section', 'speaker-survey-panel speaker-survey-crosstab');
  panel.append(
    analysisElement('h4', '', '2項目クロス集計'),
    analysisElement('p', 'speaker-survey-help', `${primaryQuestion} × ${secondaryQuestion} の組み合わせ人数と行内割合です。`)
  );
  const primary = speakerSurveyQuestionSummary(records, primaryQuestion);
  const secondary = speakerSurveyQuestionSummary(records, secondaryQuestion);
  const rowValues = primary.values.slice(0, 12).map(item => item.value);
  const columnValues = secondary.values.slice(0, 10).map(item => item.value);
  if (!rowValues.length || !columnValues.length) {
    panel.append(analysisElement('p', 'analysis-no-data', 'クロス集計できる回答がありません。'));
    return panel;
  }
  const wrap = analysisElement('div', 'speaker-survey-table-wrap');
  const table = document.createElement('table');
  table.className = 'speaker-survey-table';
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  headRow.append(analysisElement('th', '', primaryQuestion));
  columnValues.forEach(value => headRow.append(analysisElement('th', '', value)));
  headRow.append(analysisElement('th', '', '合計'));
  head.append(headRow);
  const body = document.createElement('tbody');
  rowValues.forEach(rowValue => {
    const row = document.createElement('tr');
    row.append(analysisElement('th', '', rowValue));
    const rowTotal = records.filter(record => speakerSurveyAnswer(record, primaryQuestion) === rowValue).length;
    columnValues.forEach(columnValue => {
      const count = records.filter(record => (
        speakerSurveyAnswer(record, primaryQuestion) === rowValue
        && speakerSurveyAnswer(record, secondaryQuestion) === columnValue
      )).length;
      const cell = analysisElement('td', count ? 'has-value' : '', count
        ? `${count}（${rowTotal ? (100 * count / rowTotal).toFixed(0) : 0}%）`
        : '—');
      if (count) cell.style.setProperty('--survey-cell-strength', String(count / Math.max(1, rowTotal)));
      row.append(cell);
    });
    row.append(analysisElement('td', 'total', String(rowTotal)));
    body.append(row);
  });
  table.append(head, body);
  wrap.append(table);
  panel.append(wrap);
  if (primary.values.length > rowValues.length || secondary.values.length > columnValues.length) {
    panel.append(analysisElement('p', 'speaker-survey-note', '表示量を抑えるため、回答数が多い選択肢を優先して表示しています。'));
  }
  const correlation = speakerSurveyCorrelation(records, primaryQuestion, secondaryQuestion);
  if (correlation) {
    const correlationBox = analysisElement('div', 'speaker-survey-correlation');
    correlationBox.append(
      analysisElement('span', '', '数値回答の相関'),
      analysisElement('strong', '', `r = ${correlation.coefficient.toFixed(3)}`),
      analysisElement('small', '', `n = ${correlation.count}。関連の強さを示す記述値で、因果関係は示しません。`)
    );
    panel.append(correlationBox);
  }
  return panel;
}

function renderSpeakerSurveyAnalysis() {
  const container = document.querySelector('#speaker-survey-analysis-content');
  if (!container) return;
  window.clearTimeout(speakerSurveyAnalysisTimer);
  speakerSurveyAnalysisTimer = null;
  const allQuestions = speakerSurveyQuestionKeys(speakerRegistry);
  const metric = document.querySelector('#registry-survey-metric');
  if (metric) metric.textContent = String(allQuestions.length);
  container.replaceChildren();
  if (!allQuestions.length) {
    const empty = analysisElement('div', 'speaker-survey-empty');
    empty.append(
      analysisElement('strong', '', '事前アンケート回答がまだありません'),
      analysisElement('p', '', 'Googleフォームの回答CSVを読み込むか、各話者の「事前アンケート回答」に「質問=回答」の形式で入力してください。')
    );
    container.append(empty);
    return;
  }

  const records = speakerSurveyAnalysisState.includeInactive
    ? [...speakerRegistry]
    : speakerRegistry.filter(record => record.active !== false);
  if (!allQuestions.includes(speakerSurveyAnalysisState.primaryQuestion)) {
    speakerSurveyAnalysisState.primaryQuestion = allQuestions[0];
  }
  if (
    !allQuestions.includes(speakerSurveyAnalysisState.secondaryQuestion)
    || speakerSurveyAnalysisState.secondaryQuestion === speakerSurveyAnalysisState.primaryQuestion
  ) {
    speakerSurveyAnalysisState.secondaryQuestion = allQuestions.find(
      question => question !== speakerSurveyAnalysisState.primaryQuestion
    ) || '';
  }
  const primaryQuestion = speakerSurveyAnalysisState.primaryQuestion;
  const primary = speakerSurveyQuestionSummary(records, primaryQuestion);
  if (
    speakerSurveyAnalysisState.answerFilter
    && !primary.values.some(item => item.value === speakerSurveyAnalysisState.answerFilter)
  ) {
    speakerSurveyAnalysisState.answerFilter = '';
  }

  const controls = analysisElement('div', 'speaker-survey-controls');
  const primaryLabel = analysisElement('label', 'field');
  primaryLabel.append(analysisElement('span', '', '分析する質問'));
  const primarySelect = document.createElement('select');
  allQuestions.forEach(question => primarySelect.add(new Option(question, question)));
  primarySelect.value = primaryQuestion;
  primarySelect.addEventListener('change', () => {
    speakerSurveyAnalysisState.primaryQuestion = primarySelect.value;
    speakerSurveyAnalysisState.answerFilter = '';
    if (speakerSurveyAnalysisState.secondaryQuestion === primarySelect.value) {
      speakerSurveyAnalysisState.secondaryQuestion = allQuestions.find(question => question !== primarySelect.value) || '';
    }
    renderSpeakerSurveyAnalysis();
  });
  primaryLabel.append(primarySelect);

  const secondaryLabel = analysisElement('label', 'field');
  secondaryLabel.append(analysisElement('span', '', 'クロス集計する質問'));
  const secondarySelect = document.createElement('select');
  secondarySelect.add(new Option('クロス集計しない', ''));
  allQuestions.filter(question => question !== primaryQuestion)
    .forEach(question => secondarySelect.add(new Option(question, question)));
  secondarySelect.value = speakerSurveyAnalysisState.secondaryQuestion;
  secondarySelect.addEventListener('change', () => {
    speakerSurveyAnalysisState.secondaryQuestion = secondarySelect.value;
    renderSpeakerSurveyAnalysis();
  });
  secondaryLabel.append(secondarySelect);

  const filterLabel = analysisElement('label', 'field');
  filterLabel.append(analysisElement('span', '', '回答で参加者を絞り込み'));
  const answerSelect = document.createElement('select');
  answerSelect.add(new Option('すべての回答', ''));
  primary.values.forEach(item => answerSelect.add(new Option(`${item.value}（${item.count}人）`, item.value)));
  answerSelect.value = speakerSurveyAnalysisState.answerFilter;
  answerSelect.addEventListener('change', () => {
    speakerSurveyAnalysisState.answerFilter = answerSelect.value;
    renderSpeakerSurveyAnalysis();
  });
  filterLabel.append(answerSelect);

  const inactiveLabel = analysisElement('label', 'mini-check speaker-survey-inactive');
  const inactive = document.createElement('input');
  inactive.type = 'checkbox';
  inactive.checked = speakerSurveyAnalysisState.includeInactive;
  inactive.addEventListener('change', () => {
    speakerSurveyAnalysisState.includeInactive = inactive.checked;
    speakerSurveyAnalysisState.answerFilter = '';
    renderSpeakerSurveyAnalysis();
  });
  inactiveLabel.append(inactive, document.createTextNode('無効な話者を含める'));
  controls.append(primaryLabel, secondaryLabel, filterLabel, inactiveLabel);
  container.append(controls);

  const overview = analysisElement('div', 'speaker-survey-overview');
  const responseRate = records.length ? 100 * primary.answered / records.length : 0;
  [
    ['分析対象', `${records.length}人`, speakerSurveyAnalysisState.includeInactive ? '全登録話者' : '有効な話者'],
    ['質問項目', `${allQuestions.length}問`, 'CSVの未知列を含む'],
    ['回答済み', `${primary.answered}人`, `${responseRate.toFixed(1)}%`],
    ['未回答', `${primary.missing}人`, primary.missing ? '回答漏れを確認' : '回答完了']
  ].forEach(([label, value, note]) => {
    const item = analysisElement('div');
    item.append(
      analysisElement('span', '', label),
      analysisElement('strong', '', value),
      analysisElement('small', '', note)
    );
    overview.append(item);
  });
  container.append(overview);

  const grid = analysisElement('div', 'speaker-survey-grid');
  const distributionPanel = analysisElement('section', 'speaker-survey-panel');
  distributionPanel.append(
    analysisElement('h4', '', `回答分布：${primaryQuestion}`),
    analysisElement('p', 'speaker-survey-help', '同じ回答をまとめ、回答者全体に占める割合を表示します。')
  );
  const distribution = analysisElement('div', 'speaker-survey-bars');
  const maximum = Math.max(0, ...primary.values.map(item => item.count));
  primary.values.slice(0, 20).forEach(item => {
    appendSpeakerSurveyBar(distribution, item.value, item.count, primary.answered, maximum);
  });
  if (!primary.values.length) distribution.append(analysisElement('p', 'analysis-no-data', 'この質問への回答がありません。'));
  distributionPanel.append(distribution);
  if (primary.values.length > 20) {
    distributionPanel.append(analysisElement('p', 'speaker-survey-note', `回答数上位20件を表示（全${primary.values.length}種類）`));
  }
  const numeric = speakerSurveyNumericSummary(records, primaryQuestion);
  if (numeric) {
    const numericBox = analysisElement('div', 'speaker-survey-numeric');
    [
      ['平均', numeric.mean.toFixed(2)],
      ['中央値', numeric.median.toFixed(2)],
      ['最小', numeric.minimum.toFixed(2)],
      ['最大', numeric.maximum.toFixed(2)]
    ].forEach(([label, value]) => {
      const item = analysisElement('span');
      item.append(analysisElement('small', '', label), document.createTextNode(value));
      numericBox.append(item);
    });
    numericBox.append(analysisElement('p', '', `数値として解釈できた回答 n=${numeric.count}`));
    distributionPanel.append(numericBox);
  }
  grid.append(distributionPanel, buildSpeakerSurveyCompleteness(records, allQuestions));
  container.append(grid);

  if (speakerSurveyAnalysisState.secondaryQuestion) {
    container.append(buildSpeakerSurveyCrosstab(
      records,
      primaryQuestion,
      speakerSurveyAnalysisState.secondaryQuestion
    ));
  }

  const participantPanel = analysisElement('section', 'speaker-survey-panel speaker-survey-participants');
  const selectedRecords = records.filter(record => (
    !speakerSurveyAnalysisState.answerFilter
    || speakerSurveyAnswer(record, primaryQuestion) === speakerSurveyAnalysisState.answerFilter
  ));
  participantPanel.append(
    analysisElement('h4', '', `該当参加者（${selectedRecords.length}人）`),
    analysisElement('p', 'speaker-survey-help', speakerSurveyAnalysisState.answerFilter
      ? `「${speakerSurveyAnalysisState.answerFilter}」と回答した参加者です。`
      : '回答内容と参加者を照合できます。氏名より仮名・参加者コードの利用を推奨します。')
  );
  const tableWrap = analysisElement('div', 'speaker-survey-table-wrap');
  const table = document.createElement('table');
  table.className = 'speaker-survey-table participant';
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  ['参加者', '参加者コード', primaryQuestion, speakerSurveyAnalysisState.secondaryQuestion].filter(Boolean)
    .forEach(label => headRow.append(analysisElement('th', '', label)));
  head.append(headRow);
  const body = document.createElement('tbody');
  selectedRecords.slice(0, 100).forEach(record => {
    const row = document.createElement('tr');
    [
      speakerRecordName(record),
      record.participant_code || '—',
      speakerSurveyAnswer(record, primaryQuestion) || '未回答',
      speakerSurveyAnalysisState.secondaryQuestion
        ? speakerSurveyAnswer(record, speakerSurveyAnalysisState.secondaryQuestion) || '未回答'
        : null
    ].filter(value => value !== null).forEach(value => row.append(analysisElement('td', '', value)));
    body.append(row);
  });
  table.append(head, body);
  tableWrap.append(table);
  participantPanel.append(tableWrap);
  if (selectedRecords.length > 100) {
    participantPanel.append(analysisElement('p', 'speaker-survey-note', '画面には先頭100人を表示しています。全件はCSV書き出しで確認できます。'));
  }
  container.append(participantPanel);
}

function setSpeakerRegistryDirty(dirty = true, trackMutation = true) {
  speakerRegistryDirty = dirty;
  if (speakerRegistryDirty && trackMutation) speakerRegistryMutationGeneration += 1;
  const metric = document.querySelector('#registry-dirty-metric');
  if (metric) {
    metric.textContent = dirty ? '未保存' : '保存済み';
    metric.classList.toggle('unsaved', dirty);
  }
  if (speakerRegistrySaveState) {
    speakerRegistrySaveState.textContent = dirty ? '未保存の変更があります' : '保存済み';
    speakerRegistrySaveState.classList.toggle('unsaved', dirty);
  }
  if (speakerRegistrySaveButton) speakerRegistrySaveButton.disabled = !dirty || speakerRegistrySaveInProgress;
  if (speakerRegistryCard) speakerRegistryCard.classList.toggle('has-unsaved', dirty);
  scheduleSpeakerSurveyAnalysis();
}

function makeSheetInput(record, key, {
  type = 'text', wide = false, multiline = false, label = '', placeholder = '', afterInput = null
} = {}) {
  const input = document.createElement(multiline ? 'textarea' : 'input');
  if (!multiline) input.type = type;
  if (wide) input.className = 'cell-wide';
  if (label) input.setAttribute('aria-label', label);
  if (placeholder) input.placeholder = placeholder;
  input.dataset.speakerId = record.id;
  input.dataset.speakerField = key;
  input.value = Array.isArray(record[key]) ? record[key].join(', ') : (record[key] || '');
  input.addEventListener('input', () => {
    record[key] = key === 'tags'
      ? input.value.split(/[,、;]+/).map(item => item.trim()).filter(Boolean)
      : input.value;
    setSpeakerRegistryDirty();
    if (afterInput) afterInput(input.value);
  });
  return input;
}

function makeSheetSelect(record, key, labels, {label = '', afterChange = null} = {}) {
  const select = document.createElement('select');
  if (label) select.setAttribute('aria-label', label);
  select.dataset.speakerId = record.id;
  select.dataset.speakerField = key;
  Object.entries(labels).forEach(([value, label]) => select.add(new Option(label, value)));
  select.value = record[key] || Object.keys(labels)[0];
  select.addEventListener('change', () => {
    record[key] = select.value;
    setSpeakerRegistryDirty();
    if (afterChange) afterChange(select.value);
  });
  return select;
}

function appendSheetCell(row, control) {
  const cell = document.createElement('td');
  cell.append(control);
  row.append(cell);
}

async function loadSpeakerRegistry(force = false) {
  if (speakerRegistryLoaded && !force) {
    renderSpeakerRegistry();
    return speakerRegistry;
  }
  try {
    const response = await apiFetch('/api/speakers', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '話者管理データを取得できませんでした。');
    speakerRegistry = Array.isArray(data.speakers) ? data.speakers : [];
    speakerRegistryBaseline = deepCopy(speakerRegistry);
    speakerSaveConflict = false;
    document.querySelector('#speaker-draft-recovery').hidden = true;
    speakerRegistryRevision = Number(data.registry_revision || 0);
    speakerRegistryDeletedIds.clear();
    speakerRegistryLoaded = true;
    setSpeakerRegistryDirty(false);
    renderSpeakerRegistry();
    if (currentJob && !resultCard.hidden) renderSpeakerEditor();
    return speakerRegistry;
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
    return [];
  }
}

function speakerRecordName(record) {
  return String(record.pseudonym || record.display_name || record.participant_code || '名前未設定').trim();
}

function speakerRecordSearchText(record) {
  return [
    record.participant_code, record.display_name, record.pseudonym, record.organization,
    record.department, record.job_title, ...(record.tags || []),
    ...Object.entries(record.attributes || {}).flat(), record.notes
  ].join(' ').toLocaleLowerCase();
}

function visibleSpeakerRegistry() {
  const searchElement = document.querySelector('#speaker-registry-search');
  const roleElement = document.querySelector('#speaker-registry-role-filter');
  const showInactiveElement = document.querySelector('#speaker-registry-show-inactive');
  const query = (searchElement ? searchElement.value : '').trim().toLocaleLowerCase();
  const role = roleElement ? roleElement.value : '';
  const showInactive = !showInactiveElement || showInactiveElement.checked;
  return speakerRegistry.filter(record => {
    if (!showInactive && !record.active) return false;
    if (role && record.default_role !== role) return false;
    if (!query) return true;
    return speakerRecordSearchText(record).includes(query);
  });
}

function updateSpeakerRegistryOverview() {
  const active = speakerRegistry.filter(record => record.active !== false);
  const values = {
    '#registry-total-metric': speakerRegistry.length,
    '#registry-active-metric': active.length,
    '#registry-survey-metric': speakerSurveyQuestionKeys(speakerRegistry).length
  };
  Object.entries(values).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = String(value);
  });
}

function removeSpeakerRecord(record) {
  if (!window.confirm(`${speakerRecordName(record)} を話者管理から削除しますか？\n「変更を保存」するまで削除は確定しません。`)) return;
  speakerRegistryDeletedIds.add(record.id);
  speakerRegistry = speakerRegistry.filter(item => item.id !== record.id);
  setSpeakerRegistryDirty();
  renderSpeakerRegistry();
}

function makeAttributesControl(record, label) {
  const attributes = document.createElement('textarea');
  attributes.value = attributesToText(record.attributes);
  attributes.placeholder = '例：満足度=5; 年齢層=30代; 利用歴=3年以上';
  attributes.setAttribute('aria-label', label);
  attributes.dataset.speakerId = record.id;
  attributes.dataset.speakerField = 'attributes';
  attributes.addEventListener('input', () => {
    record.attributes = textToAttributes(attributes.value);
    setSpeakerRegistryDirty();
  });
  return attributes;
}

function renderSpeakerRegistryTable(visible) {
  speakerRegistryBody.replaceChildren();
  if (!visible.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 13;
    cell.className = 'speaker-registry-empty';
    cell.textContent = '条件に一致する話者はいません。検索条件を変えるか、新しい話者を追加してください。';
    row.append(cell);
    speakerRegistryBody.append(row);
    return;
  }

  visible.forEach(record => {
    const row = document.createElement('tr');
    row.dataset.speakerId = record.id;
    row.classList.toggle('inactive', !record.active);
    const active = document.createElement('input');
    active.type = 'checkbox';
    active.checked = record.active !== false;
    active.setAttribute('aria-label', `${speakerRecordName(record)}を有効にする`);
    active.addEventListener('change', () => {
      record.active = active.checked;
      setSpeakerRegistryDirty();
      row.classList.toggle('inactive', !record.active);
      updateSpeakerRegistryOverview();
      const showInactive = document.querySelector('#speaker-registry-show-inactive');
      if (!active.checked && showInactive && !showInactive.checked) renderSpeakerRegistry();
    });
    appendSheetCell(row, active);
    appendSheetCell(row, makeSheetInput(record, 'participant_code', {label: `${speakerRecordName(record)}の参加者コード`}));
    appendSheetCell(row, makeSheetInput(record, 'display_name', {label: `${speakerRecordName(record)}の氏名`}));
    appendSheetCell(row, makeSheetInput(record, 'pseudonym', {label: `${speakerRecordName(record)}の仮名・表示名`}));
    appendSheetCell(row, makeSheetSelect(record, 'default_role', speakerRoleLabels, {
      label: `${speakerRecordName(record)}の既定役割`,
      afterChange: () => {
        const roleFilter = document.querySelector('#speaker-registry-role-filter');
        if (roleFilter && roleFilter.value) renderSpeakerRegistry();
      }
    }));
    appendSheetCell(row, makeSheetInput(record, 'organization', {label: `${speakerRecordName(record)}の組織`}));
    appendSheetCell(row, makeSheetInput(record, 'department', {label: `${speakerRecordName(record)}の部署`}));
    appendSheetCell(row, makeSheetInput(record, 'job_title', {label: `${speakerRecordName(record)}の役職`}));
    appendSheetCell(row, makeSheetSelect(record, 'confidentiality_status', consentLabels, {label: `${speakerRecordName(record)}の守秘同意`}));
    appendSheetCell(row, makeSheetInput(record, 'tags', {wide: true, label: `${speakerRecordName(record)}のタグ`}));
    appendSheetCell(row, makeAttributesControl(record, `${speakerRecordName(record)}の事前アンケート回答`));
    appendSheetCell(row, makeSheetInput(record, 'notes', {multiline: true, label: `${speakerRecordName(record)}の備考`}));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'sheet-delete';
    remove.textContent = '削除';
    remove.setAttribute('aria-label', `${speakerRecordName(record)}を削除`);
    remove.addEventListener('click', () => removeSpeakerRecord(record));
    appendSheetCell(row, remove);
    speakerRegistryBody.append(row);
  });
}

function createSpeakerCardField(labelText, control, wide = false) {
  const label = document.createElement('label');
  label.className = `field speaker-card-field${wide ? ' wide' : ''}`;
  const text = document.createElement('span');
  text.textContent = labelText;
  label.append(text, control);
  return label;
}

function renderSpeakerRegistryCards(visible) {
  speakerRegistryList.replaceChildren();
  if (!visible.length) {
    const empty = document.createElement('div');
    empty.className = 'speaker-registry-empty';
    empty.textContent = '条件に一致する話者はいません。条件をクリアするか、新しい話者を追加してください。';
    speakerRegistryList.append(empty);
    return;
  }

  visible.forEach(record => {
    const card = document.createElement('article');
    card.className = 'speaker-management-card';
    card.dataset.speakerId = record.id;
    card.classList.toggle('inactive', record.active === false);

    const header = document.createElement('header');
    const identity = document.createElement('div');
    const role = document.createElement('span');
    role.className = 'speaker-card-role';
    const title = document.createElement('h3');
    const subtitle = document.createElement('p');
    identity.append(role, title, subtitle);
    const activeLabel = document.createElement('label');
    activeLabel.className = 'speaker-card-active';
    const active = document.createElement('input');
    active.type = 'checkbox';
    active.checked = record.active !== false;
    const activeText = document.createElement('span');
    activeText.textContent = '有効';
    activeLabel.append(active, activeText);
    header.append(identity, activeLabel);

    const refreshIdentity = () => {
      role.textContent = speakerRoleLabels[record.default_role] || 'その他';
      title.textContent = speakerRecordName(record);
      subtitle.textContent = [record.participant_code, record.organization, record.job_title].filter(Boolean).join(' ・ ') || '基本情報を入力してください';
      active.setAttribute('aria-label', `${speakerRecordName(record)}を有効にする`);
    };
    refreshIdentity();
    active.addEventListener('change', () => {
      record.active = active.checked;
      card.classList.toggle('inactive', !active.checked);
      setSpeakerRegistryDirty();
      updateSpeakerRegistryOverview();
      const showInactive = document.querySelector('#speaker-registry-show-inactive');
      if (!active.checked && showInactive && !showInactive.checked) renderSpeakerRegistry();
    });

    const primary = document.createElement('div');
    primary.className = 'speaker-card-grid primary';
    primary.append(
      createSpeakerCardField('参加者コード', makeSheetInput(record, 'participant_code', {label: '参加者コード', afterInput: refreshIdentity})),
      createSpeakerCardField('氏名', makeSheetInput(record, 'display_name', {label: '氏名', afterInput: refreshIdentity})),
      createSpeakerCardField('仮名・表示名', makeSheetInput(record, 'pseudonym', {label: '仮名・表示名', afterInput: refreshIdentity})),
      createSpeakerCardField('既定役割', makeSheetSelect(record, 'default_role', speakerRoleLabels, {
        label: '既定役割', afterChange: () => {
          refreshIdentity();
          const roleFilter = document.querySelector('#speaker-registry-role-filter');
          if (roleFilter && roleFilter.value) renderSpeakerRegistry();
        }
      }))
    );

    const details = document.createElement('details');
    details.className = 'speaker-card-details';
    const summary = document.createElement('summary');
    summary.textContent = '所属・アンケート・詳細を編集';
    const detailGrid = document.createElement('div');
    detailGrid.className = 'speaker-card-grid details';
    detailGrid.append(
      createSpeakerCardField('組織', makeSheetInput(record, 'organization', {label: '組織', afterInput: refreshIdentity})),
      createSpeakerCardField('部署', makeSheetInput(record, 'department', {label: '部署'})),
      createSpeakerCardField('役職', makeSheetInput(record, 'job_title', {label: '役職', afterInput: refreshIdentity})),
      createSpeakerCardField('守秘同意', makeSheetSelect(record, 'confidentiality_status', consentLabels, {label: '守秘同意'})),
      createSpeakerCardField('タグ', makeSheetInput(record, 'tags', {label: 'タグ', placeholder: '例：顧客, 管理職'}), true),
      createSpeakerCardField('事前アンケート回答', makeAttributesControl(record, '事前アンケート回答'), true),
      createSpeakerCardField('備考', makeSheetInput(record, 'notes', {multiline: true, label: '備考'}), true)
    );
    details.append(summary, detailGrid);

    const footer = document.createElement('footer');
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'sheet-delete';
    remove.textContent = 'この話者を削除';
    remove.addEventListener('click', () => removeSpeakerRecord(record));
    footer.append(remove);

    card.append(header, primary, details, footer);
    speakerRegistryList.append(card);
  });
}

function renderSpeakerRegistry() {
  if (!speakerRegistryBody || !speakerRegistryList) return;
  const visible = visibleSpeakerRegistry();
  if (mobileWizardMedia.matches) {
    speakerRegistryBody.replaceChildren();
    renderSpeakerRegistryCards(visible);
  } else {
    speakerRegistryList.replaceChildren();
    renderSpeakerRegistryTable(visible);
  }
  updateSpeakerRegistryOverview();
  renderSpeakerSurveyAnalysis();
  const count = document.querySelector('#speaker-registry-count');
  if (count) count.textContent = `${visible.length}人を表示（登録 ${speakerRegistry.length}人）`;
}

async function saveSpeakerRegistry() {
  if (speakerRegistrySaveInProgress) return;
  const invalid = speakerRegistry.find(record => (
    !String(record.participant_code || '').trim()
    && !String(record.display_name || '').trim()
    && !String(record.pseudonym || '').trim()
  ));
  if (invalid) {
    setAlert(document.querySelector('#speaker-registry-message'), '氏名、仮名、参加者コードのいずれかを入力してください。', true);
    return;
  }
  const button = speakerRegistrySaveButton;
  const saveGeneration = speakerRegistryMutationGeneration;
  speakerRegistrySaveInProgress = true;
  if (button) button.disabled = true;
  try {
    const response = await apiFetch('/api/speakers', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        registry_revision: speakerRegistryRevision,
        speakers: speakerRegistry,
        delete_ids: [...speakerRegistryDeletedIds]
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) {
      const conflict = response.status === 409
        ? '別の画面で話者管理が更新されています。未保存内容をJSONで退避してから再読み込みしてください。'
        : '話者管理データを保存できませんでした。';
      if (response.status === 409) { speakerSaveConflict = true; showDraftRecovery('speakers'); }
      throw new Error(response.status === 409 ? conflict : (data.error || conflict));
    }
    speakerRegistryRevision = Number(data.registry_revision || speakerRegistryRevision);
    if (speakerRegistryMutationGeneration === saveGeneration) {
      speakerRegistry = data.speakers || [];
      speakerRegistryBaseline = deepCopy(speakerRegistry);
      speakerSaveConflict = false;
      document.querySelector('#speaker-draft-recovery').hidden = true;
      speakerRegistryDeletedIds.clear();
      setSpeakerRegistryDirty(false);
      renderSpeakerRegistry();
      setAlert(document.querySelector('#speaker-registry-message'), `${speakerRegistry.length}人の話者情報を保存しました。`);
      if (currentJob && !resultCard.hidden) renderSpeakerEditor();
    } else {
      setSpeakerRegistryDirty(true, false);
      setAlert(document.querySelector('#speaker-registry-message'), '保存開始後の追加変更が残っています。内容を確認して、もう一度保存してください。', true);
    }
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
  } finally {
    speakerRegistrySaveInProgress = false;
    if (button) button.disabled = !speakerRegistryDirty;
  }
}

function cancelSpeakerImport() {
  pendingSpeakerImport = null;
  document.querySelector('#speaker-import-preview').hidden = true;
  document.querySelector('#speaker-csv-input').value = '';
}
