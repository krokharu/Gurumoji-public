---
note_id: expert-thematic-analysis-limits
note_type: expert-limits
expert_id: exp-thematic-analysis
title: テーマ分析の専門家：適用条件と限界
status: current
updated: 2026-09-28
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# テーマ分析の専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| 研究質問がある | 分析を始めない（`ta-a1`） | [文献] Braun & Clarke 2006：テーマは研究質問に関して重要な何かを捉える |
| 分析できる発話がある | 分析を始めない（`ta-a2`） | [実装判断] |
| 分析前の判断とTAの形の記録 | 研究者が確認（`ta-a4`、`ta-a5`） | [文献] Braun & Clarke 2006、2021 |
| 言い淀みなどを取り除いていない書き起こし | 研究者が確認（`ta-a6`） | [文献] 岡ほか 2022、p.149 |

## この手法の結果から言えないこと

- テーマの発話数や話者数から、その意見の重要性、代表性、支持人数（[文献] 再帰的TAはテーマの頻度の測定と報告を行わない、岡ほか 2022）。
- テーマがデータの中に客観的に存在し、研究者と無関係に「浮かび上がった」ということ（[文献] Braun & Clarke 2006、岡ほか 2022）。

## テーマ分析とTransformerテーマ分析の違い

[整理] Gurumojiの `transformer_topics` は、文埋め込みとK-meansによる意味クラスタで、研究者の解釈によるテーマの生成ではない（[[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]]）。クラスタは、研究者がデータを読み返す入口としてだけ使える。

## グループインタビューでの注意

- [文献] フォーカスグループの結果を1人ずつの引用で報告すると、個人の見解を相互作用から切り離せるかのような印象を与えうる（[[50-Analysis-Methods/20-Literature/LIT-gronkjaer-2011-fg-interaction|Grønkjær et al. 2011]]、p.16）。テーマの抜粋を示すときは、前後の応答の文脈を確認する。
- [文献] 相互作用のコード化をSystematic Text Condensationと並行して行う一例が報告されている（[[50-Analysis-Methods/20-Literature/LIT-hermann-2024-fg-interaction-coding|Hermann et al. 2024]]、本文）。同論文のコード枠組みは特定のデータで開発・試行されたものなので、組み込む場合は相互作用分析の専門家の定義と並べて適合を確認する。
- [実装判断] 司会者の質問の言い回しがテーマの名前に入り込んでいないかを確認する。
