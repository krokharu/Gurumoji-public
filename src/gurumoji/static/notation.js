/* Explicit sends only; draft/navigation guards follow the existing editor. */
let notationPreview = null;
let notationBusy = false;
const notationStatus = document.querySelector('#notation-status');
const notationGroups = document.querySelector('#notation-groups');
const notationApply = document.querySelector('#notation-apply');
const notationSourceLabels = {dictionary: '表記辞書', vocabulary: '登録語', speaker_registry: '話者台帳', researcher_history: '研究者の確定履歴', llm: 'AI候補・要確認', unresolved: '未確定'};

function resetNotationView() {
  notationPreview = null;
  if (notationGroups) notationGroups.replaceChildren();
  if (notationStatus) notationStatus.textContent = '';
  if (notationApply) notationApply.hidden = true;
}
function notationCleanEditor() {
  if (typeof currentJobDirty !== 'undefined' && currentJobDirty) throw new Error('未保存の編集があります。先に編集内容を保存してください。');
  if (!currentJobId) throw new Error('会話を開いてください。');
}
async function notationRequest(path, body) {
  const response = await apiFetch(path, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
  const data = await readJsonResponse(response);
  if (!response.ok) throw new Error(data.error || '表記を確認できませんでした。');
  return data;
}
async function withNotationWork(work) {
  if (notationBusy) return;
  notationBusy = true;
  document.querySelectorAll('#notation-preview, #notation-load-review, #notation-apply, #notation-groups button').forEach(b => { b.disabled = true; });
  const owner = currentJob, id = currentJobId, generation = currentJobMutationGeneration;
  const owns = () => currentJobId === id && currentJob === owner && currentJobMutationGeneration === generation;
  try { notationCleanEditor(); await work(id, owns); }
  catch (error) { if (owns()) notationStatus.textContent = error.message; }
  finally {
    notationBusy = false;
    document.querySelectorAll('#notation-preview, #notation-load-review, #notation-apply, #notation-groups button').forEach(b => { b.disabled = false; });
  }
}
function showNotationGroups(groups, review, itemId) {
  notationGroups.replaceChildren();
  groups.forEach(g => {
    const card = document.createElement('section');
    card.className = 'notation-group';
    const title = document.createElement('h4');
    title.textContent = g.variants.map(v => `${v.term} (${v.count}件)`).join(' / ');
    const detail = document.createElement('p');
    const reviewed = review && Object.hasOwn(review.overrides, g.id);
    const choice = reviewed ? review.overrides[g.id] : g.canonical;
    const source = notationSourceLabels[g.source] || `${notationSourceLabels[g.source.replace(/_conflict$/, '')] || '出典'}が競合・未確定`;
    detail.textContent = `表記: ${choice || (reviewed ? '取消済み' : '未確定')} / 出典: ${reviewed ? `研究者の変更（候補の出典: ${source}）` : source}${g.needs_review && !reviewed ? ' / 要確認' : ''}`;
    card.append(title, detail);
    if (review) {
      const label = document.createElement('label');
      label.textContent = '正しい表記 ';
      const input = document.createElement('input');
      input.type = 'text'; input.maxLength = 80; input.value = choice || g.variants[0].term;
      label.append(input); card.append(label);
      const actions = document.createElement('div'); actions.className = 'notation-actions'; card.append(actions);
      for (const [action, text] of [['cancel', '取り消し'], ['change', 'この表記へ変更'], ['register', '辞書へ登録'], ['delete_dictionary', 'この群の辞書項目を削除']]) {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'secondary-button'; button.textContent = text;
        button.addEventListener('click', () => withNotationWork(async (id, owns) => {
          if (id !== itemId) return;
          const result = await notationRequest(`/api/library/${encodeURIComponent(id)}/notation/review`, {
            action, canonical: input.value, group_id: g.id, seq: review.seq, revision_count: review.revision_count});
          if (!owns()) return;
          if (result.id) renderResult(result);
          const updated = await notationRequest(`/api/library/${encodeURIComponent(id)}/notation`);
          if (currentJobId !== id || (typeof currentJobDirty !== 'undefined' && currentJobDirty)) return;
          showNotationGroups(updated.groups, updated, id);
          notationStatus.textContent = result.message || '研究者の変更を保存しました。';
        }));
        actions.append(button);
      }
    }
    notationGroups.append(card);
  });
}
document.querySelector('#notation-preview')?.addEventListener('click', () => withNotationWork(async (id, owns) => {
  const provider = document.querySelector('#notation-provider').value;
  const preview = await notationRequest(`/api/library/${encodeURIComponent(id)}/notation/preview?provider=${encodeURIComponent(provider)}`);
  if (!owns()) return;
  notationPreview = preview;
  showNotationGroups(preview.plan.groups, null, id);
  notationStatus.textContent = `${preview.plan.groups.length}群 / 送信先: ${preview.destination}${preview.model ? ` (${preview.model})` : ''} / 見込み入力トークン: 約${preview.estimated_input_tokens}。送るのは未確定群の表記・出現数・短い前後文だけです。`;
  notationApply.hidden = !preview.plan.groups.length;
}));
document.querySelector('#notation-provider')?.addEventListener('change', resetNotationView);
document.querySelector('#notation-apply')?.addEventListener('click', () => withNotationWork(async (id, owns) => {
  if (!notationPreview) throw new Error('候補を再表示してください。');
  const result = await notationRequest(`/api/library/${encodeURIComponent(id)}/notation`, {provider: notationPreview.provider, preview_hash: notationPreview.preview_hash});
  if (!owns()) return;
  renderResult(result);
  const review = await notationRequest(`/api/library/${encodeURIComponent(id)}/notation`);
  if (currentJobId !== id || (typeof currentJobDirty !== 'undefined' && currentJobDirty)) return;
  showNotationGroups(review.groups, review, id);
  notationStatus.textContent = result.notation_archive_warning || '表記統一の結果と差分を保存しました。AI候補は確認してください。';
}));
document.querySelector('#notation-load-review')?.addEventListener('click', () => withNotationWork(async (id, owns) => {
  const review = await notationRequest(`/api/library/${encodeURIComponent(id)}/notation`);
  if (!owns()) return;
  resetNotationView(); showNotationGroups(review.groups, review, id);
  notationStatus.textContent = review.groups.length ? '保存した表記統一の結果です。' : '表記統一の記録はありません。';
}));
