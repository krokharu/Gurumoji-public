/* Saved-run reading is strictly GET-only. No model calls, automatic recovery,
 * live editor adoption, browser storage or logging of research content.
 * The separate Slides panel has one explicit design-note save operation. */
(() => {
  'use strict';
  const node = id => document.getElementById(`analysis-history-${id}`);
  const state = {epoch:0, runEpoch:0, listRequest:0, pageRequest:0, detailRequest:0, sourceRequest:0, slidesRequest:0,
    itemId:'', runId:'', context:null, run:null, version:null, runOffset:0, offset:0, tab:'history', opener:null, slides:null};
  const labels = {initial:'初期版',task:'タスク',result:'分析結果',decision:'判断',label:'ラベル',legacy_label:'ラベル（旧形式）',event:'イベント',
    add:'追加',update:'更新',delete:'削除',proposal:'提案・未採用',proposed:'提案・未採用',adopt:'採用',adopted:'採用',committed:'採用',reject:'却下',rejected:'却下',defer:'保留',deferred:'保留',conflict:'競合',
    core:'Core',handler:'Handler',interpretation:'会話解釈',statistics:'数量・統計',verification:'独立検証',critic:'批判者',
    completed:'処理終了',succeeded:'処理成功',running:'実行中',failed:'失敗',stopped:'停止',cancelled:'利用者停止',pending:'待機',queued:'待機',accepted:'受付済み',recovery_required:'復旧待ち',quarantined:'結果を隔離'};
  const missing = value => value === null || value === undefined || value === '';
  const text = value => missing(value) ? '未記録' : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
  const label = value => Object.hasOwn(labels,value) ? labels[value] : text(value);
  const el = (tag, value, className) => {const element=document.createElement(tag);if(value!==undefined)element.textContent=text(value);if(className)element.className=className;return element;};
  const button = (value, action) => {const element=el('button',value,'secondary-button');element.type='button';element.addEventListener('click',action);return element;};
  const base = () => `/api/library/${encodeURIComponent(state.itemId)}/analysis/orchestration`;
  const runBase = () => `${base()}/${encodeURIComponent(state.runId)}`;
  const token = () => ({epoch:state.epoch,runEpoch:state.runEpoch,itemId:state.itemId,runId:state.runId});
  const current = stamp => node('dialog').open && stamp.epoch===state.epoch && stamp.runEpoch===state.runEpoch && stamp.itemId===state.itemId && stamp.runId===state.runId && (!state.context || isAnalysisContextCurrent(state.context));
  const queryVersion = () => state.version===null ? '' : `?annotation_version=${encodeURIComponent(state.version)}`;
  async function get(url) {
    const response=await fetch(url,{method:'GET',cache:'no-store',credentials:'same-origin'});
    if(!response.ok)throw Error(`記録を取得できません（HTTP ${response.status}）。`);
    return response.json();
  }
  const notice = value => {node('message').textContent=value;};
  function metadata(entries) {const dl=el('dl',undefined,'analysis-history-metadata');for(const [key,value] of entries){dl.append(el('dt',key),el('dd',value));}return dl;}
  function pageLabel(page, count) {return Number.isInteger(page?.total) ? page.total===0 ? '該当する記録なし' : `${(page.offset||0)+1}〜${(page.offset||0)+count} / ${page.total}件` : `総件数: 未記録 · このページ ${count}件`;}
  function setPagination(prefix, page, count) {node(`${prefix}prev`).disabled=!(page?.offset>0);node(`${prefix}next`).disabled=!page?.has_more;node(`${prefix}page`).textContent=pageLabel(page,count);}
  function clearDetail() {++state.detailRequest;++state.sourceRequest;node('detail').replaceChildren(el('p','記録を選ぶと、変更前後・理由・固定原文を確認できます。'));}
  function close() {
    const wasOpen=Boolean(node('dialog')?.open);++state.epoch;++state.runEpoch;++state.slidesRequest;
    state.slides=null;state.run=null;state.context=null;
    if(wasOpen)node('dialog').close();
    node('run-list')?.replaceChildren();node('timeline')?.replaceChildren();node('detail')?.replaceChildren();node('slides')?.replaceChildren();node('summary')?.replaceChildren();
    for(const id of ['run-title','run-meta','summary-links','target','audit','message'])node(id)?.replaceChildren();
    if(node('selected'))node('selected').hidden=true;
    return wasOpen;
  }
  async function open(options={}) {
    const context=captureAnalysisContext();
    close();state.context=context;state.itemId=String(options.itemId||context.itemId||'');state.runId='';state.version=null;state.runOffset=0;state.offset=0;state.tab='history';state.opener=document.activeElement;
    // A live-run entry may refer to a run other than the currently edited item.
    if(options.itemId && options.itemId!==context.itemId)state.context=null;
    node('target').textContent=`会話: ${options.itemName||context.data?.item?.source_name||state.itemId||'未選択'} · 保存された実行を選択`;
    node('selected').hidden=true;node('empty').hidden=false;node('filters').reset();
    node('dialog').showModal();node('close').focus();
    if(!state.itemId){notice('分析対象の会話を選択してください。');return;}
    await loadRuns(options.runId||'');
  }
  async function loadRuns(preferred='') {
    const stamp=token(),request=++state.listRequest;notice('保存済み実行を取得しています…');
    node('runs-prev').disabled=true;node('runs-next').disabled=true;
    try {
      const data=await get(`${base()}/viewer?limit=20&offset=${state.runOffset}`);
      if(!current(stamp)||request!==state.listRequest)return;
      const runs=Array.isArray(data.runs)?data.runs:[];node('run-list').replaceChildren();
      for(const run of runs) {
        if(!run?.run_id || run.item_id && run.item_id!==state.itemId)continue;
        const b=button('',()=>selectRun(run.run_id));b.className='analysis-history-run-button';b.dataset.runId=run.run_id;b.setAttribute('aria-pressed',String(run.run_id===state.runId));
        b.replaceChildren(el('strong',run.question||run.run_id),el('span',`${label(run.status)} · ${text(run.created_at)}`),el('span',`Run ${run.run_id}`));node('run-list').append(b);
      }
      setPagination('runs-',data.pagination,runs.length);notice(runs.length?'実行を選択すると、固定された入力・版・変更の根拠を読めます。':'保存済み実行はありません。');
      if(preferred)await selectRun(preferred);else if(!state.runId&&runs[0]?.run_id)await selectRun(runs[0].run_id);
    }catch(error){if(current(stamp)&&request===state.listRequest)notice(error.message);}
  }
  function selectTab(tab) {
    state.tab=tab;
    for(const name of ['history','results','labels','slides'])node(`tab-${name}`).setAttribute('aria-pressed',String(tab===name));
    node('records').hidden=tab==='slides';node('slides').hidden=tab!=='slides';
    if(tab==='slides'){++state.pageRequest;clearDetail();return loadSlideTemplates();}
    ++state.slidesRequest;node('kind').value={results:'result',labels:'label'}[tab]||'';state.offset=0;return loadTimeline();
  }
  async function selectRun(runId) {
    ++state.runEpoch;++state.slidesRequest;state.runId=String(runId);state.version=null;state.run=null;state.slides=null;state.offset=0;
    node('filters').reset();state.tab='history';node('records').hidden=false;node('slides').hidden=true;node('slides').replaceChildren();
    for(const name of ['history','results','labels','slides'])node(`tab-${name}`).setAttribute('aria-pressed',String(name==='history'));
    for(const b of node('run-list').querySelectorAll('button'))b.setAttribute('aria-pressed',String(b.dataset.runId===state.runId));
    node('selected').hidden=true;node('empty').hidden=true;clearDetail();node('timeline').replaceChildren();
    await loadTimeline();
  }
  function timelineQuery() {
    const q=new URLSearchParams({limit:'30',offset:String(state.offset)});
    if(state.version!==null)q.set('annotation_version',String(state.version));
    for(const name of ['role','kind','operation','status'])if(node(name).value)q.set(name,node(name).value);
    const after=node('after').value,before=node('before').value;
    if(after&&before&&after>before)throw Error('開始日は終了日以前にしてください。');
    if(after)q.set('after',`${after}T00:00:00Z`);
    if(before)q.set('before',`${before}T23:59:59.999999Z`);
    return q;
  }
  function renderRun(data) {
    const run=data.run,versions=data.versions||{};state.run=run;
    state.version=Number.isInteger(versions.selected)?versions.selected:null;
    node('selected').hidden=false;node('empty').hidden=true;
    node('run-title').textContent=text(run.question||run.run_id);
    node('run-meta').textContent=`Run ${run.run_id} · ${label(run.status)} · 入力版 ${text(run.source_revision)} / 分析版 ${text(run.analysis_revision)} · 保存日時 ${text(run.updated_at)} · 入力hash ${text(run.input_hash)}`;
    node('summary').textContent=text(run.current_summary);
    node('summary-title').textContent=`最新保存の統合結果 · AI下書き · 作成時ラベル v${text(run.summary_annotation_version)}`;node('summary-links').replaceChildren();
    if(run.summary_entry_id)node('summary-links').append(button('この統合結果の判断・根拠へ',()=>loadEntry(run.summary_entry_id)));
    else node('summary-links').append(el('p','統合結果の出典リンク: 未記録','field-note'));
    node('audit').textContent=`記録の網羅性: ${data.audit?.status==='complete'?'保存された項目を取得':data.audit?.status==='partial'?'一部未記録':'未記録'} · ${text(data.audit?.message)}${run.truncated_fields?.length ? ` · 表示上限による省略: ${text(run.truncated_fields)}` : ''}`;
    const select=node('version');select.replaceChildren();
    const values=[...new Set([versions.initial,...(Array.isArray(versions.available)?versions.available:[]),versions.latest,versions.selected].filter(Number.isInteger))].sort((a,b)=>a-b);
    for(const version of values){const option=el('option',`${version===versions.initial?'初期版':version===versions.latest?'最新版':'過去版'} · v${version}${version===versions.initial&&version===versions.latest?'（最新）':''}`);option.value=String(version);select.append(option);}
    if(state.version!==null)select.value=String(state.version);else {const option=el('option','版は未記録');option.value='';select.append(option);}
    select.disabled=values.length<2;
    node('version-form').hidden=!versions.has_more;node('version-number').max=Number.isInteger(versions.latest)?String(versions.latest):'';node('version-number').value=state.version===null?'':String(state.version);
    node('version-note').textContent=`表示中 v${text(versions.selected)} / 初期 v${text(versions.initial)} / 最新 v${text(versions.latest)}。原文はこの実行の固定入力です。統合結果は最新保存を表示します。${versions.has_more?'版の一覧は一部のみ取得しています。':''}`;
  }
  async function loadTimeline() {
    const stamp=token(),request=++state.pageRequest;clearDetail();node('timeline').replaceChildren(el('li','記録を取得しています…'));node('prev').disabled=true;node('next').disabled=true;
    try {
      const q=timelineQuery();notice('保存された記録を取得しています…');
      const expectedVersion=state.version;
      const data=await get(`${runBase()}/viewer?${q}`);
      if(!current(stamp)||request!==state.pageRequest)return;
      if(data.run?.run_id!==state.runId || data.run?.item_id && data.run.item_id!==state.itemId)throw Error('取得した記録の対象が一致しません。');
      if(expectedVersion!==null&&data.versions?.selected!==expectedVersion)throw Error('取得した記録のラベル版が一致しません。');
      renderRun(data);const entries=Array.isArray(data.entries)?data.entries:[];node('timeline').replaceChildren();
      for(const entry of entries){const li=el('li'),b=button('',()=>loadEntry(entry.entry_id));b.dataset.entryId=entry.entry_id;b.setAttribute('aria-pressed','false');
        b.replaceChildren(el('strong',entry.title),el('small',`${label(entry.kind)} · ${label(entry.disposition||entry.status)} · ${label(entry.operation)}`),el('small',`${label(entry.role)} · ${text(entry.created_at)}`));li.append(b);node('timeline').append(li);}
      if(!entries.length)node('timeline').append(el('li','この条件の記録はありません。条件を解除すると他の履歴を確認できます。'));
      setPagination('',data.pagination,entries.length);notice('保存記録を表示しました。処理成功は研究者による採用・確認を意味しません。');
    }catch(error){if(current(stamp)&&request===state.pageRequest){node('timeline').replaceChildren(el('li',error.message));notice(error.message);}}
  }
  function valueAt(entry,which) {
    if(which==='after'&&entry.tombstone===true)return '削除済み（履歴を保持）';
    if(entry[`${which}_present`]===false)return '値なし（記録上）';
    return text(entry[`${which}_value`]);
  }
  async function loadEntry(entryId,evidenceOffset=0) {
    if(!entryId)return;
    const stamp=token(),request=++state.detailRequest;++state.sourceRequest;node('detail').replaceChildren(el('p','詳細を取得しています…'));
    for(const b of node('timeline').querySelectorAll('button'))b.setAttribute('aria-pressed',String(b.dataset.entryId===entryId));
    try {
      const q=new URLSearchParams({evidence_offset:String(evidenceOffset),evidence_limit:'30'});if(state.version!==null)q.set('annotation_version',String(state.version));
      const data=await get(`${runBase()}/viewer/entries/${encodeURIComponent(entryId)}?${q}`);
      if(!current(stamp)||request!==state.detailRequest)return;
      const entry=data.entry;if(!entry||entry.entry_id!==entryId)throw Error('取得した詳細の記録IDが一致しません。');
      const host=node('detail');host.replaceChildren(el('h3',entry.title),el('p',`${label(entry.kind)} · ${label(entry.disposition||entry.status)} · ${label(entry.operation)}`));
      if(entry.disposition==='proposal'||entry.status==='proposed'||entry.operation==='proposal')host.append(el('p','この記録は提案です。変更案を採用済みのラベルとして扱いません。','analysis-history-audit'));
      host.append(metadata([['記録ID',entry.entry_id],['担当',label(entry.role)],['モデル',entry.model],['日時',entry.created_at],['タスク',entry.task_id],['結果ID',entry.result_id],['判断ID',entry.decision_id],['提案ID',entry.proposal_id],['対象発話',entry.utterance_id],['対象項目',entry.field],['ラベル版',entry.annotation_version],['要約',entry.summary],['理由',entry.reason]]));
      const changes=el('div',undefined,'analysis-history-before-after');for(const which of ['before','after']){const section=el('section');section.append(el('h4',`${which==='before'?'変更前':'変更後'} · v${text(entry[`${which}_annotation_version`])}`),el('pre',valueAt(entry,which)));changes.append(section);}host.append(changes);
      if(Object.hasOwn(entry,'proposed_value')){host.append(el('h4','提案値（採用された値とは別の記録）'),el('pre',entry.proposed_value));}
      if(['label','legacy_label'].includes(entry.kind)&&Object.hasOwn(entry,'stated_old_value'))host.append(el('h4','提案が申告した変更前値（実値とは別）'),el('pre',entry.stated_old_value));
      if(Array.isArray(entry.claims)&&entry.claims.length){host.append(el('h4','保存された主張'));for(const claim of entry.claims)host.append(el('pre',claim));}
      host.append(el('h4','根拠と固定原文'));const evidenceHost=el('div',undefined,'analysis-history-evidence'),ids=new Set();
      for(const evidence of Array.isArray(data.evidence)?data.evidence:[]){if(!evidence.utterance_id)continue;ids.add(evidence.utterance_id);evidenceHost.append(button(`固定原文 ${evidence.utterance_id} · ${text(evidence.speaker)}`,()=>loadSource(evidence.utterance_id,request)));}
      if(entry.utterance_id&&!ids.has(entry.utterance_id))evidenceHost.append(button(`固定原文 ${entry.utterance_id}`,()=>loadSource(entry.utterance_id,request)));
      if(!evidenceHost.children.length)evidenceHost.append(el('p','根拠の原文リンク: 未記録'));
      host.append(evidenceHost,metadata([['記録された根拠ID',entry.evidence_ids],['未記録の項目',entry.missing_fields],['固定原文が見つからない根拠',entry.missing_evidence_ids]]));
      const evidencePage=data.evidence_pagination;
      if(evidencePage){const pager=el('div',undefined,'analysis-history-pagination'),prev=button('前の根拠',()=>loadEntry(entryId,Math.max(0,evidenceOffset-30))),next=button('次の根拠',()=>loadEntry(entryId,evidenceOffset+30));prev.disabled=!(evidencePage.offset>0);next.disabled=!evidencePage.has_more;pager.append(prev,next);host.append(pager,el('p',`根拠: ${pageLabel(evidencePage,(data.evidence||[]).length)}`,'field-note'));}
      else if(data.evidence_has_more)host.append(el('p',`根拠は一部のみ表示しています（総数 ${text(data.evidence_total)}）。`,'field-note'));
      if(data.truncated_fields?.length || entry.truncated_fields?.length)host.append(el('p',`表示上限による省略: ${text(data.truncated_fields||entry.truncated_fields)}`,'field-note'));
      if(Array.isArray(entry.related_entry_ids)&&entry.related_entry_ids.length){const related=el('div',undefined,'analysis-history-evidence');related.append(el('span','関連記録: '));for(const id of entry.related_entry_ids)related.append(button(id,()=>loadEntry(id)));host.append(related);}
      const source=el('section',undefined,'analysis-history-source');source.id='analysis-history-source';source.hidden=true;host.append(source);host.focus({preventScroll:true});
    }catch(error){if(current(stamp)&&request===state.detailRequest)node('detail').replaceChildren(el('p',error.message));}
  }
  async function loadSource(utteranceId,detailRequest=state.detailRequest) {
    const stamp=token(),request=++state.sourceRequest,host=node('source');if(!host)return;
    host.hidden=false;host.replaceChildren(el('p','固定原文を取得しています…'));
    try {
      const expectedVersion=state.version;
      const data=await get(`${runBase()}/viewer/sources/${encodeURIComponent(utteranceId)}${queryVersion()}`);
      if(!current(stamp)||request!==state.sourceRequest||detailRequest!==state.detailRequest)return;
      const source=data.source;if(!source||source.utterance_id!==utteranceId||data.provenance?.run_id!==state.runId||data.provenance?.item_id!==state.itemId)throw Error('固定原文の対象・版を確認できません。');
      if(expectedVersion!==null&&data.versions?.selected!==expectedVersion)throw Error('固定原文のラベル版が一致しません。');
      host.replaceChildren(el('h4',`固定原文 · ${source.utterance_id}`),el('blockquote',source.text),metadata([['話者',source.speaker],['時刻（秒）',`${text(source.start)} → ${text(source.end)}`],['除外',source.excluded===true?'除外済み':source.excluded===false?'対象内':'未記録'],['入力hash',data.provenance.input_hash],['固定原文hash',source.source_hash],['固定入力ID',data.provenance.initial_id]]));
      for(const [key,title] of [['initial','初期ラベル'],['selected','選択版ラベル'],['latest','最新ラベル']])host.append(el('h4',`${title} · v${text(data.versions?.[key])}`),el('pre',data.labels?.[key]));
      if(source.text_truncated)host.append(el('p','原文は表示上限により一部を省略しています。全文ではありません。','analysis-history-audit'));
      if(data.truncated_fields?.length)host.append(el('p',`表示上限による省略: ${text(data.truncated_fields)}`,'field-note'));
      host.append(el('p',`記録: ${text(data.audit?.message)}`,'field-note'),button('固定原文を閉じる',()=>{++state.sourceRequest;host.hidden=true;host.replaceChildren();}));host.scrollIntoView({block:'nearest'});
    }catch(error){if(current(stamp)&&request===state.sourceRequest&&detailRequest===state.detailRequest)host.replaceChildren(el('p',error.message));}
  }
  function slideCurrent(stamp,request) {return current(stamp)&&request===state.slidesRequest&&state.tab==='slides';}
  async function loadSlideTemplates() {
    const stamp=token(),request=++state.slidesRequest,host=node('slides');state.slides=null;host.replaceChildren(el('p','スライド設計を取得しています…'));
    try {
      const data=await get(`${runBase()}/slides/templates`);if(!slideCurrent(stamp,request))return;
      const templates=Array.isArray(data.templates)?data.templates:[];
      host.replaceChildren(el('h4','保存済み分析からスライドを作る'),el('p','スライドは実行の最新保存版から作成します。履歴の絞り込みや選択した過去版は反映しません。AIによる新しい解釈は追加しません。'));
      if(!templates.length){host.append(el('p','利用できるスライドテンプレートはありません。'));return;}
      const field=el('label',undefined,'field'),select=el('select');select.id='analysis-history-slide-template';field.append(el('span','スライドテンプレート'),select);
      for(const template of templates){const option=el('option',`${text(template.name)} · ${text(template.version)}`);option.value=template.id;select.append(option);}host.append(field);
      const design=el('section');design.id='analysis-history-slide-design';const status=el('p');status.id='analysis-history-slide-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
      const actions=el('div',undefined,'analysis-history-pagination'),save=button('VisualizationVaultに設計とpromptを保存',saveSlideDesign),preview=button('保存済み設計でプレビュー',loadSlidePreview);save.id='analysis-history-slide-save';preview.id='analysis-history-slide-preview';
      const exportLink=el('a','PowerPointをダウンロード','secondary-button');exportLink.id='analysis-history-slide-download';exportLink.hidden=true;exportLink.setAttribute('download','');
      actions.append(save,preview,exportLink);const content=el('div',undefined,'analysis-history-slides-content');content.id='analysis-history-slide-content';
      host.append(design,el('p','このボタンはVisualizationVaultに今回の設計・promptを1件保存します。保存するのはrun・版情報と設計で、会話原文のコピーではありません。実行時のVault出力設定は変更しません。','analysis-history-audit'),actions,status,content);
      state.slides={templates,receipt:data.design?.matches_snapshot===false?null:data.design||null,snapshot:data.snapshot_signature||null,templateId:select.value,busy:false};
      select.addEventListener('change',()=>{++state.slidesRequest;state.slides.templateId=select.value;state.slides.receipt=null;state.slides.busy=false;renderSlideDesign();});renderSlideDesign();
    }catch(error){if(slideCurrent(stamp,request))host.replaceChildren(el('p',error.message));}
  }
  function renderSlideDesign() {
    const slides=state.slides;if(!slides)return;
    const template=slides.templates.find(item=>item.id===slides.templateId)||{};
    node('slide-design').replaceChildren(el('h4',template.name),el('p',template.description));
    if(template.design)node('slide-design').append(el('h4','設計'),el('pre',template.design));
    if(template.prompt){const details=el('details');details.append(el('summary','保存するpromptを確認'),el('pre',template.prompt));node('slide-design').append(details);}
    if(Array.isArray(template.source_references)&&template.source_references.length){const refs=el('details');refs.append(el('summary','設計の参照資料'),el('pre',template.source_references));node('slide-design').append(refs);}
    const saved=slides.receipt?.template_id===slides.templateId && Boolean(slides.receipt?.design_hash);
    node('slide-status').textContent=saved?'このテンプレートの設計保存記録があります。プレビュー時にも入力版を照合します。':'設計保存の確認待ち。保存前はプレビュー・PowerPoint出力を行いません。';
    node('slide-save').disabled=slides.busy;node('slide-preview').disabled=!saved||slides.busy;node('slide-template').disabled=slides.busy;
    node('slide-download').hidden=true;node('slide-download').removeAttribute('href');node('slide-content').replaceChildren();
  }
  async function saveSlideDesign() {
    if(!state.slides||state.slides.busy)return;
    const stamp=token(),request=++state.slidesRequest,template=state.slides.templateId;state.slides.busy=true;state.slides.receipt=null;renderSlideDesign();node('slide-status').textContent='設計とpromptの保存を確認しています…';
    try {
      const response=await fetch(`${runBase()}/slides/design`,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({template,expected_snapshot:state.slides.snapshot})});
      if(!response.ok)throw Error(`設計の保存を確認できません（HTTP ${response.status}）。`);
      const data=await response.json();if(!slideCurrent(stamp,request))return;
      const receipt=data.design;if(!receipt||receipt.template_id!==template||!receipt.design_hash||!state.slides.snapshot||receipt.snapshot_signature!==state.slides.snapshot)throw Error('設計の保存記録を確認できません。');
      state.slides.receipt=receipt;state.slides.snapshot=receipt.snapshot_signature||data.snapshot_signature;state.slides.busy=false;renderSlideDesign();node('slide-status').textContent='設計とpromptを保存しました。保存済み設計でプレビューできます。';
    }catch(error){if(slideCurrent(stamp,request)){state.slides.busy=false;state.slides.receipt=null;renderSlideDesign();node('slide-status').textContent=error.message;}}
  }
  async function loadSlidePreview() {
    if(!state.slides||state.slides.busy||state.slides.receipt?.template_id!==state.slides.templateId||!state.slides.receipt?.design_hash)return;
    const stamp=token(),request=++state.slidesRequest,template=state.slides.templateId;state.slides.busy=true;renderSlideDesign();node('slide-status').textContent='保存版と設計を照合し、スライドを取得しています…';
    try {
      const expectedSnapshot=state.slides.receipt.snapshot_signature||state.slides.snapshot;
      const data=await get(`${runBase()}/slides/preview?template=${encodeURIComponent(template)}&expected_snapshot=${encodeURIComponent(expectedSnapshot||'')}`);if(!slideCurrent(stamp,request))return;
      if(data.template?.id!==template||data.provenance?.run_id!==state.runId||data.provenance?.item_id!==state.itemId||!expectedSnapshot||data.snapshot_signature!==expectedSnapshot)throw Error('スライドの対象・保存版を確認できません。');
      state.slides.busy=false;renderSlideDesign();const content=node('slide-content');
      content.append(metadata([['テンプレート',`${text(data.template.name)} · ${text(data.template.version)}`],['固定run',data.provenance.run_id],['入力hash',data.provenance.input_hash],['ラベル版',data.provenance.annotation_version],['スライドの固定版',data.snapshot_signature]]));
      for(const warning of Array.isArray(data.warnings)?data.warnings:[])content.append(el('p',warning,'analysis-history-audit'));
      for(const [index,slide] of (Array.isArray(data.slides)?data.slides:[]).entries()){
        const article=el('article');article.append(el('h4',`${index+1}. ${text(slide.title)}`));for(const paragraph of Array.isArray(slide.paragraphs)?slide.paragraphs:[])article.append(el('p',paragraph));
        if(slide.missing)article.append(el('p','必要な保存記録の一部は未記録です。'));if(slide.truncated)article.append(el('p','表示量の上限により一部を省略しています。'));
        article.append(metadata([['根拠ID',slide.evidence_ids],['結果ID',slide.result_ids]]));if(slide.notes){const details=el('details');details.append(el('summary','ノートと出典'),el('pre',slide.notes));article.append(details);}content.append(article);
      }
      const link=node('slide-download');if(data.download?.available){link.href=`${runBase()}/slides/presentation.pptx?template=${encodeURIComponent(template)}&expected_snapshot=${encodeURIComponent(data.snapshot_signature)}`;link.hidden=false;}
      node('slide-status').textContent=data.download?.available?'プレビューを取得しました。PowerPointは明示的にダウンロードできます。':`PowerPoint出力: ${text(data.download?.reason)}`;
    }catch(error){if(slideCurrent(stamp,request)){state.slides.busy=false;state.slides.receipt=null;renderSlideDesign();node('slide-status').textContent=error.message;}}
  }
  function bind() {
    if(!node('dialog'))return;
    node('open')?.addEventListener('click',()=>open());
    document.getElementById('orchestration-viewer')?.addEventListener('click',()=>{
      const options={itemId:orchestrationState.itemId,runId:orchestrationState.runId,itemName:orchestrationState.itemName};
      if(document.getElementById('orchestration-live')?.open)document.getElementById('orchestration-live').close();open(options);
    });
    node('close').addEventListener('click',()=>{const opener=state.opener;close();if(opener?.isConnected&&!opener.closest('[hidden]')&&(!opener.closest('dialog')||opener.closest('dialog').open))opener.focus();else node('open')?.focus();});
    node('dialog').addEventListener('close',()=>{if(!node('dialog').open)close();});
    node('dialog').addEventListener('cancel',event=>{event.preventDefault();node('close').click();});
    node('runs-prev').addEventListener('click',()=>{state.runOffset=Math.max(0,state.runOffset-20);loadRuns();});
    node('runs-next').addEventListener('click',()=>{state.runOffset+=20;loadRuns();});
    node('prev').addEventListener('click',()=>{state.offset=Math.max(0,state.offset-30);loadTimeline();});
    node('next').addEventListener('click',()=>{state.offset+=30;loadTimeline();});
    node('filters').addEventListener('submit',event=>{event.preventDefault();state.offset=0;loadTimeline();});
    node('filter-reset').addEventListener('click',()=>{node('filters').reset();selectTab('history');});
    node('version-form').addEventListener('submit',event=>{event.preventDefault();const value=Number(node('version-number').value);if(!Number.isInteger(value)||value<0)return;state.version=value;state.offset=0;loadTimeline();});
    node('version').addEventListener('change',()=>{state.version=node('version').value===''?null:Number(node('version').value);state.offset=0;loadTimeline();});
    node('refresh').addEventListener('click',()=>{state.version=null;state.offset=0;if(state.tab==='slides')loadSlideTemplates();else loadTimeline();});
    for(const tab of ['history','results','labels','slides'])node(`tab-${tab}`).addEventListener('click',()=>selectTab(tab));
  }
  window.openAnalysisHistoryViewer=open;window.closeAnalysisHistoryViewer=close;
  window.addEventListener('DOMContentLoaded',bind);
})();
