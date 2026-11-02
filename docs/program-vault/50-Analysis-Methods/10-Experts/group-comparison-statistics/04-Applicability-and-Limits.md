---
note_id: expert-group-comparison-statistics-limits
note_type: expert-limits
expert_id: exp-group-comparison-statistics
title: 群間比較の専門家：適用条件と限界
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 群間比較の専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| SciPyが使える | 分析を始めない（`grp-a1`） | [実装判断] |
| 群が2つ以上 | 分析を始めない（`grp-a2`） | [実装判断] |
| 期待度数の小さいセルが20%以下 | 要確認（`grp-a3`） | [実装判断] |
| 入れ子の理解 | 研究者が確認（`grp-a4`） | [文献] Aarts et al. 2014、Jaeger 2008 |
| 多重比較の扱い | 研究者が確認（`grp-a5`） | [文献] Benjamini & Hochberg 1995 |
| 話者の確認 | 要確認（`grp-a6`） | [文献] Park et al. 2022 |

## この手法の結果から言えないこと

- 有意差から、因果、実質的な重要性、個人差の安定性（既存ノート [[50-Analysis-Methods/03-Statistics/02-Group-Statistics]]）。
- 発話を独立な標本とした検定から、参加者や会話の母集団の違い（[文献] Aarts et al. 2014）。

## グループインタビューでの注意

- [整理] 同じ話者の発話は互いに似やすく、話者を群にすると群内の発話は独立ではない。1回のグループの話者数は少なく、話者を単位にした推測統計はほとんどできない。
- [整理] 役割を群にする場合、司会者の発話は質問が多いなど、役割そのものによる違いが大きい。役割の違いを「意見の違い」と読まない。
- [実装判断] 検定の結果は、原文を読み返す手がかりとしてだけ使う。
