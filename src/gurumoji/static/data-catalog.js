/* Conversation selection stays separate from transcript edits. */
(() => {
  const $ = id => document.getElementById(id);
  const dialog = $('data-catalog-dialog');
  if (!dialog) return;
  let catalog = {items: [], groups: [], tags: [], definitions: []};
  let editing = null;
  const selected = new Set();
  const status = message => { $('data-catalog-status').textContent = message; };
  const element = (tag, text) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; return e; };
  const button = (text, action) => { const b = element('button', text); b.type = 'button'; b.className = 'secondary-button compact-button'; b.addEventListener('click', () => act(action)); return b; };
  async function api(url, body, method = 'POST') {
    const response = await apiFetch(url, {method, headers: {'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '保存できませんでした。');
    return data;
  }
  async function act(action) {
    const controls = [...dialog.querySelectorAll('button')];
    controls.forEach(b => { b.disabled = true; });
    try { await action(); } catch (error) { status(error.message); }
    finally { controls.forEach(b => { b.disabled = false; }); }
  }
  function options(select, rows, key, empty) {
    const value = select.value;
    select.replaceChildren(new Option(empty, ''));
    rows.forEach(row => select.add(new Option(`${row.name}（${row.item_count}件）`, row[key])));
    select.value = [...select.options].some(o => o.value === value) ? value : '';
  }
  document.addEventListener('gurumoji-library-catalog', event => {
    options($('library-data-group'), event.detail.data_groups || [], 'group_id', 'すべての分析グループ');
    options($('library-tag'), event.detail.tags || [], 'tag_id', 'すべてのタグ');
  });
  ['library-data-group', 'library-tag'].forEach(id => $(id)?.addEventListener('change', () => loadLibrary()));
  function count() { $('data-selection-count').textContent = `${selected.size}件選択`; }
  async function refresh() {
    catalog = await api('/api/library/catalog', undefined, 'GET');
    const ids = new Set(catalog.items.map(i => i.id));
    [...selected].forEach(id => { if (!ids.has(id)) selected.delete(id); });
    $('data-catalog-items').replaceChildren();
    catalog.items.forEach(item => {
      const label = element('label'); label.className = 'comparison-override-check';
      const check = element('input'); check.type = 'checkbox'; check.value = item.id;
      check.checked = selected.has(item.id);
      check.addEventListener('change', () => { if (check.checked) selected.add(item.id); else selected.delete(item.id); count(); });
      const tags = catalog.tags.filter(t => item.tag_ids.includes(t.tag_id)).map(t => t.name);
      const groups = catalog.groups.filter(g => g.item_ids.includes(item.id)).map(g => g.name);
      label.append(check, element('span', `${item.name} / タグ: ${tags.join('、') || 'なし'} / 分析グループ: ${groups.join('、') || 'なし'}`));
      $('data-catalog-items').append(label);
    });
    count();
    const target = $('data-assignment'), previous = target.value;
    target.replaceChildren(new Option('選択してください', ''));
    catalog.tags.forEach(t => target.add(new Option(`タグ: ${t.name}`, `tags:${t.tag_id}`)));
    catalog.groups.filter(g => g.kind === 'manual').forEach(g => target.add(new Option(`グループ: ${g.name}`, `groups:${g.group_id}`)));
    target.value = previous;
    $('data-catalog-entities').replaceChildren();
    for (const [entity, rows, key] of [['tags', catalog.tags, 'tag_id'], ['data-groups', catalog.groups, 'group_id']]) {
      rows.forEach(row => {
        const line = element('div'); line.className = 'data-catalog-entity';
        const input = element('input'); input.value = row.name; input.maxLength = 120; input.setAttribute('aria-label', `${row.name}の名前`);
        line.append(element('strong', `${entity === 'tags' ? 'タグ' : row.kind === 'rule' ? '条件グループ' : '手動グループ'} / ${row.item_count}件`), input);
        line.append(button('名前を保存', async () => {
          await api(`/api/library/${entity}/${row[key]}`, {...row, name: input.value}, 'PUT');
          await refresh(); await loadLibrary(); status('名前を保存しました。');
        }));
        if (row.kind === 'rule') line.append(button('条件を編集', async () => {
          editing = row; $('data-group-name').value = row.name; $('data-group-kind').value = 'rule'; $('data-group-kind').disabled = true;
          $('data-rule-mode').value = row.rule.mode; $('data-rule-conditions').replaceChildren();
          row.rule.conditions.forEach(addCondition); toggleRule();
          $('data-group-save').textContent = 'グループの条件を保存'; $('data-group-cancel').hidden = false;
          $('data-group-name').focus();
        }));
        line.append(button('削除', async () => {
          if (!window.confirm(`「${row.name}」を削除します。使用中の会話は${row.item_count}件です。過去の分析で固定した所属・属性値は変わりません。`)) return;
          await api(`/api/library/${entity}/${row[key]}`, undefined, 'DELETE');
          if (editing?.group_id === row[key]) resetGroup();
          await refresh(); await loadLibrary(); status('削除しました。過去の分析は保存時点のままです。');
        }));
        $('data-catalog-entities').append(line);
      });
    }
    $('data-definition-list').replaceChildren();
    catalog.definitions.forEach(d => {
      const row = element('p', `${{conversation: '会話', speaker: '話者', segment: '発話'}[d.scope]} / ${d.key} / ${d.data_type} / ${d.type_status} / 版${d.version} `);
      row.append(button('この定義を編集', async () => {
        $('data-definition-scope').value = d.scope; $('data-definition-key').value = d.key;
        $('data-definition-type').value = d.data_type; $('data-definition-level').value = d.measurement_level;
        $('data-definition-key').focus();
      }));
      $('data-definition-list').append(row);
    });
  }
  function conditionKeys() {
    return [
      ...catalog.definitions.filter(d => d.scope !== 'segment').map(d => ({value: `${d.scope}:${d.key}`, label: `${d.scope === 'conversation' ? '会話属性' : '話者属性'}: ${d.key}${d.origin === 'discovered' ? '（型未確定）' : ''}`, type: d.data_type})),
      ...catalog.tags.map(t => ({value: `tag:${t.tag_id}`, label: `タグ: ${t.name}`, type: 'boolean'})),
      ...['session_role', 'organization', 'department', 'attendance_status'].map(key => ({value: `speaker:${key}`, label: `話者: ${{session_role: '役割', organization: '組織', department: '部署', attendance_status: '出席状態'}[key]}`, type: 'string'})),
      ...['char_count', 'start', 'end', 'speaker_label'].map(key => ({value: `segment:${key}`, label: `発話: ${{char_count:'文字数', start:'開始秒', end:'終了秒', speaker_label:'話者ラベル'}[key]}`, type: key === 'speaker_label' ? 'string' : 'number'}))
    ];
  }
  function addCondition(condition = {}) {
    const row = element('div'); row.className = 'data-rule-condition';
    const key = element('select'); key.setAttribute('aria-label', '条件の属性またはタグ');
    conditionKeys().forEach(k => key.add(new Option(k.label, k.value)));
    if (condition.scope) key.value = `${condition.scope}:${condition.key}`;
    const op = element('select'); op.setAttribute('aria-label', '条件の比較方法');
    [['eq', '等しい'], ['ne', '異なる'], ['exists', '値・タグがある'], ['gte', '以上'], ['lte', '以下']].forEach(([v, text]) => op.add(new Option(text, v)));
    op.value = condition.op || (key.value.startsWith('tag:') ? 'exists' : 'eq');
    const value = element('input'); value.setAttribute('aria-label', '条件の値'); value.value = condition.value ?? '';
    const update = () => { if (key.value.startsWith('tag:')) op.value = 'exists'; value.disabled = op.value === 'exists'; $('data-rule-preview-result').textContent = ''; };
    key.addEventListener('change', update); op.addEventListener('change', update); value.addEventListener('input', () => { $('data-rule-preview-result').textContent = ''; }); update();
    row.append(key, op, value, button('この条件を削除', async () => { row.remove(); $('data-rule-preview-result').textContent = ''; }));
    $('data-rule-conditions').append(row);
  }
  function rule() {
    return {mode: $('data-rule-mode').value, conditions: [...$('data-rule-conditions').children].map(row => {
      const [key, op, input] = row.children; const split = key.value.indexOf(':');
      if (split < 0) throw new Error('先に属性キーまたはタグを作成してください。');
      const scope = key.value.slice(0, split), attribute = key.value.slice(split + 1);
      const type = conditionKeys().find(k => k.value === key.value)?.type;
      let value = input.value;
      if (op.value !== 'exists' && (['number', 'integer'].includes(type) || ['gte', 'lte'].includes(op.value))) {
        if (!value.trim() || !Number.isFinite(Number(value))) throw new Error('条件の値は数値で入力してください。');
        value = Number(value);
      } else if (op.value !== 'exists' && type === 'boolean') {
        if (!['true', 'false'].includes(value)) throw new Error('真偽値は true または false で入力してください。');
        value = value === 'true';
      }
      return {scope, key: attribute, op: op.value, value: op.value === 'exists' ? null : value};
    })};
  }
  function toggleRule() {
    $('data-group-rule').hidden = $('data-group-kind').value !== 'rule';
    if (!$('data-group-rule').hidden && !$('data-rule-conditions').children.length) addCondition();
  }
  function resetGroup() {
    editing = null; $('data-group-form').reset(); $('data-group-kind').disabled = false;
    $('data-group-save').textContent = 'グループを作成'; $('data-group-cancel').hidden = true;
    $('data-rule-conditions').replaceChildren(); $('data-rule-preview-result').textContent = ''; toggleRule();
  }
  $('manage-data-catalog-button').addEventListener('click', () => act(async () => { await refresh(); status(''); dialog.showModal(); }));
  $('data-catalog-close').addEventListener('click', () => dialog.close());
  $('data-tag-form').addEventListener('submit', event => { event.preventDefault(); act(async () => {
    await api('/api/library/tags', {name: $('data-tag-name').value}); $('data-tag-form').reset();
    await refresh(); await loadLibrary(); status('タグを作成しました。');
  }); });
  $('data-group-kind').addEventListener('change', toggleRule);
  $('data-rule-add').addEventListener('click', () => addCondition());
  $('data-group-cancel').addEventListener('click', resetGroup);
  $('data-rule-mode').addEventListener('change', () => { $('data-rule-preview-result').textContent = ''; });
  $('data-rule-preview').addEventListener('click', () => act(async () => {
    const preview = await api('/api/library/data-groups/preview', {rule: rule()});
    $('data-rule-preview-result').textContent = `${preview.item_count}件: ${catalog.items.filter(i => preview.item_ids.includes(i.id)).map(i => i.name).join('、') || '該当なし'}`;
  }));
  $('data-group-form').addEventListener('submit', event => { event.preventDefault(); act(async () => {
    const body = {...(editing || {}), name: $('data-group-name').value, kind: $('data-group-kind').value};
    if (body.kind === 'rule') body.rule = rule();
    await api(`/api/library/data-groups${editing ? '/' + editing.group_id : ''}`, body, editing ? 'PUT' : 'POST');
    resetGroup(); await refresh(); await loadLibrary(); status('分析グループを保存しました。');
  }); });
  for (const [id, remove] of [['data-assign', false], ['data-unassign', true]]) $(id).addEventListener('click', () => act(async () => {
    if (!selected.size || !$('data-assignment').value) throw new Error('会話と付与・解除する対象を選択してください。');
    const [entity, identity] = $('data-assignment').value.split(':');
    await api(`/api/library/${entity === 'groups' ? 'data-groups' : 'tags'}/${identity}/members`, {item_ids: [...selected], remove}, 'PUT');
    await refresh(); await loadLibrary(); status(`${selected.size}件の${remove ? '解除' : '付与'}を保存しました。`);
  }));
  $('data-definition-form').addEventListener('submit', event => { event.preventDefault(); act(async () => {
    const scope = $('data-definition-scope').value, key = $('data-definition-key').value;
    const old = catalog.definitions.find(d => d.scope === scope && d.key === key);
    await api('/api/library/attribute-definitions', {...(old || {}), key, scope,
      data_type: $('data-definition-type').value, measurement_level: $('data-definition-level').value}, 'PUT');
    await refresh(); status('属性定義を保存しました。');
  }); });
})();
