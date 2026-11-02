---
note_id: expert-correlation-cases
note_type: expert-cases
expert_id: exp-correlation
title: 相関の専門家：適用例
status: current
updated: 2026-09-28
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 相関の専門家：適用例

| 文献 | 領域・データ | 確認範囲 | 分かること |
| --- | --- | --- | --- |
| [[50-Analysis-Methods/20-Literature/LIT-bishara-hittner-2012-correlation\|Bishara & Hittner 2012]] | 2つのシミュレーション研究（12の方法の比較） | 要旨 | 標本の大きさと非正規性によって、誤りの少ない方法が異なる |
| [[50-Analysis-Methods/20-Literature/RES-scipy-pearsonr\|SciPy v1.18.0 pearsonr API]] | Pearson相関のp値と信頼区間の公式API仕様 | 公式APIページ | `method`で置換検定またはモンテカルロ法を選べる。信頼区間はFisher変換が既定で、`BootstrapMethod`はSciPy bootstrapに委譲する。退化した再標本化でNaNとなる場合があり、非常に小さい標本（約6観測）で典型的とされる |

## 確認できていないこと

- 会話の発話単位の相関分析を扱った方法論の文献は確認していない。
- SciPy APIの機能説明だけでは、再標本化法が特定の会話データで妥当か、またプロジェクトの分析実装で利用できるかは確認できない。約6観測は注意例であり標本数の閾値ではない。
