---
note_id: lit-aarts-2014-nested-data
note_type: literature
literature_id: LIT-aarts-2014-nested-data
title: "A solution to dependency: using multilevel analysis to accommodate nested data"
authors:
  - Emmeke Aarts
  - Matthijs Verhage
  - Jesse V. Veenvliet
  - Conor V. Dolan
  - Sophie van der Sluis
year: 2014
venue: "Nature Neuroscience, 17(4), 491–496"
source_type: journal_article
peer_review: unconfirmed
peer_review_basis: "掲載誌の査読方針を確認していない。"
doi: 10.1038/nn.3648
url: https://doi.org/10.1038/nn.3648
accessed: 2026-09-15
access_scope: abstract
access_detail: "Europe PMCの要旨を読んだ。本文は読んでいない。"
correction_status: none_found
related_experts:
  - exp-group-comparison-statistics
  - exp-correlation
  - exp-descriptive-statistics
  - exp-cross-session-comparison
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/statistics
---

# Aarts et al.（2014）：入れ子のデータへのマルチレベル分析

## 研究目的

一つの研究対象から複数の観測を集める入れ子のデザインで、観測の依存をどう扱うかを論じる（要旨）。

## 対象データと研究条件

神経科学の5つの主要誌の論文314本を検討し、53%がこの種のデータを含んでいた（要旨）。

## 分析手順の要約

入れ子のデザインで第1種の誤りの確率と検出力に影響する要因、観測間の依存を扱う方法、最適な研究デザインの決め方を論じる（要旨）。

## 主要な知見

- 入れ子のデザインのデータは独立とみなせず、t検定などの従来の方法の独立性の前提に反する。
- 依存を無視すると、誤って有意と結論する確率が名目の水準（通常5%）より大幅に高く（最大80%）なりうる。
- 研究デザインの最適化は、一つの対象からの観測を増やすことより、真に独立な観測を増やすことにほぼ常に関わるとする（要旨）。

## 適用上の注意と限界

- 神経科学の実験デザインを対象にした論文であり、会話データを扱ったものではない。
- 要旨だけを読んだため、依存の程度と誤りの確率の関係の詳細は確認していない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert|群間比較の専門家]]、[[50-Analysis-Methods/10-Experts/correlation/01-Expert|相関の専門家]]、[[50-Analysis-Methods/10-Experts/descriptive-statistics/01-Expert|記述統計の専門家]]：[整理] 発話は話者と会話に入れ子になっているため、発話を独立な標本とした検定のp値を一般化の根拠にしない。
- [[50-Analysis-Methods/10-Experts/cross-session-comparison/01-Expert|会話間比較の専門家]]：独立な単位は会話（グループ）であり、会話の数が少ない比較で推測統計を行わない。
- [実装判断] マルチレベルモデルは現在の実装にない。

## 根拠の位置情報

要旨。

## 未確認事項

本文の方法とシミュレーションの条件。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-jaeger-2008-logit-mixed]]、[[50-Analysis-Methods/08-Common-Knowledge/03-Group-Interview-Data]]
