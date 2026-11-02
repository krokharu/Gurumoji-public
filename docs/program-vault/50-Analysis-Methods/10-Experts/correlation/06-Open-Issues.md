---
note_id: expert-correlation-open-issues
note_type: expert-open-issues
expert_id: exp-correlation
title: 相関の専門家：未解決事項
status: current
updated: 2026-09-28
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 相関の専門家：未解決事項

専門家定義全体の確認日：2026-09-15。SciPy公式API項目の確認日：2026-09-28。

## 知識が不足している点

- Spearman（1904）とHolm（1979）は書誌のみの確認。
- Bishara & Hittner（2012）のシミュレーション条件の詳細は要旨の範囲。

## 実装上の課題

- 変換や並べ替え検定による相関の検定は未実装。
- SciPy v1.18.0の`pearsonr`は`PermutationMethod`と`MonteCarloMethod`によるp値計算を提供するが、専門家定義では変換・並べ替え検定は未実装のまま。API機能の確認は、発話の入れ子構造などの研究設計で再標本化法が妥当かを決めるものではない。
- 多重比較の補正は未実装。
- 10件の目安は実装上の判断。
