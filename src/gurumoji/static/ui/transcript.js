/* 公開版の画面処理: transcript。共有状態はapp.jsで管理する。 */
function speakerMetrics() {
  const metrics = Object.create(null);
  let totalSeconds = 0, missingTimeCount = 0;
  const segments = currentJob.segments || [], timing = currentJob.segment_timings;
  const ids = segments.map(segment => segment.id);
  const timingBound = Array.isArray(timing) && timing.length === segments.length
    && ids.every(id => typeof id === 'string' && id) && new Set(ids).size === ids.length
    && timing.every((row, index) => row && typeof row === 'object' && !Array.isArray(row)
      && ['segment_id', 'source_start', 'source_end', 'source_time_unknown', 'valid', 'start', 'end'].every(key => Object.hasOwn(row, key))
      && row.segment_id === ids[index]);
  // Python's existing false markers include empty JSON containers. Keep this
  // finite compatibility rule local to measurement; the audio/evidence guard is separate.
  const emptyMarkerKind = value => Array.isArray(value) && value.length === 0 ? 'array'
    : value && Object.prototype.toString.call(value) === '[object Object]' && Object.keys(value).length === 0 ? 'object' : '';
  const markerKnown = value => value == null || value === false || value === 0 || value === '' || Boolean(emptyMarkerKind(value));
  const markerMatches = (left, right) => Object.is(left, right)
    || Boolean(emptyMarkerKind(left) && emptyMarkerKind(left) === emptyMarkerKind(right));
  const valid = row => row && markerKnown(row.time_unknown)
    && analysisEvidenceTimeValid({start: row.start, end: row.end})
    && row.start <= 31 * 86400 && row.end <= 31 * 86400;
  segments.forEach((segment, index) => {
    const label = segment.speaker || 'UNKNOWN';
    const data = metrics[label] || {count: 0, timedCount: 0, missingTimeCount: 0, timedSeconds: 0, seconds: null, characters: 0};
    data.count += 1;
    // Use the backend's Python-compatible conversion only while its raw binding matches.
    // A local edit or malformed/stale projection falls back to the numeric measurement guard.
    const projection = timingBound ? timing[index] : null;
    const projected = projection && {start: projection.start, end: projection.end, time_unknown: segment.time_unknown};
    const useProjection = projection?.valid === true
      && Object.is(projection.source_start, segment.start ?? null)
      && Object.is(projection.source_end, segment.end ?? null)
      && markerMatches(projection.source_time_unknown, segment.time_unknown ?? null)
      && (typeof segment.start !== 'number' || Object.is(segment.start, projection.start))
      && (typeof segment.end !== 'number' || Object.is(segment.end, projection.end)) && valid(projected);
    const measured = useProjection ? projected : segment;
    // Participation's 31-day bound does not change the separate evidence/audio seek guard.
    if (valid(measured)) {
      const duration = measured.end - measured.start;
      data.timedCount += 1;
      data.timedSeconds += duration;
      totalSeconds += duration;
    } else {
      data.missingTimeCount += 1;
      missingTimeCount += 1;
    }
    data.characters += String(segment.text || '').length;
    metrics[label] = data;
  });
  Object.values(metrics).forEach(data => {
    data.seconds = data.timedCount && Number.isFinite(data.timedSeconds) ? data.timedSeconds : null;
    data.share = missingTimeCount === 0 && Number.isFinite(totalSeconds) && totalSeconds > 0
      ? data.seconds / totalSeconds : null;
  });
  return metrics;
}

function ensureConversationSpeakerProfiles() {
  // Speaker labels are literal user data, including Object prototype property names.
  // Copy only own entries, preserving JSON keys while making subsequent writes safe.
  currentJob.speaker_names = Object.assign(Object.create(null), currentJob.speaker_names || {});
  currentJob.speaker_profiles = Object.assign(Object.create(null), currentJob.speaker_profiles || {});
  speakerLabels().forEach((label, index) => {
    currentJob.speaker_profiles[label] = {
      speaker_label: label,
      global_speaker_id: '',
      registration_status: currentJob.speaker_names[label] ? 'temporary_single_group' : 'unidentified',
      display_name: currentJob.speaker_names[label] || '',
      theme_color: speakerThemeColors[index % speakerThemeColors.length],
      session_role: 'participant',
      organization: '',
      department: '',
      job_title: '',
      attendance_status: 'attended',
      conditions: '',
      notes: '',
      ...(currentJob.speaker_profiles[label] || {})
    };
  });
}

function conversationControl(type, value, options, onChange) {
  const owner = currentJob, itemId = currentJobId;
  const apply = () => {
    if (!control.isConnected || currentJob !== owner || currentJobId !== itemId) return;
    if (onChange(control.value) !== false) setCurrentJobDirty();
  };
  const control = document.createElement(type === 'textarea' ? 'textarea' : type === 'select' ? 'select' : 'input');
  if (type === 'select') {
    Object.entries(options || {}).forEach(([optionValue, label]) => control.add(new Option(label, optionValue)));
    control.value = value || Object.keys(options || {})[0];
    control.addEventListener('change', apply);
  } else {
    if (type !== 'textarea') control.type = type === 'color' ? 'color' : 'text';
    control.value = value || '';
    control.addEventListener('input', apply);
  }
  return control;
}

function conversationRoleControl(profile, label, metrics, index) {
  const owner = currentJob, itemId = currentJobId;
  const container = document.createElement('div');
  container.className = 'conversation-role-control';
  const select = document.createElement('select');
  Object.entries(speakerRoleLabels).forEach(([value, text]) => select.add(new Option(text, value)));
  select.value = profile.session_role || 'participant';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'この会話の役割として設定';
  const status = document.createElement('span');
  status.className = 'conversation-role-status';
  status.id = `conversation-role-status-${index}`;
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  status.textContent = ({
    __proto__: null,
    default: 'この会話では未設定（初期表示）',
    legacy_unknown: '旧データ等：設定元不明',
    registry: '話者管理から設定',
    explicit: 'この会話で明示設定'
  })[profile.session_role_source] || '旧データ等：設定元不明';
  const describe = () => {
    const displayName = (owner.speaker_profiles[label] || profile).display_name || fallbackSpeaker(label);
    const name = `${displayName}（話者ID ${label}）`;
    select.setAttribute('aria-label', `${name}の会話役割`);
    button.setAttribute('aria-label', `${name}の役割を「${speakerRoleLabels[select.value] || select.value}」としてこの会話に設定`);
  };
  for (const control of [select, button]) control.setAttribute('aria-describedby', `${status.id} conversation-role-help`);
  const applyRole = () => {
    // Detached controls and responses from an older editor cannot edit another item.
    if (!container.isConnected || currentJob !== owner || currentJobId !== itemId) return;
    // Normal save normalization replaces profiles while this editor stays mounted.
    const activeProfile = currentJob.speaker_profiles[label];
    if (!activeProfile) return;
    describe();
    if (activeProfile.session_role === select.value && activeProfile.session_role_source === 'explicit') return;
    activeProfile.session_role = select.value;
    activeProfile.session_role_source = 'explicit';
    setCurrentJobDirty();
    status.textContent = `「${speakerRoleLabels[select.value] || select.value}」をこの会話の役割に設定しました。まだ保存されていません`;
    renderSpeakerInsights(metrics);
  };
  select.addEventListener('change', applyRole);
  button.addEventListener('click', applyRole);
  describe();
  // Rename labels without dispatching a role change or certifying its provenance.
  container.refreshAccessibleName = describe;
  container.append(select, button, status);
  return container;
}

function renderSpeakerInsights(metrics) {
  const container = document.querySelector('#speaker-insights');
  if (!container) return;
  container.replaceChildren();
  const profiles = Object.values(currentJob.speaker_profiles || {});
  const sessionType = (currentJob.session_profile || {}).session_type
    || (document.querySelector('#session-type') || {}).value
    || 'focus_group';
  const add = (text, level = '') => {
    const chip = document.createElement('span');
    chip.className = `speaker-insight${level ? ` ${level}` : ''}`;
    chip.textContent = text;
    container.append(chip);
  };
  add(`話者 ${profiles.length}人`);
  const uncertainRoleCount = profiles.filter(profile => !['explicit', 'registry'].includes(profile.session_role_source)).length;
  const provisional = uncertainRoleCount > 0;
  if (provisional) add(`役割未設定・記録元不明 ${uncertainRoleCount}人（役割別人数は仮集計）`, 'warning');
  if (!Object.keys(metrics).length) add('発話なし');
  if (sessionType === 'focus_group') {
    const participants = profiles.filter(profile => profile.session_role === 'participant');
    const moderators = profiles.filter(profile => ['moderator', 'facilitator', 'assistant_moderator'].includes(profile.session_role));
    const observers = profiles.filter(profile => ['observer', 'note_taker'].includes(profile.session_role));
    add(`参加者${provisional ? '（仮）' : ''} ${participants.length}人`, !provisional && participants.length >= 6 && participants.length <= 8 ? '' : 'warning');
    add(provisional ? `司会・進行（仮） ${moderators.length}人` : moderatorCountText(moderators.length), provisional ? 'warning' : moderators.length ? '' : 'error');
    add(`観察・記録${provisional ? '（仮）' : ''} ${observers.length}人`, observers.length ? '' : 'warning');
    const participantTimeMissing = participants.some(profile => (metrics[profile.speaker_label]?.missingTimeCount || 0) > 0);
    const participantSeconds = participants.reduce((sum, profile) => (
      sum + (metrics[profile.speaker_label]?.timedSeconds || 0)
    ), 0);
    const participantTurnCount = participants.reduce((sum, profile) => sum + (metrics[profile.speaker_label]?.count || 0), 0);
    if (provisional) {
      add('役割未設定・記録元不明の話者がいるため、参加者内の割合は判定できません', 'warning');
    } else if (participants.length && !participantTurnCount) {
      add('参加者の発話なし');
    } else if (participantTimeMissing) {
      add('参加者の時刻不明があるため、発言時間の割合は判定できません', 'warning');
    } else if (participants.length && participantSeconds === 0) {
      add('参加者の総時間が0秒のため、発言時間の割合は判定できません');
    } else if (!Number.isFinite(participantSeconds)) {
      add('参加者の総時間を算出できないため、発言時間の割合は判定できません', 'warning');
    } else {
      const dominant = participants.find(profile => (
        participantSeconds > 0 && (metrics[profile.speaker_label]?.seconds || 0) / participantSeconds >= 0.5
      ));
      if (dominant) add(`${dominant.display_name || dominant.speaker_label} の発言が参加者内50%以上`, 'warning');
    }
  } else if (sessionType === 'meeting') {
    const leaders = profiles.filter(profile => ['chair', 'facilitator', 'moderator'].includes(profile.session_role));
    add(`進行・議長${provisional ? '（仮）' : ''} ${leaders.length}人`, leaders.length ? '' : 'warning');
    const decisionMakers = profiles.filter(profile => profile.session_role === 'decision_maker');
    if (decisionMakers.length) add(`意思決定者${provisional ? '（仮）' : ''} ${decisionMakers.length}人`);
  }
}

function moderatorCountText(count) {
  return `司会・進行 ${count}人`;
}

function renderConversationParticipation(metrics) {
  const container = document.querySelector('#conversation-participation');
  if (!container) return;
  container.replaceChildren();
  if (!currentJob) return;
  const entries = Object.entries(metrics);
  const totalCount = entries.reduce((sum, [, metric]) => sum + metric.count, 0);
  const missingCount = entries.reduce((sum, [, metric]) => sum + metric.missingTimeCount, 0);
  const useTime = entries.length > 0 && entries.every(([, metric]) => metric.share !== null);
  const heading = document.createElement('h4');
  heading.id = 'conversation-participation-title';
  heading.textContent = '話者別の発言量';
  const note = document.createElement('p');
  note.className = 'conversation-participation-note';
  note.textContent = !totalCount ? '発話を追加すると、話者ごとの発言量を表示します。'
    : `全 ${totalCount}発話 / ${entries.length}話者。棒グラフは${useTime ? '発言時間' : '発話回数'}の割合です。`
      + (missingCount ? ` 時刻不明 ${missingCount}発話のため、時間の割合は算出できません。` : '')
      + (useTime ? ' 発言時間は各発話の時間の合計です（重なりを含みます）。' : '');
  container.append(heading, note);
  const list = document.createElement('ul');
  list.className = 'conversation-participation-list';
  entries.sort(([, a], [, b]) => useTime ? b.seconds - a.seconds : b.count - a.count);
  entries.forEach(([label, metric]) => {
    const row = document.createElement('li');
    row.className = 'conversation-participation-row';
    const name = document.createElement('strong');
    name.className = 'conversation-participation-name';
    name.textContent = displaySpeakerName(label);
    name.title = `話者ID: ${label}`;
    const share = useTime ? metric.share : metric.count / totalCount;
    const percentage = document.createElement('span');
    percentage.className = 'conversation-participation-share';
    percentage.textContent = `${(share * 100).toFixed(1)}%`;
    const track = document.createElement('div');
    track.className = 'conversation-participation-track';
    track.setAttribute('aria-hidden', 'true');
    const bar = document.createElement('span');
    bar.style.width = `${Math.max(0, Math.min(100, share * 100))}%`;
    const color = currentJob.speaker_profiles?.[label]?.theme_color || '';
    if (/^#[0-9a-f]{6}$/i.test(color)) bar.style.backgroundColor = color;
    track.append(bar);
    const detail = document.createElement('span');
    detail.className = 'conversation-participation-detail';
    const time = !metric.timedCount ? '時刻不明'
      : metric.seconds === null ? '時間を算出できません'
      : `${formatTime(metric.seconds)}${metric.missingTimeCount ? '（時刻あり分）' : ''}`;
    detail.textContent = `${metric.count}回 / ${time} / ${metric.characters}文字`;
    if (metric.missingTimeCount) detail.textContent += ` / 時刻不明 ${metric.missingTimeCount}発話`;
    row.append(name, percentage, track, detail);
    list.append(row);
  });
  container.append(list);
}

function renderSpeakerEditor({focusSpeakerLabel = '', focusField = ''} = {}) {
  speakerEditor.replaceChildren();
  if (!currentJob) return;
  const owner = currentJob, itemId = currentJobId;
  let focusTarget = null;
  captureSessionProfile();
  ensureConversationSpeakerProfiles();
  const labels = speakerLabels();
  const metrics = speakerMetrics();
  renderConversationParticipation(metrics);
  renderSpeakerInsights(metrics);
  if (!labels.length) {
    const note = document.createElement('p');
    note.className = 'segment-empty';
    note.textContent = '発話を追加すると、会話別の話者連携を設定できます。';
    speakerEditor.append(note);
    return;
  }
  const roleHelp = document.createElement('p');
  roleHelp.id = 'conversation-role-help';
  roleHelp.className = 'muted';
  roleHelp.textContent = '変更は「保存」で反映します。分析準備で記録した発話別の役割がある場合は、そちらを優先します。「登録済み」は人物の登録状態で、会話役割の設定状態とは別です。';
  speakerEditor.append(roleHelp);
  const table = document.createElement('table');
  table.className = 'conversation-speaker-sheet';
  const head = document.createElement('thead');
  head.innerHTML = '<tr><th>音声話者</th><th>表示名</th><th>テーマカラー</th><th>話者登録</th><th>グローバル話者</th><th>会話役割</th><th>組織</th><th>部署</th><th>役職</th><th>参加状態</th><th>会話固有条件</th><th>メモ</th><th>発言量</th></tr>';
  table.append(head);
  const body = document.createElement('tbody');
  labels.forEach((label, index) => {
    const profile = currentJob.speaker_profiles[label];
    const row = document.createElement('tr');
    const activeProfile = () => currentJob === owner && currentJobId === itemId && row.isConnected
      ? currentJob.speaker_profiles[label] : null;
    const fieldNames = {display_name: '表示名', theme_color: 'テーマカラー', global_speaker_id: 'グローバル話者',
      organization: '組織', department: '部署', job_title: '役職', attendance_status: '参加状態', conditions: '会話固有条件', notes: 'メモ'};
    const namedControls = [];
    const nameControl = (control, field) => {
      control.dataset.speakerLabel = label;
      control.dataset.speakerField = field;
      namedControls.push([control, field]);
      if (label === focusSpeakerLabel && field === focusField) focusTarget = control;
      return control;
    };
    const refreshNames = () => {
      const name = (owner.speaker_profiles[label] || profile).display_name || fallbackSpeaker(label);
      namedControls.forEach(([control, field]) => control.setAttribute('aria-label', `${name}（話者ID ${label}）の${fieldNames[field]}`));
      roleControl.refreshAccessibleName();
    };
    const labelCell = document.createElement('td');
    labelCell.className = 'speaker-label-cell';
    labelCell.textContent = displaySpeakerName(label);
    labelCell.title = `話者ID: ${label}`;
    row.append(labelCell);
    const displayName = conversationControl('input', profile.display_name || currentJob.speaker_names[label], null, value => {
      const targetProfile = activeProfile();
      if (!targetProfile) return false;
      targetProfile.display_name = value.trim();
      currentJob.speaker_names[label] = value.trim();
      refreshNames();
      updateSpeakerBadges();
    });
    displayName.placeholder = fallbackSpeaker(label);
    appendSheetCell(row, nameControl(displayName, 'display_name'));
    const themeColor = conversationControl('color', profile.theme_color, null, value => {
      const targetProfile = activeProfile();
      if (!targetProfile) return false;
      targetProfile.theme_color = value.toUpperCase();
      updateSpeakerBadges();
    });
    themeColor.className = 'speaker-theme-color';
    appendSheetCell(row, nameControl(themeColor, 'theme_color'));

    const globalSelect = document.createElement('select');
    globalSelect.add(new Option('未連携', ''));
    speakerRegistry.filter(record => record.active !== false).forEach(record => {
      const name = record.pseudonym || record.display_name || record.participant_code;
      const detail = [record.organization, record.job_title].filter(Boolean).join(' / ');
      globalSelect.add(new Option(detail ? `${name} — ${detail}` : name, record.id));
    });
    if (profile.global_speaker_id && !speakerRegistry.some(record => record.id === profile.global_speaker_id)) {
      globalSelect.add(new Option('削除済みの管理対象話者', profile.global_speaker_id));
    }
    globalSelect.value = profile.global_speaker_id || '';
    globalSelect.addEventListener('change', () => {
      const profile = activeProfile();
      if (!profile) return;
      const restoreFocus = document.activeElement === globalSelect;
      profile.global_speaker_id = globalSelect.value;
      const record = speakerRegistry.find(item => item.id === globalSelect.value);
      if (record) {
        profile.registration_status = 'registered';
        profile.display_name = record.pseudonym || record.display_name || record.participant_code;
        profile.session_role = record.default_role || 'participant';
        profile.session_role_source = 'registry';
        profile.organization = record.organization || '';
        profile.department = record.department || '';
        profile.job_title = record.job_title || '';
        profile.conditions = attributesToText(record.attributes);
        currentJob.speaker_names[label] = profile.display_name;
      } else {
        profile.registration_status = profile.display_name ? 'temporary_single_group' : 'unidentified';
      }
      renderSpeakerEditor(restoreFocus ? {focusSpeakerLabel: label, focusField: 'global_speaker_id'} : {});
      updateSpeakerBadges();
      setCurrentJobDirty();
    });
    const registration = document.createElement('span');
    const registrationStatus = profile.global_speaker_id
      ? 'registered'
      : (profile.registration_status || (profile.display_name ? 'temporary_single_group' : 'unidentified'));
    registration.className = `speaker-registration ${registrationStatus}`;
    registration.textContent = registrationStatus === 'registered'
      ? '登録済み'
      : registrationStatus === 'temporary_single_group'
        ? '一時話者（この会話のみ）'
        : '未特定';
    appendSheetCell(row, registration);
    appendSheetCell(row, nameControl(globalSelect, 'global_speaker_id'));
    const roleControl = conversationRoleControl(profile, label, metrics, index);
    appendSheetCell(row, roleControl);
    const addProfileControl = (type, key, options = null) => {
      const control = conversationControl(type, profile[key], options, value => {
        const targetProfile = activeProfile();
        if (!targetProfile) return false;
        targetProfile[key] = value;
      });
      appendSheetCell(row, nameControl(control, key));
    };
    ['organization', 'department', 'job_title'].forEach(key => addProfileControl('input', key));
    addProfileControl('select', 'attendance_status', attendanceLabels);
    addProfileControl('textarea', 'conditions');
    addProfileControl('textarea', 'notes');
    refreshNames();
    const metric = metrics[label];
    const metricCell = document.createElement('td');
    metricCell.className = 'speaker-metric-cell';
    const timeText = !metric.timedCount ? `時刻不明${metric.missingTimeCount}件`
      : metric.seconds === null ? '時間を算出できません'
      : metric.missingTimeCount ? `時刻あり${formatTime(metric.seconds)}（${metric.timedCount}/${metric.count}発話、時刻不明${metric.missingTimeCount}発話）`
      : formatTime(metric.seconds);
    const shareText = metric.share === null ? '割合は算出不可' : `${(metric.share * 100).toFixed(1)}%`;
    metricCell.textContent = `${metric.count}回 / ${timeText} / ${shareText}`;
    row.append(metricCell);
    body.append(row);
  });
  table.append(body);
  speakerEditor.append(table);
  if (currentJob === owner && currentJobId === itemId && focusTarget?.isConnected) focusTarget.focus();
}

function updateSegmentFilterOptions() {
  const select = document.querySelector('#segment-speaker-filter');
  const selected = select.value;
  select.replaceChildren(new Option('すべて', ''));
  speakerLabels().forEach(label => select.add(new Option(displaySpeakerName(label), label)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

function occurrenceCount(text, keyword) {
  if (!keyword) return 0;
  return String(text || '').toLocaleLowerCase().split(keyword).length - 1;
}

function segmentReviewAgreement(segment) {
  const review = segment && segment.jev_review;
  const comparison = review && typeof review.comparison === 'object' ? review.comparison : null;
  return comparison ? String(comparison.agreement || '') : '';
}

function renderJevComparisonSummary() {
  const host = document.querySelector('#jev-comparison-summary');
  if (!host || !currentJob) return;
  const reviewed = currentJob.segments.filter(segment => segmentReviewAgreement(segment));
  host.replaceChildren();
  if (!reviewed.length) {
    host.hidden = true;
    return;
  }
  const labels = {
    both_flagged: '両方：修正が必要',
    current_only: '現行AIのみ',
    jev_only: 'Jevのみ',
    both_clear: '両方：修正不要'
  };
  const counts = Object.fromEntries(Object.keys(labels).map(key => [key, 0]));
  reviewed.forEach(segment => {
    const key = segmentReviewAgreement(segment);
    if (Object.hasOwn(counts, key)) counts[key] += 1;
  });
  const agreementCount = counts.both_flagged + counts.both_clear;
  const heading = document.createElement('div');
  heading.className = 'jev-comparison-heading';
  const text = document.createElement('div');
  const title = document.createElement('h3');
  title.textContent = '現行AI × Jev　修正要否の比較';
  const note = document.createElement('p');
  note.textContent = `判定一致 ${agreementCount} / ${reviewed.length} 発話（${Math.round(agreementCount / reviewed.length * 100)}%）。不一致は原音確認の優先候補です。`;
  text.append(title, note);
  const scope = document.createElement('span');
  scope.textContent = `${reviewed.length}発話を判定`;
  heading.append(text, scope);
  const grid = document.createElement('div');
  grid.className = 'jev-comparison-grid';
  Object.entries(labels).forEach(([key, label]) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = `jev-comparison-card ${key}`;
    const caption = document.createElement('span');
    caption.textContent = label;
    const value = document.createElement('strong');
    value.textContent = String(counts[key]);
    const unit = document.createElement('small');
    unit.textContent = '発話';
    card.append(caption, value, unit);
    card.addEventListener('click', () => {
      const filter = document.querySelector('#segment-jev-filter');
      if (filter) filter.value = key;
      renderSegments();
    });
    grid.append(card);
  });
  const caution = document.createElement('p');
  caution.className = 'jev-comparison-caution';
  caution.textContent = 'Jevは音声を聞かず、日本語の文字起こしと会話文脈だけで二択判定します。最終判断は元の音声・動画で確認してください。';
  host.append(heading, grid, caution);
  host.hidden = false;
}

function transcriptSelectionInput() {
  return {
    rows: currentJob.segments.map((segment, index) => ({
      index, text: String(segment.text || ''), speaker: segment.speaker || 'UNKNOWN',
      sortSpeaker: String(segment.speaker || ''), start: Number(segment.start || 0),
      emotion: kushinadaEmotion(segment), agreement: segmentReviewAgreement(segment),
    })),
    query: transcriptSelectionQuery(),
  };
}

function transcriptSelectionQuery() {
  return {
    keyword: document.querySelector('#segment-keyword').value.trim().toLocaleLowerCase(),
    speaker: document.querySelector('#segment-speaker-filter').value,
    emotion: document.querySelector('#segment-emotion-filter').value,
    agreement: document.querySelector('#segment-jev-filter')?.value || '',
    sort: document.querySelector('#segment-sort').value,
  };
}

function visibleSegments() {
  return GurumojiTranscriptMath.select(transcriptSelectionInput()).map(index => currentJob.segments[index]);
}

function createField(labelText, control) {
  const label = document.createElement('label');
  label.className = 'field';
  const caption = document.createElement('span');
  caption.textContent = labelText;
  label.append(caption, control);
  return label;
}

function selectSegmentForEdit(segmentId, {focus = false} = {}) {
  selectedSegmentId = segmentId;
  if (![...segmentEditor.querySelectorAll('.segment')].some(row => row.dataset.segmentId === segmentId)
      && currentJob?.segments.some(segment => segment.id === segmentId)) {
    renderSegments({focusSegmentId: segmentId, focus});
    return;
  }
  document.querySelectorAll('.segment').forEach(row => {
    const selected = row.dataset.segmentId === segmentId;
    row.classList.toggle('selected', selected);
    row.querySelector('.segment-edit')?.setAttribute('aria-expanded', String(selected));
    if (selected && focus) row.querySelector('textarea')?.focus();
  });
}

function undoSegmentDeletion() {
  const undo = deletedSegmentUndo.pop();
  if (!undo || undo.itemId !== currentJobId) return;
  currentJob.segments.splice(Math.min(undo.index, currentJob.segments.length), 0, undo.segment);
  selectedSegmentId = undo.segment.id;
  setCurrentJobDirty(); renderSpeakerEditor(); updateSegmentFilterOptions(); renderSegments();
  selectSegmentForEdit(undo.segment.id, {focus: true});
  setAlert(document.querySelector('#segment-delete-status'), '削除した発話を元に戻しました');
  document.querySelector('#undo-segment-delete').hidden = !deletedSegmentUndo.length;
}

function renderSegmentPage(values, pageIndex = 0) {
  const active = document.activeElement;
  const focusId = active?.closest?.('.segment')?.dataset.segmentId;
  const focusField = active?.dataset.segmentField;
  const selection = typeof active?.selectionStart === 'number' ? [active.selectionStart, active.selectionEnd] : null;
  renderJevComparisonSummary();
  segmentEditor.replaceChildren();
  const offset = pageIndex * SEGMENT_PAGE_SIZE;
  const pageValues = values.slice(offset, offset + SEGMENT_PAGE_SIZE);
  const controls = document.querySelector('#segment-pagination');
  if (controls) {
    controls.hidden = values.length <= SEGMENT_PAGE_SIZE;
    document.querySelector('#segment-page-label').textContent = `${pageIndex + 1} / ${Math.max(1, Math.ceil(values.length / SEGMENT_PAGE_SIZE))}`;
    document.querySelector('#segment-page-previous').disabled = pageIndex === 0;
    document.querySelector('#segment-page-next').disabled = offset + pageValues.length >= values.length;
  }
  document.querySelector('#segment-count').textContent = values.length > SEGMENT_PAGE_SIZE
    ? `表示 ${offset + 1}–${offset + pageValues.length} / 絞込 ${values.length} / 全 ${currentJob.segments.length} 発話`
    : `表示 ${values.length} / 全 ${currentJob.segments.length} 発話`;
  if (!values.length) {
    const empty = document.createElement('div');
    empty.className = 'segment-empty';
    empty.textContent = currentJob.segments.length ? '絞り込み条件に一致する発話はありません。' : '発話はまだありません。「発話を追加」から登録できます。';
    segmentEditor.append(empty);
    return;
  }
  pageValues.forEach((segment, pageOffset) => {
    const index = offset + pageOffset;
    const row = document.createElement('article');
    row.className = `segment${segment.id === selectedSegmentId ? ' selected' : ''}`;
    row.dataset.segmentId = segment.id;
    const meta = document.createElement('div');
    meta.className = 'segment-meta';
    const time = document.createElement('span');
    time.className = 'segment-time';
    time.textContent = `${formatTime(segment.start)}–${formatTime(segment.end)}`;
    const speaker = document.createElement('span');
    speaker.className = 'segment-speaker';
    speaker.dataset.label = segment.speaker || 'UNKNOWN';
    speaker.textContent = displaySpeakerName(speaker.dataset.label);
    speaker.style.borderColor = (currentJob.speaker_profiles[speaker.dataset.label] || {}).theme_color || '';
    meta.append(time, speaker);
    const emotionText = segmentEmotionText(segment);
    if (emotionText) {
      const emotion = document.createElement('span');
      emotion.className = 'segment-emotion';
      emotion.textContent = emotionText;
      meta.append(emotion);
    }
    const agreement = segmentReviewAgreement(segment);
    if (agreement) {
      const agreementLabels = {
        both_flagged: '両方：修正必要',
        current_only: '現行AIのみ',
        jev_only: 'Jevのみ',
        both_clear: '両方：修正不要'
      };
      const badge = document.createElement('span');
      badge.className = `segment-jev-badge ${agreement}`;
      badge.textContent = agreementLabels[agreement] || 'AI判定比較';
      meta.append(badge);
    }
    const play = document.createElement('button');
    play.type = 'button';
    play.className = 'segment-play';
    play.textContent = currentJob.media_url ? '▶ 前後を再生' : '元メディアなし';
    play.disabled = !currentJob.media_url;
    play.addEventListener('click', () => playSegment(segment.id));
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'segment-edit';
    edit.textContent = '発話を編集';
    edit.setAttribute('aria-label', `${speaker.textContent} ${formatTime(segment.start)}の発話を編集`);
    edit.setAttribute('aria-expanded', String(segment.id === selectedSegmentId));
    edit.setAttribute('aria-controls', `segment-edit-body-${index}`);
    edit.addEventListener('click', () => selectSegmentForEdit(segment.id, {focus: true}));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'segment-delete';
    remove.textContent = '発話を削除';
    remove.addEventListener('click', () => {
      deletedSegmentUndo.push({itemId: currentJobId, index: currentJob.segments.findIndex(item => item.id === segment.id), segment: deepCopy(segment)});
      currentJob.segments = currentJob.segments.filter(item => item.id !== segment.id);
      if (selectedSegmentId === segment.id) selectedSegmentId = null;
      setCurrentJobDirty();
      renderSpeakerEditor();
      updateSegmentFilterOptions();
      renderSegments();
    });
    remove.addEventListener('click', () => {
      setAlert(document.querySelector('#segment-delete-status'), '発話を削除しました。保存するまでは元に戻せます');
      const undo = document.querySelector('#undo-segment-delete');
      undo.hidden = false; undo.focus();
    });
    meta.append(edit, play, remove);

    const body = document.createElement('div');
    body.className = 'segment-body';
    body.id = `segment-edit-body-${index}`;
    const fields = document.createElement('div');
    fields.className = 'segment-fields';
    const start = document.createElement('input');
    start.dataset.segmentField = 'start';
    start.type = 'number'; start.min = '0'; start.step = '0.01'; start.value = Number(segment.start || 0).toFixed(2);
    start.addEventListener('change', () => {
      segment.start = Math.max(0, Number(start.value) || 0);
      setCurrentJobDirty();
      renderSpeakerEditor();
      renderSegments();
    });
    const end = document.createElement('input');
    end.dataset.segmentField = 'end';
    end.type = 'number'; end.min = '0'; end.step = '0.01'; end.value = Number(segment.end || 0).toFixed(2);
    end.addEventListener('change', () => {
      segment.end = Math.max(0, Number(end.value) || 0);
      setCurrentJobDirty();
      renderSpeakerEditor();
      renderSegments();
    });
    const speakerInput = document.createElement('select');
    speakerInput.dataset.segmentField = 'speaker';
    speakerLabels().forEach(label => speakerInput.add(new Option(displaySpeakerName(label), label)));
    speakerInput.value = segment.speaker || 'UNKNOWN';
    speakerInput.addEventListener('change', () => {
      segment.speaker = speakerInput.value || 'UNKNOWN';
      setCurrentJobDirty();
      renderSpeakerEditor();
      updateSegmentFilterOptions();
      renderSegments();
    });
    const emotionSelect = document.createElement('select');
    emotionSelect.dataset.segmentField = 'emotion';
    [['', '未設定'], ['neu', '平常'], ['hap', '喜び'], ['ang', '怒り'], ['sad', '悲しみ']].forEach(([value, label]) => emotionSelect.add(new Option(label, value)));
    emotionSelect.value = kushinadaEmotion(segment);
    emotionSelect.addEventListener('change', () => {
      segment.kushinada_label = emotionSelect.value;
      segment.emotions = segment.emotions || {};
      if (emotionSelect.value) {
        const labels = {neu: '平常', hap: '喜び', ang: '怒り', sad: '悲しみ'};
        segment.emotions.kushinada = {...(segment.emotions.kushinada || {}), label: emotionSelect.value, label_ja: labels[emotionSelect.value], model_name: 'くしなだ'};
      } else {
        delete segment.emotions.kushinada;
      }
      setCurrentJobDirty();
      renderSegments();
    });
    fields.append(createField('開始（秒）', start), createField('話者', speakerInput), createField('終了（秒）', end), createField('くしなだ感情', emotionSelect));
    const textarea = document.createElement('textarea');
    textarea.dataset.segmentField = 'text';
    textarea.value = segment.text || '';
    textarea.setAttribute('aria-label', `${speaker.textContent}の発話`);
    const textPreview = document.createElement('p');
    textPreview.className = 'segment-text-preview';
    textPreview.textContent = segment.text || '';
    textarea.addEventListener('input', () => {
      segment.text = textarea.value;
      textPreview.textContent = textarea.value;
      renderConversationParticipation(speakerMetrics());
      setCurrentJobDirty();
    });
    body.append(fields, textPreview, textarea);
    if (segment.ai_review && Array.isArray(segment.ai_review.fragments)) {
      const review = document.createElement('details');
      review.className = 'segment-ai-review';
      const summary = document.createElement('summary');
      summary.textContent = segment.ai_review.noise_candidate
        ? 'AI仕上げ：ノイズ候補あり（自動削除せず保持）' : 'AI仕上げ：修正理由と原文';
      const reasons = document.createElement('p');
      reasons.textContent = segment.ai_review.fragments.map(item => item.reason).filter(Boolean).join(' / ');
      const original = document.createElement('p');
      original.textContent = `校正前：${segment.ai_review.original_text || ''}`;
      const restore = document.createElement('button');
      restore.type = 'button';
      restore.textContent = '校正前の本文に戻す';
      restore.addEventListener('click', () => {
        segment.text = segment.ai_review.original_text || '';
        textarea.value = segment.text;
        textPreview.textContent = segment.text;
        renderConversationParticipation(speakerMetrics());
        setCurrentJobDirty();
      });
      review.append(summary, reasons, original, restore);
      body.append(review);
    }
    if (segment.jev_review && segment.jev_review.comparison) {
      const jevReview = document.createElement('details');
      jevReview.className = 'segment-jev-review';
      const summary = document.createElement('summary');
      const jevNeedsCorrection = segment.jev_review.decision === 'correction_needed';
      const probability = Number(segment.jev_review.correction_needed_probability);
      summary.textContent = `Jev：${jevNeedsCorrection ? '修正が必要' : '修正不要'}${Number.isFinite(probability) ? `（修正必要 ${Math.round(probability * 100)}%）` : ''}`;
      const comparison = segment.jev_review.comparison;
      const decisions = document.createElement('p');
      decisions.textContent = `現行AI：${comparison.current_ai_flagged ? '修正あり' : '修正なし'} ／ Jev：${comparison.jev_flagged ? '修正が必要' : '修正不要'}`;
      const metadata = document.createElement('p');
      const confidence = Number(segment.jev_review.confidence);
      metadata.textContent = [
        segment.jev_review.model ? `モデル ${segment.jev_review.model}` : '',
        Number.isFinite(confidence) ? `確信度 ${Math.round(confidence * 100)}%` : ''
      ].filter(Boolean).join(' ／ ');
      const original = document.createElement('p');
      original.textContent = `判定対象（校正前）：${segment.jev_review.original_text || ''}`;
      jevReview.append(summary, decisions, metadata, original);
      body.append(jevReview);
    }
    row.append(meta, body);
    row.addEventListener('click', event => {
      const isButtonOrDetails = event.target.closest('button, details, select');
      if (isButtonOrDetails) return;

      // 行またはテキストエリアをクリックしたら選択行として展開
      if (selectedSegmentId !== segment.id) {
        selectSegmentForEdit(segment.id);
      }
      // テキストエリア・入力欄自体のクリックでなければメディア再生も連動
      if (!event.target.closest('textarea, input') && currentJob.media_url) {
        playSegment(segment.id);
      }
    });
    segmentEditor.append(row);
  });
  if (focusId && focusField) {
    const row = [...segmentEditor.querySelectorAll('.segment')].find(item => item.dataset.segmentId === focusId);
    const control = row?.querySelector(`[data-segment-field="${focusField}"]`);
    if (control) { control.focus(); if (selection && control.setSelectionRange) control.setSelectionRange(...selection); }
  }
}

function updateSpeakerBadges() {
  renderConversationParticipation(speakerMetrics());
  document.querySelectorAll('.segment-speaker').forEach(badge => {
    const label = badge.dataset.label;
    badge.textContent = displaySpeakerName(label);
    badge.style.borderColor = (currentJob.speaker_profiles[label] || {}).theme_color || '';
  });
}

async function rerunSpeakerIdentification() {
  if (!currentJobId || !currentJob || !rerunSpeakerIdentificationButton
      || rerunSpeakerIdentificationButton.disabled) return;
  if (currentJobDirty) {
    setAlert(document.querySelector('#save-message'), '編集内容を保存してから話者名を再特定してください。', true);
    return;
  }
  const provider = speakerIdentityProvider ? speakerIdentityProvider.value : 'openai';
  const owner = {id: currentJobId, job: currentJob, navigation: resultRequestSequence,
    mutation: currentJobMutationGeneration};
  const ownsScreen = () => currentJobId === owner.id && resultRequestSequence === owner.navigation;
  rerunSpeakerIdentificationButton.disabled = true;
  if (speakerIdentityProvider) speakerIdentityProvider.disabled = true;
  if (speakerIdentityStatus) speakerIdentityStatus.textContent = '自己紹介候補の抽出と話者IDの再確認を実行しています…';
  setAlert(document.querySelector('#save-message'), '');
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(owner.id)}/speaker-identification`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        provider,
        revision_count: Number(currentJob.revision_count || 0)
      })
    });
    const data = await readJsonResponse(response);
    if (!ownsScreen() || currentJob !== owner.job) return;
    if (!response.ok) throw new Error(data.error || '話者名を再特定できませんでした。');
    if (currentJobMutationGeneration !== owner.mutation || currentJobDirty) {
      resultSaveConflict = true;
      showDraftRecovery('transcript');
      setAlert(document.querySelector('#save-message'),
        '話者の再特定は保存済みです。編集中の内容は保持しました。未保存内容を退避してから再読み込みしてください。', true);
      return;
    }
    const summary = data.speaker_identity || {};
    renderResult(data);
    owner.job = currentJob;
    owner.navigation = resultRequestSequence;
    const ambiguousCount = Object.keys(summary.ambiguous_labels || {}).length
      + Object.keys(summary.duplicate_names || {}).length;
    const repairs = summary.repairs || {};
    const repairedSegments = Math.max(0, Number(repairs.aliased_segments) || 0)
      + Math.max(0, Number(repairs.corrected_segments) || 0);
    const registeredCount = Object.keys((summary.registration || {}).created || {}).length;
    const hasChanges = Boolean(summary.applied_count || repairedSegments || registeredCount);
    const nameMessage = summary.applied_count
      ? `${summary.applied_count}名を話者IDへ反映しました。`
      : '新たに反映できる話者名はありませんでした。';
    const registrationMessage = registeredCount
      ? ` ${registeredCount}名を話者管理へ登録しました。`
      : '';
    const repairMessage = repairedSegments
      ? ` 話者ラベルの重複・断裂を${repairedSegments}発話修正しました。`
      : '';
    const ambiguityMessage = ambiguousCount
      ? ` 一意に特定できない${ambiguousCount}件は反映していません。`
      : '';
    const message = nameMessage + registrationMessage + repairMessage + ambiguityMessage;
    if (registeredCount && !speakerRegistryDirty) await loadSpeakerRegistry(true);
    if (!ownsScreen() || currentJobMutationGeneration !== owner.mutation) return;
    if (speakerIdentityStatus) speakerIdentityStatus.textContent = message;
    setAlert(document.querySelector('#save-message'), message, !hasChanges);
  } catch (error) {
    if (!ownsScreen()) return;
    if (speakerIdentityStatus) speakerIdentityStatus.textContent = error.message;
    setAlert(document.querySelector('#save-message'), error.message, true);
  } finally {
    if (ownsScreen()) {
      rerunSpeakerIdentificationButton.disabled = false;
      if (speakerIdentityProvider) speakerIdentityProvider.disabled = false;
    }
  }
}

async function rerunOutline() {
  if (!currentJobId || !currentJob || !outlineRerunButton || outlineRerunButton.disabled) return;
  const say = (text, isError = false) => {
    if (outlineRerunStatus) { outlineRerunStatus.textContent = text; outlineRerunStatus.dataset.error = isError ? '1' : ''; }
  };
  if (currentJobDirty) {
    say('編集内容を保存してからアウトラインを再実行してください。', true);
    return;
  }
  if (currentJob.outline && !window.confirm('現在のアウトラインを新しい結果で置き換えます。AIの利用料がかかります。実行しますか？')) return;
  const owner = {id: currentJobId, job: currentJob, navigation: resultRequestSequence,
    mutation: currentJobMutationGeneration};
  const ownsScreen = () => currentJobId === owner.id && resultRequestSequence === owner.navigation;
  outlineRerunButton.disabled = true;
  if (outlineRerunProvider) outlineRerunProvider.disabled = true;
  say('会話全体からアウトラインと全体要約を作成しています。長い会話では数分かかります…');
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(owner.id)}/outline`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        provider: outlineRerunProvider ? outlineRerunProvider.value : 'openai',
        revision_count: Number(currentJob.revision_count || 0)
      })
    });
    const data = await readJsonResponse(response);
    if (!ownsScreen() || currentJob !== owner.job) return;
    if (!response.ok) throw new Error(data.error || 'アウトラインを再実行できませんでした。');
    if (currentJobMutationGeneration !== owner.mutation || currentJobDirty) {
      say('アウトラインは保存済みです。編集中の内容を保持したため、保存後に再読み込みすると反映されます。', true);
      return;
    }
    renderResult(data);
    owner.job = currentJob;
    owner.navigation = resultRequestSequence;
    say(`アウトラインを作り直しました（${(data.outline_run || {}).section_count || 0}議題）。`);
  } catch (error) {
    if (ownsScreen()) say(error.message, true);
  } finally {
    if (ownsScreen()) {
      outlineRerunButton.disabled = false;
      if (outlineRerunProvider) outlineRerunProvider.disabled = false;
    }
  }
}

function playSegment(segmentId) {
  if (!mediaPlayer || !currentJob) return;
  const segment = currentJob.segments.find(item => item.id === segmentId);
  if (!segment) return;
  selectedSegmentId = segmentId;
  if (activeItemTab !== 'transcript') setItemTab('transcript');
  const context = Number(document.querySelector('#play-context').value) || 5;
  const start = Math.max(0, Number(segment.start || 0) - context);
  playbackStopAt = Number(segment.end || segment.start || 0) + context;
  document.querySelector('#media-caption').textContent = `${formatTime(segment.start)}–${formatTime(segment.end)} / ${displaySpeakerName(segment.speaker)}（前後 ${context} 秒）`;
  mediaPlayer.currentTime = start;
  const promise = mediaPlayer.play();
  if (promise) promise.catch(() => {});
  selectSegmentForEdit(segmentId);
  mediaReview.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function adjacentSegment(direction) {
  if (!currentJob || !currentJob.segments.length) return;
  const ordered = [...currentJob.segments].sort((a, b) => Number(a.start || 0) - Number(b.start || 0));
  let index = ordered.findIndex(segment => segment.id === selectedSegmentId);
  if (index < 0) index = direction > 0 ? -1 : ordered.length;
  index = Math.max(0, Math.min(ordered.length - 1, index + direction));
  playSegment(ordered[index].id);
}


// 原本と編集世代を鍵にし、ページ移動では再検索も本文の複製も行わない。
const SEGMENT_PAGE_SIZE = 100;
let segmentRenderGeneration = 0, segmentPageIndex = 0, segmentSelectionCache = null;
function renderSegments({page = null, focusSegmentId = '', focus = false} = {}) {
  const generation = ++segmentRenderGeneration, owner = currentJob;
  if (!owner) { segmentEditor.replaceChildren(); return; }
  const mutation = currentJobMutationGeneration;
  const signature = JSON.stringify(transcriptSelectionQuery());
  const cached = segmentSelectionCache;
  const same = cached?.owner === owner && cached.mutation === mutation
    && cached.length === owner.segments.length && cached.signature === signature;
  const apply = indices => {
    if (!indices || currentJob !== owner || generation !== segmentRenderGeneration) return;
    if (mutation !== currentJobMutationGeneration) {
      renderSegments({page, focusSegmentId, focus});
      return;
    }
    segmentEditor.removeAttribute('aria-busy');
    segmentSelectionCache = {owner, mutation, length: owner.segments.length, signature, indices};
    if ((!same && cached?.signature !== signature) || cached?.owner !== owner) segmentPageIndex = 0;
    if (Number.isInteger(page)) segmentPageIndex = page;
    const focusIndex = focusSegmentId ? indices.findIndex(index => owner.segments[index]?.id === focusSegmentId) : -1;
    if (focusIndex >= 0) segmentPageIndex = Math.floor(focusIndex / SEGMENT_PAGE_SIZE);
    segmentPageIndex = Math.max(0, Math.min(segmentPageIndex, Math.ceil(indices.length / SEGMENT_PAGE_SIZE) - 1));
    renderSegmentPage(indices.map(index => owner.segments[index]), segmentPageIndex);
    if (focusIndex >= 0) selectSegmentForEdit(focusSegmentId, {focus});
  };
  if (same) { apply(cached.indices); return; }
  const payload = transcriptSelectionInput();
  if (owner.segments.length < 1000) { apply(GurumojiTranscriptMath.select(payload)); return; }
  if (cached?.owner !== owner) segmentEditor.replaceChildren();
  segmentEditor.setAttribute('aria-busy', 'true');
  document.querySelector('#segment-count').textContent = '発話を絞り込んでいます…';
  GurumojiTranscriptTasks.select(payload).then(apply).catch(() => {
    if (generation !== segmentRenderGeneration || currentJob !== owner) return;
    segmentEditor.removeAttribute('aria-busy');
    document.querySelector('#segment-count').textContent = '発話を表示できませんでした。条件を変更して再試行してください。';
  });
}
document.querySelector('#segment-page-previous')?.addEventListener('click', () => renderSegments({page: segmentPageIndex - 1}));
document.querySelector('#segment-page-next')?.addEventListener('click', () => renderSegments({page: segmentPageIndex + 1}));
