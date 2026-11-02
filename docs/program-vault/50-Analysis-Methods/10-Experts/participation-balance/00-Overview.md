---
note_id: expert-participation-balance-overview
note_type: expert-overview
expert_id: exp-participation-balance
title: 参加バランスの専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/conversation
---

# 参加バランスの専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/participation-balance/01-Expert]]

## この専門家が答える問い

- 話者や属性群ごとに、発話数、発話時間、割合はどれだけか。参加は偏っているか（Gini係数、正規化evenness、HHI、最大参加者比）。[実装判断] 計算の定義は既存の手法ノート [[50-Analysis-Methods/04-Conversation/01-Participation]] による。
- 発言の少ない参加者や、発話時間が集中している箇所を、確認の候補として示す。

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 応答によって意見がどう形成されたか | [[50-Analysis-Methods/10-Experts/focus-group-interaction/01-Expert\|相互作用分析]] |
| 間や重なりの時間構造 | [[50-Analysis-Methods/10-Experts/conversation-timing/01-Expert\|会話の時間構造]] |
| 群の差の検定 | [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert\|群間比較]] |
| 影響力、満足度、議論の質 | 発話量はそれらを測定しない（既存ノート） |

## 文献との関係

- [文献] 課題を遂行する2〜5人の集団の研究で、集団の成績に関わる因子が、会話のターン交替の分布の平等さと相関したとする報告がある（[[50-Analysis-Methods/20-Literature/LIT-woolley-2010-collective-intelligence|Woolley et al. 2010]]、要旨）。対象はフォーカスグループではなく、相関の報告である。
- [文献] フォーカスグループでは、司会者が発言の多い参加者を把握し、全員の声が聞かれるようにする役割を持つとされる（[[50-Analysis-Methods/20-Literature/LIT-gronkjaer-2011-fg-interaction|Grønkjær et al. 2011]]、p.25）。

## 担当する実装

- `participation`（[[50-Analysis-Methods/04-Conversation/01-Participation]]）
