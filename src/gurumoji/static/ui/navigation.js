/* 公開版の画面処理: navigation。共有状態はapp.jsで管理する。 */


function routeHash(view, id = '') {
  const encoded = id ? encodeURIComponent(String(id)) : '';
  if (view === 'item') return `#/data/${encoded}`;

  return viewRouteHashes[view] || '#/new';
}

function parseRouteHash(hash) {
  const parts = String(hash || '').replace(/^#\/?/, '').split('/').filter(Boolean).map(part => {
    try { return decodeURIComponent(part); } catch (_) { return part; }
  });
  const [head, id = ''] = parts;
  if (head === 'data' && id) return {view: 'item', itemId: id};
  if (head === 'data') return {view: 'library', itemId: ''};

  if (head === 'speakers') return {view: 'speakers', itemId: ''};
  if (Object.hasOwn(viewRouteHashes, head)) return {view: head, itemId: ''};
  return null;
}

function syncRouteHash(hash, {replace = false} = {}) {
  currentRouteHash = hash;
  if (window.location.hash === hash) return;
  try {
    if (replace) window.history.replaceState(null, '', hash);
    else window.history.pushState(null, '', hash);
  } catch (_) {
    // Screens still switch when the history API is unavailable.
  }
}

function confirmLeave({target, itemId = ''}) {
  const resultVisible = resultCard && !resultCard.hidden;
  const sameItem = target === 'item' && itemId && currentJob && String(currentJob.id) === String(itemId);
  const leavingCurrentResult = currentJobDirty && !sameItem && (resultVisible || target === 'item');
  if (leavingCurrentResult && !window.confirm('文字起こし、会話プロファイル、または話者連携に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  const leavingSpeakerManagement = target !== 'speakers'
    && speakerRegistryCard
    && !speakerRegistryCard.hidden
    && speakerRegistryDirty;
  if (leavingSpeakerManagement && !window.confirm('話者管理に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  return true;
}


function setActiveNavigation(view) {
  [
    [showNewButton, view === 'new'],
    [showLibraryButton, view === 'library' || view === 'item'],

    [showSpeakersButton, view === 'speakers'],
    ...priorDataButtons.map(button => [button, view === button.dataset.priorView])
  ].forEach(([button, active]) => {
    if (!button) return;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
    button.tabIndex = active ? 0 : -1;
  });
  [
    [showLibraryListButton, view === 'library'],

  ].forEach(([button, active]) => {
    if (!button) return;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
}

function showView(view, {itemId = '', force = false, replace = false} = {}) {
  const target = view === 'item' || Object.hasOwn(viewRouteHashes, view) ? view : 'new';

  if (target === 'item' && !currentJob) return false;
  const targetItemId = target === 'item' ? String(itemId || currentJob.id) : '';
  if (!force && !confirmLeave({target, itemId: targetItemId})) return false;
  const resultVisible = resultCard && !resultCard.hidden;
  resultRequestSequence += 1;
  // A previous view's save cannot own this view's button or messages.
  if (saveButton) saveButton.disabled = false;
  if (resultVisible && currentJobDirty && target !== 'item') setCurrentJobDirty(false);
  if (target !== 'item' && mediaPlayer) mediaPlayer.pause();
  if (createView) createView.hidden = target !== 'new';
  if (processedDataHub) processedDataHub.hidden = target !== 'library';
  if (libraryCard) libraryCard.hidden = target !== 'library';

  if (speakerRegistryCard) speakerRegistryCard.hidden = target !== 'speakers';
  if (resultCard) resultCard.hidden = target !== 'item';
  priorDataPanels.forEach(panel => { panel.hidden = panel.dataset.priorPanel !== target; });
  document.body.dataset.view = target;
  setActiveNavigation(target);
  if (target === 'library') loadLibrary();
  if (target === 'speakers' && speakerRegistryCard) loadSpeakerRegistry();
  if (target === 'folders') loadLibraryGroupManager();
  if (target === 'new') {
    renderMobileWizard();
    syncCreateViewState();
  }
  const hashId = target === 'item' ? targetItemId : '';
  syncRouteHash(routeHash(target, hashId), {replace});
  document.dispatchEvent(new CustomEvent('gurumoji-view-change', {detail: {view: target}}));
  return true;
}


function openResultDestination(destination) {
  const target = String(destination || '').trim();

  if (target === 'library' || target === 'speakers') return showView(target);
  return false;
}

function setItemTab(name) {
  const target = itemPanels.some(panel => panel.dataset.itemPanel === name) ? name : 'transcript';
  activeItemTab = target;
  itemPanels.forEach(panel => { panel.hidden = panel.dataset.itemPanel !== target; });
  itemTabButtons.forEach(button => {
    const active = button.dataset.itemTab === target;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
}

function syncCreateViewState() {
  const progressVisible = Boolean(progressCard && !progressCard.hidden);
  if (form) form.hidden = jobRunning && progressVisible;
  const dismiss = document.querySelector('#progress-dismiss');
  if (dismiss) dismiss.hidden = jobRunning || !progressVisible;
  updateJobChip(lastProgressJob);
}

function syncTabStops() {
  document.querySelectorAll('[role="tablist"]').forEach(tablist => {
    const tabs = [...tablist.querySelectorAll('[role="tab"]')];
    const selected = tabs.find(tab => tab.getAttribute('aria-selected') === 'true') || tabs[0];
    tabs.forEach(tab => tab.setAttribute('tabindex', tab === selected ? '0' : '-1'));
  });
}

function applyRouteFromLocation({fromHistory = false, initial = false} = {}) {
  let route = parseRouteHash(window.location.hash);
  if (!route && initial) {
    const requestedView = requestedParameters.get('view');
    const view = Object.hasOwn(viewRouteHashes, requestedView) ? requestedView : 'new';
    route = {view, itemId: ''};

  }
  if (!route) route = {view: 'new', itemId: ''};
  if (route.view === 'item') {
    if (currentJob && String(currentJob.id) === route.itemId) {
      if (!showView('item', {itemId: route.itemId, replace: initial}) && fromHistory) syncRouteHash(currentRouteHash);
      return;
    }
    if (!confirmLeave({target: 'item', itemId: route.itemId})) {
      if (fromHistory) syncRouteHash(currentRouteHash);
      return;
    }
    const opening = openLibraryItem(route.itemId);
    const requestSequence = resultRequestSequence;
    opening.then(() => {
      // A stale route must not hide newer content or cancel its in-flight request.
      if (requestSequence !== resultRequestSequence) return;
      if (!currentJob || String(currentJob.id) !== route.itemId) showView('library', {replace: true});
    });
    return;
  }

  const opened = showView(route.view, {replace: initial});
  if (!opened && fromHistory) syncRouteHash(currentRouteHash);
}
