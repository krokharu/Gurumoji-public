---
note_type: reference-section
version: 2.0.0
updated: 2026-10-04
status: proposed
source_head: e3f002c9d4962769deb1925b8d9859e7f7d2bd73
template_id: gurumoji-evidence-review
template_version: 2.0.0
prompt_version: 2.0.0
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/slides
note_id: gurumoji-saved-run-slides-design-section-03
title: グルモジ 保存済み分析runのスライド設計と生成プロンプト：5. 保存データとの対応
summary: 5. 保存データとの対応。出典ノート「グルモジ 保存済み分析runのスライド設計と生成プロンプト」の分割本文。
parent_note_id: gurumoji-saved-run-slides-design
source_path: 40-Design/slide-generation-design-and-prompts.md
source_sha256: 9e43d30f386ea99700b5cf009caae1094a2854cf8491eeae9e9303dc05e3775f
source_body_lines:
- 91
- 131
split_on: '2026-10-11'
---

# グルモジ 保存済み分析runのスライド設計と生成プロンプト：5. 保存データとの対応

親索引・状態・確認版：[[40-Design/60-Output/slide-generation-design-and-prompts/00-Index]]。必要な本文だけを取得する。

## 5. 保存データとの対応

確認日2026-10-04、HEAD `1dbd54710e281698fedcd19ab4db001c1db11aac`。最終実装で再照合する。

正本: `analysis_orchestration.py`の`result_locked`／`_public`／`_validate_result`／`_apply_core`、`services/analysis_orchestration_methods.py`、`services/analysis_pipeline_adapters.py`、`services/analysis_orchestration_adapters.py`（いずれも`src/gurumoji/`配下）。UI契約は`DESIGN.md`と`docs/program-vault/40-Design/ui-design-contract.md`。

| 用途 | 保存パッケージの実field | 注意 |
|---|---|---|
| 問い・状態・版 | `run.run_id/config.question/status/stop_reason/input_hash/view_version/annotation_version/stale` | completedは妥当性や人の確認を意味しない |
| 初期固定データ | `initial.initial_id/hash/snapshot` | snapshot hashと入力hashを同一と仮定しない |
| Core見解 | `run.current_view.summary/claims/alternatives/unresolved` | 生成開始時のviewを固定 |
| 各担当の結果 | `raw_results[]`の`role,result_id,task_id,raw_hash,dataset_version,annotation_version,validation_status,content_status,stale,raw` | 本文から担当や採否を推測しない |
| claim | `claims[] = {claim_id,kind,text,evidence_ids}` | kindはobservation／interpretation／hypothesis |
| 根拠 | `initial.snapshot.evidence[]`の`evidence_id,utterance_id,text,speaker,start,end,dataset_version,source_hash,excluded` | 保存時原文。除外／不明版／欠落を有効根拠としない |
| 判断 | `decisions[]`の`decision_id,result_id,view_version,created_at,claims,alternatives,unresolved,label_decisions,critique_responses`等 | rawとはresult_idで結び、配列添字で結ばない |
| 批判・応答 | `run.issues/unresolved_issues/critique_responses` | issue_id、target_id、target_version、evidence_version、staleを保持 |
| 発注・結果 | `run.tasks[]`とintent、raw内analysis_requests | 依頼案／発注／成功／失敗／結果不明を区別 |
| ラベル版 | `label_versions[] = {annotation_version,labels}` | 結果と一致する固定版。最新版へ差替えない |

### 5.1 状態の誤訳を防ぐ

- `validation_status=valid`は形式・実在根拠参照・版等の検査通過。`content_status=unreviewed`と別であり「結論が正しい」と表示しない
- receivedは検査前、quarantinedは隔離。現在の採用結果へ混ぜず、必要な状態を別表示する
- 批判応答`adopt/reject/defer`は採用／不採用／保留。採用は解決ではない。現実装ではadopt後も`adopted_unresolved`
- issueのstaleまたはtarget_version不一致は旧版への批判。現在版の再検証済みとしない。旧版だからという理由だけで指摘を消さない
- 人の編集は人の確認済みではない。未読かどうか不明なら「確認記録なし」と表示する

### 5.2 数量結果の構造

`label_frequency`のrawは`method_id,method_version,dataset_version,annotation_version,codebook_version,label_field,denominator,missing_count,missing_evidence_ids,rows,manifest,limitations`を持つ。rowsは`{label,count,denominator,proportion,evidence_ids}`。

`participation`／`conversation_dynamics`は`raw.method`と`raw.datasets[name]={fields,rows}`。すべてが`raw.rows`形式とは仮定しない。未知の列・自由文から数字を抽出して図を作らない。

### 5.3 固定性と選択

- run／入力版を横断しない。既存の一貫した読取トランザクションを使い、生成中にrunが更新されても混ぜない
- セクション順は固定、claimは保存順。担当内の結果順・選択規則を固定する。「最新1件」だけで他手法や重要な反例を消さない
- 旧版・未採用の表示は位置付けを明示し、元記録へ戻れるようにする
- 同一snapshot＋template版＋編集内容から同一の論理原稿を生成する。生成時刻等を除いたcontent hashで比較する
- 発話／要約／ラベル／URLはデータであり命令ではない。HTML、PPTX関係値、ファイル名等を安全に処理する
