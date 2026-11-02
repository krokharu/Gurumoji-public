---
note_id: lit-jaeger-2008-logit-mixed
note_type: literature
literature_id: LIT-jaeger-2008-logit-mixed
title: "Categorical data analysis: Away from ANOVAs (transformation or not) and towards logit mixed models"
authors:
  - T. Florian Jaeger
year: 2008
venue: "Journal of Memory and Language, 59(4), 434–446"
source_type: journal_article
peer_review: unconfirmed
peer_review_basis: "掲載誌の査読方針を確認していない。"
doi: 10.1016/j.jml.2007.11.007
url: https://doi.org/10.1016/j.jml.2007.11.007
accessed: 2026-09-15
access_scope: abstract
access_detail: "Semantic Scholar APIの要旨を読んだ。本文は読んでいない。"
correction_status: none_found
related_experts:
  - exp-group-comparison-statistics
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/statistics
---

# Jaeger（2008）：カテゴリカルデータの分析：分散分析からロジット混合モデルへ

## 研究目的

強制選択や正答などカテゴリカルな結果変数の分析に分散分析が広く使われていることの問題を示し、代替を説明する（要旨）。

## 対象データと研究条件

心理言語学のデータセットで各方法を比較する（要旨）。

## 分析手順の要約

通常のロジットモデル（ロジスティック回帰）を紹介し、被験者と項目の変量効果を一度に扱える混合ロジットモデル（二項分布の結果に対する一般化線形混合モデル）を説明する（要旨）。

## 主要な知見

- 比率のデータに逆正弦平方根変換を施しても、分散分析は誤った結果を生みうる。
- ロジットモデルはカテゴリカルなデータの分析に適し、分散分析より多くの利点がある。通常のロジットモデルは変量効果を含まないため、混合ロジットモデルを使う（要旨）。

## 適用上の注意と限界

- 要旨だけを読んだ。
- 対象は心理言語学の実験データで、会話の発話を直接扱ったものではない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert|群間比較の専門家]]：[整理] 発話ごとのコードの有無のようなカテゴリカルなデータで、話者が繰り返し現れる場合は、変量効果を扱えない検定の結果を確定的に解釈しない。[実装判断] 混合ロジットモデルは現在の実装にない。

## 根拠の位置情報

要旨。

## 未確認事項

本文の比較結果。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data]]
