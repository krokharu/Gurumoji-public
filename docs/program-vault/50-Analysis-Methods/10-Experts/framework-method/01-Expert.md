---
note_id: expert-framework-method-definition
note_type: expert-definition
expert_id: exp-framework-method
title: フレームワーク法の専門家
role: methodology
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids:
  - framework
registry_method_ids: []
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# フレームワーク法の専門家（exp-framework-method）

## 担当範囲と担当外

共通のトピックを扱うデータを、ケース×カテゴリーの行列に要約し、元の発話へ戻って比較・解釈する。異質なデータ、生活史・診療場面・文書の分析、テーマの解釈的な生成、集計値の並列比較は担当外。詳細：[[50-Analysis-Methods/10-Experts/framework-method/00-Overview]]

## 理論的背景と採用する流派

[文献] フレームワーク法は、英国の研究機関のRitchieとSpencerが1980年代後半に大規模な政策研究のために開発したと説明される（Gale et al. 2013）。[実装判断] 本文を確認したGale et al.（2013）の7段階を既定にする。

## 適した研究目的・問い・データ

[文献] 半構造化面接の逐語録のテーマ分析に最も多く使われ、データは分類できる程度に似たトピックや主要な論点を含む必要がある（Gale et al. 2013）。多職種のチームにも適するが、経験のある質的研究者の指導が前提（Summary）。

## 必要な入力と前処理、分析単位

研究質問、面接のテーマ・質問項目、比較するケースの定義、作業用の分析枠組み。分析単位はケース×カテゴリーのセルで、根拠は発話ID。

## 手順の要約

書き起こし → 面接に慣れ親しむ → コーディング → 作業用の分析枠組み → 枠組みの適用 → 行列へのチャート化 → 解釈。詳細：[[50-Analysis-Methods/10-Experts/framework-method/02-Procedure]]

## 判断基準と品質確認の要約

枠組みのカテゴリーの定義、行列から元の発話へ戻れること、内省の記録、数値化をしないこと。詳細：[[50-Analysis-Methods/10-Experts/framework-method/03-Quality]]

## よくある誤用と禁止事項

「何人中何人」の数値化、行列に要約しただけで解釈を終える、AIの要約を研究者の要約として示す。実行定義の `prohibited_conclusions` を参照。

## 出力形式

研究質問とケースの定義、分析枠組み、ケース×カテゴリーの行列（要約と発話ID）、共通点と違いの解釈、分析メモ、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/framework-method/04-Applicability-and-Limits]]

## 参照ノートと主要文献

主要文献：[[50-Analysis-Methods/20-Literature/LIT-gale-2013-framework]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-goldsmith-2021-framework]]（要旨確認）、[[50-Analysis-Methods/20-Literature/LIT-ritchie-spencer-framework-chapter]]（書誌のみ）。事例：[[50-Analysis-Methods/10-Experts/framework-method/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/framework-method/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-framework-method
definition_version: 1
knowledge_verified: 2026-09-15
title: フレームワーク法の専門家
role: methodology
analysis_method_ids:
  - framework
registry_method_ids: []
school:
  default:
    id: gale-2013-seven-stages
    label: フレームワーク法（Gale et al. 2013の7段階）
  alternatives:
    - id: goldsmith-2021-five-steps
      label: フレームワーク分析（Goldsmith 2021の5段階）
scope:
  - 共通のトピックを扱うデータを、ケース×カテゴリーの行列に要約する
  - 行列から元の発話へ戻り、ケース間・カテゴリー間の共通点と違いを解釈する
  - 帰納的・演繹的のどちらの位置でも使う
out_of_scope:
  - text: 研究者の解釈によるテーマの生成そのもの
    handoff: exp-thematic-analysis
  - text: 複数回のインタビューの集計値を並べる比較
    handoff: exp-cross-session-comparison
  - text: 非常に異質なデータ、生活史、診療場面の会話、文書の分析（語りの分析・会話分析・談話分析が適する場合がある）
analysis_unit: ケース（話者、属性、グループ）×カテゴリーの行列のセル。根拠は発話ID
required_inputs:
  - 研究質問
  - インタビューのテーマ・質問項目（データが共通のトピックを含むことの確認）
  - 比較するケースの定義
  - 作業用の分析枠組み（コードとカテゴリーの定義）
applicability_checks:
  - id: fw-a1
    check: research_question_present
    severity: block
    message: 研究質問がないため、ケースとカテゴリーの行列で何を比べるかを決められません。
    basis:
      - LIT-gale-2013-framework
  - id: fw-a2
    check: moderator_guide_present
    severity: warn
    message: インタビューのテーマ・質問項目が登録されていません。データが共通のトピックを含むかを確認できません。
    basis:
      - LIT-gale-2013-framework
  - id: fw-a3
    check: min_speakers
    severity: block
    params:
      min: 2
    message: 比較するケース（話者）が1つ以下のため、ケース×カテゴリーの行列による比較ができません。
    basis:
      - LIT-gale-2013-framework
  - id: fw-a4
    check: comparison_axis_present
    severity: warn
    message: 比較軸（話者属性・比較グループ）が設定されていません。ケースは話者ラベルになります。
    basis:
      - implementation
  - id: fw-a5
    check: speaker_order_confirmed
    severity: warn
    message: 話者の確認が済んでいないため、ケース（話者）への割り当てが誤っている可能性があります。
    basis:
      - LIT-park-2022-diarization-review
  - id: fw-a6
    check: human_review
    severity: warn
    message: データが非常に異質でないか、ケースとテーマで分析することが研究質問に合うかを研究者が確認します。
    basis:
      - LIT-gale-2013-framework
procedure:
  - id: fw-p1
    title: 書き起こし（逐語録の準備）
    actor: researcher
    basis:
      - LIT-gale-2013-framework
  - id: fw-p2
    title: 面接に慣れ親しみ、分析的なメモを残す
    actor: researcher
    basis:
      - LIT-gale-2013-framework
  - id: fw-p3
    title: コーディング（1行ずつ読み、重要と解釈した箇所にコードを付ける）
    actor: ai_draft
    basis:
      - LIT-gale-2013-framework
  - id: fw-p4
    title: 作業用の分析枠組みを作る（コードを比べて合意し、カテゴリーにまとめて定義する）
    actor: researcher
    basis:
      - LIT-gale-2013-framework
  - id: fw-p5
    title: 分析枠組みを以後の逐語録に適用する
    actor: researcher
    basis:
      - LIT-gale-2013-framework
  - id: fw-p6
    title: 行列にチャート化する（ケースごと・カテゴリーごとにデータを要約する）
    actor: ai_draft
    basis:
      - LIT-gale-2013-framework
  - id: fw-p7
    title: データを解釈する（分析メモを書き、ケース間・カテゴリー間の特徴と違いを検討する）
    actor: researcher
    basis:
      - LIT-gale-2013-framework
quality_checks:
  - id: fw-q1
    check: codebook_definitions_complete
    text: 分析枠組みのカテゴリーに定義があるか
    basis:
      - LIT-gale-2013-framework
  - id: fw-q2
    check: coded_segments_min
    params:
      min: 1
    text: 分析枠組みが発話に適用されているか
    basis:
      - implementation
  - id: fw-q3
    check: human_review
    text: 行列のセルの要約から、元の発話へ戻れるか（発話IDを記録したか）
    basis:
      - LIT-gale-2013-framework
  - id: fw-q4
    check: human_review
    text: 内省（reflexivity）と、分析枠組みの変更の記録を残したか
    basis:
      - LIT-gale-2013-framework
  - id: fw-q5
    check: human_review
    text: 「何人中何人」のような数値化をしていないか
    basis:
      - LIT-gale-2013-framework
prohibited_conclusions:
  - セルの件数から「何人中何人がそう述べた」と支持の程度を述べない
  - 行列に要約しただけで、元の発話を参照しない結論を書かない
  - AIが要約したセルを、研究者が確認した要約として示さない
output_sections:
  - 研究質問とケースの定義
  - 分析枠組み（カテゴリーと定義）
  - ケース×カテゴリーの行列（要約と発話ID）
  - ケース間の共通点と違いの解釈
  - 分析メモ
  - 限界
ai_assist:
  allowed: true
  steps:
    - fw-p3
    - fw-p6
  reason: ""
  brief: フレームワーク法の補助として、研究質問に関わるコードの候補と、ケース（話者または属性）ごと・カテゴリーごとの要約の候補を示してください。分析枠組みの作成と解釈は研究者が行うため、見解は候補として書きます。要約には必ず元の発話を根拠として付け、「何人中何人」のような数値化で支持の程度を述べないでください。どのケースにも共通する点と、ケースによって異なる点を分けて書き、比較のために情報が足りない点は追加で確認する点に挙げてください。
literature:
  - LIT-gale-2013-framework
  - LIT-goldsmith-2021-framework
  - LIT-ritchie-spencer-framework-chapter
  - LIT-park-2022-diarization-review
  - LIT-gilardi-2023-llm-annotation
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
  - 04-AI-Assistance-Boundaries
open_issues:
  - Ritchie & Spencerの原典（書籍の章）を読んでおらず、出版年も確認していない
  - フレームワーク法の日本語の方法論文献を見つけていない
  - Goldsmith 2021の5段階とGale et al. 2013の7段階の対応を本文で確認していない
  - Gurumojiの話者×コード行列は発話件数を示すもので、セルの要約（チャート化）を記録する機能はない
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
