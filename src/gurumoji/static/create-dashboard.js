/* Create-screen dashboard (Stitch design). Every control here is a proxy for a field
   app.js already owns, so the form still submits the same data. The few new behaviours
   (presets, tag/group assignment after a run) use existing APIs or the browser only. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const fire = (element, type) => element.dispatchEvent(new Event(type, {bubbles: true}));
  const swallowEnter = element => element && element.addEventListener('keydown', event => {
    if (event.key === 'Enter') event.preventDefault();
  });
  if (typeof form === 'undefined' || !form || !$('.stitch-topbar')) return;

  // ヘッダーの時計
  const clock = $('#app-clock');
  const tickClock = () => {
    if (clock) clock.textContent = `${new Date().toLocaleTimeString('ja-JP', {hour12: false, timeZone: 'Asia/Tokyo'})} JST`;
  };
  tickClock();
  window.setInterval(tickClock, 1000);

  // ヘッダーの実寸をサイドバー・設定画面の配置にも反映する。
  const appBar = $('.app-bar');
  const syncAppBarHeight = () => {
    const height = Math.ceil(appBar?.getBoundingClientRect().height || 0);
    if (height) document.documentElement.style.setProperty('--app-bar-height', `${height}px`);
  };
  if (appBar && typeof ResizeObserver !== 'undefined') new ResizeObserver(syncAppBarHeight).observe(appBar);
  window.addEventListener('resize', syncAppBarHeight);
  syncAppBarHeight();

  $$('[data-open-connection]').forEach(button => {
    if (!button.closest('.create-sidebar')) button.addEventListener('click', () => $('#connection-button')?.click());
  });

  // ---- Settings drawer: on a wide screen the 詳細設定 card slides in instead of sitting below the page ----
  const drawer = $('#setup-settings');
  const backdrop = $('#stitch-backdrop');
  const wideScreen = window.matchMedia('(min-width: 1280px)');
  const closeDrawer = () => {
    document.body.classList.remove('settings-open');
    if (backdrop) backdrop.hidden = true;
  };
  const openDrawer = () => {
    if (!wideScreen.matches) return;
    document.body.classList.add('settings-open');
    if (backdrop) backdrop.hidden = false;
  };
  wideScreen.addEventListener('change', closeDrawer);
  $('#stitch-settings-close')?.addEventListener('click', closeDrawer);
  backdrop?.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('settings-open') && !document.querySelector('dialog[open]')) closeDrawer();
  });
  const baseOpenSettingsPanel = window.openSettingsPanel;
  window.openSettingsPanel = function () {
    openDrawer();
    return baseOpenSettingsPanel.apply(this, arguments);
  };
  const baseShowView = window.showView;
  window.showView = function () {
    closeDrawer();
    return baseShowView.apply(this, arguments);
  };
  const readiness = $('#setup-readiness-details');
  readiness?.addEventListener('click', () => readiness.classList.toggle('is-open'));

  // ---- Sidebar ----
  const sideButtons = $$('.create-sidebar-nav button');
  let lastSide = null;
  const paintSidebar = () => sideButtons.forEach(button => {
    const panel = button.dataset.openPanel && settingsPanels.find(item => item.dataset.settingsPanel === button.dataset.openPanel);
    button.classList.toggle('active', button === lastSide && (!panel || panel.open));
  });
  sideButtons.forEach(button => button.addEventListener('click', () => {
    lastSide = button;
    const {sideScroll, sideFocus, sideDrawer, openPanel} = button.dataset;
    if (sideDrawer !== undefined) {
      openDrawer();
      if (drawer) drawer.scrollTop = 0;
    } else if (sideFocus) {
      const target = $(sideFocus);
      if (target) { target.scrollIntoView({behavior: 'smooth', block: 'center'}); target.focus({preventScroll: true}); }
    } else if (sideScroll) {
      window.setTimeout(() => $(sideScroll)?.scrollIntoView({behavior: 'smooth', block: 'center'}), openPanel ? 240 : 0);
    }
    paintSidebar();
  }));
  settingsPanels.forEach(panel => panel.addEventListener('toggle', paintSidebar));

  // ---- Top bar: file, target count, presets ----
  $('#stitch-pick-file')?.addEventListener('click', () => { if (!jobRunning && browsePathButton) browsePathButton.click(); });

  const presetSelect = $('#stitch-preset');
  const presetName = $('#stitch-preset-name');
  const presetDelete = $('#stitch-preset-delete');
  const managerSelect = $('#preset-manager-select');
  const managerName = $('#preset-manager-name');
  const managerDelete = $('#preset-manager-delete');
  const presetStatus = $('#preset-manager-status');
  function syncPresetManager() {
    if (!managerSelect) return;
    managerSelect.replaceChildren(...[...presetSelect.options].map(option => option.cloneNode(true)));
    managerSelect.value = presetSelect.value;
    managerDelete.hidden = presetDelete.hidden;
    managerName.value = presetName.value;
  }
  const PRESET_KEY = 'gurumoji.createPresets.v1';
  const MODE_PRESETS = [['meeting', '会議プリセット（定例・商談）'], ['group_interview', 'グループインタビュープリセット'], ['chat', '雑談プリセット']];
  const skipNames = new Set(['source_path', 'output_dir', 'custom_vocabulary', 'use_custom_vocabulary', 'input_file']);
  const readPresets = () => { try { return JSON.parse(localStorage.getItem(PRESET_KEY) || '{}') || {}; } catch (_) { return {}; } };
  const writePresets = value => { try { localStorage.setItem(PRESET_KEY, JSON.stringify(value)); return true; } catch (_) { return false; } };
  const presetFields = () => [...form.elements].filter(element => element.name && !skipNames.has(element.name)
    && !['file', 'hidden', 'button', 'submit'].includes(element.type) && !element.closest('.stitch-only'));
  function captureForm() {
    const values = {};
    const checks = {};
    presetFields().forEach(element => {
      if (element.type === 'radio' || element.type === 'checkbox') checks[`${element.name}|${element.value}`] = element.checked;
      else values[element.name] = element.value;
    });
    return {values, checks};
  }
  function applyPreset(data) {
    const fields = presetFields();
    // Recording type first: it rewrites other fields, which the saved values then override.
    [...fields.filter(item => item.name === 'conversation_mode'), ...fields.filter(item => item.name !== 'conversation_mode')].forEach(element => {
      if (element.type === 'radio' || element.type === 'checkbox') {
        const wanted = data.checks[`${element.name}|${element.value}`];
        if (typeof wanted === 'boolean' && element.checked !== wanted && (wanted || element.type === 'checkbox')) {
          element.checked = wanted;
          fire(element, 'change');
        }
      } else if (element.name in data.values && element.value !== data.values[element.name]) {
        element.value = data.values[element.name];
        fire(element, 'input');
        fire(element, 'change');
      }
    });
    updateCreateSummary();
  }
  function renderPresets(selected) {
    const saved = readPresets();
    presetSelect.replaceChildren();
    MODE_PRESETS.forEach(([value, label]) => presetSelect.add(new Option(label, `mode:${value}`)));
    Object.keys(saved).sort().forEach(name => presetSelect.add(new Option(`保存済み: ${name}`, `user:${name}`)));
    if (selected && [...presetSelect.options].some(option => option.value === selected)) presetSelect.value = selected;
    else presetSelect.value = `mode:${selectedConversationMode()}`;
    presetDelete.hidden = !presetSelect.value.startsWith('user:');
    syncPresetManager();
  }
  presetSelect?.addEventListener('change', () => {
    const [kind, ...rest] = presetSelect.value.split(':');
    const key = rest.join(':');
    presetDelete.hidden = kind !== 'user';
    if (kind === 'mode') {
      const radio = conversationModeInputs.find(input => input.value === key);
      if (radio && !radio.checked) { radio.checked = true; fire(radio, 'change'); }
    } else if (kind === 'user') {
      const data = readPresets()[key];
      if (data) { applyPreset(data); presetName.value = key; }
    }
    syncPresetManager();
    if (presetStatus) presetStatus.textContent = '';
  });
  $('#stitch-preset-save')?.addEventListener('click', () => {
    const name = presetName.value.trim();
    if (!name) { presetName.focus(); return; }
    const saved = readPresets();
    if (!(name in saved) && Object.keys(saved).length >= 30) { presetName.setCustomValidity('保存できるプリセットは30件までです。'); presetName.reportValidity(); presetName.setCustomValidity(''); return; }
    saved[name] = captureForm();
    if (writePresets(saved)) {
      renderPresets(`user:${name}`);
      if (presetStatus) presetStatus.textContent = `「${name}」を保存しました。`;
    } else if (presetStatus) presetStatus.textContent = 'プリセットを保存できませんでした。ブラウザーの保存領域を確認してください。';
  });
  presetDelete?.addEventListener('click', () => {
    const [kind, ...rest] = presetSelect.value.split(':');
    if (kind !== 'user') return;
    const saved = readPresets();
    delete saved[rest.join(':')];
    if (!writePresets(saved)) {
      if (presetStatus) presetStatus.textContent = 'プリセットを削除できませんでした。';
      return;
    }
    presetName.value = '';
    renderPresets();
    if (presetStatus) presetStatus.textContent = 'プリセットを削除しました。';
  });
  swallowEnter(presetName);
  swallowEnter(managerName);
  managerSelect?.addEventListener('change', () => {
    presetSelect.value = managerSelect.value;
    fire(presetSelect, 'change');
  });
  managerName?.addEventListener('input', () => { presetName.value = managerName.value; });
  $('#preset-manager-save')?.addEventListener('click', () => {
    if (!managerName.value.trim()) { managerName.focus(); return; }
    presetName.value = managerName.value;
    if (Object.keys(readPresets()).length >= 30 && !(presetName.value.trim() in readPresets())) {
      presetStatus.textContent = '保存できるプリセットは30件までです。';
      return;
    }
    $('#stitch-preset-save').click();
  });
  $('#preset-manager-delete')?.addEventListener('click', () => presetDelete.click());
  $('#preset-manager-open')?.addEventListener('click', () => showView('new'));
  document.addEventListener('gurumoji-view-change', event => {
    if (event.detail.view === 'presets') syncPresetManager();
  });
  presetName?.addEventListener('keydown', event => { if (event.key === 'Enter') $('#stitch-preset-save')?.click(); });
  renderPresets();

  // ---- Video card ----
  const videoFrame = $('#stitch-video-frame');
  const video = $('#stitch-video');
  const videoDate = $('#stitch-video-date');
  const videoDuration = $('#stitch-video-duration');
  const sourceSection = $('#setup-source');
  let videoUrl = '';
  let videoSignature = '';
  const hhmmss = seconds => {
    if (!Number.isFinite(seconds)) return '—:—:—';
    const whole = Math.round(seconds);
    return [Math.floor(whole / 3600), Math.floor(whole / 60) % 60, whole % 60].map(part => String(part).padStart(2, '0')).join(':');
  };
  function clearVideo() {
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    videoUrl = '';
    if (video) { video.removeAttribute('src'); video.load(); }
    if (videoFrame) videoFrame.hidden = true;
    sourceSection?.classList.remove('has-video');
    if (videoDate) videoDate.textContent = '—';
    if (videoDuration) videoDuration.textContent = '—:—:—';
  }
  function showFile(file) {
    clearVideo();
    videoUrl = URL.createObjectURL(file);
    video.src = videoUrl;
    videoFrame.hidden = false;
    sourceSection?.classList.add('has-video');
    videoDate.textContent = new Date(file.lastModified).toLocaleDateString('ja-JP');
  }
  video?.addEventListener('loadedmetadata', () => { videoDuration.textContent = hhmmss(video.duration); });
  function syncVideo() {
    if (!video || typeof inputFile === 'undefined' || !inputFile) return;
    const file = inputFile.files && inputFile.files[0];
    const signature = file ? `${file.name}|${file.size}|${file.lastModified}` : '';
    if (signature === videoSignature) return;
    videoSignature = signature;
    if (file) showFile(file); else clearVideo();
  }

  // ---- Registration lamp on the video card title ----
  const videoStateLabel = $('#stitch-video-state');
  const videoNameLabel = $('#stitch-video-name');
  function syncRegistration() {
    if (!sourceSection) return;
    const failed = Boolean(pathError && !pathError.hidden && pathError.textContent.trim());
    const registered = !failed && hasSelectedSource();
    sourceSection.classList.toggle('is-registered', registered);
    sourceSection.classList.toggle('has-problem', failed);
    if (videoStateLabel) videoStateLabel.textContent = failed ? '要確認' : registered ? (queueItems.length > 1 ? `${queueItems.length}件 登録済み` : '登録済み') : '未登録';
    if (videoNameLabel && pathDetail) videoNameLabel.textContent = pathDetail.textContent.trim() || 'ファイルが選択されていません';
  }
  [pathDetail, pathError].forEach(element => element && new MutationObserver(syncRegistration).observe(element, {childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['hidden']}));

  // ---- Speakers card ----
  const speakerSeg = $$('[data-speaker-mode]');
  const speakerCount = $('#stitch-speaker-count');
  let speakerMode = 'max';
  const speakerField = mode => (mode === 'fixed' ? fixedSpeakerCountInput : mode === 'min' ? minSpeakersInput : maxSpeakersInput);
  function paintSpeakers() {
    const locked = Boolean(speakerCountFixButton && speakerCountFixButton.disabled);
    speakerSeg.forEach(button => {
      const active = button.dataset.speakerMode === speakerMode;
      button.classList.toggle('active', active);
      button.setAttribute('aria-checked', String(active));
      button.disabled = locked;
    });
    speakerCount.disabled = locked;
    if (document.activeElement !== speakerCount) speakerCount.value = speakerField(speakerMode).value || '';
  }
  speakerSeg.forEach(button => button.addEventListener('click', () => {
    speakerMode = button.dataset.speakerMode;
    if (speakerMode === 'fixed') { if (!isSpeakerCountFixed()) setSpeakerCountFixed(true); }
    else if (isSpeakerCountFixed()) setSpeakerCountFixed(false);
    paintSpeakers();
    speakerCount.focus();
  }));
  speakerCount?.addEventListener('input', () => {
    const field = speakerField(speakerMode);
    field.value = speakerCount.value;
    fire(field, 'input');
  });
  swallowEnter(speakerCount);
  const autoRegister = $('#stitch-auto-register');
  autoRegister?.addEventListener('change', () => { detectNames.checked = autoRegister.checked; fire(detectNames, 'change'); });

  // ---- Prior speakers card: a participant list that hints recognition and name matching ----
  const peopleList = $('#stitch-people');
  const peopleNote = $('#stitch-people-note');
  const priorField = $('#stitch-prior-speakers');
  const personName = $('#stitch-person-name');
  const personRole = $('#stitch-person-role');
  const picker = $('#stitch-registry-picker');
  const MAX_PEOPLE = 20;
  let people = [];
  const textEl = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    return element;
  };
  function renderPeople(message = '') {
    priorField.value = JSON.stringify(people);
    peopleList.replaceChildren(...(people.length ? people.map((person, index) => {
      const row = textEl('div', 'stitch-person', '');
      const remove = textEl('button', '', '×');
      remove.type = 'button';
      remove.setAttribute('aria-label', `${person.name}を削除`);
      remove.addEventListener('click', () => { people.splice(index, 1); renderPeople(); });
      row.append(textEl('strong', '', person.name), textEl('span', '', person.role), remove);
      return row;
    }) : [textEl('p', 'stitch-people-empty', '参加者が未登録です。名前を追加すると、認識と話者特定のヒントに使います。')]));
    peopleNote.replaceChildren();
    if (message) peopleNote.append(message);
    else if (people.length) {
      peopleNote.append(`${people.length}人を登録中。`);
      const apply = textEl('button', 'stitch-link', `話者数の最大を${people.length}人にする`);
      apply.type = 'button';
      apply.addEventListener('click', () => {
        speakerSeg.find(button => button.dataset.speakerMode === 'max')?.click();
        speakerCount.value = String(people.length);
        fire(speakerCount, 'input');
      });
      peopleNote.append(' ', apply);
    }
  }
  function addPeople(entries) {
    let skipped = 0;
    entries.forEach(({name, role = ''}) => {
      const cleanName = String(name || '').replace(/\s+/g, ' ').trim().slice(0, 40);
      const cleanRole = String(role || '').replace(/\s+/g, ' ').trim().slice(0, 40);
      if (!cleanName) return;
      if (people.some(person => person.name.toLowerCase() === cleanName.toLowerCase())) return;
      if (people.length >= MAX_PEOPLE) { skipped += 1; return; }
      people.push({name: cleanName, role: cleanRole});
    });
    renderPeople(skipped ? `登録できるのは最大${MAX_PEOPLE}人です。超えた${skipped}人は追加していません。` : '');
  }
  const submitPerson = () => {
    addPeople([{name: personName.value, role: personRole.value}]);
    personName.value = '';
    personRole.value = '';
    personName.focus();
  };
  $('#stitch-person-add')?.addEventListener('click', submitPerson);
  [personName, personRole].forEach(input => input?.addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); if (!event.isComposing) submitPerson(); }
  }));
  const closePicker = () => { picker.hidden = true; };
  $('#stitch-people-registry')?.addEventListener('click', async event => {
    event.stopPropagation();
    if (!picker.hidden) { closePicker(); return; }
    picker.replaceChildren(textEl('p', 'stitch-people-empty', '読み込んでいます…'));
    picker.hidden = false;
    try {
      const response = await apiFetch('/api/speakers?include_inactive=0', {cache: 'no-store'});
      const data = await readJsonResponse(response);
      if (!response.ok) throw new Error(data.error || '話者管理を読み込めませんでした。');
      const rows = (data.speakers || []).map(row => ({name: row.display_name || row.pseudonym || row.participant_code || '', role: row.default_role || ''})).filter(row => row.name);
      picker.replaceChildren(...(rows.length ? rows.map(row => {
        const option = textEl('button', '', row.role ? `${row.name}（${row.role}）` : row.name);
        option.type = 'button';
        option.setAttribute('role', 'option');
        option.disabled = people.some(person => person.name.toLowerCase() === row.name.toLowerCase());
        option.addEventListener('click', () => { addPeople([row]); closePicker(); });
        return option;
      }) : [textEl('p', 'stitch-people-empty', '話者管理に登録された話者がありません。')]));
    } catch (error) {
      picker.replaceChildren(textEl('p', 'stitch-people-empty', error.message));
    }
  });
  document.addEventListener('click', event => {
    if (!picker.hidden && !picker.contains(event.target)) closePicker();
  });
  const peopleFileInput = $('#stitch-people-file-input');
  $('#stitch-people-file')?.addEventListener('click', () => peopleFileInput.click());
  peopleFileInput?.addEventListener('change', async () => {
    const file = peopleFileInput.files && peopleFileInput.files[0];
    peopleFileInput.value = '';
    if (!file) return;
    if (file.size > 1024 * 1024) { renderPeople('1MBまでのCSV・テキストを選んでください。'); return; }
    const rows = (await file.text()).split(/\r?\n/).map(line => line.split(/[,\t，]/).map(cell => cell.trim().replace(/^"|"$/g, '')));
    const header = /^(name|display_name|名前|氏名|参加者|話者)$/i;
    addPeople(rows.filter((cells, index) => cells[0] && !(index === 0 && header.test(cells[0]))).map(cells => ({name: cells[0], role: cells[1] || ''})));
  });
  renderPeople();

  // ---- Prior outline card: agenda text whose key terms hint recognition ----
  const outlineText = $('#stitch-outline-text');
  const outlineNote = $('#stitch-outline-note');
  const outlineEnabled = $('#stitch-outline-enabled');
  const OUTLINE_TERM = /[ァ-ヶー]{3,}|[A-Za-z][A-Za-z0-9._-]{2,}|[「『]([^「」『』\n]{2,20})[」』]/g;
  const outlineTerms = text => {
    const terms = [];
    const seen = new Set();
    for (const match of text.matchAll(OUTLINE_TERM)) {
      const term = (match[1] || match[0]).trim();
      if (term && !seen.has(term.toLowerCase())) { seen.add(term.toLowerCase()); terms.push(term); }
      if (terms.length >= 30) break;
    }
    return terms;
  };
  function renderOutline() {
    const text = outlineText.value;
    const qwen = typeof transcriptionBackend !== 'undefined' && ['qwen3_nemotron', 'haas_ja'].includes(transcriptionBackend?.value);
    outlineNote.textContent = !text.trim()
      ? '台本や議事アジェンダを入れると、固有名詞や専門用語の聞き取りに役立ちます。'
      : `${text.length}/4000字・認識ヒント語 ${outlineTerms(text).length}語を抽出（名前・カタカナ語・英数字語・「」内）`
        + (qwen ? '。Qwen方式ではヒントを使いません' : '') + (outlineEnabled.checked ? '' : '。今回は使いません');
  }
  outlineText?.addEventListener('input', renderOutline);
  outlineEnabled?.addEventListener('change', renderOutline);
  const outlineFileInput = $('#stitch-outline-file-input');
  $('#stitch-outline-file')?.addEventListener('click', () => outlineFileInput.click());
  outlineFileInput?.addEventListener('change', async () => {
    const file = outlineFileInput.files && outlineFileInput.files[0];
    outlineFileInput.value = '';
    if (!file) return;
    if (file.size > 1024 * 1024) { outlineNote.textContent = '1MBまでのテキストを選んでください。'; return; }
    const text = await file.text();
    outlineText.value = text.slice(0, 4000);
    renderOutline();
    if (text.length > 4000) outlineNote.textContent += '。4000字を超えた分は読み込んでいません';
  });
  $('#stitch-outline-clear')?.addEventListener('click', () => { outlineText.value = ''; renderOutline(); });
  renderOutline();

  // ---- Vocabulary card ----
  const vocabInput = $('#stitch-vocab-input');
  const vocabChips = $('#stitch-vocab-chips');
  const vocabEnabled = $('#stitch-vocab-enabled');
  const vocabNote = $('#stitch-vocab-note');
  const VOCAB_LIMIT = 100;
  let vocabSignature = null;

  // Word presets: named term lists kept in this browser; choosing one replaces the registered words.
  const vocabPresetSelect = $('#stitch-vocab-preset');
  const vocabPresetName = $('#stitch-vocab-preset-name');
  const vocabPresetSave = $('#stitch-vocab-preset-save');
  const vocabPresetDelete = $('#stitch-vocab-preset-delete');
  const VOCAB_PRESET_KEY = 'gurumoji.vocabularyPresets.v1';
  const VOCAB_PRESET_LIMIT = 30;
  const readVocabPresets = () => {
    try {
      const stored = JSON.parse(localStorage.getItem(VOCAB_PRESET_KEY) || '{}') || {};
      return Object.fromEntries(Object.entries(stored).filter(([, terms]) => Array.isArray(terms)));
    } catch (_) { return {}; }
  };
  const writeVocabPresets = value => { try { localStorage.setItem(VOCAB_PRESET_KEY, JSON.stringify(value)); return true; } catch (_) { return false; } };
  function renderVocabPresets(selected = vocabPresetSelect?.value || '') {
    if (!vocabPresetSelect) return;
    const saved = readVocabPresets();
    vocabPresetSelect.replaceChildren(new Option(Object.keys(saved).length ? '単語プリセットを選択' : '単語プリセットなし', ''),
      ...Object.keys(saved).sort().map(name => new Option(`${name}（${saved[name].length}語）`, name)));
    vocabPresetSelect.value = selected in saved ? selected : '';
    vocabPresetDelete.hidden = !vocabPresetSelect.value;
  }
  // Keep the picker on the preset whose words are registered right now (none when they differ).
  function syncVocabPresetSelection(signature) {
    if (!vocabPresetSelect) return;
    const saved = readVocabPresets();
    const match = Object.keys(saved).find(name => saved[name].join('\n') === signature && signature);
    if ((match || '') !== vocabPresetSelect.value) renderVocabPresets(match || '');
  }
  vocabPresetSelect?.addEventListener('change', () => {
    const name = vocabPresetSelect.value;
    vocabPresetDelete.hidden = !name;
    const terms = readVocabPresets()[name];
    if (!terms) return;
    vocabPresetName.value = name;
    writeTerms(terms.slice(0, VOCAB_LIMIT));
    vocabEnabled.checked = true;
    fire(vocabEnabled, 'change');
  });
  vocabPresetSave?.addEventListener('click', () => {
    const name = vocabPresetName.value.replace(/\s+/g, ' ').trim();
    const terms = vocabularyTermsFromInput();
    const fail = message => { vocabNote.textContent = message; vocabPresetName.focus(); };
    if (!name) { fail('プリセット名を入力してください。'); return; }
    if (!terms.length) { fail('保存する単語がありません。先に単語を登録してください。'); return; }
    const saved = readVocabPresets();
    if (!(name in saved) && Object.keys(saved).length >= VOCAB_PRESET_LIMIT) { fail(`保存できる単語プリセットは${VOCAB_PRESET_LIMIT}件までです。`); return; }
    saved[name] = terms;
    if (!writeVocabPresets(saved)) { fail('このブラウザには保存できませんでした。'); return; }
    vocabPresetName.value = name;
    renderVocabPresets(name);
    vocabNote.textContent = `「${name}」に${terms.length}語を保存しました。`;
  });
  vocabPresetDelete?.addEventListener('click', () => {
    const name = vocabPresetSelect.value;
    if (!name || !window.confirm(`単語プリセット「${name}」を削除しますか？（登録中の単語は変わりません）`)) return;
    const saved = readVocabPresets();
    delete saved[name];
    writeVocabPresets(saved);
    vocabPresetName.value = '';
    renderVocabPresets('');
  });
  vocabPresetName?.addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); if (!event.isComposing) vocabPresetSave.click(); }
  });
  renderVocabPresets('');
  const writeTerms = list => { customVocabulary.value = list.join('\n'); fire(customVocabulary, 'input'); };
  function addTerms(candidates) {
    const current = vocabularyTermsFromInput();
    const known = new Set(current);
    candidates.map(term => String(term).trim()).filter(Boolean).forEach(term => { if (!known.has(term)) { known.add(term); current.push(term); } });
    const clipped = current.length > VOCAB_LIMIT;
    writeTerms(current.slice(0, VOCAB_LIMIT));
    if (clipped) vocabNote.textContent = `登録できるのは最大${VOCAB_LIMIT}語です。超えた分は追加していません。`;
  }
  function renderVocab() {
    const terms = vocabularyTermsFromInput();
    const signature = terms.join('\n');
    if (signature !== vocabSignature) {
      vocabSignature = signature;
      vocabChips.replaceChildren(...terms.map(term => {
        const chip = document.createElement('span');
        chip.className = 'stitch-chip';
        const label = document.createElement('span');
        label.textContent = term;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.setAttribute('aria-label', `${term}を削除`);
        remove.textContent = '×';
        remove.addEventListener('click', () => writeTerms(vocabularyTermsFromInput().filter(item => item !== term)));
        chip.append(label, remove);
        return chip;
      }));
      vocabNote.textContent = terms.length ? `${terms.length}語を登録中（最大${VOCAB_LIMIT}語）` : '登録語はありません';
      syncVocabPresetSelection(signature);
    }
    const qwen = Boolean(typeof qwenVocabularyNote !== 'undefined' && qwenVocabularyNote && !qwenVocabularyNote.hidden);
    vocabEnabled.disabled = qwen;
    [vocabPresetSelect, vocabPresetName, vocabPresetSave, vocabPresetDelete].forEach(control => { if (control) control.disabled = qwen || jobRunning; });
    $('#stitch-vocab-state').textContent = qwen ? '対象外' : (vocabEnabled.checked ? '有効' : '無効');
    $('.stitch-vocab').classList.toggle('is-off', qwen || !vocabEnabled.checked);
    if (qwen) vocabNote.textContent = '単語登録はWhisperXのみで使用します。';
  }
  const submitVocab = () => { addTerms([vocabInput.value]); vocabInput.value = ''; };
  $('#stitch-vocab-add')?.addEventListener('click', submitVocab);
  vocabInput?.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); if (!event.isComposing) submitVocab(); } });
  vocabEnabled?.addEventListener('change', renderVocab);
  $('#stitch-vocab-clear')?.addEventListener('click', () => { if (vocabularyTermsFromInput().length && window.confirm('登録した単語をすべて削除しますか？')) writeTerms([]); });
  const vocabFileInput = $('#stitch-vocab-file-input');
  $('#stitch-vocab-file')?.addEventListener('click', () => vocabFileInput.click());
  vocabFileInput?.addEventListener('change', async () => {
    const file = vocabFileInput.files && vocabFileInput.files[0];
    vocabFileInput.value = '';
    if (!file || file.size > 1024 * 1024) { if (file) vocabNote.textContent = '1MBまでのテキストを選んでください。'; return; }
    addTerms((await file.text()).split(/[\r\n\t,、，]+/));
  });

  // ---- Tag / group assignment (applied to the result once the run completes) ----
  const tagInput = $('#stitch-tag-input');
  const groupInput = $('#stitch-group-input');
  const metaNote = $('#stitch-meta-note');
  const META = {
    tag: {label: 'タグ', idKey: 'tag_id', listKey: 'tags', createUrl: '/api/library/tags', list: $('#stitch-tag-list')},
    group: {label: 'グループ', idKey: 'id', listKey: 'groups', createUrl: '/api/library/groups', list: $('#stitch-group-list')}
  };
  const metaKey = value => String(value || '').normalize('NFKC').trim().toLowerCase();
  async function fetchMeta() {
    const response = await apiFetch('/api/library?sort=updated_desc', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '');
    return data;
  }
  async function loadMeta() {
    try {
      const data = await fetchMeta();
      Object.values(META).forEach(kind => {
        const rows = Array.isArray(data[kind.listKey]) ? data[kind.listKey] : [];
        kind.list.replaceChildren(...rows.map(row => new Option(row.name)));
      });
    } catch (_) { /* the suggestions simply stay empty; typing still works */ }
  }
  // A typed name maps to an existing tag/group, or is created once the run has completed.
  async function resolveMeta(kind, typed) {
    const wanted = metaKey(typed);
    const find = data => (Array.isArray(data[kind.listKey]) ? data[kind.listKey] : []).find(row => metaKey(row.name) === wanted);
    const existing = find(await fetchMeta());
    if (existing) return existing[kind.idKey];
    const response = await apiFetch(kind.createUrl, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: typed.trim()})});
    const created = await readJsonResponse(response);
    if (response.ok) return created[kind.idKey];
    const raced = response.status === 409 ? find(await fetchMeta()) : null;
    if (raced) return raced[kind.idKey];
    throw new Error(created.error || `${kind.label}を作成できませんでした。`);
  }
  [tagInput, groupInput].forEach(input => input && swallowEnter(input));
  let pending = null;
  form.addEventListener('submit', () => {
    pending = {group: groupForCurrentFile(), tag: tagInput.value.trim(), jobId: ''};
    queueRun = queueItems.length > 1;
    queueJobId = '';
  }, true);
  const baseStoreActiveJobId = window.storeActiveJobId;
  if (typeof baseStoreActiveJobId === 'function') {
    window.storeActiveJobId = function (id) {
      if (id && pending && !pending.jobId) pending.jobId = String(id);
      if (id) queueJobStarted(String(id));
      return baseStoreActiveJobId.apply(this, arguments);
    };
  }
  async function applyPending(job) {
    if (!pending || !job || job.status !== 'completed' || pending.jobId !== String(job.id)) return;
    const {group, tag} = pending;
    pending = null;
    const put = (url, body) => apiFetch(url, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    try {
      if (group) await put(`/api/library/${encodeURIComponent(job.id)}/group`, {group_id: await resolveMeta(META.group, group)});
      if (tag) await put(`/api/library/tags/${encodeURIComponent(await resolveMeta(META.tag, tag))}/members`, {item_ids: [job.id], remove: false});
      loadMeta();
    } catch (error) { metaNote.textContent = `${error.message || 'タグ・グループを設定できませんでした。'} 結果は保存済みです。データ一覧から設定できます。`; }
  }
  const baseRenderResult = window.renderResult;
  if (typeof baseRenderResult === 'function') {
    window.renderResult = function (job) {
      // While more registered files wait, stay on the progress card instead of opening this result.
      if (queueHoldsResult(job)) { applyPending(job); return undefined; }
      const output = baseRenderResult.apply(this, arguments);
      applyPending(job);
      return output;
    };
  }

  // ---- Several files: each one runs as its own job, in order ----
  // The drop zone and picker register a list. The form always carries one file; when its job
  // ends the next file is loaded and started. Without a typed group, each file joins the group
  // of its modification date (YYYY-MM-DD).
  const SOURCE_EXT = /\.(mp4|m4v|mov|mkv|wav|mp3|m4a|flac)$/i;
  const VIDEO_EXT = /\.(mp4|m4v|mov|mkv)$/i;
  const MAX_QUEUE = 30;
  const ICON_BASE = document.querySelector('meta[name="gurumoji-icon-base"]')?.content || 'static/icons/';
  const ACTIVE_STATUSES = ['admitting', 'queued', 'running', 'committing'];
  const queueBox = $('#source-queue');
  const queueList = $('#source-queue-list');
  const queueTitle = $('#source-queue-title');
  const queueNote = $('#source-queue-note');
  const queueProgress = $('#queue-progress');
  let queueItems = [];
  let queueRun = false;
  let queueJobId = '';
  let queueAppendNext = false;
  const STATUS_TEXT = {ready: '待機中', running: '処理中', done: '完了', failed: '失敗'};
  const fileSig = file => (file ? `${file.name}|${file.size}|${file.lastModified}` : '');
  const pad2 = value => String(value).padStart(2, '0');
  function dateGroupName(file) {
    const modified = new Date(file.lastModified);
    const date = Number.isFinite(modified.getTime()) && file.lastModified > 0 ? modified : new Date();
    return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
  }
  const currentSig = () => fileSig(inputFile.files && inputFile.files[0]);
  const currentQueueItem = () => queueItems.find(item => item.sig === currentSig());
  function groupForCurrentFile() {
    const typed = groupInput.value.trim();
    const item = currentQueueItem();
    return typed || (queueItems.length > 1 && item ? dateGroupName(item.file) : '');
  }
  function setInputFile(file) {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    inputFile.files = transfer.files;
  }
  function queueThumb(item) {
    if (item.thumb) return item.thumb;
    const box = textEl('div', 'source-queue-thumb', '');
    if (VIDEO_EXT.test(item.file.name)) {
      item.url = URL.createObjectURL(item.file);
      const clip = document.createElement('video');
      clip.muted = true;
      clip.preload = 'metadata';
      clip.tabIndex = -1;
      clip.setAttribute('aria-hidden', 'true');
      clip.src = `${item.url}#t=0.5`;
      box.append(clip);
    } else {
      const audio = document.createElement('img');
      audio.src = `${ICON_BASE}dark/03-audio-import.svg`;
      audio.alt = '';
      box.append(audio);
    }
    item.thumb = box;
    return box;
  }
  function releaseItem(item) {
    if (item.url) URL.revokeObjectURL(item.url);
    item.url = '';
    item.thumb = null;
  }
  function renderQueue() {
    const many = queueItems.length > 1;
    sourceSection?.classList.toggle('has-queue', many);
    if (queueBox) queueBox.hidden = !many;
    if (!many) { queueList?.replaceChildren(); return; }
    const done = queueItems.filter(item => item.status === 'done').length;
    queueTitle.textContent = `登録ファイル ${queueItems.length}件${done ? `（完了 ${done}件）` : ''}`;
    const typed = groupInput.value.trim();
    queueNote.textContent = typed
      ? `グループ「${typed}」にまとめて入ります。`
      : 'グループ未入力のため、各ファイルを更新日のグループ（例: 2026-11-02）に自動で入れます。';
    queueList.replaceChildren(...queueItems.map(item => {
      const row = textEl('li', `source-queue-row is-${item.status}`, '');
      const body = textEl('div', 'source-queue-body', '');
      body.append(
        textEl('strong', '', item.file.name),
        textEl('span', '', `${new Date(item.file.lastModified).toLocaleDateString('ja-JP')} ・ ${formatBytes(item.file.size)} ・ グループ: ${typed || dateGroupName(item.file)}`)
      );
      const remove = textEl('button', 'source-queue-remove', '×');
      remove.type = 'button';
      remove.disabled = item.status === 'running';
      remove.setAttribute('aria-label', `${item.file.name}を解除`);
      remove.addEventListener('click', () => removeQueueItem(item));
      row.append(queueThumb(item), body, textEl('b', 'source-queue-status', STATUS_TEXT[item.status] || ''), remove);
      return row;
    }));
  }
  function renderQueueProgress() {
    if (!queueProgress) return;
    const current = queueItems.find(item => item.status === 'running');
    queueProgress.hidden = !(queueRun && queueItems.length > 1);
    if (queueProgress.hidden) return;
    const position = queueItems.indexOf(current) + 1 || queueItems.filter(item => item.status === 'done').length + 1;
    queueProgress.textContent = `複数登録: ${Math.min(position, queueItems.length)} / ${queueItems.length} 件目${current ? ` — ${current.file.name}` : ''}`;
  }
  function loadQueueFile(file) {
    setInputFile(file);
    handleInputFileSelection();
  }
  function clearQueue({keepInput = false} = {}) {
    queueItems.forEach(releaseItem);
    queueItems = [];
    queueRun = false;
    queueJobId = '';
    if (!keepInput && inputFile) { inputFile.value = ''; handleInputFileSelection(); }
    renderQueue();
    renderQueueProgress();
  }
  function removeQueueItem(item) {
    if (jobRunning || item.status === 'running') return;
    const wasCurrent = item.sig === currentSig();
    queueItems = queueItems.filter(other => other !== item);
    releaseItem(item);
    if (queueItems.length === 0) { clearQueue(); return; }
    if (wasCurrent) loadQueueFile((queueItems.find(other => other.status === 'ready') || queueItems[0]).file);
    renderQueue();
    updateCreateSummary();
  }
  function registerSourceFiles(files, {append = false} = {}) {
    if (jobRunning || !inputFile) return;
    setAlert(pathError, '');
    const valid = files.filter(file => SOURCE_EXT.test(file.name));
    if (!valid.length) {
      if (!append || !queueItems.length) clearQueue();
      setAlert(pathError, '対応している動画・音声ファイルを選択してください。', true);
      return;
    }
    const base = append ? queueItems : [];
    if (!append) queueItems.forEach(releaseItem);
    const known = new Set(base.map(item => item.sig));
    const added = [];
    valid.forEach(file => {
      const sig = fileSig(file);
      if (known.has(sig)) return;
      known.add(sig);
      added.push({file, sig, status: 'ready', url: '', thumb: null});
    });
    const merged = [...base, ...added];
    queueItems = merged.slice(0, MAX_QUEUE);
    merged.slice(MAX_QUEUE).forEach(releaseItem);
    queueRun = false;
    queueJobId = '';
    const skipped = files.length - valid.length;
    const dropped = merged.length - queueItems.length;
    const notes = [];
    if (skipped) notes.push(`対応していない${skipped}件は登録していません`);
    if (dropped) notes.push(`登録は最大${MAX_QUEUE}件までです。超えた${dropped}件は登録していません`);
    // Keep the file already on the form while appending; otherwise start from the first ready one.
    const keep = append && queueItems.find(item => item.sig === currentSig() && item.status !== 'done');
    const first = keep || queueItems.find(item => item.status === 'ready') || queueItems[0];
    loadQueueFile(first.file);
    renderQueue();
    if (notes.length) setAlert(pathError, `${notes.join('。')}。`, true);
  }
  window.registerSourceFiles = registerSourceFiles;
  // Capture phase: app.js would only look at the first file of a multi-file selection.
  inputFile?.addEventListener('change', event => {
    event.stopImmediatePropagation();
    const files = [...(inputFile.files || [])];
    const append = queueAppendNext;
    queueAppendNext = false;
    if (files.length) registerSourceFiles(files, {append});
    else handleInputFileSelection();
  }, true);
  browsePathButton?.addEventListener('click', () => { queueAppendNext = false; });
  $('#source-queue-add')?.addEventListener('click', () => { if (jobRunning) return; queueAppendNext = true; inputFile.click(); });
  $('#source-queue-clear')?.addEventListener('click', () => { if (!jobRunning) clearQueue(); });
  groupInput?.addEventListener('input', () => { if (queueItems.length > 1) renderQueue(); });

  function queueJobStarted(id) {
    if (!queueRun || queueJobId) return;
    const item = currentQueueItem();
    if (!item) return;
    queueJobId = id;
    item.status = 'running';
    renderQueue();
    renderQueueProgress();
  }
  function queueHoldsResult(job) {
    return queueRun && Boolean(job) && String(job.id) === queueJobId && queueItems.some(item => item.status === 'ready');
  }
  function queueJobEnded(job) {
    if (!queueRun || !job || String(job.id) !== queueJobId || ACTIVE_STATUSES.includes(job.status)) return;
    const item = queueItems.find(other => other.status === 'running');
    const completed = job.status === 'completed';
    if (item) item.status = completed ? 'done' : 'failed';
    queueJobId = '';
    if (completed) applyPending(job);
    const next = completed && queueItems.find(other => other.status === 'ready');
    if (!next) {
      queueRun = false;
      renderQueue();
      renderQueueProgress();
      if (!completed && queueNote) queueNote.textContent = `${item ? `「${item.file.name}」` : 'このファイル'}は完了しませんでした。残りのファイルは待機中です。この行を解除して次へ進むか、もう一度実行してください。`;
      return;
    }
    renderQueue();
    renderQueueProgress();
    loadQueueFile(next.file);
    window.setTimeout(() => {
      if (!startButton || startButton.disabled || jobRunning) {
        queueRun = false;
        renderQueueProgress();
        if (queueNote) queueNote.textContent = '次のファイルを開始できませんでした。開始前の確認を済ませてから、もう一度実行してください。';
        return;
      }
      startButton.click();
    }, 400);
  }
  const baseResumeJob = window.resumeJob;
  if (typeof baseResumeJob === 'function') {
    window.resumeJob = function (job) {
      const output = baseResumeJob.apply(this, arguments);
      try { queueJobEnded(job); } catch (error) { console.error(error); }
      return output;
    };
  }

  // ---- Execution settings: output folder, level tiles, run ----
  const launch = $('#setup-launch');
  const outputMain = $('#output-dir');
  const outputDash = $('#stitch-output-dir');
  if (outputMain && outputDash) {
    outputDash.value = outputMain.value;
    outputDash.addEventListener('input', () => { outputMain.value = outputDash.value; fire(outputMain, 'input'); });
    outputMain.addEventListener('input', () => { if (outputDash.value !== outputMain.value) outputDash.value = outputMain.value; });
    swallowEnter(outputDash);
  }
  const LEVEL_TEXT = {high: '高', mid: '中', low: '低', none: '無'};
  const tile = name => $(`[data-tile="${name}"]`);
  const paintTile = (name, level, hint) => {
    const button = tile(name);
    if (!button) return;
    const badge = button.querySelector('[data-lv]');
    badge.textContent = LEVEL_TEXT[level];
    badge.dataset.level = level;
    button.title = hint;
  };
  const setRadio = value => {
    const radio = transcriptFinishingModeInputs.find(input => input.value === value);
    if (radio) { radio.checked = true; fire(radio, 'change'); }
  };
  const setSelect = (select, value) => { select.value = value; fire(select, 'input'); fire(select, 'change'); };
  const finishingLevel = {advanced: 'high', recommended: 'mid', off: 'none'};
  const finishingValue = {high: 'advanced', mid: 'recommended', none: 'off'};
  const volumeLevel = {reuse: 'high', strong: 'high', standard: 'mid', light: 'low', none: 'none'};
  const modelLevel = model => (model === 'large-v3' ? 'high' : ['medium', 'small'].includes(model) ? 'mid' : 'low');
  // A tile opens a speech bubble with the real choices; picking one applies it and closes the bubble.
  const BUBBLES = {
    finishing: {
      title: 'AI仕上げ',
      options: () => [['high', '全文を整える', '高'], ['mid', '必要な箇所を整える', '中'], ['none', 'しない', '無']],
      current: () => finishingLevel[selectedTranscriptFinishingMode()] || 'none',
      apply: value => setRadio(finishingValue[value])
    },
    volume: {
      title: '音量調節（動画・音声の前処理）',
      options: () => ['reuse', 'strong', 'standard', 'light', 'none'].map(value => {
        const option = [...audioPreprocess.options].find(item => item.value === value);
        return [value, option.textContent, LEVEL_TEXT[volumeLevel[value]]];
      }),
      current: () => audioPreprocess.value,
      apply: value => setSelect(audioPreprocess, value)
    },
    model: {
      title: '認識モデル',
      options: () => [...modelName.options].map(option => [option.value, option.textContent, LEVEL_TEXT[modelLevel(option.value)]]),
      current: () => modelName.value,
      apply: value => setSelect(modelName, value)
    }
  };
  let openBubbleName = '';
  function closeBubble() {
    $$('.stitch-bubble').forEach(bubble => bubble.remove());
    $$('[data-tile][aria-expanded="true"]').forEach(button => button.setAttribute('aria-expanded', 'false'));
    openBubbleName = '';
  }
  function openBubble(name) {
    closeBubble();
    setConfirm(false);
    const spec = BUBBLES[name];
    const button = tile(name);
    if (!spec || !button) return;
    const bubble = textEl('div', 'stitch-bubble', '');
    bubble.setAttribute('role', 'listbox');
    bubble.setAttribute('aria-label', `${spec.title}を選ぶ`);
    bubble.append(textEl('strong', '', spec.title));
    const current = spec.current();
    spec.options().forEach(([value, label, badge]) => {
      const option = textEl('button', '', '');
      option.type = 'button';
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', String(value === current));
      const level = textEl('b', 'lv', badge);
      level.dataset.level = Object.keys(LEVEL_TEXT).find(key => LEVEL_TEXT[key] === badge) || 'none';
      option.append(level, textEl('span', '', label));
      option.addEventListener('click', event => { event.stopPropagation(); spec.apply(value); closeBubble(); button.focus(); });
      bubble.append(option);
    });
    bubble.addEventListener('keydown', event => {
      const options = [...bubble.querySelectorAll('button')];
      const index = options.indexOf(document.activeElement);
      if (event.key === 'ArrowDown') { event.preventDefault(); options[(index + 1) % options.length].focus(); }
      if (event.key === 'ArrowUp') { event.preventDefault(); options[(index - 1 + options.length) % options.length].focus(); }
    });
    button.closest('.stitch-tile').append(bubble);
    button.setAttribute('aria-expanded', 'true');
    openBubbleName = name;
    (bubble.querySelector('[aria-selected="true"]') || bubble.querySelector('button')).focus();
  }
  Object.keys(BUBBLES).forEach(name => tile(name)?.addEventListener('click', event => {
    event.stopPropagation();
    if (openBubbleName === name) closeBubble(); else openBubble(name);
  }));
  document.addEventListener('click', event => { if (openBubbleName && !event.target.closest('.stitch-bubble')) closeBubble(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && openBubbleName) { const button = tile(openBubbleName); closeBubble(); button?.focus(); }
  });
  const emotionToggle = $('#stitch-emotion');
  emotionToggle?.addEventListener('change', () => { emotionAnalysis.checked = emotionToggle.checked; fire(emotionAnalysis, 'change'); });

  // The long confirmation text lives in a pop-up above the floating bar; it opens by itself
  // when the run is blocked so the reason is never hidden.
  const confirmToggle = $('#stitch-confirm-toggle');
  const setConfirm = open => {
    if (open) closeBubble();
    launch.classList.toggle('confirm-open', open);
    confirmToggle?.setAttribute('aria-expanded', String(open));
  };
  confirmToggle?.addEventListener('click', event => { event.stopPropagation(); setConfirm(!launch.classList.contains('confirm-open')); });
  document.addEventListener('click', event => {
    if (launch.classList.contains('confirm-open') && !launch.contains(event.target)) setConfirm(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && launch.classList.contains('confirm-open')) setConfirm(false);
  });
  const runButton = $('#stitch-run-button');
  runButton?.addEventListener('click', event => {
    event.stopPropagation();
    if (startButton && !startButton.disabled) { setConfirm(false); startButton.click(); return; }
    setConfirm(true);
  });

  // ---- Keep every proxy in step with the fields it mirrors ----
  function syncDashboard() {
    // A path or a file picked elsewhere replaces the registered list.
    if (queueItems.length && !jobRunning && !queueItems.some(item => item.sig === currentSig())) clearQueue({keepInput: true});
    $('#stitch-target-count').textContent = queueItems.length > 1 ? String(queueItems.length) : hasSelectedSource() ? '1' : '0';
    if (speakerMode === 'fixed' && !isSpeakerCountFixed()) speakerMode = 'max';
    if (isSpeakerCountFixed()) speakerMode = 'fixed';
    paintSpeakers();
    if (autoRegister) { autoRegister.checked = detectNames.checked; autoRegister.disabled = detectNames.disabled; }
    if (emotionToggle) { emotionToggle.checked = emotionAnalysis.checked; emotionToggle.disabled = emotionAnalysis.disabled; }
    paintTile('finishing', finishingLevel[selectedTranscriptFinishingMode()] || 'none', 'AI仕上げ: 高=全文を整える / 中=必要な箇所を整える / 無=しない');
    paintTile('volume', volumeLevel[audioPreprocess.value] || 'mid', `動画・音声前処理: ${selectedOptionText(audioPreprocess).split(' — ')[0]}`);
    paintTile('model', modelLevel(modelName.value), `認識モデル: ${selectedOptionText(modelName).split(' — ')[0]}`);
    const qwen = typeof transcriptionBackend !== 'undefined' && ['qwen3_nemotron', 'haas_ja'].includes(transcriptionBackend?.value);
    const modelTile = tile('model');
    if (modelTile) modelTile.disabled = qwen;
    if (outputMain && outputDash) outputDash.placeholder = outputMain.placeholder || '既定の output フォルダー';
    renderVocab();
    renderOutline();
    syncRegistration();
    syncVideo();
    if (runButton) {
      const blocked = Boolean(startButton && startButton.disabled);
      runButton.classList.toggle('is-disabled', blocked);
      runButton.setAttribute('aria-disabled', String(blocked));
      confirmToggle?.classList.toggle('needs-attention', blocked);
      const status = $('#stitch-run-status');
      if (status && setupReadyState) status.textContent = setupReadyState.textContent;
      runButton.title = blocked ? (setupReadyState ? setupReadyState.textContent : '開始前の確認が必要です') : '文字起こしを開始';
    }
    if (presetSelect.value.startsWith('mode:')) presetSelect.value = `mode:${selectedConversationMode()}`;
    syncPresetManager();
  }
  const baseUpdateCreateSummary = window.updateCreateSummary;
  window.updateCreateSummary = function () {
    const output = baseUpdateCreateSummary.apply(this, arguments);
    try { syncDashboard(); } catch (error) { console.error(error); }
    return output;
  };
  if (startButton) new MutationObserver(() => { try { syncDashboard(); } catch (_) { /* ignored */ } }).observe(startButton, {attributes: true, attributeFilter: ['disabled']});
  loadMeta();
  syncDashboard();
})();
