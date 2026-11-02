---
note_id: expert-participation-balance-limits
note_type: expert-limits
expert_id: exp-participation-balance
title: 参加バランスの専門家：適用条件と限界
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/conversation
---

# 参加バランスの専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| 話者が2人以上 | 分析を始めない（`part-a1`） | [実装判断] |
| 話者の確認 | 要確認（`part-a2`） | [文献] Park et al. 2022 |
| 不明な話者が10%以下 | 要確認（`part-a3`） | [実装判断] |
| 有効な時刻が90%以上 | 要確認（`part-a4`） | [実装判断] |
| 役割と分母の設定 | 研究者が確認（`part-a5`） | [実装判断] |

## この手法の結果から言えないこと

- 長い発話、多いターン、低いGini係数から、影響力、満足度、発言機会の公平性、会話の質（既存ノート [[50-Analysis-Methods/04-Conversation/01-Participation]]）。
- 発言の少ない参加者の関心の低さや同意（[整理]）。

## グループインタビューでの注意

- [整理] 参加の偏りは、司会者の指名や質問の向け方、グループの構成（同質性・異質性）の影響を受ける（[[50-Analysis-Methods/20-Literature/LIT-gronkjaer-2011-fg-interaction|Grønkjær et al. 2011]]）。
- [整理] 相づちや短い同意の発話もターンとして数えられる。発話量の多さと、内容のある発言の多さを区別する。
- [実装判断] 話者分離で1人が2つのラベルに分かれた場合や、2人が1つのラベルになった場合、偏りの指標は大きく変わる。
