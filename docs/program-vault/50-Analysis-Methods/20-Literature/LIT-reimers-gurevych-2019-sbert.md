---
note_id: lit-reimers-gurevych-2019-sbert
note_type: literature
literature_id: LIT-reimers-gurevych-2019-sbert
title: "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks"
authors:
  - Nils Reimers
  - Iryna Gurevych
year: 2019
venue: "Proceedings of EMNLP-IJCNLP 2019（頁はCrossrefで3980–3990、ACL Anthologyと既存の一覧で3982–3992）"
source_type: conference_paper
peer_review: confirmed
peer_review_basis: "EMNLP-IJCNLP 2019の論文募集で、3名以上のプログラム委員による二重盲検の査読を確認（2026-09-15）。"
doi: 10.18653/v1/D19-1410
url: https://aclanthology.org/D19-1410/
accessed: 2026-09-15
access_scope: abstract
access_detail: "Semantic Scholar APIの要旨を読んだ。書誌はCrossref APIで確認し、頁の記録が情報源で2頁ずれていることを記録した。本文は読んでいない。"
correction_status: none_found
related_experts:
  - exp-embedding-topic-exploration
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/semantic
---

# Reimers & Gurevych（2019）：Sentence-BERT

## 研究目的

BERTやRoBERTaは文の対を同時に入力する必要があり、大量の文の類似検索やクラスタリングのような教師なしの課題には計算量の点で不向きなため、比較可能な文埋め込みを作る方法を提案する（要旨）。

## 対象データと研究条件

文の意味的類似度（STS）の標準課題と転移学習の課題で評価する（要旨）。

## 分析手順の要約

事前学習済みのBERTを、Siamese・tripletのネットワーク構造で調整し、コサイン類似度で比べられる意味のある文埋め込みを作る（要旨）。

## 主要な知見

- 1万文の中で最も似た対を探す計算が、BERTでは約65時間かかるのに対し、SBERTでは約5秒になり、BERTの精度を保つ。
- STSの課題と転移学習の課題で、他の最先端の文埋め込みの方法を上回った（要旨）。

## 適用上の注意と限界

- 英語を中心とした標準課題での評価であり、日本語の会話の逐語録での性能を示すものではない。
- Gurumojiが使うmultilingual-e5-smallはSBERTそのものではない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert|埋め込みによるテーマ探索の専門家]]：[整理] 文埋め込みとコサイン類似度で文の意味的な近さを比べ、クラスタリングに使うという考え方の根拠にする。類似度が高いことを、同じ意見や合意と解釈しない。

## 根拠の位置情報

要旨。

## 未確認事項

本文、頁の正しい記録（Crossrefと会議録の差）。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-wang-2024-multilingual-e5]]、[[50-Analysis-Methods/20-Literature/LIT-rousseeuw-1987-silhouette]]
