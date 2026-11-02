---
note_id: expert-conversation-timing-limits
note_type: expert-limits
expert_id: exp-conversation-timing
title: 会話の時間構造の専門家：適用条件と限界
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/conversation
---

# 会話の時間構造の専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| 有効な時刻が50%以上 | 分析を始めない（`time-a1`） | [実装判断] |
| 有効な時刻が95%以上 | 要確認（`time-a2`） | [実装判断] |
| 話者の確認 | 要確認（`time-a3`） | [文献] Park et al. 2022 |
| 話者が2人以上 | 分析を始めない（`time-a4`） | [実装判断] |
| 時刻の精度の確認 | 研究者が確認（`time-a5`） | [文献] Stivers et al. 2009、[実装判断] |

## この手法の結果から言えないこと

- 無音から同意・熟考・不参加、重なりから遮り・対立、話者遷移から影響関係（既存ノート [[50-Analysis-Methods/04-Conversation/02-Conversation-Dynamics]]）。
- 発話間の短い間の差から、文化差や参加者の態度（[整理]、ミリ秒単位の研究との精度の違い）。

## グループインタビューでの注意

- [整理] 複数の人が同時に話す場面では、話者分離の誤りと重なりの候補が増える。重なりの候補の多い区間は、話者の確認を優先する。
- [実装判断] 司会者の質問の後の長い無音は、質問の難しさ、考える時間、録音の欠落など複数の可能性がある。音声で確認するまで意味を付けない。
- [整理] 沈黙を同意とみなさないという共通の注意（[[50-Analysis-Methods/08-Common-Knowledge/03-Group-Interview-Data]]）をそのまま適用する。
