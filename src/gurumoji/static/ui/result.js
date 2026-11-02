/* 公開版の画面処理: result。共有状態はapp.jsで管理する。 */
function meetingPriorityLabel(priority) {
  return ({high: '高', medium: '中', low: '低', unspecified: '未設定'})[priority] || '未設定';
}

function meetingPriorityClass(priority) {
  return ['high', 'medium', 'low'].includes(priority) ? priority : 'unspecified';
}

function appendMeetingMetric(container, label, count, total, className = '') {
  const row = document.createElement('div');
  row.className = `meeting-metric-row${className ? ` ${className}` : ''}`;
  const heading = document.createElement('span');
  heading.textContent = label;
  const bar = document.createElement('i');
  bar.style.width = `${total ? Math.max(4, Math.round((Number(count) || 0) / total * 100)) : 0}%`;
  const value = document.createElement('b');
  value.textContent = String(Number(count) || 0);
  row.append(heading, bar, value);
  container.append(row);
}


function renderMeetingMinutes(minutes, jobId) {
  if (!meetingMinutesView) return;
  const data = minutes && typeof minutes === 'object' ? minutes : null;
  const tasks = data && Array.isArray(data.tasks) ? data.tasks : [];
  const decisions = data && Array.isArray(data.decisions) ? data.decisions : [];
  const analysis = data && typeof data.analysis === 'object' && data.analysis ? data.analysis : {};
  const hasMeetingData = data && (tasks.length || decisions.length || Array.isArray(data.summary));
  meetingMinutesView.hidden = !hasMeetingData;
  if (!hasMeetingData) return;

  const prefix = `/api/library/${encodeURIComponent(jobId)}`;
  const exports = [
    ['#meeting-minutes-download', `${prefix}/meeting-minutes.md`],
    ['#meeting-tasks-download', `${prefix}/meeting-tasks.csv`],
    ['#meeting-json-download', `${prefix}/meeting.json`],
  ];
  exports.forEach(([selector, href]) => {
    const link = document.querySelector(selector);
    if (link) link.href = href;
  });

  const method = document.querySelector('#meeting-minutes-method');
  if (method) {
    method.textContent = data.method === 'rule_based_candidate_extraction'
      ? '抽出方法：ルールベースの候補抽出。元発話の時刻を確認してから取り込んでください。'
      : `抽出方法：${data.method || '未記録'}`;
  }
  const summary = document.querySelector('#meeting-minutes-summary');
  summary.replaceChildren();
  (data.summary || []).forEach(text => {
    const item = document.createElement('p');
    item.textContent = text;
    summary.append(item);
  });

  const priorityChart = document.querySelector('#meeting-priority-chart');
  priorityChart.replaceChildren();
  const priorityCounts = analysis.priority_counts || {};
  const priorityTotal = tasks.length || 1;
  [['high', '高'], ['medium', '中'], ['low', '低'], ['unspecified', '未設定']].forEach(([key, label]) => {
    appendMeetingMetric(priorityChart, label, priorityCounts[key], priorityTotal, key);
  });

  const dueSummary = document.querySelector('#meeting-due-summary');
  dueSummary.replaceChildren();
  const dated = tasks.filter(task => task.due_date).length;
  const relative = tasks.filter(task => !task.due_date && task.due_text).length;
  const missing = Math.max(0, tasks.length - dated - relative);
  appendMeetingMetric(dueSummary, '日付あり', dated, tasks.length || 1, 'dated');
  appendMeetingMetric(dueSummary, '期限表現あり', relative, tasks.length || 1, 'relative');
  appendMeetingMetric(dueSummary, '期限未設定', missing, tasks.length || 1, 'missing');

  const speakerChart = document.querySelector('#meeting-speaker-chart');
  speakerChart.replaceChildren();
  const activity = Array.isArray(analysis.speaker_activity) ? analysis.speaker_activity : [];
  const maxSeconds = Math.max(1, ...activity.map(item => Number(item.seconds) || 0));
  activity.slice(0, 6).forEach(item => {
    const row = document.createElement('div');
    row.className = 'meeting-speaker-row';
    const label = document.createElement('span');
    label.textContent = item.speaker || '話者不明';
    const bar = document.createElement('i');
    bar.style.width = `${Math.max(4, Math.round((Number(item.seconds) || 0) / maxSeconds * 100))}%`;
    const value = document.createElement('small');
    value.textContent = `${item.turns || 0}回 / ${formatTime(item.seconds || 0)}`;
    row.append(label, bar, value);
    speakerChart.append(row);
  });
  if (!activity.length) speakerChart.textContent = '発話量データはありません。';

  const taskList = document.querySelector('#meeting-task-list');
  taskList.replaceChildren();
  if (!tasks.length) {
    const empty = document.createElement('p');
    empty.className = 'meeting-empty';
    empty.textContent = 'タスク候補は検出されませんでした。録音中の依頼・担当・期限の表現を確認してください。';
    taskList.append(empty);
  }
  tasks.forEach(task => {
    const card = document.createElement('article');
    card.className = 'meeting-task-card';
    const top = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = task.title || '要確認のタスク候補';
    const priority = document.createElement('span');
    priority.className = `meeting-priority ${meetingPriorityClass(task.priority)}`;
    priority.textContent = `優先度 ${meetingPriorityLabel(task.priority)}`;
    top.append(title, priority);
    const meta = document.createElement('p');
    const due = task.due_date || task.due_text || '未設定';
    meta.textContent = `担当候補: ${task.owner || '未特定'} / 期限: ${due} / 根拠: ${formatTime(task.evidence_start || 0)}`;
    const source = document.createElement('small');
    source.textContent = task.source_text || '';
    card.append(top, meta, source);
    taskList.append(card);
  });

  const decisionList = document.querySelector('#meeting-decision-list');
  decisionList.replaceChildren();
  if (!decisions.length) {
    const empty = document.createElement('p');
    empty.className = 'meeting-empty';
    empty.textContent = '決定事項候補は検出されませんでした。';
    decisionList.append(empty);
  }
  decisions.forEach(decision => {
    const item = document.createElement('article');
    item.className = 'meeting-decision-item';
    const text = document.createElement('p');
    text.textContent = decision.text || '';
    const meta = document.createElement('small');
    meta.textContent = `${decision.speaker || '話者不明'} / ${formatTime(decision.evidence_start || 0)}`;
    item.append(text, meta);
    decisionList.append(item);
  });

}

function renderSessionOutline(data, outline) {
  const box = document.querySelector('#session-outline');
  const host = document.querySelector('#session-outline-content');
  const headline = document.querySelector('#session-outline-headline');
  if (!box || !host) return;
  host.replaceChildren();
  const plan = data?.plan || {items: []};
  const rows = data?.result?.rows || (outline?.sections || []).map(section => ({
    start: section.start, end: section.end, title: section.title || '議題'
  }));
  box.hidden = !plan.items?.length && !rows.length;
  if (headline) headline.textContent = rows.length ? '保存済みアウトライン ' + rows.length + '区間' : '議題を確認';
  if (plan.items?.length) {
    const section = uiElement('section', 'session-outline-block');
    section.append(uiElement('h3', '', '事前に入力した議題'));
    const list = uiElement('ol');
    plan.items.forEach(item => list.append(uiElement('li', '', item.text)));
    section.append(list);
    host.append(section);
  }
  if (rows.length) {
    const section = uiElement('section', 'session-outline-block');
    section.append(uiElement('h3', '', '結果（時間順）'));
    const list = uiElement('ol', 'session-outline-rows');
    rows.forEach(row => {
      const entry = uiElement('li');
      entry.append(uiElement('span', 'session-outline-time', formatTime(row.start) + '–' + formatTime(row.end)),
                   uiElement('strong', '', row.title || '議題'));
      list.append(entry);
    });
    section.append(list);
    host.append(section);
  }
}

function renderOutline(outline) {
  const view = document.querySelector('#outline-view');
  const content = document.querySelector('#outline-content');
  content.replaceChildren();
  const sections = outline && Array.isArray(outline.sections) ? outline.sections : [];
  const rerunStatus = document.querySelector('#outline-rerun-status');
  if (rerunStatus) rerunStatus.textContent = '';
  if (!sections.length) {
    const empty = document.createElement('p');
    empty.className = 'outline-empty';
    empty.textContent = 'AIアウトラインはまだありません。右上の「アウトラインを再実行」で、保存済みの文字起こしから作成できます。';
    content.append(empty);
    view.hidden = false;
    return;
  }
  if (typeof outline.summary === 'string' && outline.summary.trim()) {
    const overall = document.createElement('section');
    overall.className = 'outline-overall-summary';
    const label = document.createElement('h4');
    label.textContent = '全体要約';
    const text = document.createElement('p');
    text.textContent = outline.summary;
    overall.append(label, text);
    content.append(overall);
  }
  const segments = (currentJob && Array.isArray(currentJob.segments) ? currentJob.segments : [])
    .slice().sort((a, b) => Number(a.start || 0) - Number(b.start || 0));
  const timed = segments.filter(validSegmentTime);
  const mediaLength = mediaPlayer && Number.isFinite(mediaPlayer.duration) ? mediaPlayer.duration : 0;
  const wholeEnd = Math.max(mediaLength, ...timed.map(segment => segment.end), 0);
  if (timed.length) {
    const all = outlineSpeechStats(timed, 0, wholeEnd, true);
    const totals = document.createElement('section');
    totals.className = 'outline-totals';
    const label = document.createElement('h4');
    label.textContent = '全体の発話量・空白時間';
    totals.append(label, outlineStatChips(all));
    if (timed.length < segments.length) {
      const note = document.createElement('small');
      note.textContent = `時刻のない発話 ${segments.length - timed.length}件は時間の集計に含めていません。`;
      totals.append(note);
    }
    content.append(totals);
  }
  // Meetings: decisions found in the minutes are listed up front and again under
  // the agenda item they were made in. They are rule-based candidates.
  const decisions = ((currentJob && currentJob.meeting_minutes && currentJob.meeting_minutes.decisions) || [])
    .filter(item => item && item.text);
  const decisionLine = decision => {
    const line = document.createElement('div');
    line.className = 'outline-decision';
    const play = document.createElement('button');
    play.type = 'button';
    play.className = 'outline-utterance-time';
    play.textContent = formatTime(decision.evidence_start);
    if (decision.evidence_segment_id) play.addEventListener('click', () => playSegment(decision.evidence_segment_id));
    else play.disabled = true;
    const text = document.createElement('span');
    text.textContent = `${decision.speaker ? decision.speaker + '：' : ''}${decision.text}`;
    line.append(play, text);
    return line;
  };
  if (decisions.length) {
    const box = document.createElement('section');
    box.className = 'outline-decisions';
    const label = document.createElement('h4');
    label.textContent = `決まったこと（候補 ${decisions.length}件）`;
    box.append(label);
    decisions.forEach(decision => box.append(decisionLine(decision)));
    const note = document.createElement('small');
    note.textContent = '「決定」「にします」などの表現から自動抽出した候補です。時刻を押すと元の発話を再生します。';
    box.append(note);
    content.append(box);
  }
  sections.forEach((section, index) => {
    const row = document.createElement('details');
    row.className = 'outline-section';
    const sectionDecisions = decisions.filter(item => Number(item.evidence_start) >= (Number(section.start) || 0)
      && (index === sections.length - 1 ? Number(item.evidence_start) <= Number(section.end)
        : Number(item.evidence_start) < Number(section.end)));
    const head = document.createElement('summary');
    const time = document.createElement('span');
    time.className = 'outline-time';
    time.textContent = `${formatTime(section.start)}–${formatTime(section.end)}`;
    const heading = document.createElement('div');
    heading.className = 'outline-section-head';
    const title = document.createElement('h4');
    title.textContent = section.title || '議題';
    heading.append(title);
    const last = index === sections.length - 1;
    const stats = outlineSpeechStats(timed, Number(section.start) || 0, Number(section.end) || 0, last);
    if (timed.length) heading.append(outlineStatChips(stats));
    if (sectionDecisions.length) {
      const badge = document.createElement('span');
      badge.className = 'outline-decision-badge';
      badge.textContent = `決定 ${sectionDecisions.length}`;
      heading.append(badge);
    }
    head.append(time, heading);

    const body = document.createElement('div');
    body.className = 'outline-section-body';
    const list = document.createElement('ul');
    (section.bullets || []).forEach(value => {
      const item = document.createElement('li');
      item.textContent = value;
      list.append(item);
    });
    body.append(list);
    if (sectionDecisions.length) {
      const decided = document.createElement('div');
      decided.className = 'outline-decisions-inline';
      const label = document.createElement('small');
      label.textContent = 'この議題で決まったこと（候補）';
      decided.append(label);
      sectionDecisions.forEach(decision => decided.append(decisionLine(decision)));
      body.append(decided);
    }
    row.append(head, body);
    // The utterances behind the agenda item are built on first open.
    row.addEventListener('toggle', () => {
      if (!row.open || body.querySelector('.outline-utterances')) return;
      const inside = timed.filter(segment => segment.start >= (Number(section.start) || 0)
        && (last ? segment.start <= Number(section.end) : segment.start < Number(section.end)));
      const box = document.createElement('div');
      box.className = 'outline-utterances';
      const caption = document.createElement('small');
      caption.textContent = inside.length ? `この区間の発話（${inside.length}件・時刻を押すと再生）` : 'この区間に時刻付きの発話はありません。';
      box.append(caption);
      inside.forEach(segment => {
        const line = document.createElement('div');
        line.className = 'outline-utterance';
        const play = document.createElement('button');
        play.type = 'button';
        play.className = 'outline-utterance-time';
        play.textContent = formatTime(segment.start);
        play.addEventListener('click', () => playSegment(segment.id));
        const who = document.createElement('strong');
        who.textContent = displaySpeakerName(segment.speaker);
        const text = document.createElement('span');
        text.textContent = segment.text || '';
        line.append(play, who, text);
        box.append(line);
      });
      body.append(box);
    });
    content.append(row);
  });
  view.hidden = false;
}

function formatSpan(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), s = total % 60;
  if (h) return `${h}時間${m}分`;
  return m ? `${m}分${String(s).padStart(2, '0')}秒` : `${s}秒`;
}

function outlineSpeechStats(timed, from, to, inclusiveEnd) {
  const spans = [];
  let count = 0, characters = 0;
  timed.forEach(segment => {
    const start = Math.max(from, segment.start), end = Math.min(to, segment.end);
    if (end > start) spans.push([start, end]);
    if (segment.start >= from && (inclusiveEnd ? segment.start <= to : segment.start < to)) {
      count += 1;
      characters += String(segment.text || '').length;
    }
  });
  spans.sort((a, b) => a[0] - b[0]);
  let speech = 0, cursor = from;
  spans.forEach(([start, end]) => {
    const from_ = Math.max(start, cursor);
    if (end > from_) { speech += end - from_; cursor = end; }
  });
  const total = Math.max(0, to - from);
  return {total, speech, silence: Math.max(0, total - speech), count, characters};
}

function outlineStatChips(stats) {
  const host = document.createElement('div');
  host.className = 'outline-stats';
  const share = stats.total > 0 ? ` (${Math.round(stats.speech / stats.total * 100)}%)` : '';
  [
    `全体 ${formatSpan(stats.total)}`,
    `発話 ${formatSpan(stats.speech)}${share}`,
    `空白 ${formatSpan(stats.silence)}`,
    `${stats.count}発話・${stats.characters}文字`,
  ].forEach(text => {
    const chip = document.createElement('span');
    chip.textContent = text;
    host.append(chip);
  });
  return host;
}

function segmentEmotionText(segment) {
  const emotions = segment && typeof segment.emotions === 'object' && segment.emotions ? segment.emotions : {};
  return Object.keys(emotions).sort().map(key => {
    const item = emotions[key] || {};
    const confidence = typeof item.confidence === 'number' ? ` ${item.confidence.toFixed(2)}` : '';
    return `${item.model_name || key}: ${item.label_ja || item.label || '不明'}${confidence}`;
  }).join(' / ');
}

function kushinadaEmotion(segment) {
  const data = segment && segment.emotions && segment.emotions.kushinada;
  return data && data.label ? data.label : '';
}



function syncMediaPlayback(currentTime) {
  if (!currentJob || !Array.isArray(currentJob.segments)) return;
  const match = currentJob.segments.find(segment => {
    const s = Number(segment.start || 0);
    const e = Number(segment.end || 0);
    return currentTime >= s && currentTime <= e;
  });
  const matchId = match ? match.id : null;
  if (matchId === activePlaybackSegmentId) return;
  activePlaybackSegmentId = matchId;

  document.querySelectorAll('.segment.is-active-playback').forEach(el => {
    el.classList.remove('is-active-playback');
  });

  if (matchId) {
    const target = document.querySelector(`.segment[data-segment-id="${matchId}"]`);
    if (target) {
      target.classList.add('is-active-playback');
      const autoScroll = document.querySelector('#media-autoscroll');
      if (!autoScroll || autoScroll.checked) {
        target.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      }
    }
  }
}

function renderMedia(job) {
  mediaPlayerHost.replaceChildren();
  mediaPlayer = null;
  playbackStopAt = null;
  selectedSegmentId = null;
  activePlaybackSegmentId = null;
  if (!job.media_url) {
    mediaReview.hidden = true;
    return;
  }
  mediaPlayer = document.createElement(job.media_kind === 'video' ? 'video' : 'audio');
  mediaPlayer.controls = true;
  mediaPlayer.preload = 'metadata';
  mediaPlayer.src = job.media_url;
  mediaPlayer.addEventListener('timeupdate', () => {
    if (playbackStopAt !== null && mediaPlayer.currentTime >= playbackStopAt) {
      mediaPlayer.pause();
      playbackStopAt = null;
    }
    syncMediaPlayback(mediaPlayer.currentTime);
  });
  mediaPlayerHost.append(mediaPlayer);
  mediaReview.hidden = false;
}

function renderFormattingResult(result) {
  const section = document.querySelector('#formatting-result');
  const mode = document.querySelector('#formatting-result-mode');
  const metrics = document.querySelector('#formatting-result-metrics');
  const detailsHost = document.querySelector('#formatting-result-details');
  if (!section || !metrics || !detailsHost) return;
  const value = result && typeof result === 'object' ? result : null;
  section.hidden = !value || !value.summary;
  metrics.replaceChildren();
  detailsHost.replaceChildren();
  if (!value || !value.summary) return;
  if (mode) mode.textContent = `${value.mode_label || value.mode || '整形結果'}${value.manual_edit_status ? '・手動編集後' : ''}`;
  const summary = value.summary || {};
  [
    ['文字調整', summary.text_change_count, '件'],
    ['境界確認', summary.boundary_warning_count, '件'],
    ['AI文章置換', summary.recommended_replacement_count, '件'],
    ['ノイズ候補', summary.noise_candidate_count, '件'],
    ['句読点確認', summary.punctuation_warning_count, '件'],
    ['話者統合', summary.speaker_relabel_count, '発話'],
    ['AI呼び出し', summary.llm_request_count, '回']
  ].forEach(([label, count, unit]) => {
    const card = document.createElement('article');
    const caption = document.createElement('span');
    const number = document.createElement('strong');
    caption.textContent = label;
    number.textContent = `${Number(count || 0)}${unit}`;
    card.append(caption, number);
    metrics.append(card);
  });
  const appendDetails = (title, rows, describe) => {
    if (!Array.isArray(rows) || !rows.length) return;
    const details = document.createElement('details');
    const summaryElement = document.createElement('summary');
    const list = document.createElement('ul');
    summaryElement.textContent = `${title}（${rows.length}件）`;
    rows.slice(0, 50).forEach(row => {
      const item = document.createElement('li');
      item.textContent = describe(row);
      list.append(item);
    });
    details.append(summaryElement, list);
    detailsHost.append(details);
  };
  appendDetails('処理方法', value.methods, row => `${row.label}: ${row.status}`);
  appendDetails('自己紹介から抽出した話者', value.self_introductions, row => `${row.name}（${row.speaker}${row.status === 'local_candidate' ? '・ローカル抽出候補' : '・確認済み'}）`);
  appendDetails('不自然な分割の確認候補', value.boundary_warnings, row => `${row.message} 間隔 ${Number(row.gap_seconds || 0).toFixed(2)}秒`);
  appendDetails('おすすめ文章整形（Jev＋LLM）', value.recommended_reviews, row => `${row.replacement_applied ? '置換済み' : (row.llm_confirmed ? '問題確認・置換なし' : '補正不要')}［${row.effort || '中'}］— ${row.reason || row.original_text}`);
  appendDetails('ノイズ候補', value.noise_candidates, row => `${formatTime(row.start)} ${row.text} — ${row.reason}`);
  appendDetails('句読点の確認候補', value.punctuation_warnings, row => row.message || row.type || '確認してください');
  appendDetails('話者ラベルの統合', value.speaker_changes, row => `${row.from} → ${row.to}`);
}

function renderMediaBasicInfo(job) {
  const target = document.querySelector('#media-basic-info');
  if (!target) return;
  target.replaceChildren();
  const reasons = {
    ffprobe_unavailable: 'ffprobeを利用できません', file_not_found: 'ファイルが見つかりません',
    no_media_path: '元メディアの記録がありません', path_check_failed: '保存場所を確認できません',
    ffprobe_failed: 'メディア情報を取得できません', invalid_probe_json: '取得結果を読み取れません',
    metadata_unavailable: 'メタデータに値がありません'
  };
  const add = (list, label, value) => {
    const term = document.createElement('dt'), description = document.createElement('dd');
    term.textContent = label;
    description.textContent = value;
    list.append(term, description);
  };
  const general = document.createElement('dl');
  add(general, 'アプリへの取込日時', job.created_at || '不明');
  add(general, '文字起こしの最終時刻', transcriptEndpointText(job.duration, job.timed_turn_count, job.missing_time_turn_count));
  target.append(general);
  if (!job.media_assets?.length) {
    const note = document.createElement('p');
    note.textContent = 'メディア情報は未記録です。起動後の記録処理が終わってから開き直してください。';
    target.append(note);
  }
  (job.media_assets || []).forEach(asset => {
    const heading = document.createElement('h4');
    heading.textContent = asset.role === 'original' ? '元ファイル' : 'アプリ保存版';
    const list = document.createElement('dl');
    add(list, '保存場所', asset.path || (asset.path_status === 'no_media_path'
      ? '不明（元メディアの記録がありません）' : '不明（保存場所の表示は許可されていません）'));
    add(list, '現在の状態', asset.path_status === 'available' ? '見つかりました' : reasons[asset.path_status] || '不明');
    const fields = [
      ['original_filename', '元ファイル名'], ['media_created_at', '収録日時'], ['file_modified_at', 'ファイル更新日時'],
      ['imported_at', 'アプリへの取込日時'], ['duration_seconds', 'メディアの長さ（秒）'], ['bytes', 'サイズ（バイト）'],
      ['container', '形式'], ['video_codec', '映像コーデック'], ['width', '幅'], ['height', '高さ'], ['fps', 'フレームレート'],
      ['audio_codec', '音声コーデック'], ['sample_rate', 'サンプリング周波数'], ['channels', 'チャンネル数'],
      ['probed_at', 'メディア情報の取得日時'], ['path_checked_at', '記録時の保存場所確認日時']
    ];
    fields.forEach(([field, label]) => add(list, label, asset[field] == null
      ? `不明（${reasons[asset.unknown_reasons?.[field]] || '値が記録されていません'}）` : String(asset[field])));
    target.append(heading, list);
  });
}

function renderResult(job) {
  if (rerunSpeakerIdentificationButton) rerunSpeakerIdentificationButton.disabled = false;
  if (speakerIdentityProvider) speakerIdentityProvider.disabled = false;


  currentJob = deepCopy(job);
  currentJobBaseline = deepCopy(job);
  resultSaveConflict = false;
  deletedSegmentUndo = [];
  document.querySelector('#result-draft-recovery').hidden = true;
  document.querySelector('#undo-segment-delete').hidden = true;
  setAlert(document.querySelector('#segment-delete-status'), '');
  currentJob.segments = Array.isArray(currentJob.segments) ? currentJob.segments : [];
  currentJob.speaker_names = currentJob.speaker_names || {};
  currentJob.session_profile = currentJob.session_profile || {};
  currentJob.speaker_profiles = currentJob.speaker_profiles || {};
  currentJob.meeting_minutes = currentJob.meeting_minutes || null;
  if (speakerIdentityProvider && aiProvider && ['openai', 'google', 'lmstudio'].includes(aiProvider.value)) {
    speakerIdentityProvider.value = aiProvider.value;
  }
  if (speakerIdentityStatus) {
    const identifiedCount = Object.values(currentJob.speaker_names).filter(value => String(value || '').trim()).length;
    const registeredCount = Object.keys((job.speaker_registration || {}).created || {}).length;
    speakerIdentityStatus.textContent = identifiedCount
      ? `${identifiedCount}名の表示名を反映済みです。${registeredCount ? `${registeredCount}名を話者管理へ登録しました。` : '既存名は再実行で上書きしません。'}`
      : '話者名は未反映です。OpenAI、Gemini、またはローカルLLMで話者特定だけを実行できます。';
  }
  currentJobId = job.id;
  if (typeof resetNotationView === 'function') resetNotationView();
  if (!activeJobId) storeActiveJobId('');
  document.querySelector('#result-title').textContent = job.source_name || '確認・手動編集';
  const outputDirectory = document.querySelector('#result-output-dir');
  if (outputDirectory) {
    outputDirectory.textContent = job.output_dir ? `Gurumoji実行環境の出力フォルダー　${job.output_dir}（閲覧端末への保存はダウンロード操作で行います）` : '';
    outputDirectory.hidden = !job.output_dir;
  }
  renderDownloads(job.files);
  renderMediaBasicInfo(job);
  renderAiTokenUsage('#result-ai-usage', job.ai_usage);
  renderFormattingResult(job.formatting_result);
  renderMeetingMinutes(currentJob.meeting_minutes, job.id);
  renderOutline(job.outline);
  renderSessionOutline(job.session_outline, job.outline);

  renderMedia(job);
  renderSessionProfile();
  renderSpeakerEditor();
  updateSegmentFilterOptions();
  renderSegments();
  if (Object.keys((job.speaker_registration || {}).created || {}).length && !speakerRegistryDirty) {
    void loadSpeakerRegistry(true);
  }
  setAlert(document.querySelector('#save-message'), '');
  if (job.output_warning) {
    setAlert(document.querySelector('#save-message'), job.output_warning, true);
  }
  const switchingItem = renderedItemId !== String(job.id);
  renderedItemId = String(job.id);
  if (progressCard && !jobRunning) progressCard.hidden = true;
  setCurrentJobDirty(false);
  showView('item', {itemId: job.id, force: true});
  if (switchingItem) {
    setItemTab('transcript');
    window.scrollTo({top: 0, behavior: 'auto'});
  }
}

function speakerLabels() {
  return [...new Set(currentJob.segments.map(segment => segment.speaker || 'UNKNOWN'))].sort();
}

function displaySpeakerName(label) {
  const speakerLabel = String(label || 'UNKNOWN');
  const profiles = currentJob?.speaker_profiles || {}, names = currentJob?.speaker_names || {};
  const profile = Object.hasOwn(profiles, speakerLabel) ? profiles[speakerLabel] : {};
  const name = Object.hasOwn(names, speakerLabel) ? names[speakerLabel] : '';
  return profile?.display_name || name || fallbackSpeaker(speakerLabel);
}

function renderSessionProfile() {
  if (!currentJob) return;
  const profile = currentJob.session_profile || {};
  const fields = {
    '#session-type': ['session_type', 'focus_group'],
    '#session-date': ['session_date', ''],
    '#session-location': ['location', ''],
    '#session-interview-group-id': ['interview_group_id', ''],
    '#session-comparison-group': ['comparison_group', ''],
    '#session-objective': ['objective', ''],
    '#session-guide': ['moderator_guide', ''],
    '#session-conditions': ['group_conditions', ''],
    '#session-field-notes': ['field_notes', '']
  };
  Object.entries(fields).forEach(([selector, [key, fallback]]) => {
    const element = document.querySelector(selector);
    if (element) element.value = profile[key] || fallback;
  });
  const dateInput = document.querySelector('#session-date');
  const dateNote = document.querySelector('#session-date-note');
  if (dateInput) {
    dateInput.dataset.autoValue = profile.session_date_source === 'media_metadata'
      ? String(profile.session_date || '')
      : '';
  }
  if (dateNote) {
    dateNote.textContent = profile.session_date_source === 'media_metadata'
      ? '動画の撮影日時から自動入力しました。必要に応じて変更できます。'
      : '動画から取得できない場合は、手動で入力・変更できます。';
  }
  const notesDetails = document.querySelector('#session-notes-details');
  const notesSummary = document.querySelector('#session-notes-summary');
  const hasNotes = Boolean(String(profile.field_notes || '').trim());
  if (notesDetails) notesDetails.open = hasNotes;
  if (notesSummary) notesSummary.textContent = hasNotes ? '入力済み' : '未入力';
  const exportLink = document.querySelector('#conversation-speaker-export');
  if (exportLink) {
    exportLink.href = currentJob.speaker_data_url || `/api/library/${currentJobId}/speakers.csv`;
  }
}

function captureSessionProfile() {
  if (!currentJob) return {};
  const read = selector => {
    const element = document.querySelector(selector);
    return element ? element.value.trim() : '';
  };
  const sessionDate = read('#session-date');
  const dateInput = document.querySelector('#session-date');
  const sessionDateSource = sessionDate && dateInput && dateInput.dataset.autoValue === sessionDate
    ? 'media_metadata'
    : sessionDate ? 'manual' : '';
  currentJob.session_profile = {
    session_type: read('#session-type') || 'focus_group',
    session_date: sessionDate,
    session_date_source: sessionDateSource,
    location: read('#session-location'),
    interview_group_id: read('#session-interview-group-id'),
    comparison_group: read('#session-comparison-group'),
    objective: read('#session-objective'),
    moderator_guide: read('#session-guide'),
    group_conditions: read('#session-conditions'),
    field_notes: read('#session-field-notes')
  };
  return currentJob.session_profile;
}

function renderDownloads(files) {
  const container = document.querySelector('#download-links');
  container.replaceChildren();
  (files || []).filter(file => !String(file.name || '').toLowerCase().endsWith('.json')).forEach(file => {
    const link = document.createElement('a');
    link.href = file.url;
    link.textContent = `${file.name.split('.').pop().toUpperCase()} を保存`;
    link.setAttribute('download', file.name);
    container.append(link);
  });
}
