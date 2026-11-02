---
note_id: expert-speech-emotion-recognition-overview
note_type: expert-overview
expert_id: exp-speech-emotion-recognition
title: 音声感情推定の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/audio
---

# 音声感情推定の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/speech-emotion-recognition/01-Expert]]

## この専門家が答える問い

- 話者分離後の発話音声に、音声モデルが付けた感情ラベル（ang・hap・sad・neu）は、話者・モデル・ラベル別にどう分布しているか。推定のカバー率と未推定の発話はどれだけか。[実装判断] 計算の定義は既存の手法ノート [[50-Analysis-Methods/02-Semantic-and-Audio/02-Audio-Emotion]] による。

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 本人が経験した感情、感情の強さ、意図 | 音声モデルの分類からは判定できない（既存ノート） |
| 応答の意味、同意・不同意 | [[50-Analysis-Methods/10-Experts/focus-group-interaction/01-Expert\|相互作用分析]] |
| 発話量の偏り | [[50-Analysis-Methods/10-Experts/participation-balance/01-Expert\|参加バランス]] |

## 文献との関係

- [文献] 使用する「くしなだ」のモデルカードは、JTES（v1.1）で学習した音声感情認識モデルで、セッションごとの正解率（平均0.8477）を示す（[[50-Analysis-Methods/20-Literature/RES-kushinada-hubert-jtes-er-model-card|モデルカード]]）。評価はJTESでの値である。
- [文献] 顔の動きについては、表出から感情状態を推論することに大きな不確かさがあるとする総説がある（[[50-Analysis-Methods/20-Literature/LIT-barrett-2019-emotional-expressions|Barrett et al. 2019]]、要旨、訂正記事あり）。音声についての直接の証拠ではない（[整理]）。

## 流派

| 流派 | この定義での扱い |
| --- | --- |
| JTESで学習した自己教師あり音声モデル（くしなだ：HuBERT、いざなみ：wav2vec 2.0）の分類 | 既定（実装済み） |

## 担当する実装

- `audio_emotion`（[[50-Analysis-Methods/02-Semantic-and-Audio/02-Audio-Emotion]]）
