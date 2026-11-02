---
note_id: res-kushinada-hubert-jtes-er-model-card
note_type: literature
literature_id: RES-kushinada-hubert-jtes-er-model-card
title: "imprt/kushinada-hubert-large-jtes-er（モデルカード）"
authors:
  - Intelligent Media Processing Research Team
year: 2025
venue: "Hugging Face（最終更新 2025-03-11）"
source_type: model_card
peer_review: not_peer_reviewed
peer_review_basis: "モデル配布ページで、査読を経た資料ではない。"
doi: ""
url: https://huggingface.co/imprt/kushinada-hubert-large-jtes-er
accessed: 2026-09-15
access_scope: official_page
access_detail: "公開されているモデルページとHugging FaceのモデルAPIを読んだ。ファイルの取得には利用条件への同意が必要なゲート付きのリポジトリで、READMEの直接取得は401だった。モデルファイルは取得していない。"
correction_status: not_checked
related_experts:
  - exp-speech-emotion-recognition
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/audio
---

# kushinada-hubert-large-jtes-er のモデルカード

## 研究目的

S3PRL向けの音声感情認識モデルとして、JTES（Japanese Twitter-based Emotional Speech v1.1）で学習したモデルを配布する（モデルカード）。

## 対象データと研究条件

- 学習データ：JTES v1.1。上流モデル：`imprt/kushinada-hubert-large`。
- ライセンス表示：Apache-2.0。ファイルの取得にはログインと利用条件の確認が必要（ゲート付き）。
- タグにSUPERBのarXiv（2105.01051）が含まれる。

## 分析手順の要約

S3PRLの下流タスクとして評価する手順（fold1のチェックポイントでSession1を評価するコマンド例）を示す。

## 主要な知見

モデルカードの正解率（accuracy）：session1 0.8446、session2 0.8471、session3 0.8725、session4 0.7925、session5 0.8822、平均 0.8477。

## 適用上の注意と限界

- 正解率はJTESのセッションでの評価であり、会議やグループインタビューの自然な会話、話者分離後の切り出し音声、異なるマイク環境での性能を示すものではない。
- JTESの収録条件（演技か自然発話かなど）は本調査で確認していない。
- Gurumojiは `imprt/kushinada-hubert-large-jtes-er` の `fold1` のチェックポイントと、`imprt/izanami-wav2vec2-large-jtes-er` を選べる（`src/gurumoji/app.py` の `AIST_EMOTION_MODEL_CONFIG`）。いざなみのモデルカードは今回確認していない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/speech-emotion-recognition/01-Expert|音声感情推定の専門家]]：モデル名、リポジトリ、fold、学習データ（JTES）、評価条件を結果に必ず記録し、評価セットの正解率を手元の会話での正確さとして示さない。
- ラベルは ang・hap・sad・neu の4つの主ラベルに限られる（既存ノート [[50-Analysis-Methods/02-Semantic-and-Audio/02-Audio-Emotion]]）。

## 根拠の位置情報

モデルカードの「RESULTS」「License」の欄、モデルAPIの `cardData`・`gated`・`lastModified`。

## 未確認事項

JTESの論文本文と収録条件、いざなみのモデルカード、fold別の評価の意味。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-hsu-2021-hubert]]、[[50-Analysis-Methods/20-Literature/LIT-kosaka-2024-emotional-speech-recognition]]
