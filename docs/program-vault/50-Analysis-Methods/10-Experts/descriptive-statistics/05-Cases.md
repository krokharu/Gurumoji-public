---
note_id: expert-descriptive-statistics-cases
note_type: expert-cases
expert_id: exp-descriptive-statistics
title: 記述統計の専門家：適用例
status: current
updated: 2026-09-28
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 記述統計の専門家：適用例

| 文献 | 領域・データ | 確認範囲 | 分かること |
| --- | --- | --- | --- |
| [[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data\|Aarts et al. 2014]] | 神経科学の5誌の論文314本の検討 | 要旨 | 53%が1つの研究対象から複数の観測を集める入れ子のデザインだった |
| [[50-Analysis-Methods/20-Literature/RES-scipy-describe\|SciPy stats.describe API]] | 配列の要約統計 | SciPy v1.18.0公式API | `axis=0`が既定で、`axis=None`は配列全体を集計する。`bias=False`は歪度・尖度を補正し、分散の`ddof`とは別に指定する |

## 確認できていないこと

- 会話の発話単位の記述統計を扱った方法論の文献は確認していない。記述統計の定義は実装が一次資料。
