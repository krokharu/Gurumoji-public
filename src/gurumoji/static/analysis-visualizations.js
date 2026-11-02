// Shared analysis cards, charts, and navigation.
// methodIds tags a panel with the analysis methods it belongs to, so the method view
// can collect the same panels the long automatic view builds.
function analysisCardPanel(titleText, classification, exportDataset = '', wide = false, methodIds = '') {
  const panel = analysisElement('section', `analysis-panel${wide ? ' wide' : ''}`);
  if (methodIds) panel.dataset.analysisMethod = methodIds;
  const heading = analysisElement('header', 'analysis-panel-heading');
  const titleGroup = analysisElement('div');
  const badgeLabels = {automatic: '自動集計', configured: '要設定', manual: '要確認・解釈'};
  titleGroup.append(
    analysisElement('span', `analysis-kind ${classification}`, badgeLabels[classification] || classification),
    analysisElement('h3', '', titleText)
  );
  heading.append(titleGroup);
  if (exportDataset) {
    const link = analysisExportLink('CSV', exportDataset);
    if (link) heading.append(link);
  }
  const body = analysisElement('div', 'analysis-panel-body');
  panel.append(heading, body);
  return {panel, body};
}

function appendAnalysisMetric(container, label, value, note = '') {
  const card = analysisElement('div', 'analysis-overview-metric');
  card.append(analysisElement('span', '', label), analysisElement('strong', '', value));
  if (note) card.append(analysisElement('small', '', note));
  container.append(card);
}

function appendAnalysisBar(container, label, value, detail = '', color = '#1C6B50') {
  const row = analysisElement('div', 'analysis-bar-row');
  const heading = analysisElement('div', 'analysis-bar-heading');
  heading.append(analysisElement('strong', '', label), analysisElement('span', '', detail));
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) {
    row.append(heading, analysisElement('p', 'analysis-caption', '割合は算出不可'));
    container.append(row);
    return row;
  }
  const track = analysisElement('div', 'analysis-bar-track');
  const fill = analysisElement('i');
  const percent = boundedAnalysisPercent(value);
  fill.style.width = `${percent}%`;
  fill.style.backgroundColor = safeAnalysisColor(color);
  track.setAttribute('role', 'img');
  track.setAttribute('aria-label', `${label} ${percent.toFixed(1)}%`);
  track.append(fill);
  row.append(heading, track);
  container.append(row);
  return row;
}

function analysisSvgElement(tagName, attributes = {}, textValue = '') {
  const element = document.createElementNS('http://www.w3.org/2000/svg', tagName);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  if (textValue !== '') element.textContent = String(textValue);
  return element;
}

function buildAnalysisProcessFlow({title, note, nodes}) {
  const flow = analysisElement('section', 'analysis-process-flow');
  const heading = analysisElement('div', 'analysis-process-flow-heading');
  heading.append(analysisElement('strong', '', title), analysisElement('small', '', note));
  const viewport = analysisElement('div', 'analysis-process-flow-viewport');
  const track = analysisElement('div', 'analysis-process-flow-track');
  nodes.forEach((item, index) => {
    const node = analysisElement('div', `analysis-process-node ${item.state || 'pending'}`);
    node.dataset.processNode = item.id;
    node.append(
      analysisElement('span', 'analysis-process-node-kind', item.kind || `STEP ${index + 1}`),
      analysisElement('strong', '', item.label),
      analysisElement('small', '', item.detail || '')
    );
    if (Array.isArray(item.terms) && item.terms.length) {
      const terms = analysisElement('div', 'analysis-process-terms');
      item.terms.slice(0, 3).forEach(term => terms.append(analysisElement('span', '', term)));
      node.append(terms);
    }
    track.append(node);
    if (index < nodes.length - 1) {
      const next = nodes[index + 1];
      const state = item.state === 'running' || next.state === 'running' ? 'active'
        : item.state === 'complete' && next.state === 'complete' ? 'complete' : 'pending';
      const link = analysisElement('span', `analysis-process-link ${state}`);
      link.setAttribute('aria-hidden', 'true');
      track.append(link);
    }
  });
  viewport.append(track);
  flow.append(heading, viewport);
  return flow;
}

function buildAnalysisLineSvg(series, bins) {
  const svg = analysisSvgElement('svg', {
    class: 'analysis-timeline-chart', viewBox: '0 0 760 300', role: 'img', tabindex: '0'
  });
  svg.append(
    analysisSvgElement('title', {}, '時間帯別の発話量の折れ線グラフ'),
    analysisSvgElement('desc', {}, '横軸が会話の時刻、縦軸が各時間帯に含まれる発話秒数です。点にカーソルを合わせると値を確認できます。')
  );
  const plot = {x: 58, y: 18, width: 674, height: 224};
  const allValues = series.flatMap(item => item.values).map(value => Math.max(0, Number(value) || 0));
  const maximum = Math.max(1, ...allValues);
  [0, .25, .5, .75, 1].forEach(ratio => {
    const y = plot.y + plot.height * (1 - ratio);
    svg.append(
      analysisSvgElement('line', {
        x1: plot.x, x2: plot.x + plot.width, y1: y, y2: y, class: 'analysis-chart-grid'
      }),
      analysisSvgElement('text', {
        x: plot.x - 10, y: y + 4, 'text-anchor': 'end', class: 'analysis-chart-axis-label'
      }, (maximum * ratio).toFixed(maximum < 10 ? 1 : 0))
    );
  });
  const count = Math.max(1, bins.length);
  series.forEach(item => {
    const points = item.values.map((rawValue, index) => {
      const value = Math.max(0, Number(rawValue) || 0);
      const x = plot.x + plot.width * (count === 1 ? .5 : index / (count - 1));
      const y = plot.y + plot.height * (1 - value / maximum);
      return {x, y, value, index};
    });
    const path = analysisSvgElement('path', {
      d: points.map((point, index) => `${index ? 'L' : 'M'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' '),
      class: 'analysis-line-series', stroke: safeAnalysisColor(item.color),
      'vector-effect': 'non-scaling-stroke'
    });
    svg.append(path);
    points.forEach(point => {
      const circle = analysisSvgElement('circle', {
        cx: point.x, cy: point.y, r: bins.length > 45 ? 2.3 : 4,
        class: 'analysis-line-point', fill: safeAnalysisColor(item.color)
      });
      const bin = bins[point.index] || {};
      circle.append(analysisSvgElement('title', {}, `${item.label} / ${formatTime(bin.start || 0)}–${formatTime(bin.end || 0)} / ${point.value.toFixed(1)}秒`));
      svg.append(circle);
    });
  });
  const labelIndexes = [...new Set([0, Math.floor((count - 1) / 2), count - 1])];
  labelIndexes.forEach(index => {
    const bin = bins[index] || {};
    const x = plot.x + plot.width * (count === 1 ? .5 : index / (count - 1));
    const anchor = index === 0 ? 'start' : index === count - 1 ? 'end' : 'middle';
    svg.append(analysisSvgElement('text', {
      x, y: 275, 'text-anchor': anchor, class: 'analysis-chart-axis-label'
    }, formatTime(bin.start || 0)));
  });
  svg.append(analysisSvgElement('text', {
    x: 17, y: 135, transform: 'rotate(-90 17 135)', 'text-anchor': 'middle', class: 'analysis-chart-axis-title'
  }, '発話秒数'));
  return svg;
}

function buildAnalysisTimelineChart(rawBins, speakerMetrics = []) {
  const bins = Array.isArray(rawBins) ? rawBins : [];
  const module = analysisElement('div', 'analysis-chart-module');
  const toolbar = analysisElement('div', 'analysis-chart-toolbar');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', '会話中の発話量を追う'),
    analysisElement('span', '', '表示を切り替えて、全体の山と話者ごとの参加タイミングを比較できます。')
  );
  const switcher = analysisElement('div', 'analysis-chart-switch');
  switcher.setAttribute('role', 'group');
  switcher.setAttribute('aria-label', '時間推移グラフの表示');
  const totalButton = analysisElement('button', 'active', '全体');
  const speakerButton = analysisElement('button', '', '話者別');
  [totalButton, speakerButton].forEach(button => button.type = 'button');
  switcher.append(totalButton, speakerButton);
  toolbar.append(explanation, switcher);
  const stage = analysisElement('div', 'analysis-chart-stage');
  const legend = analysisElement('div', 'analysis-chart-legend');
  const note = analysisElement('p', 'analysis-chart-note');
  module.append(toolbar, stage, legend, note);

  const palette = ['#1C6B50', '#2F80ED', '#E87941', '#9B51E0', '#6C8B3C', '#C34F72'];
  const metricMap = new Map((Array.isArray(speakerMetrics) ? speakerMetrics : []).map(item => [String(item.speaker), item]));
  const speakerTotals = new Map();
  bins.forEach(bin => (Array.isArray(bin.speakers) ? bin.speakers : []).forEach(item => {
    const id = String(item.speaker || item.speaker_name || 'UNKNOWN');
    speakerTotals.set(id, (speakerTotals.get(id) || 0) + Math.max(0, Number(item.seconds) || 0));
  }));
  const visibleSpeakers = [...speakerTotals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);

  function render(mode) {
    const speakerMode = mode === 'speakers';
    totalButton.classList.toggle('active', !speakerMode);
    speakerButton.classList.toggle('active', speakerMode);
    totalButton.setAttribute('aria-pressed', String(!speakerMode));
    speakerButton.setAttribute('aria-pressed', String(speakerMode));
    const series = speakerMode
      ? visibleSpeakers.map(([speaker], index) => {
          const metric = metricMap.get(speaker) || {};
          return {
            id: speaker,
            label: metric.speaker_name || (bins.flatMap(bin => bin.speakers || []).find(item => String(item.speaker) === speaker) || {}).speaker_name || speaker,
            color: safeAnalysisColor(metric.color, palette[index % palette.length]),
            values: bins.map(bin => Number(((bin.speakers || []).find(item => String(item.speaker) === speaker) || {}).seconds) || 0)
          };
        })
      : [{
          id: 'total', label: '全体', color: '#1C6B50',
          values: bins.map(item => Number(item.speaking_seconds) || 0)
        }];
    stage.replaceChildren(buildAnalysisLineSvg(series, bins));
    legend.replaceChildren();
    series.forEach(item => {
      const entry = analysisElement('span');
      const marker = analysisElement('i');
      marker.style.backgroundColor = safeAnalysisColor(item.color);
      entry.append(marker, document.createTextNode(item.label));
      legend.append(entry);
    });
    note.textContent = speakerMode
      ? `発話時間が多い上位${visibleSpeakers.length}話者を表示しています。折れ線の高さは各時間帯の秒数で、累積値ではありません。`
      : '時間帯ごとの総発話秒数です。重なり発話がある場合、時間帯の長さを超えることがあります。';
    const missing = speakerMetrics.reduce((sum, metric) => sum + (Number(metric.missing_time_turn_count) || 0), 0);
    if (missing > 0) note.textContent += ` 時刻不明${missing}発話は時間帯へ配置できず、時刻あり発話だけの集計です。`;
  }
  totalButton.addEventListener('click', () => render('total'));
  speakerButton.addEventListener('click', () => render('speakers'));
  render('total');
  return module;
}

function analysisExcitementPoints(rawBins) {
  return (Array.isArray(rawBins) ? rawBins : []).map(bin => {
    const start = Math.max(0, Number(bin.start) || 0);
    const end = Math.max(start, Number(bin.end) || start);
    const duration = Math.max(.001, end - start);
    const speaking = Math.max(0, Number(bin.speaking_seconds) || 0);
    const turns = Math.max(0, Number(bin.turn_count) || 0);
    // A descriptive activity index: speech occupancy and turn starts, each capped.
    const occupancy = Math.min(1, speaking / duration);
    const turnRate = Math.min(1, turns / Math.max(1, duration / 12));
    return {start, end, speaking, turns, score: Math.round(100 * (.65 * occupancy + .35 * turnRate))};
  }).filter(point => point.end > point.start);
}

function buildAnalysisExcitementChart(rawBins, sessionOutline = {}) {
  const points = analysisExcitementPoints(rawBins);
  const module = analysisElement('div', 'analysis-chart-module');
  const explanation = analysisElement('p', 'analysis-caption',
    '縦軸は発話時間の割合（65%）と発話開始回数（35%）から計算した会話活発度です。声の大きさや感情を測った値ではありません。');
  module.append(explanation);
  if (!points.length) {
    module.append(analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため表示できません。'));
    return module;
  }
  const result = sessionOutline?.result || {};
  const stale = Boolean(result.transformer_stale);
  const duration = Math.max(...points.map(point => point.end));
  const rows = (Array.isArray(result.rows) ? result.rows : []).filter(row => {
    const start = Number(row.start);
    const end = Number(row.end);
    return Number.isFinite(start) && Number.isFinite(end) && end > start
      && start < duration && (!stale || row.title_source === 'outline');
  });
  const stage = analysisElement('div', 'analysis-chart-stage');
  const svg = analysisSvgElement('svg', {
    class: 'analysis-timeline-chart analysis-excitement-chart', viewBox: '0 0 760 350', role: 'img', tabindex: '0'
  });
  svg.append(
    analysisSvgElement('title', {}, '時間別の盛り上がりと議題・話題'),
    analysisSvgElement('desc', {}, '横軸は会話の経過時間、縦軸は発話量と発話開始回数から計算した盛り上がりの目安です。下の帯にアウトラインと話題を表示します。')
  );
  const plot = {x: 70, y: 22, width: 650, height: 195};
  const at = time => plot.x + plot.width * Math.min(1, Math.max(0, time / duration));
  [0, 25, 50, 75, 100].forEach(score => {
    const y = plot.y + plot.height * (1 - score / 100);
    svg.append(
      analysisSvgElement('line', {x1: plot.x, x2: plot.x + plot.width, y1: y, y2: y, class: 'analysis-chart-grid'}),
      analysisSvgElement('text', {x: plot.x - 9, y: y + 4, 'text-anchor': 'end', class: 'analysis-chart-axis-label'}, String(score))
    );
  });
  const coordinates = points.map(point => ({
    ...point, x: at((point.start + point.end) / 2),
    y: plot.y + plot.height * (1 - point.score / 100)
  }));
  const line = coordinates.map((point, index) => `${index ? 'L' : 'M'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ');
  const area = `M ${plot.x} ${plot.y + plot.height} L ${coordinates.map(point => `${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' L ')} L ${plot.x + plot.width} ${plot.y + plot.height} Z`;
  svg.append(
    analysisSvgElement('path', {d: area, class: 'analysis-excitement-area'}),
    analysisSvgElement('path', {d: line, class: 'analysis-excitement-line', 'vector-effect': 'non-scaling-stroke'})
  );
  coordinates.forEach(point => {
    const related = rows.find(row => Number(row.start) <= point.start && point.start < Number(row.end));
    const topic = !stale && related ? (related.topics || []).map(item => item.label).filter(Boolean).join('・') : '';
    const circle = analysisSvgElement('circle', {cx: point.x, cy: point.y, r: 4, class: 'analysis-excitement-point'});
    circle.append(analysisSvgElement('title', {},
      `${formatTime(point.start)}–${formatTime(point.end)} / 盛り上がり ${point.score} / 発話 ${point.speaking.toFixed(1)}秒 / 発話開始 ${point.turns}回`
      + (related ? ` / アウトライン ${related.title}` : '') + (topic ? ` / 話題 ${topic}` : '')));
    svg.append(circle);
  });
  svg.append(
    analysisSvgElement('text', {x: 14, y: 122, transform: 'rotate(-90 14 122)', 'text-anchor': 'middle', class: 'analysis-chart-axis-title'}, '盛り上がり（目安）'),
    analysisSvgElement('text', {x: 35, y: 251, class: 'analysis-chart-axis-title'}, '議題'),
    analysisSvgElement('text', {x: 35, y: 278, class: 'analysis-chart-axis-title'}, '話題')
  );
  rows.forEach(row => {
    const x = at(Number(row.start));
    const width = Math.max(2, at(Math.min(duration, Number(row.end))) - x);
    const labels = [
      {text: row.title_source === 'outline' ? String(row.title || '') : '', y: 236, kind: 'outline'},
      {text: !stale ? (row.topics || []).map(item => item.label).filter(Boolean).join('・')
        || (row.title_source === 'transformer' ? String(row.title || '') : '') : '', y: 263, kind: 'topic'}
    ];
    labels.filter(item => item.text).forEach(item => {
      const group = analysisSvgElement('g');
      group.append(analysisSvgElement('rect', {
        x, y: item.y, width, height: 22, rx: 3, class: `analysis-excitement-band ${item.kind}`
      }));
      if (width >= 30) group.append(analysisSvgElement('text', {
        x: x + 4, y: item.y + 15, class: 'analysis-excitement-band-label'
      }, Array.from(item.text).slice(0, Math.floor((width - 8) / 11)).join('')));
      group.append(analysisSvgElement('title', {}, `${formatTime(row.start)}–${formatTime(row.end)} / ${item.text}`));
      svg.append(group);
    });
  });
  [0, duration / 2, duration].forEach((time, index) => svg.append(analysisSvgElement('text', {
    x: at(time), y: 315, 'text-anchor': index === 0 ? 'start' : index === 2 ? 'end' : 'middle', class: 'analysis-chart-axis-label'
  }, formatTime(time))));
  svg.append(analysisSvgElement('text', {
    x: plot.x + plot.width / 2, y: 338, 'text-anchor': 'middle', class: 'analysis-chart-axis-title'
  }, '経過時間'));
  stage.append(svg);
  module.append(stage);
  const labels = analysisElement('div', 'analysis-excitement-labels');
  if (!rows.length) {
    labels.append(analysisElement('p', 'analysis-no-data', 'アウトライン・話題の時刻付きラベルはまだありません。'));
  } else {
    rows.forEach(row => {
      const entry = analysisElement('div', 'analysis-excitement-label');
      const topic = !stale ? (row.topics || []).map(item => item.label).filter(Boolean).join('・')
        || (row.title_source === 'transformer' ? String(row.title || '') : '話題未解析') : '話題を再分析してください';
      entry.append(
        analysisElement('time', '', `${formatTime(row.start)}–${formatTime(row.end)}`),
        analysisElement('span', '', row.title_source === 'outline' ? `議題: ${row.title}` : '議題: アウトライン未設定'),
        analysisElement('span', '', `話題: ${topic}`)
      );
      labels.append(entry);
    });
  }
  module.append(labels);
  if (stale) module.append(analysisElement('p', 'analysis-chart-note', '本文などが更新されたため、古いTransformer話題は表示していません。テーマ分析を再実行するとラベルを更新できます。'));
  return module;
}

function analysisPValueText(value) {
  if (value === null || value === undefined || value === '') return '未計算';
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0 || number > 1) return '未計算';
  if (number === 0) return 'p < 1e-308（数値精度限界）';
  if (number < .001) return `p = ${number.toExponential(2)}`;
  return `p = ${number.toFixed(3)}`;
}

function buildAnalysisCooccurrenceChart(rawEdges) {
  const namespace = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(namespace, 'svg');
  svg.classList.add('analysis-cooccurrence-chart');
  svg.setAttribute('viewBox', '0 0 720 430');
  svg.setAttribute('role', 'img');
  const title = document.createElementNS(namespace, 'title');
  title.textContent = '発話単位の語の共起ネットワーク';
  const description = document.createElementNS(namespace, 'desc');
  description.textContent = '同じ発話に現れた内容語をJaccard係数の強さで結んだ探索用ネットワークです。';
  svg.append(title, description);
  const edges = (Array.isArray(rawEdges) ? rawEdges : []).slice(0, 35);
  const weights = new Map();
  edges.forEach(edge => {
    weights.set(edge.term_a, (weights.get(edge.term_a) || 0) + (Number(edge.jaccard) || 0));
    weights.set(edge.term_b, (weights.get(edge.term_b) || 0) + (Number(edge.jaccard) || 0));
  });
  const nodes = [...weights.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 18)
    .map(([term, weight], index, values) => {
      const angle = -Math.PI / 2 + 2 * Math.PI * index / Math.max(1, values.length);
      const ring = 145 + 28 * (index % 2);
      return {
        term, weight,
        x: 360 + Math.cos(angle) * ring,
        y: 215 + Math.sin(angle) * ring
      };
    });
  const nodeMap = new Map(nodes.map(node => [node.term, node]));
  const visibleEdges = edges.filter(edge => nodeMap.has(edge.term_a) && nodeMap.has(edge.term_b));
  const maxJaccard = Math.max(.001, ...visibleEdges.map(edge => Number(edge.jaccard) || 0));
  visibleEdges.forEach(edge => {
    const source = nodeMap.get(edge.term_a);
    const target = nodeMap.get(edge.term_b);
    const line = document.createElementNS(namespace, 'line');
    line.setAttribute('x1', String(source.x));
    line.setAttribute('y1', String(source.y));
    line.setAttribute('x2', String(target.x));
    line.setAttribute('y2', String(target.y));
    line.setAttribute('class', 'analysis-network-edge');
    line.setAttribute('stroke-width', String(1 + 7 * (Number(edge.jaccard) || 0) / maxJaccard));
    const tooltip = document.createElementNS(namespace, 'title');
    tooltip.textContent = `${edge.term_a} × ${edge.term_b}: 共起 ${edge.cooccurrence_count}発話 / Jaccard ${Number(edge.jaccard || 0).toFixed(3)}`;
    line.append(tooltip);
    svg.append(line);
  });
  const maxWeight = Math.max(.001, ...nodes.map(node => node.weight));
  nodes.forEach(node => {
    const group = document.createElementNS(namespace, 'g');
    group.setAttribute('class', 'analysis-network-node');
    const radius = 12 + 13 * node.weight / maxWeight;
    const circle = document.createElementNS(namespace, 'circle');
    circle.setAttribute('cx', String(node.x));
    circle.setAttribute('cy', String(node.y));
    circle.setAttribute('r', String(radius));
    const label = document.createElementNS(namespace, 'text');
    label.setAttribute('x', String(node.x));
    label.setAttribute('y', String(node.y + radius + 15));
    label.setAttribute('text-anchor', 'middle');
    label.textContent = node.term;
    group.append(circle, label);
    svg.append(group);
  });
  return svg;
}

function buildAnalysisTermTreeChart(rawEdges) {
  const edges = (Array.isArray(rawEdges) ? rawEdges : []).slice(0, 60);
  const weights = new Map();
  edges.forEach(edge => {
    const weight = Math.max(0, Number(edge.jaccard) || 0);
    weights.set(String(edge.term_a), (weights.get(String(edge.term_a)) || 0) + weight);
    weights.set(String(edge.term_b), (weights.get(String(edge.term_b)) || 0) + weight);
  });
  const nodeIds = [...weights.entries()].sort((a, b) => b[1] - a[1]).slice(0, 16).map(item => item[0]);
  const nodeSet = new Set(nodeIds);
  const candidates = edges
    .filter(edge => nodeSet.has(String(edge.term_a)) && nodeSet.has(String(edge.term_b)))
    .sort((a, b) => Number(b.jaccard || 0) - Number(a.jaccard || 0));
  const parent = new Map(nodeIds.map(id => [id, id]));
  const find = id => {
    let value = id;
    while (parent.get(value) !== value) value = parent.get(value);
    let cursor = id;
    while (parent.get(cursor) !== cursor) {
      const next = parent.get(cursor);
      parent.set(cursor, value);
      cursor = next;
    }
    return value;
  };
  const treeEdges = [];
  candidates.forEach(edge => {
    const source = String(edge.term_a);
    const target = String(edge.term_b);
    const sourceRoot = find(source);
    const targetRoot = find(target);
    if (sourceRoot === targetRoot) return;
    parent.set(targetRoot, sourceRoot);
    treeEdges.push({...edge, source, target});
  });
  const adjacency = new Map(nodeIds.map(id => [id, []]));
  treeEdges.forEach(edge => {
    adjacency.get(edge.source).push({id: edge.target, edge});
    adjacency.get(edge.target).push({id: edge.source, edge});
  });
  const components = [];
  const componentSeen = new Set();
  nodeIds.forEach(id => {
    if (componentSeen.has(id)) return;
    const values = [];
    const queue = [id];
    componentSeen.add(id);
    while (queue.length) {
      const current = queue.shift();
      values.push(current);
      (adjacency.get(current) || []).forEach(item => {
        if (!componentSeen.has(item.id)) {
          componentSeen.add(item.id);
          queue.push(item.id);
        }
      });
    }
    components.push(values);
  });
  const positions = new Map();
  const directedEdges = [];
  let leafCursor = 0;
  let maxDepth = 0;
  const place = (id, from, depth) => {
    maxDepth = Math.max(maxDepth, depth);
    const children = (adjacency.get(id) || []).filter(item => item.id !== from);
    const childPositions = children.map(item => {
      directedEdges.push({source: id, target: item.id, edge: item.edge});
      return place(item.id, id, depth + 1);
    });
    const y = childPositions.length
      ? childPositions.reduce((sum, value) => sum + value, 0) / childPositions.length
      : 54 + leafCursor++ * 66;
    positions.set(id, {x: 80 + depth * 178, y, depth});
    return y;
  };
  components
    .sort((a, b) => b.length - a.length)
    .forEach(component => {
      const root = [...component].sort((a, b) => (weights.get(b) || 0) - (weights.get(a) || 0))[0];
      place(root, '', 0);
      leafCursor += .55;
    });
  const width = Math.max(760, 185 + maxDepth * 178);
  const height = Math.max(310, 95 + leafCursor * 66);
  const svg = analysisSvgElement('svg', {
    class: 'analysis-term-tree', viewBox: `0 0 ${width} ${height}`, role: 'img', tabindex: '0'
  });
  svg.append(
    analysisSvgElement('title', {}, '共起語の関連ツリー'),
    analysisSvgElement('desc', {}, 'Jaccard係数が強い辺を優先して循環を除いた最大重み全域木です。語の因果関係や階層を示すものではありません。')
  );
  directedEdges.forEach(item => {
    const source = positions.get(item.source);
    const target = positions.get(item.target);
    const middle = (source.x + target.x) / 2;
    const path = analysisSvgElement('path', {
      d: `M ${source.x + 62} ${source.y} C ${middle} ${source.y}, ${middle} ${target.y}, ${target.x - 62} ${target.y}`,
      class: 'analysis-tree-edge', 'vector-effect': 'non-scaling-stroke'
    });
    path.append(analysisSvgElement('title', {}, `${item.source} × ${item.target} / Jaccard ${Number(item.edge.jaccard || 0).toFixed(3)}`));
    svg.append(path);
  });
  positions.forEach((position, id) => {
    const group = analysisSvgElement('g', {class: `analysis-tree-node${position.depth === 0 ? ' root' : ''}`});
    const label = id.length > 11 ? `${id.slice(0, 10)}…` : id;
    group.append(
      analysisSvgElement('rect', {x: position.x - 62, y: position.y - 22, width: 124, height: 44, rx: 11}),
      analysisSvgElement('text', {x: position.x, y: position.y + 4, 'text-anchor': 'middle'}, label),
      analysisSvgElement('title', {}, `${id} / 接続強度合計 ${(weights.get(id) || 0).toFixed(3)}`)
    );
    svg.append(group);
  });
  return svg;
}

function buildAnalysisCooccurrenceExplorer(edges) {
  const module = analysisElement('div', 'analysis-chart-module');
  const toolbar = analysisElement('div', 'analysis-chart-toolbar');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', '語の結びつきを探索する'),
    analysisElement('span', '', '全体像はネットワーク、経路を追うときは関連ツリーが見やすくなります。')
  );
  const switcher = analysisElement('div', 'analysis-chart-switch');
  switcher.setAttribute('role', 'group');
  switcher.setAttribute('aria-label', '共起グラフの表示');
  const networkButton = analysisElement('button', 'active', 'ネットワーク');
  const treeButton = analysisElement('button', '', '関連ツリー');
  [networkButton, treeButton].forEach(button => button.type = 'button');
  switcher.append(networkButton, treeButton);
  toolbar.append(explanation, switcher);
  const stage = analysisElement('div', 'analysis-chart-stage analysis-network-stage');
  const note = analysisElement('p', 'analysis-chart-note');
  module.append(toolbar, stage, note);
  const render = mode => {
    const treeMode = mode === 'tree';
    networkButton.classList.toggle('active', !treeMode);
    treeButton.classList.toggle('active', treeMode);
    networkButton.setAttribute('aria-pressed', String(!treeMode));
    treeButton.setAttribute('aria-pressed', String(treeMode));
    stage.replaceChildren(treeMode ? buildAnalysisTermTreeChart(edges) : buildAnalysisCooccurrenceChart(edges));
    note.textContent = treeMode
      ? 'Jaccard係数が強い結びつきを優先し、循環を除いて表示しています。左右の位置は概念上の上下関係を意味しません。'
      : '円が大きい語ほど、表示中の他の語とのJaccard係数合計が大きいことを示します。';
  };
  networkButton.addEventListener('click', () => render('network'));
  treeButton.addEventListener('click', () => render('tree'));
  render('network');
  return module;
}

function groupAnalysisDependencies(dependencies) {
  const groups = new Map();
  (Array.isArray(dependencies) ? dependencies : []).forEach(item => {
    const key = `${item.segment_id || '—'}::${item.sentence_id || 1}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });
  return [...groups.entries()].map(([key, rows]) => {
    rows.sort((a, b) => Number(a.token_id || 0) - Number(b.token_id || 0));
    return {key, rows, label: `発話 ${rows[0].segment_id || '—'}・文 ${rows[0].sentence_id || 1}: ${rows.map(item => item.surface || '').join('').slice(0, 42)}`};
  });
}

function buildAnalysisDependencyTree(rows) {
  const visibleRows = (Array.isArray(rows) ? rows : []).slice(0, 28);
  const nodes = new Map(visibleRows.map(item => [Number(item.token_id), {...item}]));
  const children = new Map([...nodes.keys()].map(id => [id, []]));
  const roots = [];
  nodes.forEach((item, id) => {
    const head = Number(item.head_token_id || 0);
    if (!head || head === id || !nodes.has(head)) roots.push(id);
    else children.get(head).push(id);
  });
  children.forEach(values => values.sort((a, b) => a - b));
  const positions = new Map();
  const renderedEdges = [];
  const visited = new Set();
  let leafCursor = 0;
  let maxDepth = 0;
  const place = (id, depth, trail = new Set()) => {
    if (trail.has(id)) return 54 + leafCursor++ * 112;
    if (visited.has(id)) return (positions.get(id) || {}).x || 54 + leafCursor++ * 112;
    visited.add(id);
    maxDepth = Math.max(maxDepth, depth);
    const nextTrail = new Set(trail).add(id);
    const childIds = (children.get(id) || []).filter(child => !nextTrail.has(child));
    const childPositions = childIds.map(child => {
      renderedEdges.push({source: id, target: child});
      return place(child, depth + 1, nextTrail);
    });
    const x = childPositions.length
      ? childPositions.reduce((sum, value) => sum + value, 0) / childPositions.length
      : 64 + leafCursor++ * 112;
    positions.set(id, {x, depth});
    return x;
  };
  const orderedRoots = roots.length ? roots : [...nodes.keys()].slice(0, 1);
  orderedRoots.forEach(root => place(root, 0));
  nodes.forEach((item, id) => {
    if (!visited.has(id)) place(id, 0);
  });
  const width = Math.max(760, 128 + Math.max(1, leafCursor - 1) * 112);
  const height = Math.max(270, 126 + maxDepth * 94);
  const svg = analysisSvgElement('svg', {
    class: 'analysis-dependency-tree', viewBox: `0 0 ${width} ${height}`, role: 'img', tabindex: '0'
  });
  svg.append(
    analysisSvgElement('title', {}, '文の係り受けツリー'),
    analysisSvgElement('desc', {}, 'ROOTを上に置き、係り先から係る語へ線を伸ばしています。各ノードには表層形、依存関係、品詞を表示します。')
  );
  renderedEdges.forEach(edge => {
    const source = positions.get(edge.source);
    const target = positions.get(edge.target);
    if (!source || !target) return;
    const sourceY = 46 + source.depth * 94;
    const targetY = 46 + target.depth * 94;
    const middleY = (sourceY + targetY) / 2;
    svg.append(analysisSvgElement('path', {
      d: `M ${source.x} ${sourceY + 27} C ${source.x} ${middleY}, ${target.x} ${middleY}, ${target.x} ${targetY - 27}`,
      class: 'analysis-dependency-edge', 'vector-effect': 'non-scaling-stroke'
    }));
  });
  positions.forEach((position, id) => {
    const item = nodes.get(id) || {};
    const y = 46 + position.depth * 94;
    const isRoot = !Number(item.head_token_id || 0) || Number(item.head_token_id) === id;
    const group = analysisSvgElement('g', {class: `analysis-dependency-node${isRoot ? ' root' : ''}`});
    const surface = String(item.surface || '—');
    group.append(
      analysisSvgElement('rect', {x: position.x - 48, y: y - 27, width: 96, height: 54, rx: 11}),
      analysisSvgElement('text', {x: position.x, y: y - 3, 'text-anchor': 'middle', class: 'surface'}, surface.length > 9 ? `${surface.slice(0, 8)}…` : surface),
      analysisSvgElement('text', {x: position.x, y: y + 15, 'text-anchor': 'middle', class: 'meta'}, `${isRoot ? 'ROOT' : item.dependency || 'dep'} · ${item.upos || 'X'}`),
      analysisSvgElement('title', {}, `${surface} / 原形 ${item.lemma || '—'} / 係り先 ${item.head_surface || 'ROOT'}`)
    );
    svg.append(group);
  });
  if (rows.length > visibleRows.length) {
    svg.append(analysisSvgElement('text', {x: width - 16, y: height - 14, 'text-anchor': 'end', class: 'analysis-tree-truncation'}, `先頭${visibleRows.length}語を表示`));
  }
  return svg;
}

function buildAnalysisDependencyExplorer(dependencies, compact) {
  const groups = groupAnalysisDependencies(dependencies).slice(0, compact ? 12 : 30);
  const module = analysisElement('div', 'analysis-dependency-explorer');
  const toolbar = analysisElement('div', 'analysis-tree-toolbar');
  const field = analysisElement('label');
  field.append(analysisElement('span', '', '表示する文'));
  const select = document.createElement('select');
  groups.forEach((group, index) => select.add(new Option(group.label, String(index))));
  field.append(select);
  const controls = analysisElement('div', 'analysis-tree-pager');
  const previous = analysisElement('button', '', '← 前の文');
  const next = analysisElement('button', '', '次の文 →');
  [previous, next].forEach(button => button.type = 'button');
  controls.append(previous, next);
  toolbar.append(field, controls);
  const stage = analysisElement('div', 'analysis-tree-stage');
  const status = analysisElement('p', 'analysis-chart-note');
  module.append(toolbar, stage, status);
  const render = rawIndex => {
    const index = Math.min(Math.max(0, Number(rawIndex) || 0), Math.max(0, groups.length - 1));
    select.value = String(index);
    const group = groups[index];
    stage.replaceChildren(buildAnalysisDependencyTree(group.rows));
    previous.disabled = index === 0;
    next.disabled = index === groups.length - 1;
    status.textContent = `${index + 1} / ${groups.length}文・${group.rows.length}語。線は係り先から係る語へ向かう依存構造です。`;
  };
  select.addEventListener('change', () => render(select.value));
  previous.addEventListener('click', () => render(Number(select.value) - 1));
  next.addEventListener('click', () => render(Number(select.value) + 1));
  render(0);
  return module;
}

function buildAnalysisCorrelationTable(rows) {
  const computed = rows.filter(item => item.status === 'computed' && Number.isFinite(Number(item.coefficient)));
  const variables = [];
  const labels = new Map();
  computed.forEach(item => {
    [[item.variable_a, item.label_a], [item.variable_b, item.label_b]].forEach(([id, label]) => {
      if (!labels.has(id)) variables.push(id);
      labels.set(id, label || id);
    });
  });
  const values = new Map();
  computed.forEach(item => {
    values.set(`${item.variable_a}::${item.variable_b}`, item);
    values.set(`${item.variable_b}::${item.variable_a}`, item);
  });
  const wrap = analysisElement('div', 'analysis-correlation-wrap');
  const table = analysisElement('table', 'analysis-correlation-table');
  const head = analysisElement('thead');
  const headRow = analysisElement('tr');
  headRow.append(analysisElement('th', '', '変数'));
  variables.forEach(id => {
    const th = analysisElement('th', '', labels.get(id));
    th.title = labels.get(id);
    headRow.append(th);
  });
  head.append(headRow);
  const body = analysisElement('tbody');
  variables.forEach(rowId => {
    const row = analysisElement('tr');
    row.append(analysisElement('th', '', labels.get(rowId)));
    variables.forEach(columnId => {
      const diagonal = rowId === columnId;
      const item = values.get(`${rowId}::${columnId}`);
      const coefficient = diagonal ? 1 : item ? Number(item.coefficient) : NaN;
      const cell = analysisElement('td', 'analysis-correlation-cell', Number.isFinite(coefficient) ? coefficient.toFixed(2) : '—');
      if (Number.isFinite(coefficient)) {
        const strength = Math.abs(coefficient);
        cell.style.setProperty('--correlation-strength', strength.toFixed(3));
        cell.classList.add(coefficient < 0 ? 'negative' : 'positive');
        cell.title = diagonal
          ? `${labels.get(rowId)}（同一変数）`
          : `${labels.get(rowId)} × ${labels.get(columnId)}: r = ${coefficient.toFixed(3)}, ${analysisPValueText(item.p_value)}, N = ${item.n || 0} / 欠測 ${item.missing ?? '—'} / 発話単位 / p値未補正`;
      }
      row.append(cell);
    });
    body.append(row);
  });
  table.append(head, body);
  wrap.append(table);
  return wrap;
}

function buildAnalysisCorrelationExplorer(correlations) {
  const methods = [...new Set((Array.isArray(correlations) ? correlations : []).filter(item => item.status === 'computed').map(item => item.method))];
  const module = analysisElement('div', 'analysis-chart-module');
  const toolbar = analysisElement('div', 'analysis-chart-toolbar');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', '変数間の相関を俯瞰する'),
    analysisElement('span', '', '色の濃さが関連の強さ、緑が正、紫が負の相関です。')
  );
  const switcher = analysisElement('div', 'analysis-chart-switch');
  switcher.setAttribute('role', 'group');
  switcher.setAttribute('aria-label', '相関係数の種類');
  const buttons = new Map();
  methods.forEach(method => {
    const button = analysisElement('button', '', method);
    button.type = 'button';
    buttons.set(method, button);
    switcher.append(button);
  });
  toolbar.append(explanation, switcher);
  const stage = analysisElement('div', 'analysis-correlation-stage');
  const legend = analysisElement('div', 'analysis-correlation-legend');
  legend.append(
    analysisElement('span', '', '−1 強い負'),
    analysisElement('i'),
    analysisElement('span', '', '+1 強い正')
  );
  const note = analysisElement('p', 'analysis-chart-note', '相関は因果関係を示しません。発話単位の探索値として原文・散布図・標本数・欠測も確認してください。p値は多重検定未補正で、同一話者内の発話の独立性は未検証です。');
  module.append(toolbar, stage, legend, note);
  const render = method => {
    buttons.forEach((button, key) => {
      const active = key === method;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    stage.replaceChildren(buildAnalysisCorrelationTable(correlations.filter(item => item.method === method)));
  };
  buttons.forEach((button, method) => button.addEventListener('click', () => render(method)));
  render(methods.includes('Pearson') ? 'Pearson' : methods[0]);
  return module;
}

function buildAnalysisDescriptiveChart(rows) {
  const chart = analysisElement('div', 'analysis-distribution-chart');
  chart.setAttribute('aria-label', '記述統計の分布');
  (Array.isArray(rows) ? rows : []).forEach(item => {
    const minimum = Number(item.minimum);
    const maximum = Number(item.maximum);
    if (!Number.isFinite(minimum) || !Number.isFinite(maximum)) return;
    const span = Math.max(maximum - minimum, Number.EPSILON);
    const position = value => {
      const number = Number(value);
      return Number.isFinite(number) ? boundedAnalysisPercent(100 * (number - minimum) / span) : 0;
    };
    const q1 = position(item.q1);
    const q3 = position(item.q3);
    const median = position(item.median);
    const mean = position(item.mean);
    const row = analysisElement('article', 'analysis-distribution-row');
    const heading = analysisElement('header');
    heading.append(
      analysisElement('strong', '', item.label || item.variable),
      analysisElement('span', '', `N=${item.n || 0}`)
    );
    const plot = analysisElement('div', 'analysis-distribution-plot');
    plot.setAttribute('role', 'img');
    plot.setAttribute('aria-label', `${item.label || item.variable}: 最小 ${analysisNumberText(minimum, 2)}、第1四分位 ${analysisNumberText(item.q1, 2)}、中央値 ${analysisNumberText(item.median, 2)}、平均 ${analysisNumberText(item.mean, 2)}、第3四分位 ${analysisNumberText(item.q3, 2)}、最大 ${analysisNumberText(maximum, 2)}`);
    const range = analysisElement('i', 'analysis-distribution-range');
    const box = analysisElement('i', 'analysis-distribution-box');
    box.style.left = `${Math.min(q1, q3)}%`;
    box.style.width = `${Math.max(1, Math.abs(q3 - q1))}%`;
    const medianMark = analysisElement('i', 'analysis-distribution-median');
    medianMark.style.left = `${median}%`;
    const meanMark = analysisElement('i', 'analysis-distribution-mean');
    meanMark.style.left = `${mean}%`;
    meanMark.title = `平均 ${analysisNumberText(item.mean, 2)}`;
    plot.append(range, box, medianMark, meanMark);
    const scale = analysisElement('div', 'analysis-distribution-scale');
    scale.append(
      analysisElement('span', '', analysisNumberText(minimum, 2)),
      analysisElement('span', '', `中央値 ${analysisNumberText(item.median, 2)}`),
      analysisElement('span', '', analysisNumberText(maximum, 2))
    );
    row.append(heading, plot, scale);
    chart.append(row);
  });
  const legend = analysisElement('div', 'analysis-distribution-legend');
  legend.append(
    analysisElement('span', 'box', '第1〜第3四分位'),
    analysisElement('span', 'median', '中央値'),
    analysisElement('span', 'mean', '平均')
  );
  chart.append(legend);
  return chart;
}

function buildAnalysisFrequencyExplorer(frequencies, compact) {
  const rows = Array.isArray(frequencies) ? frequencies : [];
  const variables = [];
  rows.forEach(item => {
    const key = String(item.variable || 'unknown');
    if (!variables.some(entry => entry.key === key)) {
      variables.push({key, label: item.label || key});
    }
  });
  const module = analysisElement('div', 'analysis-chart-module');
  const toolbar = analysisElement('div', 'analysis-chart-toolbar');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', 'カテゴリ別の構成割合'),
    analysisElement('span', '', '項目を切り替えて、件数と全体に占める割合を確認できます。')
  );
  const selectLabel = analysisElement('label', 'analysis-chart-select');
  selectLabel.append(analysisElement('span', '', '表示項目'));
  const select = analysisElement('select');
  variables.forEach(item => select.add(new Option(item.label, item.key)));
  selectLabel.append(select);
  toolbar.append(explanation, selectLabel);
  const stage = analysisElement('div', 'analysis-frequency-stage');
  module.append(toolbar, stage);
  const render = variable => {
    stage.replaceChildren();
    rows.filter(item => String(item.variable || 'unknown') === variable)
      .sort((a, b) => Number(b.count || 0) - Number(a.count || 0))
      .slice(0, compact ? 8 : 14)
      .forEach(item => appendAnalysisBar(
        stage,
        item.value || '未設定',
        Number(item.percent) || 0,
        `${item.count || 0}件 / ${analysisNumberText(item.percent, 1, '%')}`,
        '#438F70'
      ));
  };
  select.addEventListener('change', () => render(select.value));
  if (variables.length) render(variables[0].key);
  return module;
}

function buildAnalysisEffectChart(tests, compact) {
  const rows = (Array.isArray(tests) ? tests : [])
    .filter(item => item.status === 'computed' && Number.isFinite(Number(item.effect_size)))
    .slice(0, compact ? 10 : 24);
  const chart = analysisElement('div', 'analysis-effect-chart');
  const axis = analysisElement('div', 'analysis-effect-axis');
  axis.append(
    analysisElement('span', '', '0'),
    analysisElement('span', '', '効果量 0.5'),
    analysisElement('span', '', '1.0')
  );
  chart.append(axis);
  rows.forEach(item => {
    const effect = Math.abs(Number(item.effect_size));
    const row = analysisElement('article', 'analysis-effect-row');
    const heading = analysisElement('header');
    heading.append(
      analysisElement('strong', '', item.outcome_label || item.outcome || item.test),
      analysisElement('span', '', `${item.effect_name || 'effect'}=${analysisNumberText(effect, 3)} / ${analysisPValueText(item.p_value)}`)
    );
    const track = analysisElement('div', 'analysis-effect-track');
    track.setAttribute('role', 'img');
    track.setAttribute('aria-label', `${item.outcome_label || item.outcome}: 効果量 ${analysisNumberText(effect, 3)}、p値 ${analysisPValueText(item.p_value)}`);
    const fill = analysisElement('i');
    fill.style.width = `${boundedAnalysisPercent(effect * 100)}%`;
    track.append(fill);
    row.append(heading, track);
    chart.append(row);
  });
  return chart;
}

function buildAnalysisCrosstabExplorer(crosstabs, compact) {
  const rows = Array.isArray(crosstabs) ? crosstabs : [];
  const tables = [];
  rows.forEach(item => {
    const key = String(item.table_id || item.table_label || 'table');
    if (!tables.some(entry => entry.key === key)) {
      tables.push({key, label: item.table_label || key});
    }
  });
  const palette = ['#1C6B50', '#74A57F', '#E2A45E', '#6B8FD4', '#9B70B6', '#D97872'];
  const module = analysisElement('div', 'analysis-chart-module');
  const toolbar = analysisElement('div', 'analysis-chart-toolbar');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', '項目の組み合わせを割合で比較'),
    analysisElement('span', '', '各行を100%として、回答・分類の構成差を色分けします。')
  );
  const selectLabel = analysisElement('label', 'analysis-chart-select');
  selectLabel.append(analysisElement('span', '', 'クロス集計'));
  const select = analysisElement('select');
  tables.forEach(item => select.add(new Option(item.label, item.key)));
  selectLabel.append(select);
  toolbar.append(explanation, selectLabel);
  const stage = analysisElement('div', 'analysis-crosstab-stage');
  const legend = analysisElement('div', 'analysis-chart-legend');
  module.append(toolbar, stage, legend, analysisElement('p', 'analysis-chart-note', '色の幅は行内割合です。件数が少ない行は割合が大きく変動するため、詳細表の度数も確認してください。'));
  const render = tableId => {
    stage.replaceChildren();
    legend.replaceChildren();
    const tableRows = rows.filter(item => String(item.table_id || item.table_label || 'table') === tableId);
    const columnValues = [...new Set(tableRows.map(item => String(item.column_value || '未設定')))];
    const rowValues = [...new Set(tableRows.map(item => String(item.row_value || '未設定')))];
    columnValues.forEach((value, index) => {
      const entry = analysisElement('span');
      const marker = analysisElement('i');
      marker.style.backgroundColor = palette[index % palette.length];
      entry.append(marker, document.createTextNode(value));
      legend.append(entry);
    });
    rowValues.slice(0, compact ? 8 : 14).forEach(value => {
      const item = analysisElement('article', 'analysis-crosstab-row');
      const values = columnValues.map(column => tableRows.find(row => String(row.row_value || '未設定') === value && String(row.column_value || '未設定') === column));
      const total = values.reduce((sum, row) => sum + Number(row?.count || 0), 0);
      item.append(analysisElement('strong', '', `${value}（${total}件）`));
      const bar = analysisElement('div', 'analysis-stacked-bar');
      bar.setAttribute('role', 'img');
      bar.setAttribute('aria-label', `${value}: ${values.map((row, index) => `${columnValues[index]} ${row?.count || 0}件`).join('、')}`);
      values.forEach((row, index) => {
        const count = Number(row?.count || 0);
        const percent = total ? 100 * count / total : 0;
        const part = analysisElement('i');
        part.style.width = `${percent}%`;
        part.style.backgroundColor = palette[index % palette.length];
        part.title = `${columnValues[index]} ${count}件（${percent.toFixed(1)}%）`;
        bar.append(part);
      });
      item.append(bar);
      stage.append(item);
    });
  };
  select.addEventListener('change', () => render(select.value));
  if (tables.length) render(tables[0].key);
  return module;
}

function analysisSectionHeading(anchor, eyebrow, titleText, description) {
  const section = analysisElement('section', 'analysis-section-heading wide');
  section.dataset.analysisAnchor = anchor;
  section.append(
    analysisElement('span', '', eyebrow),
    analysisElement('h2', '', titleText),
    analysisElement('p', '', description)
  );
  return section;
}

function applyAnalysisPage(content, requested) {
  const pages = [...content.querySelectorAll('[data-analysis-page]')];
  const selected = pages.some(page => page.dataset.analysisPage === requested) ? requested : 'overview';
  pages.forEach(page => { page.hidden = page.dataset.analysisPage !== selected; });
  content.querySelectorAll('[data-analysis-jump]').forEach(button => {
    const active = button.dataset.analysisJump === selected;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
    if (active) button.setAttribute('aria-current', 'true');
    else button.removeAttribute('aria-current');
  });
}

function selectAnalysisPage(page) {
  analysisState.automaticPage = page;
  [analysisDesktopContent, analysisMobileContent].filter(Boolean)
    .forEach(content => applyAnalysisPage(content, page));
}

function buildAnalysisNavigation() {
  const nav = analysisElement('nav', 'analysis-insight-nav');
  nav.setAttribute('aria-label', '分析ダッシュボード内の移動');
  [
    ['overview', '概要'],
    ['content', '内容・文脈検索'],
    ['conversation', '会話推移'],
    ['language', '言語構造'],
    ['statistics', '統計'],
    ['exports', '出力・検証']
  ].forEach(([anchor, label], index) => {
    const button = analysisElement('button', index === 0 ? 'active' : '', label);
    button.type = 'button';
    button.dataset.analysisJump = anchor;
    if (index === 0) button.setAttribute('aria-current', 'true');
    nav.append(button);
  });
  return nav;
}

function syncAnalysisNavigationToScroll() {
  analysisNavigationFrame = 0;
  if (!analysisCard || analysisCard.hidden || analysisState.mode !== 'automatic') return;
  const mobile = window.matchMedia('(max-width: 959px)').matches;
  const content = mobile ? analysisMobileContent : analysisDesktopContent;
  if (!content) return;
  if (content.querySelector('[data-analysis-page]')) return;
  const anchors = [...content.querySelectorAll('[data-analysis-anchor]')];
  if (!anchors.length) return;
  const threshold = mobile ? 235 : 105;
  let activeAnchor = anchors[0].dataset.analysisAnchor;
  anchors.forEach(anchor => {
    if (anchor.getBoundingClientRect().top <= threshold) activeAnchor = anchor.dataset.analysisAnchor;
  });
  content.querySelectorAll('[data-analysis-jump]').forEach(button => {
    const active = button.dataset.analysisJump === activeAnchor;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'true');
    else button.removeAttribute('aria-current');
  });
}

function scheduleAnalysisNavigationSync() {
  if (analysisNavigationFrame) return;
  analysisNavigationFrame = window.requestAnimationFrame(syncAnalysisNavigationToScroll);
}
