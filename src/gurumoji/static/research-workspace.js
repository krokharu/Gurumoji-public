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
})();
