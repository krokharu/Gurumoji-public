---
note_id: expert-descriptive-statistics-overview
note_type: expert-overview
expert_id: exp-descriptive-statistics
title: 記述統計の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 記述統計の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/descriptive-statistics/01-Expert]]

## この専門家が答える問い

- 発話時間、文字数、形態素数、内容語数、語彙多様性、文字／分の分布は、全体と比較群（話者・役割）でどうか（N、欠測、平均、標準偏差、中央値、四分位、最小・最大）。話者、役割、質問候補の度数はどうか。[実装判断] 計算の定義は既存の手法ノート [[50-Analysis-Methods/03-Statistics/01-Descriptive-Statistics]] による。

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 群の差が偶然を超えるか | [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert\|群間比較]] |
| 変数どうしの関連 | [[50-Analysis-Methods/10-Experts/correlation/01-Expert\|相関]] |
| 影響力、理解度、関与の質 | 記述量はそれらを測定しない（既存ノート） |

## 文献との関係

- [文献] 心理学の量的研究の報告基準は、分析を主要・副次・探索的に分けて扱う（[[50-Analysis-Methods/20-Literature/LIT-appelbaum-2018-jars-quant|Appelbaum et al. 2018]]、要旨。訂正記事あり）。
- [文献] 入れ子になったデータの観測は独立ではない（[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data|Aarts et al. 2014]]、要旨）。発話は話者と会話に入れ子になる（[整理]）。

## 担当する実装

- `descriptive_statistics`（[[50-Analysis-Methods/03-Statistics/01-Descriptive-Statistics]]）
