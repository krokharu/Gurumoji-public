/* Explicit imports and local navigation; server text is rendered as text only. */
(() => {
  const $ = selector => document.querySelector(selector);
  const node = (tag, text = '') => { const element = document.createElement(tag); element.textContent = text; return element; };
  const button = (text, action) => { const element = node('button', text); element.type = 'button'; element.className = 'secondary-button'; element.addEventListener('click', action); return element; };
  async function request(url, value) {
    const response = await apiFetch(url, value === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '処理を完了できませんでした。');
    return data;
  }
  const controlRequests = new WeakMap();
  async function busy(control, status, work, owns = () => true) {
    if (control.disabled || !owns()) return;
    const token = {}; controlRequests.set(control,token);
    control.disabled = true; status.textContent = '確認しています…';
    try { await work(); } catch (error) { if(owns()) status.textContent = error.message; }
    finally { if(controlRequests.get(control)===token) control.disabled = false; }
  }
  let searchSequence = 0;
  function searchResults(data, again) {
    const output = $('#cross-search-results'); output.replaceChildren();
    for (const match of data.matches || []) {
      const article = node('article'); const link = node('a', `${match.item_id} / 発話 ${match.segment_id}`);
      link.href = `#/data/${encodeURIComponent(match.item_id)}`;
      article.append(link, node('p', match.text), node('small', `入力版 ${match.source_revision}・分析版 ${match.analysis_revision}${match.similarity === undefined ? '' : `・類似度 ${match.similarity.toFixed(3)}`}`));
      article.append(button('他の会話の似た発話', event => busy(event.currentTarget, $('#cross-search-status'), async () => {
        const sequence = ++searchSequence;
        const next = await request(`/api/library/search/similar?${new URLSearchParams({item_id:match.item_id,segment_id:match.segment_id})}`);
        if (sequence !== searchSequence) return;
        searchResults(next); $('#cross-search-status').textContent = `${next.matches.length}件。${next.limitations}`;
      })));
      output.append(article);
    }
    if (data.pagination?.has_more && again) output.append(button('次の50件', () => again(data.pagination.offset + data.pagination.limit)));
  }
  $('#cross-search-form')?.addEventListener('submit', event => {
    event.preventDefault(); const control = event.submitter || event.currentTarget.querySelector('button');
    const query = $('#cross-search-query').value;
    const run = offset => busy(control, $('#cross-search-status'), async () => {
      const sequence = ++searchSequence;
      const data = await request(`/api/library/search/segments?${new URLSearchParams({q:query,offset,limit:50})}`);
      if (sequence !== searchSequence) return;
      searchResults(data, run); $('#cross-search-status').textContent = `${data.pagination.total}件${data.scan_truncated ? '（検索対象の上限に到達）' : ''}。除外発話は表示しません。`;
    });
    run(0);
  });
  const importStatus = $('#research-import-status');
  let importSequence=0;
  function owner() {
    const id = currentJobId, job = currentJob, navigation=resultRequestSequence;
    if (!id || !job) throw new Error('取り込む会話を開いてください。');
    return {id, valid:() => currentJobId === id && currentJob === job && resultRequestSequence===navigation};
  }
  function importBusy(control, work) {
    const target=owner(),sequence=++importSequence;
    const valid=target.valid;target.valid=()=>valid() && sequence===importSequence;
    return busy(control,importStatus,()=>work(target),target.valid);
  }
  $('#research-notes-preview')?.addEventListener('click', event => importBusy(event.currentTarget, async target => {
    const data = await request(`/api/library/${encodeURIComponent(target.id)}/research-notes/preview`, {});
    if (!target.valid()) return;
    const output = $('#research-import-preview'); output.replaceChildren();
    const selected = [];
    for (const note of data.notes) {
      const details = node('details'); details.append(node('summary', `${note.title}・${note.changed ? '変更あり' : '取込済み'}・版${note.version}`));
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = note.changed; checkbox.disabled = !note.changed;
      const label = node('label', ' この差分を取り込む'); label.prepend(checkbox); details.append(label, node('pre', note.diff.join('\n')));
      if (note.diff_truncated) details.append(node('p', `差分${note.diff_lines}行の先頭200行を表示しています。原本も確認してください。`));
      selected.push({checkbox,note}); output.append(details);
    }
    if (selected.some(entry => entry.note.changed)) output.append(button('選んだ差分を取り込む', event => busy(event.currentTarget, importStatus, async () => {
      if (!target.valid()) throw new Error('対象の会話が変わっています。差分を再確認してください。');
      const notes = selected.filter(entry => entry.checkbox.checked).map(entry => ({note_id:entry.note.note_id,source_hash:entry.note.source_hash,base_hash:entry.note.base_hash}));
      if (!notes.length) throw new Error('取り込む差分を選んでください。');
      const result = await request(`/api/library/${encodeURIComponent(target.id)}/research-notes/import`, {notes});
      if (target.valid()) { output.replaceChildren(); importStatus.textContent = `${result.imported.length}件を履歴付きで取り込みました。`; }
    },target.valid)));
    importStatus.textContent = `${data.notes.length}件の研究ノートを確認しました。`;
  }));
  $('#research-notes-history')?.addEventListener('click', event => importBusy(event.currentTarget, async target => {
    const data = await request(`/api/library/${encodeURIComponent(target.id)}/research-notes`);
    if (!target.valid()) return;
    const output = $('#research-import-preview'); output.replaceChildren();
    for (const note of data.notes) {
      const details = node('details'); details.append(node('summary', `${note.title}・版${note.version}・${{pending:'承認待ち',researcher_note:'研究者メモ'}[note.review_status]||'確認が必要'}・原本${{current:'一致',changed:'変更あり',missing:'欠落'}[note.source_status]}`),node('pre',note.text)); output.append(details);
    }
    importStatus.textContent = `${data.notes.length}件を表示しました。`;
  }));
  $('#external-analysis-import')?.addEventListener('click', event => importBusy(event.currentTarget, async target => {
    const file = $('#external-analysis-file').files[0];
    if (!file || file.size > 5*1024*1024) throw new Error('5MiB以下の結果JSONを選んでください。');
    const payload = JSON.parse(await file.text());
    if (!target.valid()) return;
    const result = await request(`/api/library/${encodeURIComponent(target.id)}/analysis/external`, payload);
    if (target.valid()) importStatus.textContent = `外部分析を未承認で保存しました。run ${result.run.id}`;
  }));
  const vaultStatus = $('#vault-tools-status');
  $('#vault-roots-load')?.addEventListener('click', event => busy(event.currentTarget, vaultStatus, async () => {
    const data = await request('/api/vaults/roots'); const fields = $('#vault-roots-fields'); fields.replaceChildren();
    for (const [kind, value] of Object.entries(data.roots)) {
      const label = node('label', `${kind} 保存先名`); label.className = 'field'; const input = document.createElement('input'); input.name = kind; input.value = value; input.pattern = '[A-Za-z0-9_-]{1,60}'; input.required = true; label.append(input); fields.append(label);
    }
    $('#vault-roots-form').hidden = false; vaultStatus.textContent = '英数字・ハイフン・下線で、空の保存先名を指定できます。';
  }));
  let vaultSequence = 0;
  $('#vault-roots-form')?.addEventListener('submit', event => {
    event.preventDefault(); const roots = Object.fromEntries([...$('#vault-roots-fields').querySelectorAll('input')].map(input => [input.name,input.value]));
    const sequence = ++vaultSequence;
    busy(event.submitter, vaultStatus, async () => {
      const plan = await request('/api/vaults/roots/preview', {roots}); if (sequence !== vaultSequence) return;
      const output = $('#vault-tools-preview'); output.replaceChildren(node('p', `${plan.file_count}ファイルをコピーします。元のファイルは残ります。`));
      for (const entry of plan.entries) output.append(node('p', `${entry.kind}: ${entry.from} → ${entry.to}`));
      output.append(button('バックアップして保存先を変更', event => busy(event.currentTarget, vaultStatus, async () => {
        if (sequence !== vaultSequence) return;
        const result = await request('/api/vaults/roots/apply', plan); if(sequence!==vaultSequence) return;
        output.replaceChildren(); vaultStatus.textContent = `${result.file_count}ファイルを検証して切り替えました。`;
      },()=>sequence===vaultSequence)));
      vaultStatus.textContent = '変更内容を確認してください。';
    });
  });
  $('#vault-roots-rollback')?.addEventListener('click', event => busy(event.currentTarget, vaultStatus, async () => {
    const sequence=++vaultSequence; const result = await request('/api/vaults/roots/rollback', {}); if(sequence!==vaultSequence) return;
    $('#vault-tools-preview').replaceChildren(); vaultStatus.textContent = result.status === 'rolled_back' ? '元の保存先へ戻しました。コピー済みファイルも残っています。' : '戻す保存先変更はありません。';
  }));
  $('#vault-publication-preview')?.addEventListener('click', event => busy(event.currentTarget, vaultStatus, async () => {
    const sequence = ++vaultSequence; const plan = await request('/api/vaults/publication/preview', {}); if (sequence !== vaultSequence) return;
    const output = $('#vault-tools-preview'); output.replaceChildren(node('p', `固定結果${plan.runs.length}件の台帳・図表仕様をVaultへ公開します。`));
    output.append(button('バックアップして公開', event => busy(event.currentTarget, vaultStatus, async () => {
      if (sequence !== vaultSequence) return;
      const result = await request('/api/vaults/publication/apply', plan); if(sequence!==vaultSequence) return;
      output.replaceChildren(); const complete=result.outcomes.filter(row=>Object.values(row.outputs).length>0 && Object.values(row.outputs).every(status=>status==='published')).length;
      vaultStatus.textContent = `公開完了${complete}件・未完了${result.outcomes.length-complete}件。`;
      for(const row of result.outcomes) output.append(node('p',`run ${row.run_id}: ${Object.entries(row.outputs).map(([kind,status])=>`${kind}=${status}`).join(' / ')}`));
    },()=>sequence===vaultSequence)));
    vaultStatus.textContent = '公開対象を確認してください。';
  }));
})();
