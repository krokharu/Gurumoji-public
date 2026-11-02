---
note_id: expert-conversation-timing-overview
note_type: expert-overview
expert_id: exp-conversation-timing
title: 会話の時間構造の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/conversation
---

# 会話の時間構造の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/conversation-timing/01-Expert]]

## この専門家が答える問い

- 話者の遷移（誰の次に誰が話したか）、話者間の平均の間、長い無音の候補、発話の重なりの候補、時間区間ごとの発話量の推移はどうか。[実装判断] 計算の定義は既存の手法ノート [[50-Analysis-Methods/04-Conversation/02-Conversation-Dynamics]] による。

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 無音が同意・熟考・不参加を意味するか | 時間の値からは判断できない |
| 重なりが遮りや対立か | 時間の値からは判断できない。応答の連鎖は [[50-Analysis-Methods/10-Experts/focus-group-interaction/01-Expert\|相互作用分析]] |
| 発話量の偏り | [[50-Analysis-Methods/10-Experts/participation-balance/01-Expert\|参加バランス]] |

## 文献との関係

- [文献] 10の言語の会話で、重なりを避け、ターン間の沈黙を最小にする傾向が共通して見られ、平均の間の言語差は言語全体の平均から250ミリ秒の範囲内だったとする研究がある（[[50-Analysis-Methods/20-Literature/LIT-stivers-2009-turn-taking|Stivers et al. 2009]]、要旨）。
- [文献] ターン間の間は200ミリ秒程度と短く、参加者は相手のターンの終わりを予測して応答を準備すると考えられている（[[50-Analysis-Methods/20-Literature/LIT-levinson-torreira-2015-timing|Levinson & Torreira 2015]]、要旨）。
- [整理] これらはミリ秒単位の測定に基づく知見であり、文字起こしのセグメントの時刻から計算するGurumojiの値で同じ精度の議論はできない。

## 担当する実装

- `conversation_dynamics`（[[50-Analysis-Methods/04-Conversation/02-Conversation-Dynamics]]）
