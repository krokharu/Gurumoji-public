---
note_id: expert-speech-emotion-recognition-cases
note_type: expert-cases
expert_id: exp-speech-emotion-recognition
title: 音声感情推定の専門家：適用例
status: current
updated: 2026-09-28
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/audio
---

# 音声感情推定の専門家：適用例

| 文献 | 領域・データ | 確認範囲 | 分かること |
| --- | --- | --- | --- |
| [[50-Analysis-Methods/20-Literature/RES-kushinada-hubert-jtes-er-model-card\|くしなだのモデルカード]] | JTES v1.1での評価 | 公式ページ | セッションごとの正解率と評価の手順 |
| [[50-Analysis-Methods/20-Literature/LIT-zhang-2021-cross-corpus-ser\|Zhang et al. 2021]] | コーパス間の音声感情認識 | 本文の選択箇所 | 既存システムの「多く」が単一コーパス・単一言語設定だという総説上の記述に加え、学習・テストコーパス間の言語、文化、distribution mode、データ規模の差による汎化課題と、基本構成の二段階（感情分類器・domain-invariant feature extraction）を確認。日本語会話音声の性能評価ではない |

## 確認できていないこと

- グループインタビューや会議の音声に日本語の音声感情認識を適用し、聴取や自己報告と比べた研究は確認していない。
- JTESの論文本文は読んでいない。
