---
note_id: expert-cross-session-comparison-definition
note_type: expert-definition
expert_id: exp-cross-session-comparison
title: 会話間比較の専門家
role: comparison
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids: []
registry_method_ids:
  - interview_comparison
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/focus-group
---

# 会話間比較の専門家（exp-cross-session-comparison）

## 担当範囲と担当外

複数回の会話の集計を並べ、会話を単位に共通点と違いを記述し、元の発話へ戻って確認する。1回の会話内の群比較、ケース×テーマの質的比較、少数の会話からの一般化は担当外。詳細：[[50-Analysis-Methods/10-Experts/cross-session-comparison/00-Overview]]

## 理論的背景と採用する流派

[実装判断] Gurumojiのインタビュー比較（`interview_comparison`）の記述的な並列比較に従う。[文献] 比較の枠組みの設定（樋口 2017）、ケースの行列から元のデータへ戻る手順（Gale et al. 2013）、独立な単位を増やす重要性（Aarts et al. 2014、要旨）を判断の根拠にする。

## 適した研究目的・問い・データ

同じ質問設計・比較グループで行った複数回のインタビューの違いを、記述的に確認したい場合。

## 必要な入力と前処理、分析単位

比較する会話（2回以上）、比較グループ・質問設計の同一性の確認、各会話の準備状態。分析単位はインタビュー（会話・グループ）。

## 手順の要約

比較の目的と含める会話の基準 → 会話ごとの集計の並列 → 違いを元の発話で確認 → 会話を独立な単位とし一般化しない報告。詳細：[[50-Analysis-Methods/10-Experts/cross-session-comparison/02-Procedure]]

## 判断基準と品質確認の要約

比較する会話の数、探索的な比較の明示、率の違いをグループの性質と断定しないこと。詳細：[[50-Analysis-Methods/10-Experts/cross-session-comparison/03-Quality]]

## よくある誤用と禁止事項

少数の会話から一般化する、発話を独立な標本として会話間の差を検定する、質問設計の違いを参加者の違いとする。

## 出力形式

比較の目的と含めた会話、会話ごとの集計の並列表、違いの確認（元の発話ID）、探索的扱いと限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/cross-session-comparison/04-Applicability-and-Limits]]

## 参照ノートと主要文献

文献：[[50-Analysis-Methods/20-Literature/LIT-higuchi-2017-khcoder]]、[[50-Analysis-Methods/20-Literature/LIT-gale-2013-framework]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data]]、[[50-Analysis-Methods/20-Literature/LIT-kidd-parshall-2000-fg-rigor]]、[[50-Analysis-Methods/20-Literature/LIT-morgan-1996-focus-groups]]（要旨確認）。事例：[[50-Analysis-Methods/10-Experts/cross-session-comparison/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/cross-session-comparison/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-cross-session-comparison
definition_version: 1
knowledge_verified: 2026-09-15
title: 会話間比較の専門家
role: comparison
analysis_method_ids: []
registry_method_ids:
  - interview_comparison
school:
  default:
    id: descriptive-cross-session
    label: 複数回のインタビューの記述的な並列比較（Gurumojiの集計）
  alternatives: []
scope:
  - 複数回の会話の発話量、共通語、特徴語、手動コード、感情ラベルを並べる
  - 会話を単位として、共通点と違いを記述する
  - 同じ比較グループの比較か、異なる内容を含む探索的な比較かを区別する
out_of_scope:
  - text: 1回の会話の中の群の違い
    handoff: exp-group-comparison-statistics
  - text: ケース×テーマの行列による質的な比較
    handoff: exp-framework-method
  - text: 応答の連鎖と意見の形成
    handoff: exp-focus-group-interaction
analysis_unit: インタビュー（会話・グループ）。値の根拠は各会話の集計
required_inputs:
  - 比較する会話（2回以上）
  - 比較グループと質問設計の同一性の確認
  - 各会話の逐語録の準備状態と話者の確認
applicability_checks:
  - id: cmp-a1
    check: comparison_sessions_min
    severity: block
    params:
      min: 2
    message: 比較する会話が2回未満です。
    basis:
      - implementation
  - id: cmp-a2
    check: human_review
    severity: warn
    message: 比較する会話が同じ質問設計・比較グループか、明確に区別でき同一の概念に含まれる比較かを研究者が確認します。
    basis:
      - LIT-higuchi-2017-khcoder
      - LIT-gale-2013-framework
  - id: cmp-a3
    check: human_review
    severity: warn
    message: 各会話の逐語録の準備状態と話者の確認がそろっているかを確認します。
    basis:
      - implementation
procedure:
  - id: cmp-p1
    title: 比較の目的と、含める会話の基準を決める
    actor: researcher
    basis:
      - LIT-higuchi-2017-khcoder
  - id: cmp-p2
    title: 会話ごとの集計（発話量、共通語、特徴語、手動コード、感情ラベル）を並べる
    actor: code
    basis:
      - implementation
  - id: cmp-p3
    title: 違いを、会話ごとの元の発話に戻って確認する
    actor: researcher
    basis:
      - LIT-gale-2013-framework
  - id: cmp-p4
    title: 会話を独立な単位として扱い、会話の数が少ない比較で一般化しない
    actor: researcher
    basis:
      - LIT-aarts-2014-nested-data
      - LIT-kidd-parshall-2000-fg-rigor
      - LIT-morgan-1996-focus-groups
quality_checks:
  - id: cmp-q1
    check: comparison_sessions_min
    params:
      min: 2
    text: 比較する会話が2回以上か
    basis:
      - implementation
  - id: cmp-q2
    check: human_review
    text: 異なる内容を含む比較を、探索的なものとして示したか
    basis:
      - implementation
  - id: cmp-q3
    check: human_review
    text: 語や感情ラベルの率の違いを、グループの性質の違いとして断定していないか
    basis:
      - LIT-higuchi-2017-khcoder
prohibited_conclusions:
  - 少数の会話の違いから、母集団やグループの性質を一般化しない
  - 発話を独立な標本として、会話間の差を検定の根拠にしない
  - 質問設計や司会の進め方が異なる会話の違いを、参加者の違いとして述べない
output_sections:
  - 比較の目的と含めた会話
  - 会話ごとの集計の並列表
  - 違いの確認（元の発話ID）
  - 探索的扱いと限界
ai_assist:
  allowed: false
  steps: []
  reason: 会話間比較は比較の集計を並べる専門家で、値はコードで計算し、違いの確認は研究者が元の発話で行うため、AI見解を使いません。
  brief: ""
literature:
  - LIT-higuchi-2017-khcoder
  - LIT-gale-2013-framework
  - LIT-aarts-2014-nested-data
  - LIT-kidd-parshall-2000-fg-rigor
  - LIT-morgan-1996-focus-groups
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
open_issues:
  - 複数のフォーカスグループを比較する分析の方法論文献を確認していない
  - 比較に必要な会話の数の基準を扱った文献を確認していない
  - 比較の同一性（質問設計・比較グループ）の判定は研究者の確認に依存している
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
