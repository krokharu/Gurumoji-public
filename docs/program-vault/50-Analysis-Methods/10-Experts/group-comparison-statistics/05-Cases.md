---
note_id: expert-group-comparison-statistics-cases
note_type: expert-cases
expert_id: exp-group-comparison-statistics
title: 群間比較の専門家：適用例
status: current
updated: 2026-09-28
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 群間比較の専門家：適用例

| 文献 | 領域・データ | 確認範囲 | 分かること |
| --- | --- | --- | --- |
| [[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data\|Aarts et al. 2014]] | 神経科学の論文314本 | 要旨 | 入れ子のデザインが多く、依存を無視すると第1種の誤りが大きくなりうる |
| [[50-Analysis-Methods/20-Literature/LIT-jaeger-2008-logit-mixed\|Jaeger 2008]] | 心理言語学のデータセット | 要旨 | カテゴリカルな結果変数で、分散分析とロジット混合モデルを比較 |
| [[50-Analysis-Methods/20-Literature/RES-scipy-f-oneway\|SciPy v1.18.0 `f_oneway` API]] | 統計ライブラリの公式API | ParametersとNotes | `equal_var=True`は等分散を仮定する標準ANOVA、`False`はWelch ANOVAを選ぶ。`nan_policy`の3値と既定も記載。API仕様の確認であり、方法論文献の確認やGurumojiへの実装を意味しない |

## 確認できていないこと

- グループインタビューの発話単位の検定を扱った方法論の文献は確認していない。
