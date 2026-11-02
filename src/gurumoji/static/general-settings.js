/* 通常設定: default language, registered output folders, start-up recording mode and colour theme.
   Everything is kept in this browser's localStorage and applied to the existing create-screen fields. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const dialog = $('#general-settings-dialog');
  if (!dialog || typeof languageSelect === 'undefined') return;
  const fire = (element, type) => element.dispatchEvent(new Event(type, {bubbles: true}));
  const SETTINGS_KEY = 'gurumoji.generalSettings.v1';
  const THEME_KEY = 'gurumoji.theme.v1';
  const MAX_FOLDERS = 20;

  const read = () => {
    try { return JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') || {}; } catch (_) { return {}; }
  };
  const write = value => { try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(value)); } catch (_) { /* storage unavailable */ } };
  let settings = read();
  const save = () => write(settings);

  // ---- Language: the default for the create screen's language field ----
  const language = $('#gs-language');
  language.value = settings.language ?? languageSelect.value;
  language.addEventListener('change', () => {
    settings.language = language.value;
    save();
    languageSelect.value = language.value;
    fire(languageSelect, 'change');
  });

  // ---- Recording mode ----
  const modeRadios = [...dialog.querySelectorAll('input[name="gs-mode"]')];
  const paintMode = () => {
    const mode = settings.mode || selectedConversationMode();
    modeRadios.forEach(radio => { radio.checked = radio.value === mode; });
  };
  modeRadios.forEach(radio => radio.addEventListener('change', () => {
    settings.mode = radio.value;
    save();
    const target = conversationModeInputs.find(input => input.value === radio.value);
    if (target && !target.checked) { target.checked = true; fire(target, 'change'); }
  }));
  paintMode();

  // ---- Registered output folders ----
  const folderInput = $('#gs-folder-input');
  const folderList = $('#gs-folder-list');
  const outputInput = $('#stitch-output-dir') || $('#output-dir');
  let datalist = $('#stitch-output-list');
  if (outputInput && !datalist) {
    datalist = document.createElement('datalist');
    datalist.id = 'stitch-output-list';
    outputInput.after(datalist);
    outputInput.setAttribute('list', datalist.id);
  }
  $('#output-dir')?.setAttribute('list', 'stitch-output-list');
  const folders = () => (Array.isArray(settings.folders) ? settings.folders : []);
  function renderFolders() {
    const list = folders();
    folderList.replaceChildren(...(list.length ? list.map(path => {
      const item = document.createElement('li');
      const label = document.createElement('code');
      label.textContent = path;
      const isDefault = settings.defaultFolder === path;
      const makeDefault = document.createElement('button');
      makeDefault.type = 'button';
      makeDefault.className = 'secondary-button compact-button';
      makeDefault.textContent = isDefault ? '既定（解除）' : '既定にする';
      makeDefault.addEventListener('click', () => {
        settings.defaultFolder = isDefault ? '' : path;
        save();
        renderFolders();
      });
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'secondary-button compact-button';
      remove.textContent = '削除';
      remove.addEventListener('click', () => {
        settings.folders = folders().filter(value => value !== path);
        if (settings.defaultFolder === path) settings.defaultFolder = '';
        save();
        renderFolders();
      });
      item.append(label, makeDefault, remove);
      return item;
    }) : [Object.assign(document.createElement('li'), {className: 'gs-empty', textContent: '登録された保存先はありません。'})]));
    if (datalist) datalist.replaceChildren(...list.map(path => Object.assign(document.createElement('option'), {value: path})));
  }
  function addFolder() {
    const path = folderInput.value.trim();
    if (!path || folders().includes(path) || folders().length >= MAX_FOLDERS) return;
    settings.folders = [...folders(), path];
    if (!settings.defaultFolder) settings.defaultFolder = path;
    save();
    folderInput.value = '';
    renderFolders();
  }
  $('#gs-folder-add').addEventListener('click', addFolder);
  folderInput.addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); if (!event.isComposing) addFolder(); }
  });
  renderFolders();

  // ---- Theme ----
  const themeRadios = [...dialog.querySelectorAll('input[name="gs-theme"]')];
  const currentTheme = () => document.documentElement.getAttribute('data-theme') || 'forest';
  const applyTheme = theme => {
    if (theme === 'forest') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', theme);
    try { if (theme === 'forest') localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, theme); } catch (_) { /* storage unavailable */ }
    themeRadios.forEach(radio => { radio.checked = radio.value === theme; });
  };
  themeRadios.forEach(radio => radio.addEventListener('change', () => applyTheme(radio.value)));
  themeRadios.forEach(radio => { radio.checked = radio.value === currentTheme(); });

  // ---- Reset ----
  $('#gs-reset').addEventListener('click', () => {
    if (!window.confirm('通常設定を初期状態に戻しますか？（登録した保存先もすべて消えます）')) return;
    settings = {};
    save();
    applyTheme('forest');
    renderFolders();
    language.value = languageSelect.value;
    paintMode();
  });

  // ---- Open / close ----
  document.querySelectorAll('#open-general-settings, [data-open-general-settings]').forEach(button => button.addEventListener('click', () => {
    paintMode();
    renderFolders();
    if (!dialog.open) dialog.showModal();
  }));

  // ---- Apply the saved defaults to the create screen once ----
  if (settings.mode) {
    const target = conversationModeInputs.find(input => input.value === settings.mode);
    if (target && !target.checked) { target.checked = true; fire(target, 'change'); }
  }
  if (settings.language !== undefined && languageSelect.value !== settings.language) {
    languageSelect.value = settings.language;
    fire(languageSelect, 'change');
  }
  if (settings.defaultFolder && outputInput && !outputInput.value) {
    outputInput.value = settings.defaultFolder;
    fire(outputInput, 'input');
  }
})();
