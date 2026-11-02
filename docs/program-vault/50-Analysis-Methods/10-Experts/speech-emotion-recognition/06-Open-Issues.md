---
note_id: expert-speech-emotion-recognition-open-issues
note_type: expert-open-issues
expert_id: exp-speech-emotion-recognition
title: 音声感情推定の専門家：未解決事項
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/audio
---

# 音声感情推定の専門家：未解決事項

知識の確認日：2026-09-15。

## 知識が不足している点

- JTESの論文本文と収録条件（演技か自然な発話かなど）を確認していない。
- いざなみ（`imprt/izanami-wav2vec2-large-jtes-er`）のモデルカードを確認していない。
- 会議やグループインタビューなど複数話者の会話での、日本語の音声感情認識の評価を確認していない。
- Baevski et al.（2020）とSchuller（2018）は書誌のみの確認。

## 既存の資料との食い違い

- 既存の一覧（[[50-Analysis-Methods/99-Peer-Reviewed-References]]）と手法ノート（[[50-Analysis-Methods/02-Semantic-and-Audio/02-Audio-Emotion]]）は、Kosaka et al.を「2023」「JTESを用いた日本語感情音声認識」と記載している。Crossrefの発行年は2024で、題名（Simultaneous Adaptation of Acoustic and Language Models for Emotional Speech Recognition Using Tweet Data）からは、感情を含む音声の音声認識（文字起こし）の論文と読める。要旨・本文を読んでいないため、既存の記載の訂正は保留し、この食い違いを記録する（[[50-Analysis-Methods/20-Literature/LIT-kosaka-2024-emotional-speech-recognition]]）。

## 実装上の課題

- 80%の目安は実装上の判断。
- 確信度がないモデルでは、推定の不確かさを発話ごとに示せない。
