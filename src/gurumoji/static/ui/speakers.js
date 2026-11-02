function surveyQuestionKeys(records = speakerRegistry) {

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
    '#registry-survey-metric': surveyQuestionKeys(speakerRegistry).length
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
