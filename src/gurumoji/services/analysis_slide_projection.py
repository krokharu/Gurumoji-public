"""Conservative semantic layouts for saved-run slides.

Only already-projected/public fields are consumed. This module neither infers
scientific conclusions nor invokes providers. Unknown/large structures return
None and retain the existing bounded text projection and its review gates.
"""
from __future__ import annotations
import math


def _map(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _str(value, maximum=400):
    return value if isinstance(value, str) and 0 < len(value) <= maximum else ''


def _finite(value):
    try:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        return False


def _saved(value):
    return str(value) if isinstance(value,(str,int,float,bool)) else '未記録'


def visible_text(value):
    """All text actually represented by a semantic layout, for caveat checks."""
    if isinstance(value, dict):
        return '\n'.join(visible_text(v) for k, v in value.items() if k != 'kind')
    if isinstance(value, list):
        return '\n'.join(visible_text(v) for v in value)
    return str(value) if value is not None else ''


def _strings(value, maximum=4, length=150):
    if value is not None and not isinstance(value, list):
        return None
    rows = _list(value)
    if len(rows) > maximum or any(not _str(v, length) for v in rows):
        return None
    return list(dict.fromkeys(rows))


def _state(value):
    labels = {'completed':'処理完了', 'incomplete':'未完了', 'unreviewed':'内容未確認',
              'valid':'形式確認済み', 'issues':'指摘あり', 'adopt':'採用（解決とは別）',
              'reject':'不採用', 'defer':'保留', 'adopted_unresolved':'採用・未解決',
              'resolved':'解決済み', 'high':'高', 'medium':'中', 'low':'低',
              'observation':'観察', 'interpretation':'解釈', 'hypothesis':'探索的仮説'}
    return labels.get(_saved(value), _saved(value))


_COMPACT_ISSUE_KEYS = {'issue_id','issue_key','target_id','target_version','severity','reason',
                       'missing_evidence','alternative','proposed_test','status','stale','evidence_ids','result_id'}
_COMPACT_RESPONSE_KEYS = {'issue_id','disposition','reason','impact'}


def _evidence_link(claim, evidence):
    ids = _list(claim.get('evidence_ids'))
    if len(ids) != 1 or not isinstance(ids[0], str) or ids[0] not in evidence:
        return None
    ev = evidence[ids[0]]
    if ev.get('excluded') is not False or not _str(ev.get('text'), 180):
        return None
    return {'quote': ev['text'], 'evidence_label': '根拠 ' + _saved(ids[0]) + ' ／ 発話 ' + _saved(ev.get('utterance_id','未記録'))}


def build_visual(section, title, exported, result_ids, provenance, section_keys=()):
    """Return a compact, source-grounded layout, otherwise preserve fallback."""
    run = _map(exported.get('run')); view = _map(run.get('current_view'))
    snapshot = _map(_map(exported.get('initial')).get('snapshot'))
    config = _map(run.get('config'))
    results = [r for r in _list(exported.get('raw_results')) if isinstance(r,dict)]
    evidence = {_saved(e.get('evidence_id',e.get('id',''))):e for e in _list(snapshot.get('evidence')) if isinstance(e,dict)}
    if section == 'purpose':
        question = _str(config.get('question',config.get('objective')), 100)
        summary = _str(view.get('summary'),180)
        if not question or not summary:
            return None
        return {'kind':'hero','question':question,'summary':summary,
                'states':['実行状態: '+_state(run.get('status')), 'レビュー: '+_state(run.get('review_status')),
                          '終了理由: '+_saved(run.get('stop_reason','未記録')),
                          '入力変更: '+('旧版' if run.get('stale') is True else '変更なし' if run.get('stale') is False else '未記録')],
                'caveat':'探索的分析・AI下書き。研究者の確定解釈や因果関係の証明ではありません。'}
    if section == 'method':
        tasks = [t for t in _list(run.get('tasks')) if isinstance(t,dict)]
        if len(tasks)>4 or any(len(_saved(t.get('title','')))>100 for t in tasks): return None
        roles = {'interpretation':'会話解釈','statistics':'数量・統計','verification':'独立検証','critic':'批判者'}
        present = [roles[r] for r in roles if any(x.get('role')==r for x in results)]
        excluded = sum(e.get('excluded') is True for e in evidence.values())
        unknown = sum(not isinstance(e.get('excluded'),bool) for e in evidence.values())
        nodes = [{'title':'固定入力','text':'保存根拠 '+str(len(evidence))+'件\n除外 '+str(excluded)+'件\n採否不明 '+str(unknown)+'件'},
                 {'title':'Handler','text':'保存タスク '+_saved(len(tasks))+'件'+('\nタスク履歴は\n未記録' if not tasks else '\n'+'\n'.join(_saved(t.get('role'))+' / '+_saved(t.get('method_id'))+' / '+_state(t.get('status'))+' / '+_saved(t.get('title')) for t in tasks))},
                 {'title':'専門担当','text':'\n'.join(present) or '保存結果は未記録'},
                 {'title':'Core','text':'表示版 '+_saved(run.get('view_version','未記録'))+'\nレビュー '+_state(run.get('review_status'))}]
        return {'kind':'method','nodes':nodes,'note':'保存資料の構成図です。矢印は実行済みタスクを証明しません。\n入力: '+_saved(run.get('input_hash','未記録'))+' ／ 停止条件: '+_saved(config.get('stop_mode','未記録'))+' ／ 終了理由: '+_saved(run.get('stop_reason','未記録'))}
    if section == 'major_results':
        claims=_list(view.get('claims'))
        if len(claims)!=1 or not isinstance(claims[0],dict):return None
        c=claims[0]
        if set(c)-{'claim_id','kind','text','evidence_ids'}:return None
        link=_evidence_link(c,evidence)
        if not link or not _str(c.get('text'),180):return None
        return {'kind':'evidence_chain',**link,'claim':c['text'],'kind_label':_state(c.get('kind')),
                'claim_id':_saved(c.get('claim_id','未記録')),'caveat':'保存された主張と根拠の対応です。引用から新しい結論を推定していません。'}
    if section == 'specialist_perspectives' or (section=='critic' and title!='批判とCoreの応答'):
        selected=[r for r in results if r.get('result_id') in result_ids]
        if len(selected)!=1:return None
        result=selected[0]
        if result.get('validation_status')!='valid':return None
        raw=_map(result.get('raw')); summary=_str(raw.get('summary'),180)
        limitations=_strings(raw.get('limitations'),3,140)
        if not summary or limitations is None:return None
        meta=['結果 '+_saved(result.get('result_id','未記録')),
              '形式確認済み ／ '+_state(result.get('content_status')),
              '入力版 '+_saved(result.get('dataset_version','未記録'))+' ／ ラベル版 '+_saved(result.get('annotation_version','未記録'))]
        if result.get('stale'): meta.append('旧版の保存結果')
        if result.get('role')=='statistics':
            if set(raw)-{'summary','method_id','denominator','missing_count','annotation_version','rows','limitations','source_refs'}:return None
            if raw.get('annotation_version') is not None and raw.get('annotation_version')!=result.get('annotation_version'):return None
            rows=_list(raw.get('rows'));den=raw.get('denominator');missing=raw.get('missing_count')
            if (not 1<=len(rows)<=5 or not _finite(den) or den<=0 or not _finite(missing) or missing<0):return None
            if any(not isinstance(r,dict) or set(r)-{'label','count','denominator','proportion','evidence_ids'} or not _str(r.get('label'),30) or not _finite(r.get('count')) or r['count']<0 or r.get('denominator')!=den or not _finite(r.get('proportion')) or not 0<=r['proportion']<=1 or abs(r['count']/den-r['proportion'])>1e-9 for r in rows):return None
            return {'kind':'statistics','categories':[r['label'] for r in rows], 'values':[r['proportion']*100 for r in rows],
                    'counts':[r['count'] for r in rows],'unit':'割合（%）','summary':summary,'denominator':den,
                    'missing_count':missing,'annotation_version':result.get('annotation_version','未記録'),
                    'caveats':limitations,'meta':meta}
        if set(raw)-{'summary','claims','limitations','source_refs','issues','review_status','reviewed_scope'}:return None
        claims=_list(raw.get('claims'))
        if len(claims)!=1 or not isinstance(claims[0],dict) or not _str(claims[0].get('text'),180):return None
        claim=claims[0]
        if set(claim)-{'claim_id','kind','text','evidence_ids'}:return None
        link=_evidence_link(claim,evidence)
        if not link:return None
        # The critic's issues must stay on the paired issue/response page;
        # unknown issue forms retain text fallback instead of dropping details.
        if result.get('role')=='critic':
            if raw.get('issues') is not None and not isinstance(raw.get('issues'),list):return None
            issues=_list(raw.get('issues')); recorded=_list(run.get('issues'))
            if any(not isinstance(i,dict) or not any(isinstance(j,dict) and all(j.get(k)==i.get(k) for k in i) for j in recorded) for i in issues):return None
            review='レビュー範囲: '+_saved(raw.get('reviewed_scope','未記録'))+' ／ '+_state(raw.get('review_status'))
            if len(review)>120:return None
            meta.append(review)
        return {'kind':'perspective','summary':summary,'claim':claim['text'],'kind_label':_state(claim.get('kind')),
                'evidence_label':link['evidence_label']+' ／ 主張 '+_saved(claim.get('claim_id','未記録')),
                'caveat':'\n'.join(limitations) or '留保は未記録','meta':meta}
    if section=='critic' and title=='批判とCoreの応答':
        if any(run.get(k) is not None and not isinstance(run.get(k),list) for k in ('issues','critique_responses')):return None
        issues=_list(run.get('issues'));responses=_list(run.get('critique_responses'))
        if len(issues)!=1 or not isinstance(issues[0],dict):return None
        issue=issues[0]
        if set(issue)-_COMPACT_ISSUE_KEYS:return None
        if any(not isinstance(r,dict) or set(r)-_COMPACT_RESPONSE_KEYS for r in responses):return None
        if not _str(issue.get('reason'),160) or any(issue.get(k) and not _str(issue[k],160) for k in ('missing_evidence','alternative','proposed_test')):return None
        matches=[r for r in responses if isinstance(r,dict) and r.get('issue_id')==issue.get('issue_id')]
        if len(matches)>1 or len(matches)!=len(responses):return None
        response=matches[0] if matches else {}
        if any(response.get(k) and not _str(response[k],160) for k in ('reason','impact')):return None
        if issue.get('alternative'):return None # Full alternative text uses existing safe fallback.
        return {'kind':'critique','issue':{'reason':issue['reason'],'missing_evidence':_saved(issue.get('missing_evidence','未記録')),
                'proposed_test':_saved(issue.get('proposed_test','未記録')),
                'metadata':['指摘 '+_saved(issue.get('issue_id','未記録'))+' ／ 重大度 '+_state(issue.get('severity')),
                            '対象 '+_saved(issue.get('target_id','未記録'))+' ／ 版 '+_saved(issue.get('target_version','未記録')),
                            '旧版' if issue.get('stale') else '旧版かどうか: '+_saved(issue.get('stale','未記録'))]},
                'response':{'disposition':_state(response.get('disposition')),'reason':_saved(response.get('reason','未記録')),
                            'impact':_saved(response.get('impact','未記録'))},'status':_state(issue.get('status'))}
    if section=='core':
        if set(view)-{'summary','claims','alternatives','unresolved'}:return None
        alts=_strings(view.get('alternatives'),3,140);summary=_str(view.get('summary'),180)
        decisions=_list(exported.get('decisions'))
        if not summary or alts is None or decisions:return None
        if run.get('critique_responses') is not None and not isinstance(run.get('critique_responses'),list):return None
        responses=[]
        for r in _list(run.get('critique_responses')):
            if not isinstance(r,dict) or not _str(r.get('impact'),140):return None
            responses.append('指摘 '+_saved(r.get('issue_id','未記録'))+': '+r['impact'])
        if len(responses)>3:return None
        return {'kind':'core','summary':summary,'alternatives':alts,'responses':responses}
    if section=='limitations':
        unresolved=_strings(view.get('unresolved'),3,140)
        if unresolved is None:return None
        # Do not remove issue fields merely because another slide shows them.
        # Dedicated issue layouts cover every field once; this section focuses
        # on the source's remaining limitations and points back by issue id.
        if run.get('unresolved_issues') is not None and not isinstance(run.get('unresolved_issues'),list):return None
        issues=_list(run.get('unresolved_issues'))
        if len(issues)>1 or (issues and 'critic' not in section_keys):return None
        recorded=_list(run.get('issues'))
        if any(not isinstance(i,dict) or not any(isinstance(j,dict) and all(j.get(k)==i.get(k) for k in i) for j in recorded) for i in issues):return None
        for issue in issues:
            if not isinstance(issue,dict) or set(issue)-_COMPACT_ISSUE_KEYS or not _str(issue.get('reason'),120):return None
            unresolved.append('指摘 '+_saved(issue.get('issue_id','未記録'))+': '+issue['reason']+'\n（'+_state(issue.get('status'))+'）')
        caveats=[]
        for result in results:
            if result.get('validation_status')!='valid':continue
            raw=_map(result.get('raw'))
            if raw.get('analysis_requests'):return None
            vals=_strings(raw.get('limitations',_map(raw.get('method')).get('limitations')),3,140)
            if vals is None:return None
            caveats.extend(vals)
        caveats=list(dict.fromkeys(caveats))
        if len(caveats)>4:return None
        return {'kind':'limitations','unresolved':unresolved,'caveats':caveats,
                'note':'探索的分析・AI下書き。研究者の確定解釈ではありません。\n追加検証は未実行の提案を含みます。レビュー: '+_state(run.get('review_status'))}
    if section=='evidence':
        keys=[('会話 / Run',_saved(provenance.get('item_id'))+' / '+_saved(provenance.get('run_id'))),
              ('入力版',_saved(provenance.get('input_hash'))),('原資料 / 分析版',_saved(provenance.get('source_revision'))+' / '+_saved(provenance.get('analysis_revision'))),
              ('表示 / ラベル / コードブック版',_saved(provenance.get('view_version'))+' / '+_saved(provenance.get('annotation_version'))+' / '+_saved(provenance.get('codebook_version'))),
              ('実行世代 / 保存結果数',_saved(provenance.get('generation'))+' / '+_saved(provenance.get('result_count'))),
              ('初期版ID',_saved(provenance.get('initial_id'))),('最終判断ID',_saved(provenance.get('last_decision_id')))]
        for label,key in [('保存版署名','snapshot_signature'),('初期版hash','initial_hash'),('結果版一覧hash','result_versions_hash')]:
            val=_saved(provenance.get(key,'未記録'));keys.append((label,val[:23]+'…（短縮）' if len(val)>26 else val))
        if any(len(v)>70 for _,v in keys):return None
        return {'kind':'audit','rows':[list(r) for r in keys], 'note':'完全なhash・結果版一覧・発話/根拠/主張ID・元記録への参照は各スライドのノートに保存しています。'}
    return None
