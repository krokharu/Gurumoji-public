/* 公開版の画面処理: library。共有状態はapp.jsで管理する。 */
function libraryFilterState() {
  return {
    keyword: document.querySelector('#library-keyword').value.trim(),
    speaker: document.querySelector('#library-speaker').value,
    emotion: document.querySelector('#library-emotion').value,
    group: document.querySelector('#library-group').value,
    data_group: document.querySelector('#library-data-group')?.value || '',
    tag: document.querySelector('#library-tag')?.value || '',
    sort: document.querySelector('#library-sort').value,
    recorded_from: document.querySelector('#library-recorded-from')?.value || '',
    recorded_to: document.querySelector('#library-recorded-to')?.value || '',
    media_duration_min: document.querySelector('#library-media-duration-min')?.value || '',
    media_duration_max: document.querySelector('#library-media-duration-max')?.value || ''
  };
}

function updateLibraryFilterState() {
  const state = libraryFilterState();
  const conditions = [];
  if (state.keyword) conditions.push(`「${state.keyword}」`);
  if (state.speaker) conditions.push(`話者: ${state.speaker}`);
  if (state.emotion) conditions.push(`感情: ${state.emotion}`);
  if (state.data_group) conditions.push(`分析グループ: ${document.querySelector('#library-data-group').selectedOptions[0].textContent}`);
  if (state.tag) conditions.push(`タグ: ${document.querySelector('#library-tag').selectedOptions[0].textContent}`);
  if (state.recorded_from) conditions.push(`収録日: ${state.recorded_from}以降`);
  if (state.recorded_to) conditions.push(`収録日: ${state.recorded_to}以前`);
  if (state.media_duration_min) conditions.push(`メディア: ${state.media_duration_min}秒以上`);
  if (state.media_duration_max) conditions.push(`メディア: ${state.media_duration_max}秒以下`);
  if (state.group) {
    const group = document.querySelector('#library-group');
    conditions.push(`フォルダー: ${group.options[group.selectedIndex].text}`);
  }
  if (state.sort !== 'updated_desc') {
    const sort = document.querySelector('#library-sort');
    conditions.push(`並び: ${sort.options[sort.selectedIndex].text}`);
  }
  const summary = document.querySelector('#library-filter-summary');
  const badge = document.querySelector('#library-filter-badge');
  const clear = document.querySelector('#library-clear-filters');
  if (summary) summary.textContent = conditions.length
    ? `${conditions.join(' / ')} で表示しています`
    : 'すべてのデータを表示しています';
  if (badge) badge.textContent = conditions.length ? `${conditions.length}条件` : '条件なし';
  if (clear) clear.disabled = conditions.length === 0;
}

function renderLibraryLoading() {
  const list = document.querySelector('#library-list');
  list.replaceChildren();
  for (let index = 0; index < 3; index += 1) {
    const skeleton = document.createElement('div');
    skeleton.className = 'library-skeleton';
    skeleton.setAttribute('aria-hidden', 'true');
    skeleton.innerHTML = '<i></i><div><b></b><span></span><span></span></div>';
    list.append(skeleton);
  }
}

function renderLibraryOverview(items) {
  const hasTime = item => item.duration !== null && item.duration !== undefined && item.duration !== ''
    && typeof item.duration !== 'boolean' && Number.isFinite(Number(item.duration)) && Number(item.duration) >= 0;
  const known = items.filter(hasTime);
  const duration = known.reduce((sum, item) => sum + Number(item.duration), 0);
  const missing = items.filter(item => !hasTime(item) || item.missing_time_turn_count > 0).length;
  const speakers = new Set(items.flatMap(item => item.speakers || []));
  const latest = items.reduce((value, item) => {
    const updated = String(item.updated_at || '');
    return updated > value ? updated : value;
  }, '');
  const values = {
    '#library-total-metric': String(items.length),
    '#library-duration-metric': !items.length ? '—' : !known.length ? '時刻不明'
      : missing ? `時刻あり計 ${formatTime(duration)} / 欠測あり${missing}件` : formatTime(duration),
    '#library-speaker-metric': String(speakers.size),
    '#library-updated-metric': latest ? formatDate(latest) : '—'
  };
  Object.entries(values).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  });
}

async function loadLibraryTrash() {
  const panel = document.querySelector('#library-trash');
  if (!panel) return;
  const list = panel.querySelector('[data-trash-list]');
  try {
    const response = await apiFetch('/api/library/trash', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'ゴミ箱を読み込めませんでした。');
    const entries = data.entries || [];
    const days = Number(data.retention_days || 0);
    panel.querySelector('[data-trash-summary]').textContent = `（${entries.length}件・${formatBytes(data.total_bytes || 0)}）`;
    panel.querySelector('[data-trash-note]').textContent = days
      ? `削除した会話はここに移り、${days}日後に自動で完全に削除されます。それまでは復元できます。`
      : '削除した会話はここに移り、完全に削除するまで残ります（自動削除なし）。';
    list.replaceChildren();
    if (!entries.length) {
      list.textContent = 'ゴミ箱は空です。';
      return;
    }
    entries.forEach(entry => {
      const row = document.createElement('div');
      row.className = 'library-trash-row';
      const label = document.createElement('span');
      label.textContent = `${entry.source_name || entry.item_id} / 削除 ${formatDate(entry.deleted_at)}`
        + `${entry.expires_at ? ` / 自動削除 ${formatDate(entry.expires_at)}` : ''} / ${formatBytes(entry.bytes || 0)}`;
      const restore = document.createElement('button');
      restore.type = 'button';
      restore.className = 'secondary-button compact-button';
      restore.textContent = '復元';
      restore.disabled = !entry.restorable;
      restore.addEventListener('click', () => changeLibraryTrash(entry, 'restore'));
      const purge = document.createElement('button');
      purge.type = 'button';
      purge.className = 'secondary-button compact-button danger';
      purge.textContent = '完全に削除';
      purge.addEventListener('click', () => changeLibraryTrash(entry, 'purge'));
      row.append(label, restore, purge);
      list.append(row);
    });
  } catch (error) {
    list.textContent = error.message;
  }
}

async function changeLibraryTrash(entry, action) {
  const name = entry.source_name || entry.item_id;
  if (action === 'purge' && !window.confirm(`「${name}」をゴミ箱から完全に削除しますか？\n元に戻せません。`)) return;
  const message = document.querySelector('#library-message');
  try {
    const url = `/api/library/trash/${encodeURIComponent(entry.id)}${action === 'restore' ? '/restore' : ''}`;
    const response = await apiFetch(url, {method: action === 'restore' ? 'POST' : 'DELETE'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '操作できませんでした。');
    if (action === 'restore') await loadLibrary(); else await loadLibraryTrash();
    setAlert(message, `「${name}」：${data.message}`);
  } catch (error) {
    setAlert(message, error.message, true);
  }
}

async function loadLibrary(pageOffset = 0) {
  const list = document.querySelector('#library-list');
  const message = document.querySelector('#library-message');
  setAlert(message, '');
  updateLibraryFilterState();
  const state = libraryFilterState();
  const filterKey = JSON.stringify(state);
  libraryPageOffset = filterKey === libraryPageFilter && Number.isInteger(pageOffset) ? pageOffset : 0;
  libraryPageFilter = filterKey;
  const params = new URLSearchParams(state);
  params.set('limit', '50'); params.set('offset', String(libraryPageOffset));
  // Preserve the existing unfiltered request shape for offline fixtures and clients.
  ['recorded_from', 'recorded_to', 'media_duration_min', 'media_duration_max', 'data_group', 'tag'].forEach(key => {
    if (state[key] === '') params.delete(key);
  });
  if (libraryRequestController) libraryRequestController.abort();
  libraryRequestController = new AbortController();
  const requestId = ++libraryRequestSequence;
  list.setAttribute('aria-busy', 'true');
  renderLibraryLoading();
  try {
    const response = await apiFetch(`/api/library?${params}`, {signal: libraryRequestController.signal});
    const data = await readJsonResponse(response);
    if (requestId !== libraryRequestSequence) return;
    if (!response.ok) throw new Error(data.error || '処理済みデータの一覧を取得できません。');
    updateFacetSelect(document.querySelector('#library-speaker'), data.facets.speakers || [], 'すべての話者');
    updateFacetSelect(document.querySelector('#library-emotion'), data.facets.emotions || [], 'すべての感情');
    libraryGroups = Array.isArray(data.groups) ? data.groups : [];
    document.dispatchEvent(new CustomEvent('gurumoji-library-catalog', {detail: data}));
    updateLibraryGroupSelect(document.querySelector('#library-group'), libraryGroups, {includeAll: true});
    const items = data.items || [];
    document.querySelector('#library-count').textContent = `${data.total}件中 ${libraryPageOffset + (items.length ? 1 : 0)}〜${libraryPageOffset + items.length}件を表示`;
    const pager = document.querySelector('#library-pagination');
    if (pager) {
      pager.replaceChildren();
      const previous = contentButton('前の50件', () => loadLibrary(Math.max(0, libraryPageOffset - 50)));
      previous.disabled = libraryPageOffset === 0;
      const next = contentButton('次の50件', () => loadLibrary(libraryPageOffset + 50));
      next.disabled = !data.pagination?.has_more;
      pager.append(previous, next);
    }
    renderLibraryOverview(items);
    renderLibraryItems(items);
    updateLibraryFilterState();
    loadLibraryTrash();
    if (!trainingStatusLoaded) loadTrainingStatus();
  } catch (error) {
    if (error.name === 'AbortError') return;
    if (requestId !== libraryRequestSequence) return;
    list.replaceChildren();
    setAlert(message, error.message, true);
  } finally {
    if (requestId === libraryRequestSequence) list.setAttribute('aria-busy', 'false');
  }
}

function renderLibraryItems(items) {
  const list = document.querySelector('#library-list');
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'library-empty';
    const title = document.createElement('strong');
    title.textContent = '条件に一致するデータはありません';
    const description = document.createElement('p');
    description.textContent = '検索条件を変えるか、新しい文字起こしを始めてください。';
    const actions = document.createElement('div');
    const clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'secondary-button';
    clear.textContent = '条件をクリア';
    clear.addEventListener('click', clearLibraryFilters);
    const create = document.createElement('button');
    create.type = 'button';
    create.className = 'primary-button small';
    create.textContent = '＋ 新しい文字起こし';
    create.addEventListener('click', () => showView('new'));
    actions.append(clear, create);
    empty.append(title, description, actions);
    list.append(empty);
    return;
  }
  const grouped = document.querySelector('#library-sort').value === 'group';
  const visibleGroupCounts = items.reduce((counts, item) => {
    const key = item.group_id || '__ungrouped__';
    counts.set(key, (counts.get(key) || 0) + 1);
    return counts;
  }, new Map());
  let previousGroupKey = null;
  items.forEach(item => {
    const groupKey = item.group_id || '__ungrouped__';
    if (grouped && groupKey !== previousGroupKey) {
      const heading = document.createElement('div');
      heading.className = 'library-group-heading';
      const name = document.createElement('strong');
      name.textContent = item.group_name || '未分類';
      const count = document.createElement('span');
      count.textContent = `${visibleGroupCounts.get(groupKey) || 0}件`;
      heading.append(name, count);
      list.append(heading);
      previousGroupKey = groupKey;
    }
    const card = document.createElement('article');
    card.className = 'library-item';
    const media = document.createElement('div');
    media.className = 'library-media';
    const mediaFallback = document.createElement('span');
    mediaFallback.className = 'library-media-fallback';
    mediaFallback.textContent = 'プレビューなし';
    const mediaBadge = document.createElement('span');
    mediaBadge.className = 'library-media-badge';
    mediaBadge.textContent = item.media_url ? (item.media_kind === 'video' ? '動画' : '音声') : 'テキスト';
    media.classList.add("unavailable");
    media.append(mediaFallback, mediaBadge);
    const body = document.createElement('div');
    body.className = 'library-item-body';
    const heading = document.createElement('div');
    heading.className = 'library-item-heading';
    const title = document.createElement('h3');
    title.textContent = item.source_name;
    const updated = document.createElement('time');
    updated.dateTime = item.updated_at || '';
    updated.textContent = `更新 ${formatDate(item.updated_at)}`;
    heading.append(title, updated);
    const meta = document.createElement('div');
    meta.className = 'library-meta';
    const mediaLabel = item.media_url ? (item.media_kind === 'video' ? '動画あり' : '音声あり') : '元メディアなし';
    [
      `発話 ${item.segment_count}件`,
      `収録日 ${item.media_created_at ? String(item.media_created_at).slice(0, 10) : '不明'}`,
      `メディア ${item.media_duration_seconds == null ? '不明' : item.media_duration_seconds < 1 ? `${item.media_duration_seconds}秒` : formatTime(item.media_duration_seconds)}`,
      `最終時刻 ${transcriptEndpointText(item.duration, item.timed_turn_count, item.missing_time_turn_count)}`,
      mediaLabel,
      `修正 ${item.revision_count}回`
    ].forEach(value => {
      const metric = document.createElement('span');
      metric.textContent = value;
      meta.append(metric);
    });
    const preview = document.createElement('p');
    preview.className = 'library-preview';
    preview.textContent = item.preview || '本文はまだありません。';
    const chips = document.createElement('div');
    chips.className = 'library-chips';
    if (item.group_name) {
      const chip = document.createElement('span');
      chip.className = 'library-chip group';
      chip.textContent = item.group_name;
      chips.append(chip);
    }
    (item.speakers || []).slice(0, 5).forEach(value => {
      const chip = document.createElement('span');
      chip.className = 'library-chip';
      chip.textContent = value;
      chips.append(chip);
    });
    if ((item.speakers || []).length > 5) {
      const chip = document.createElement('span');
      chip.className = 'library-chip';
      chip.textContent = `＋${item.speakers.length - 5}人`;
      chips.append(chip);
    }
    (item.emotions || []).forEach(value => {
      const chip = document.createElement('span');
      chip.className = 'library-chip emotion';
      chip.textContent = value;
      chips.append(chip);
    });
    if (item.match_count) {
      const chip = document.createElement('span');
      chip.className = 'library-chip';
      chip.textContent = `キーワード一致 ${item.match_count}発話`;
      chips.append(chip);
    }
    body.append(heading, meta, preview, chips);
    const actions = document.createElement('div');
    actions.className = 'library-actions';
    const groupLabel = document.createElement('label');
    groupLabel.className = 'library-group-assignment';
    const groupLabelText = document.createElement('span');
    groupLabelText.className = 'visually-hidden';
    groupLabelText.textContent = `${item.source_name}のフォルダー`;
    const groupSelect = document.createElement('select');
    groupSelect.setAttribute('aria-label', `${item.source_name}のフォルダー`);
    updateLibraryGroupSelect(groupSelect, libraryGroups, {includeUngrouped: true});
    groupSelect.value = item.group_id || '';
    groupSelect.addEventListener('click', event => event.stopPropagation());
    groupSelect.addEventListener('change', () => assignLibraryItemGroup(item, groupSelect));
    groupLabel.append(groupLabelText, groupSelect);
    const open = document.createElement('button');
    open.className = 'library-card-open';
    open.type = 'button';
    open.setAttribute('aria-label', `${item.source_name}を開いて編集`);
    open.addEventListener('click', () => openLibraryItem(item.id));


    const remove = document.createElement('button');
    remove.className = 'library-delete-button';
    remove.type = 'button';
    remove.textContent = '削除';
    remove.setAttribute('aria-label', `${item.source_name}を削除`);
    remove.addEventListener('click', () => deleteLibraryItem(item.id, item.source_name));
    actions.append(groupLabel, remove);
    card.append(open, media, body, actions);
    list.append(card);
  });
}

async function loadTrainingStatus() {
  const container = document.querySelector('#training-status');
  if (trainingStatusLoaded) return;
  trainingStatusLoaded = true;
  try {
    const response = await apiFetch('/api/training');
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '学習履歴を確認できませんでした。');
    container.replaceChildren();
    const label = document.createElement('span');
    label.textContent = `くしなだ学習データ: ${data.event_count}件（音声＋感情 ${data.ready_count}件）`;
    container.append(label);
    if (data.jsonl_url) {
      const link = document.createElement('a');
      link.href = data.jsonl_url;
      link.textContent = 'JSONL';
      link.download = '';
      container.append(link);
    }
    if (data.manifest_url) {
      const link = document.createElement('a');
      link.href = data.manifest_url;
      link.textContent = 'CSV';
      link.download = '';
      container.append(link);
    }
  } catch (error) {
    trainingStatusLoaded = false;
    container.textContent = error.message || '学習履歴を確認できませんでした。';
  }
}

function clearLibraryFilters() {
  document.querySelector('#library-keyword').value = '';
  document.querySelector('#library-speaker').value = '';
  document.querySelector('#library-emotion').value = '';
  document.querySelector('#library-group').value = '';
  document.querySelector('#library-sort').value = 'updated_desc';
  ['#library-recorded-from', '#library-recorded-to', '#library-media-duration-min', '#library-media-duration-max', '#library-data-group', '#library-tag'].forEach(selector => {
    const input = document.querySelector(selector);
    if (input) input.value = '';
  });
  updateLibraryFilterState();
  loadLibrary();
}

function setLibraryFiltersOpen(open) {
  if (!libraryCard) return;
  libraryCard.classList.toggle('filters-open', open);
  const toggle = document.querySelector('#library-filter-toggle');
  if (toggle) toggle.setAttribute('aria-expanded', String(open));
}

async function loadLibraryGroupManager() {
  setAlert(libraryGroupMessage, '読み込み中…');
  try {
    const response = await apiFetch('/api/library?limit=1&offset=0');
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'フォルダーを取得できませんでした。');
    libraryGroups = Array.isArray(data.groups) ? data.groups : [];
    renderLibraryGroupManager();
    setAlert(libraryGroupMessage, '');
  } catch (error) {
    setAlert(libraryGroupMessage, error.message, true);
  }
}

function openAddRecordDialog() {
  setAlert(document.querySelector('#add-record-error'), '');
  if (addRecordName) addRecordName.value = '';
  if (addRecordDialog && typeof addRecordDialog.showModal === 'function') {
    addRecordDialog.showModal();
    window.requestAnimationFrame(() => addRecordName && addRecordName.focus());
    return;
  }
  const fallbackName = window.prompt('追加するデータの名前を入力してください。', '新規文字起こし');
  if (fallbackName && fallbackName.trim()) createEmptyLibraryRecord(fallbackName.trim());
}

async function createEmptyLibraryRecord(sourceName) {
  try {
    const response = await apiFetch('/api/library', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source_name: sourceName})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '追加できませんでした。');
    if (addRecordDialog && addRecordDialog.open) addRecordDialog.close();
    renderResult(data);
  } catch (error) {
    const target = addRecordDialog && addRecordDialog.open
      ? document.querySelector('#add-record-error')
      : document.querySelector('#library-message');
    setAlert(target, error.message, true);
  } finally {
    const button = document.querySelector('#confirm-add-record-button');
    if (button) button.disabled = false;
  }
}

async function openLibraryItem(itemId) {
  const requestSequence = ++resultRequestSequence;
  try {
    const response = await apiFetch(`/api/library/${itemId}`);
    const data = await readJsonResponse(response);
    if (requestSequence !== resultRequestSequence) return;
    if (!response.ok) throw new Error(data.error || 'データを開けませんでした。');
    renderResult(data);
  } catch (error) {
    if (requestSequence === resultRequestSequence) {
      setAlert(document.querySelector('#library-message'), error.message, true);
    }
  }
}

function deleteRecoveryNote(data) {
  const paths = Array.isArray(data && data.recovery_paths)
    ? data.recovery_paths
      .map(value => String(value || '').trim())
      .filter(Boolean)
    : [];
  return paths.length ? ` 復旧・確認先: ${paths.join(' / ')}` : '';
}

async function deleteLibraryItem(itemId, name) {
  if (deletingLibraryItems.has(itemId)) return;
  if (!window.confirm(`「${name}」を処理済みデータから削除しますか？\n会話と保存メディアはゴミ箱に移り、保持期間を過ぎると自動で完全に削除されます。それまではゴミ箱から復元できます。出力ファイルと学習履歴は残ります。`)) return;
  deletingLibraryItems.add(itemId);
  const fromResult = currentJobId === itemId && !resultCard.hidden;
  const message = document.querySelector(fromResult ? '#save-message' : '#library-message');
  const suspendedPlayer = currentJobId === itemId ? mediaPlayer : null;
  const suspendedTime = suspendedPlayer?.currentTime || 0;
  const suspendedSource = suspendedPlayer?.getAttribute('src');
  if (fromResult && deleteRecordButton) deleteRecordButton.disabled = true;
  setAlert(message, 'ゴミ箱へ移動しています…');
  try {
    if (suspendedPlayer) {
      suspendedPlayer.pause();
      suspendedPlayer.removeAttribute('src');
      suspendedPlayer.load();
    }
    const response = await apiFetch(`/api/library/${itemId}`, {method: 'DELETE'});
    const data = await readJsonResponse(response);
    const recoveryNote = deleteRecoveryNote(data);
    if (!response.ok) {
      throw new Error(`${data.error || '削除できませんでした。'}${recoveryNote}`);
    }
    if (currentJobId === itemId) {
      currentJobId = null;
      currentJob = null;
      storeActiveJobId('');
      setCurrentJobDirty(false);
    }


    showView('library');
    await loadLibrary();
    const cleanupWarning = data.cleanup_warning || '';
    setAlert(
      document.querySelector('#library-message'),
      `「${name}」をゴミ箱に移しました。${cleanupWarning}${recoveryNote}`,
      Boolean(cleanupWarning || recoveryNote)
    );
  } catch (error) {
    if (suspendedPlayer && suspendedSource && currentJobId === itemId) {
      suspendedPlayer.src = suspendedSource;
      suspendedPlayer.addEventListener('loadedmetadata', () => { suspendedPlayer.currentTime = suspendedTime; }, {once: true});
      suspendedPlayer.load();
    }
    setAlert(message, error.message, true);
  } finally {
    deletingLibraryItems.delete(itemId);
    if (fromResult && deleteRecordButton) deleteRecordButton.disabled = false;
  }
}


function updateFacetSelect(select, values, allLabel) {
  const selected = select.value;
  select.replaceChildren(new Option(allLabel, ''));
  values.forEach(value => select.add(new Option(value, value)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

function updateLibraryGroupSelect(select, groups, {includeAll = false, includeUngrouped = false} = {}) {
  if (!select) return;
  const selected = select.value;
  select.replaceChildren();
  if (includeAll) select.add(new Option('すべてのフォルダー', ''));
  if (includeAll || includeUngrouped) select.add(new Option('未分類', includeAll ? '__ungrouped__' : ''));
  groups.forEach(group => select.add(new Option(`${group.name}（${group.item_count || 0}件）`, group.id)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

async function assignLibraryItemGroup(item, select) {
  const previous = item.group_id || '';
  select.disabled = true;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(item.id)}/group`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({group_id: select.value})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'フォルダーを変更できませんでした。');
    await loadLibrary();
  } catch (error) {
    select.value = previous;
    select.disabled = false;
    setAlert(document.querySelector('#library-message'), error.message, true);
  }
}

function renderLibraryGroupManager() {
  if (!libraryGroupList) return;
  libraryGroupList.replaceChildren();
  if (!libraryGroups.length) {
    const empty = document.createElement('p');
    empty.className = 'library-group-empty';
    empty.textContent = 'フォルダーはまだありません。上の欄から作成できます。';
    libraryGroupList.append(empty);
    return;
  }
  libraryGroups.forEach(group => {
    const row = document.createElement('div');
    row.className = 'library-group-row';
    const field = document.createElement('label');
    field.className = 'field';
    const label = document.createElement('span');
    label.textContent = `${group.item_count || 0}件`;
    const input = document.createElement('input');
    input.type = 'text';
    input.maxLength = 80;
    input.value = group.name;
    input.setAttribute('aria-label', `${group.name}のフォルダー名`);
    field.append(label, input);
    const save = document.createElement('button');
    save.type = 'button';
    save.className = 'secondary-button compact-button';
    save.textContent = '名前を保存';
    save.addEventListener('click', async () => {
      save.disabled = true;
      try {
        const response = await apiFetch(`/api/library/groups/${encodeURIComponent(group.id)}`, {
          method: 'PUT', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name: input.value})
        });
        const data = await readJsonResponse(response);
        if (!response.ok) throw new Error(data.error || 'フォルダー名を変更できませんでした。');
        await loadLibrary();
        renderLibraryGroupManager();
        setAlert(libraryGroupMessage, 'フォルダー名を変更しました。');
      } catch (error) {
        save.disabled = false;
        setAlert(libraryGroupMessage, error.message, true);
      }
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'secondary-button danger compact-button';
    remove.textContent = '削除';
    remove.addEventListener('click', async () => {
      const count = Number(group.item_count || 0);
      const note = count ? `\n所属する${count}件のデータは「未分類」に戻ります。` : '';
      if (!window.confirm(`フォルダー「${group.name}」を削除しますか？${note}\n処理済みデータ本体は削除されません。`)) return;
      remove.disabled = true;
      try {
        const response = await apiFetch(`/api/library/groups/${encodeURIComponent(group.id)}`, {method: 'DELETE'});
        const data = await readJsonResponse(response);
        if (!response.ok) throw new Error(data.error || 'フォルダーを削除できませんでした。');
        await loadLibrary();
        renderLibraryGroupManager();
        setAlert(libraryGroupMessage, `「${group.name}」を削除しました。`);
      } catch (error) {
        remove.disabled = false;
        setAlert(libraryGroupMessage, error.message, true);
      }
    });
    row.append(field, save, remove);
    libraryGroupList.append(row);
  });
}
