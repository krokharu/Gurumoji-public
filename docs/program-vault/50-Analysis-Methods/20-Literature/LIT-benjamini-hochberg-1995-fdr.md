---
note_id: lit-benjamini-hochberg-1995-fdr
note_type: literature
literature_id: LIT-benjamini-hochberg-1995-fdr
title: "Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing"
authors:
  - Yoav Benjamini
  - Yosef Hochberg
year: 1995
venue: "Journal of the Royal Statistical Society Series B, 57(1), 289–300"
source_type: journal_article
peer_review: unconfirmed
peer_review_basis: "掲載誌の査読方針を確認していない。"
doi: 10.1111/j.2517-6161.1995.tb02031.x
url: https://doi.org/10.1111/j.2517-6161.1995.tb02031.x
accessed: 2026-09-15
access_scope: abstract
access_detail: "Crossref APIの要旨欄（SUMMARY）を読んだ。本文は読んでいない。"
correction_status: none_found
related_experts:
  - exp-group-comparison-statistics
  - exp-correlation
  - exp-quantitative-text-analysis
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/statistics
---

# Benjamini & Hochberg（1995）：偽発見率の制御

## 研究目的

多重検定の問題で一般的な、族単位の誤り率（FWER）を制御する方法の欠点を指摘し、別の考え方を示す（要旨）。

## 対象データと研究条件

方法の論文。シミュレーションと例で示す（要旨）。

## 分析手順の要約

誤って棄却した仮説の割合の期待値である偽発見率（FDR）を制御する。単純な逐次的Bonferroni型の手順を示し、独立な検定統計量の場合にFDRを制御することを証明する（要旨）。

## 主要な知見

- FDRは、すべての帰無仮説が真であればFWERと等しく、そうでなければ小さいため、FDRの制御で十分な問題では検出力を高められる。
- シミュレーションで検出力の向上が大きいことを示す（要旨）。

## 適用上の注意と限界

- 要旨で示された証明は、独立な検定統計量の場合である。同じ会話の発話から作った多数の検定は独立とは限らない。
- 要旨だけを読んだため、手順の具体的な式は確認していない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert|群間比較の専門家]]、[[50-Analysis-Methods/10-Experts/correlation/01-Expert|相関の専門家]]、[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert|計量テキスト分析の専門家]]：多数のコード・語・変数の検定を行うと偽の発見が増えるため、補正の方針（FWERかFDRか）を決めていない結果は探索的と表示する。[実装判断] 補正は現在の実装にない。

## 根拠の位置情報

要旨。

## 未確認事項

本文の手順と例。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-holm-1979-multiple-testing]]
