---
note_id: lit-bishara-hittner-2012-correlation
note_type: literature
literature_id: LIT-bishara-hittner-2012-correlation
title: "Testing the significance of a correlation with nonnormal data: Comparison of Pearson, Spearman, transformation, and resampling approaches"
authors:
  - Anthony J. Bishara
  - James B. Hittner
year: 2012
venue: "Psychological Methods, 17(3), 399–417"
source_type: journal_article
peer_review: unconfirmed
peer_review_basis: "掲載誌の方針ページを確認していない（査読誌とする情報のみ）。"
doi: 10.1037/a0028087
url: https://doi.org/10.1037/a0028087
accessed: 2026-09-15
access_scope: abstract
access_detail: "Europe PMCの要旨を読んだ。本文は読んでいない。"
correction_status: none_found
related_experts:
  - exp-correlation
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/statistics
---

# Bishara & Hittner（2012）：非正規データでの相関の有意性の検定

## 研究目的

データが正規分布しない場合のPearsonの相関の検定の問題を踏まえ、代替となる方法の相対的な性能を明らかにする（要旨）。

## 対象データと研究条件

2つのシミュレーション研究で、Pearson、Spearmanの順位相関、変換、再標本化を含む12の方法を比べた（要旨）。

## 分析手順の要約

シミュレーションで、各方法の第1種・第2種の誤りの割合を比べた（要旨）。

## 主要な知見

- 非正規データでは、Pearsonのrの検定は第1種の誤りを増やし、検出力を下げうる。
- 多くの標本の大きさ（n ≥ 20）では、Pearsonの相関を検定する前にデータを正規の形に変換すると誤りが最小になり、変換の中では順位に基づく逆正規変換が最も有益だった。
- 標本が小さく（n ≤ 10）極端に非正規な場合は、並べ替え検定がブートストラップ検定などより優れることが多かった（要旨）。

## 適用上の注意と限界

要旨だけを読んだため、シミュレーションの分布の条件は確認していない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/correlation/01-Expert|相関の専門家]]：発話時間や文字数のように歪んだ分布の変数で、Pearsonの相関のp値をそのまま解釈しない。[実装判断] 変換と並べ替え検定は現在の実装になく、PearsonとSpearmanを並べて示す。

## 根拠の位置情報

要旨。

## 未確認事項

本文のシミュレーション条件。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-spearman-1904-rank]]、[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data]]
