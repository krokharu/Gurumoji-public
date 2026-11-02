---
note_id: expert-speech-emotion-recognition-limits
note_type: expert-limits
expert_id: exp-speech-emotion-recognition
title: 音声感情推定の専門家：適用条件と限界
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/audio
---

# 音声感情推定の専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| 推定済みの発話がある | 分析を始めない（`ser-a1`） | [実装判断] |
| カバー率80%以上 | 要確認（`ser-a2`） | [実装判断] |
| 話者の確認 | 要確認（`ser-a3`） | [文献] Park et al. 2022 |
| 録音条件と学習データの違いの確認 | 研究者が確認（`ser-a4`） | [文献] モデルカード |

## この手法の結果から言えないこと

- 本人が経験した感情、感情の強さ、話者の意図、発言内容の真偽（既存ノート [[50-Analysis-Methods/02-Semantic-and-Audio/02-Audio-Emotion]]）。
- 学習データと異なる場面・話者・マイクでの推定の正確さ（既存ノート、モデルカード）。

## グループインタビューでの注意

- [整理] 複数の人が同時に話す区間では、切り出した音声に他の話者の声が混ざり、推定が不安定になりうる。
- [整理] 感情ラベルを、グループの雰囲気や合意・対立の指標にしない。応答の意味は相互作用分析で扱う。
- [実装判断] 参加者の音声を扱うため、音声とラベルの保存・共有は同意と保存方針に従う。
