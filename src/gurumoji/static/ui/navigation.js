/* 公開版の画面処理: navigation。共有状態はapp.jsで管理する。 */

function hasUnsavedAnalysisChanges() {
  return Boolean(analysisState.dirty || preparationDirty);
}

function routeHash(view, id = '') {
  const encoded = id ? encodeURIComponent(String(id)) : '';
  if (view === 'item') return `#/data/${encoded}`;
  if (view === 'analysis' && encoded) return `#/analysis/${encoded}`;
  return viewRouteHashes[view] || '#/new';
}

function parseRouteHash(hash) {
  const parts = String(hash || '').replace(/^#\/?/, '').split('/').filter(Boolean).map(part => {
    try { return decodeURIComponent(part); } catch (_) { return part; }
  });
  const [head, id = ''] = parts;
  if (head === 'data' && id) return {view: 'item', itemId: id};
  if (head === 'data') return {view: 'library', itemId: ''};
  if (head === 'analysis') return {view: 'analysis', itemId: id};
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

function confirmLeave({target, itemId = '', analysisItemId = ''}) {
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
  const requestedAnalysisId = String(analysisItemId || '').trim();
  const analysisVisible = analysisCard && !analysisCard.hidden;
  const switchingAnalysisItem = target === 'analysis' && requestedAnalysisId && requestedAnalysisId !== analysisState.itemId;
  const leavingAnalysis = hasUnsavedAnalysisChanges()
    && (switchingAnalysisItem || (analysisVisible && target !== 'analysis'));
  if (leavingAnalysis && !window.confirm('分析設定・手動コード・準備記録に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  return true;
}

function loadAnalysisView(requestedItemId, {discardDirty = false} = {}) {
  if (!analysisCard) return;
  if (requestedItemId && analysisCatalogLoaded) {
    if (requestedItemId !== analysisState.itemId || !analysisState.data) {
      loadAnalysisItem(requestedItemId, {discardDirty});
    } else {
      if (analysisItemSelect) analysisItemSelect.value = requestedItemId;
      const executionView = document.querySelector('#analysis-execution-view');
      if (executionView) executionView.hidden = true;
      renderAnalysisWorkspace();
      onContentAnalysisLoaded();
    }
    return;
  }
  if (requestedItemId) {
    analysisState.itemId = requestedItemId;
    analysisState.data = null;
    if (analysisItemSelect) analysisItemSelect.value = requestedItemId;
  }
  loadAnalysisCatalog();
}

function setActiveNavigation(view) {
  [
    [showNewButton, view === 'new'],
    [showLibraryButton, view === 'library' || view === 'item'],
    [showAnalysisButton, view === 'analysis'],
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
    [showLibraryAnalysisButton, view === 'analysis']
  ].forEach(([button, active]) => {
    if (!button) return;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
}

function showView(view, {analysisItemId = '', itemId = '', force = false, replace = false} = {}) {
  const target = view === 'item' || Object.hasOwn(viewRouteHashes, view) ? view : 'new';
  const requestedAnalysisId = ANALYSIS_COMING_SOON ? '' : String(analysisItemId || '').trim();
  if (target === 'item' && !currentJob) return false;
  const targetItemId = target === 'item' ? String(itemId || currentJob.id) : '';
  if (!force && !confirmLeave({target, itemId: targetItemId, analysisItemId: requestedAnalysisId})) return false;
  const resultVisible = resultCard && !resultCard.hidden;
  const switchingAnalysisItem = target === 'analysis' && requestedAnalysisId && requestedAnalysisId !== analysisState.itemId;
  const contextChanged = document.body.dataset.view !== target || switchingAnalysisItem;
  const closedFixedViewer = contextChanged && typeof closeFixedAnalysisViewer === 'function' && closeFixedAnalysisViewer();
  const closedAnalysisDialog = contextChanged && typeof closeAnalysisExecutionDialog === 'function' && closeAnalysisExecutionDialog();
  const closedOrchestrationDialog = contextChanged && typeof closeAnalysisOrchestrationDialogs === 'function' && closeAnalysisOrchestrationDialogs();
  if (contextChanged) {
    analysisNavigationGeneration += 1;
    analysisSaveOwner = null;
    analysisSaveInProgress = false;
    analysisTermRunRequested = false;
  }
  resultRequestSequence += 1;
  // A previous view's save cannot own this view's button or messages.
  if (saveButton) saveButton.disabled = false;
  if (resultVisible && currentJobDirty && target !== 'item') setCurrentJobDirty(false);
  if (target !== 'item' && mediaPlayer) mediaPlayer.pause();
  if (createView) createView.hidden = target !== 'new';
  if (processedDataHub) processedDataHub.hidden = !['library', 'analysis'].includes(target);
  if (libraryCard) libraryCard.hidden = target !== 'library';
  if (analysisCard) analysisCard.hidden = target !== 'analysis';
  if (speakerRegistryCard) speakerRegistryCard.hidden = target !== 'speakers';
  if (resultCard) resultCard.hidden = target !== 'item';
  priorDataPanels.forEach(panel => { panel.hidden = panel.dataset.priorPanel !== target; });
  document.body.dataset.view = target;
  setActiveNavigation(target);
  if (closedFixedViewer || closedAnalysisDialog || closedOrchestrationDialog) {
    const navigation = target === 'analysis' ? showAnalysisButton : target === 'speakers' ? showSpeakersButton
      : priorDataButtons.find(button => button.dataset.priorView === target)
        || (target === 'new' ? showNewButton : showLibraryButton);
    if (navigation?.isConnected && !navigation.closest('[hidden]')) navigation.focus();
  }
  if (target === 'analysis' && !ANALYSIS_COMING_SOON) loadAnalysisView(requestedAnalysisId, {discardDirty: force || Boolean(switchingAnalysisItem)});
  if (target === 'library') loadLibrary();
  if (target === 'speakers' && speakerRegistryCard) loadSpeakerRegistry();
  if (target === 'folders') loadLibraryGroupManager();
  if (target === 'new') {
    renderMobileWizard();
    syncCreateViewState();
  }
  const hashId = target === 'item'
    ? targetItemId
    : (target === 'analysis' ? (requestedAnalysisId || analysisState.itemId) : '');
  syncRouteHash(routeHash(target, hashId), {replace});
  document.dispatchEvent(new CustomEvent('gurumoji-view-change', {detail: {view: target}}));
  return true;
}

function openAnalysisForItem(itemId) {
  if (ANALYSIS_COMING_SOON) return showView('analysis');
  const targetItemId = String(itemId || '').trim();
  if (!targetItemId) return false;
  const returning = analysisEvidenceReturn?.itemId === targetItemId;
  const sameRevision = currentJob && analysisState.data
    && Number(currentJob.revision_count) === Number(analysisState.data.item.revision_count);
  if (returning && sameRevision) {
    analysisCatalog = analysisEvidenceReturn.catalog;
    analysisCatalogLoaded = true;
  }
  const opened = showView('analysis', {analysisItemId: targetItemId});
  if (opened && returning && sameRevision) {
    restoreAnalysisEvidencePosition();
    pollContentInsights();
  }
  return opened;
}

function openResultDestination(destination) {
  const target = String(destination || '').trim();
  if (target === 'analysis') return openAnalysisForItem(currentJobId);
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
    route = {view, itemId: view === 'analysis' ? String(requestedParameters.get('item') || '') : ''};
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
  const opened = showView(route.view, {analysisItemId: route.view === 'analysis' ? route.itemId : '', replace: initial});
  if (!opened && fromHistory) syncRouteHash(currentRouteHash);
}
