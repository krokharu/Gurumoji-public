---
note_id: expert-quantitative-text-analysis-limits
note_type: expert-limits
expert_id: exp-quantitative-text-analysis
title: 計量テキスト分析の専門家：適用条件と限界
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 計量テキスト分析の専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| 研究質問がある | 要確認・探索のみ（`qta-a1`） | [文献] 樋口 2017 |
| 比較の枠組みがある | 要確認（`qta-a2`） | [文献] 樋口 2017 |
| 正式な形態素解析 | 要確認（`qta-a3`） | [文献] GiNZAの公式ページ、[実装判断] |
| 発話が20件以上 | 要確認（`qta-a4`） | [実装判断] |
| 話者が2人以上 | 要確認（`qta-a5`） | [実装判断] |

## この手法の結果から言えないこと

- 語の頻度から、意見の重要性、支持人数、合意（[整理]）。
- 共起から、概念的な関係、因果、同意（既存ノート [[50-Analysis-Methods/01-Text-and-Context/06-Cooccurrence]]）。
- 話者別特徴語の差から、話者の信念や属性による因果的な差（既存ノート [[50-Analysis-Methods/01-Text-and-Context/02-Speaker-Characteristics]]）。

## グループインタビューでの注意

- [整理] 発話の長さや司会者の質問が語の頻度と共起を大きく左右する。司会者の発話を含めるかを明示する。
- [整理] 話者別特徴語は、話者分離の誤りや話者ラベルの取り違えの影響を受ける（[[50-Analysis-Methods/20-Literature/LIT-park-2022-diarization-review|Park et al. 2022]]）。
- [文献] インタビュー記録では、計量テキスト分析で全体像や複数グループ間の違いを把握しておくと、質的な分析の道しるべとして役立つことがある（樋口 2017、3.4.2節）。結果は道しるべであり、結論ではない（[整理]）。
