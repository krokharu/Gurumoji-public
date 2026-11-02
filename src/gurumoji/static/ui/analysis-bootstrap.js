/* 公開版の画面処理: analysis-bootstrap。共有状態はapp.jsで管理する。 */
listen(analysisItemSelect, 'change', () => loadAnalysisItem(analysisItemSelect.value));

listen(document.querySelector('#analysis-refresh-button'), 'click', () => {
  if (!analysisState.itemId) return;
  if (hasUnsavedAnalysisChanges() && !window.confirm('未保存の分析設定・手動コード・準備記録を破棄して再集計しますか？')) return;
  loadAnalysisItem(analysisState.itemId, {discardDirty: true});
});

listen(analysisCard, 'click', event => {
  const runClassification = event.target.closest('[data-run-segment-classification]');
  if (runClassification) {
    runSegmentClassification();
    return;
  }
  const applyClassification = event.target.closest('[data-apply-classification-proposal]');
  if (applyClassification) {
    const segmentId = applyClassification.dataset.analysisSegmentId;
    const result = ((analysisState.data || {}).segment_classification || {}).result || {};
    const row = (result.segments || []).find(value => String(value.segment_id) === String(segmentId));
    const source = row && row[applyClassification.dataset.applyClassificationProposal];
    if (source) {
      const annotation = analysisAnnotation(segmentId);
      annotation.dialogue_act = source.dialogue_act || '';
      annotation.importance_score = source.importance_score ?? null;
      annotation.review_score = source.review_score ?? null;
      annotation.sensitivity_score = source.sensitivity_score ?? null;
      annotation.classification_status = 'draft';
      setAnalysisDirty(true);
      renderAnalysisWorkspace();
    }
    return;
  }
  const scope = event.target.closest('[data-analysis-scope]');
  if (scope) {
    analysisState.automaticScope = scope.dataset.analysisScope === 'speakers' ? 'speakers' : 'overall';
    renderAnalysisWorkspace();
    return;
  }
  const selectedSpeaker = event.target.closest('[data-analysis-speaker-id]');
  if (selectedSpeaker) {
    analysisState.selectedSpeaker = selectedSpeaker.dataset.analysisSpeakerId || '';
    const mobile = window.matchMedia('(max-width: 959px)').matches;
    renderAnalysisWorkspace();
    if (mobile) {
      window.requestAnimationFrame(() => {
        const detail = analysisCard.querySelector('.analysis-mobile-layout .analysis-speaker-detail');
        if (!detail) return;
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        detail.scrollIntoView({behavior: reducedMotion ? 'auto' : 'smooth', block: 'start'});
      });
    }
    return;
  }
  const jump = event.target.closest('[data-analysis-jump]');
  if (jump) {
    const content = jump.closest('.analysis-content');
    if (content?.querySelector('[data-analysis-page]')) {
      selectAnalysisPage(jump.dataset.analysisJump);
      return;
    }
    const target = content && content.querySelector(`[data-analysis-anchor="${jump.dataset.analysisJump}"]`);
    if (target) {
      content.querySelectorAll('[data-analysis-jump]').forEach(button => {
        const active = button === jump;
        button.classList.toggle('active', active);
        button.setAttribute('aria-current', active ? 'true' : 'false');
      });
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      target.scrollIntoView({behavior: reducedMotion ? 'auto' : 'smooth', block: 'start'});
    }
    return;
  }
  const mode = event.target.closest('[data-analysis-mode]');
  if (mode) {
    setAnalysisMode(mode.dataset.analysisMode);
    return;
  }
  const methodSelect = event.target.closest('[data-analysis-method-select]');
  if (methodSelect) {
    analysisMethodState().selected = methodSelect.dataset.analysisMethodSelect;
    renderAnalysisWorkspace();
    return;
  }
  if (event.target.closest('[data-analysis-methods-refresh]')) {
    invalidateAnalysisMethodOverview();
    renderAnalysisWorkspace();
    return;
  }
  const save = event.target.closest('[data-analysis-save]');
  if (save) {
    saveAnalysis();
    return;
  }
  const runTermCrosstab = event.target.closest('[data-analysis-run-term-crosstab]');
  if (runTermCrosstab) {
    const terms = Array.isArray(analysisState.config.crosstab_terms) ? analysisState.config.crosstab_terms : [];
    if (!terms.length) {
      setAlert(document.querySelector('#analysis-message'), '検定する単語を1つ以上入力または選択してください。', true);
      return;
    }
    analysisTermRunRequested = true;
    saveAnalysis();
    return;
  }
  const termChoice = event.target.closest('[data-analysis-crosstab-term]');
  if (termChoice) {
    const term = String(termChoice.dataset.analysisCrosstabTerm || '').trim();
    const selected = new Set(Array.isArray(analysisState.config.crosstab_terms) ? analysisState.config.crosstab_terms : []);
    if (selected.has(term)) selected.delete(term);
    else if (selected.size < 30) selected.add(term);
    analysisState.config.crosstab_terms = [...selected];
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
    return;
  }
  const addInteractionLink = event.target.closest('[data-analysis-add-interaction-link]');
  if (addInteractionLink) {
    const sourceId = addInteractionLink.dataset.analysisAddInteractionLink;
    const bySource = (attribute) => [...addInteractionLink.closest('.analysis-segment-card').querySelectorAll(`[${attribute}]`)]
      .find(control => control.getAttribute(attribute) === sourceId);
    const target = bySource('data-analysis-interaction-target');
    const relation = bySource('data-analysis-interaction-relation');
    const memo = bySource('data-analysis-interaction-memo');
    if (!target || !target.value || !relation || !relation.value) {
      setAlert(document.querySelector('#analysis-message'), '対象発話と関係を選択してください。', true);
      return;
    }
    const annotation = analysisAnnotation(sourceId);
    const links = Array.isArray(annotation.interaction_links) ? annotation.interaction_links : [];
    const candidate = {
      target_segment_id: target.value,
      relation: relation.value,
      evidence_memo: memo ? memo.value.trim() : ''
    };
    const duplicate = links.some(link => link.target_segment_id === candidate.target_segment_id
      && link.relation === candidate.relation && link.evidence_memo === candidate.evidence_memo);
    if (!duplicate) annotation.interaction_links = [...links, candidate];
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
    return;
  }
  const removeInteractionLink = event.target.closest('[data-analysis-remove-interaction-link]');
  if (removeInteractionLink) {
    const sourceId = removeInteractionLink.dataset.analysisInteractionSource;
    const index = Number(removeInteractionLink.dataset.analysisInteractionIndex);
    const annotation = analysisAnnotation(sourceId);
    if (Number.isInteger(index) && index >= 0) {
      annotation.interaction_links = (annotation.interaction_links || []).filter((_, position) => position !== index);
      setAnalysisDirty(true);
      renderAnalysisWorkspace();
    }
    return;
  }
  const addCode = event.target.closest('[data-analysis-add-code]');
  if (addCode) {
    const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
    const id = self.crypto && self.crypto.randomUUID
      ? `code_${self.crypto.randomUUID().replaceAll('-', '').slice(0, 16)}`
      : `code_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
    codebook.push({
      id,
      label: `新しいコード ${codebook.length + 1}`,
      description: '', include_example: '', exclude_example: '', category: '', theme: '',
      color: speakerThemeColors[codebook.length % speakerThemeColors.length]
    });
    analysisState.config.codebook = codebook;
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
    const target = analysisCard.querySelector(`[data-analysis-code-id="${id}"][data-analysis-code-field="label"]`);
    if (target) {
      target.focus();
      target.select();
    }
    return;
  }
  const removeCode = event.target.closest('[data-analysis-remove-code]');
  if (removeCode) {
    const codeId = removeCode.dataset.analysisRemoveCode;
    const code = (analysisState.config.codebook || []).find(item => item.id === codeId);
    const applied = Object.values(analysisState.annotations).some(item => (item.codes || []).includes(codeId));
    if (applied && !window.confirm(`「${code ? code.label : 'このコード'}」と発話への付与を削除しますか？`)) return;
    analysisState.config.codebook = (analysisState.config.codebook || []).filter(item => item.id !== codeId);
    Object.values(analysisState.annotations).forEach(item => {
      item.codes = (item.codes || []).filter(value => value !== codeId);
    });
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
  }
});

listen(analysisCard, 'input', event => {
  const control = event.target;
  if (updateAnalysisConfigFromControl(control)) return;
  if (updateAnalysisCodeFromControl(control)) return;
  if (updateAnalysisAnnotationFromControl(control)) return;
  if (control.dataset.analysisSegmentQuery !== undefined) {
    analysisState.segmentQuery = control.value;
    syncAnalysisControls(control, '[data-analysis-segment-query]', () => true);
    refreshAnalysisSegmentLists();
    return;
  }
  if (control.dataset.analysisAnnotatedOnly !== undefined) {
    analysisState.annotatedOnly = control.checked;
    syncAnalysisControls(control, '[data-analysis-annotated-only]', () => true);
    refreshAnalysisSegmentLists();
    return;
  }
  const speaker = control.dataset.analysisExcludedSpeaker;
  if (speaker !== undefined) {
    const excluded = new Set(analysisState.config.excluded_speakers || []);
    if (control.checked) excluded.add(speaker); else excluded.delete(speaker);
    analysisState.config.excluded_speakers = [...excluded];
    syncAnalysisControls(control, '[data-analysis-excluded-speaker]', peer => peer.dataset.analysisExcludedSpeaker === speaker);
    setAnalysisDirty(true);
  }
});

window.addEventListener('scroll', scheduleAnalysisNavigationSync, {passive: true});

window.addEventListener('resize', scheduleAnalysisNavigationSync, {passive: true});
