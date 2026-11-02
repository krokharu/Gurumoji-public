---
note_id: expert-cross-session-comparison-overview
note_type: expert-overview
expert_id: exp-cross-session-comparison
title: 会話間比較の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/focus-group
---

# 会話間比較の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/cross-session-comparison/01-Expert]]

## この専門家が答える問い

- 複数回のグループインタビューを、発話量、共通語、特徴語、手動コード、感情ラベルで並べると、どこが共通しどこが違うか。比較が同じ比較グループのものか、異なる内容を含む探索的な比較か。[実装判断] 集計の定義は `interview_comparison`（`analysis_method_registry.METHOD_GROUPS` の説明）による。

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 1回の会話の中の群の違い | [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert\|群間比較]] |
| ケース×テーマの質的な比較 | [[50-Analysis-Methods/10-Experts/framework-method/01-Expert\|フレームワーク法]] |
| 少数の会話から母集団やグループの性質を一般化すること | 会話が独立な単位で、数が少ないため行わない |

## 文献との関係

- [文献] 比較の枠組みは、明確に区別できるものを比べ、比較対象が適度に具体的な同一の概念に含まれるようにするのが望ましいとされる（[[50-Analysis-Methods/20-Literature/LIT-higuchi-2017-khcoder|樋口 2017]]、4節）。
- [文献] フォーカスグループの利点は、プロジェクトとグループの両方の水準の研究デザインに注意することで最大化できるとされる（[[50-Analysis-Methods/20-Literature/LIT-morgan-1996-focus-groups|Morgan 1996]]、要旨）。
- [文献] 入れ子のデータでは、1つの対象からの観測を増やすより、真に独立な観測を増やすことが重要とされる（[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data|Aarts et al. 2014]]、要旨）。グループインタビューでは会話（グループ）が独立な単位にあたる（[整理]）。

## 担当する実装

- `interview_comparison`（会話ごとの分析とは別の保存記録として保存される）
