---
note_id: lit-hsu-2021-hubert
note_type: literature
literature_id: LIT-hsu-2021-hubert
title: "HuBERT: Self-Supervised Speech Representation Learning by Masked Prediction of Hidden Units"
authors:
  - Wei-Ning Hsu
  - Benjamin Bolte
  - Yao-Hung Hubert Tsai
  - Kushal Lakhotia
  - Ruslan Salakhutdinov
  - Abdelrahman Mohamed
year: 2021
venue: "IEEE/ACM Transactions on Audio, Speech, and Language Processing, 29, 3451–3460"
source_type: journal_article
peer_review: unconfirmed
peer_review_basis: "掲載誌の査読方針を確認していない。"
doi: 10.1109/TASLP.2021.3122291
url: https://doi.org/10.1109/TASLP.2021.3122291
accessed: 2026-09-15
access_scope: abstract
access_detail: "Semantic Scholar APIの要旨を読んだ。本文は読んでいない。"
correction_status: none_found
related_experts:
  - exp-speech-emotion-recognition
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/audio
---

# Hsu et al.（2021）：HuBERT

## 研究目的

音声表現の自己教師あり学習には、1つの発話に複数の音の単位があること、事前学習の段階で音の単位の辞書がないこと、音の単位の長さが可変で明示的な区切りがないこと、という3つの問題がある。これに対応する方法としてHuBERTを提案する（要旨）。

## 対象データと研究条件

LibrispeechとLibri-lightのベンチマークで、10分から960時間までの微調整用データで評価する（要旨）。

## 分析手順の要約

オフラインのクラスタリングで、BERTに似た予測の損失のための整列済みの目標ラベルを作る。予測の損失はマスクした領域だけに適用し、連続的な入力から音響と言語のモデルを合わせて学習させる。100クラスタのk-meansから始め、クラスタリングを2回繰り返す（要旨）。

## 主要な知見

- HuBERTは、割り当てたクラスタのラベルそのものの質より、教師なしクラスタリングの一貫性に主に依存する。
- wav2vec 2.0の最先端の性能と同等かそれ以上で、10億パラメータのモデルでは難しい評価セットで単語誤り率が最大19%と13%相対的に減少した（要旨）。

## 適用上の注意と限界

- 評価は英語の音声認識のベンチマークであり、感情の推定や日本語での性能を示すものではない。
- 要旨だけを読んだ。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/speech-emotion-recognition/01-Expert|音声感情推定の専門家]]：Gurumojiの「くしなだ」モデルの上流（HuBERT）の出典として記録する。上流の表現学習の性能を、感情ラベルの妥当性の根拠にしない（[整理]）。

## 根拠の位置情報

要旨。

## 未確認事項

本文。

## 関連ノート

[[50-Analysis-Methods/20-Literature/RES-kushinada-hubert-jtes-er-model-card]]、[[50-Analysis-Methods/20-Literature/LIT-baevski-2020-wav2vec2]]
