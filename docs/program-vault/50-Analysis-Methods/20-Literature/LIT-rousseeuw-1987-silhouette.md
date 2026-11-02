---
note_id: lit-rousseeuw-1987-silhouette
note_type: literature
literature_id: LIT-rousseeuw-1987-silhouette
title: "Silhouettes: A graphical aid to the interpretation and validation of cluster analysis"
authors:
  - Peter J. Rousseeuw
year: 1987
venue: "Journal of Computational and Applied Mathematics, 20, 53–65"
source_type: journal_article
peer_review: unconfirmed
peer_review_basis: "掲載誌の査読方針を確認していない。"
doi: 10.1016/0377-0427(87)90125-7
url: https://doi.org/10.1016/0377-0427(87)90125-7
accessed: 2026-09-15
access_scope: abstract
access_detail: "Semantic Scholar APIの要旨を読んだ。本文は読んでいない。"
correction_status: none_found
related_experts:
  - exp-embedding-topic-exploration
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/semantic
---

# Rousseeuw（1987）：シルエット

## 研究目的

分割型のクラスタリングの結果を解釈し検証するための、新しい図示の方法を提案する（要旨）。

## 対象データと研究条件

方法の論文（要旨）。

## 分析手順の要約

各クラスタを、まとまり（tightness）と分離（separation）の比較に基づく「シルエット」で表す。どの対象がクラスタの内側によく収まり、どの対象がクラスタの間にあるかを示す（要旨）。

## 主要な知見

シルエットを1つの図にまとめると、クラスタの相対的な質とデータの配置を概観できる。平均シルエット幅はクラスタリングの妥当性の評価になり、「適切な」クラスタ数の選択に使える可能性があるとする（要旨）。

## 適用上の注意と限界

- シルエットはクラスタの幾何的なまとまりと分離の指標であり、クラスタの内容の意味の妥当性を示すものではない。
- 要旨だけを読んだ。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert|埋め込みによるテーマ探索の専門家]]：Gurumojiはコサイン距離のシルエットが最大の候補からテーマ数を選ぶ（[実装判断]、既存ノートの記述）。シルエットが低い場合は警告し、値が高くてもテーマの意味の妥当性は研究者が代表発話と外れ値を読んで確認する。

## 根拠の位置情報

要旨。

## 未確認事項

本文。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-lloyd-1982-kmeans]]、[[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]]
