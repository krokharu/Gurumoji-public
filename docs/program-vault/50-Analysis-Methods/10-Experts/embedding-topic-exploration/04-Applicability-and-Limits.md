---
note_id: expert-embedding-topic-exploration-limits
note_type: expert-limits
expert_id: exp-embedding-topic-exploration
title: 埋め込みによるテーマ探索の専門家：適用条件と限界
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/semantic
---

# 埋め込みによるテーマ探索の専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| 最新の結果がある | 分析を始めない（`emb-a1`） | [実装判断] |
| シルエット係数0.1以上 | 要確認（`emb-a2`） | [文献] Rousseeuw 1987、[実装判断] |
| 発話が20件以上 | 要確認（`emb-a3`） | [実装判断] |
| 話者の偏り・断片の確認 | 研究者が確認（`emb-a4`） | [実装判断] |
| 話者の確認 | 要確認（`emb-a5`） | [文献] Park et al. 2022 |

## この手法の結果から言えないこと

- 埋め込みの類似度とクラスタから、話者の合意、不一致、重要性、因果、感情（既存ノート [[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]]）。
- クラスタがテーマ分析のテーマやKJ法のグループであること（[整理]）。

## グループインタビューでの注意

- [整理] グループの会話では、同じ話題への短い応答や相づちが多く、文脈補完の設定によってクラスタが変わる。
- [整理] 相づちの応答先は時系列上の推定であり、応答関係の確定は相互作用分析の研究者の作業で行う（[[50-Analysis-Methods/10-Experts/focus-group-interaction/01-Expert]]）。
