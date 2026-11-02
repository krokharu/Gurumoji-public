---
note_id: expert-correlation-limits
note_type: expert-limits
expert_id: exp-correlation
title: 相関の専門家：適用条件と限界
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 相関の専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| SciPyが使える | 分析を始めない（`cor-a1`） | [実装判断] |
| 発話が10件以上 | 要確認（`cor-a2`） | [文献] Bishara & Hittner 2012、[実装判断] |
| 入れ子と多重比較の理解 | 研究者が確認（`cor-a3`） | [文献] Aarts et al. 2014、Benjamini & Hochberg 1995 |
| 正式な形態素解析 | 要確認（`cor-a4`） | [実装判断] |

## この手法の結果から言えないこと

- 因果、方向、話者内の変化と話者間の差の区別（既存ノート [[50-Analysis-Methods/03-Statistics/03-Correlation]]）。
- 発話を独立な観測とみなせない設計でのp値の一般化（[文献] Aarts et al. 2014）。

## グループインタビューでの注意

- [整理] 話者ごとに発話の長さの傾向が違うと、話者の違いが発話単位の相関として現れる（話者間の差と話者内の関連が混ざる）。
- [整理] 司会者の短い質問と参加者の長い回答が混ざると、役割の違いが相関を作る。役割を分けて確認する。
