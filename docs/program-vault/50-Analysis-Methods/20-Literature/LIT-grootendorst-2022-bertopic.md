---
note_id: lit-grootendorst-2022-bertopic
note_type: literature
literature_id: LIT-grootendorst-2022-bertopic
title: "BERTopic: Neural topic modeling with a class-based TF-IDF procedure"
authors:
  - Maarten Grootendorst
year: 2022
venue: "arXiv:2203.05794"
source_type: preprint
peer_review: not_peer_reviewed
peer_review_basis: "arXivのプレプリント。"
doi: ""
url: https://arxiv.org/abs/2203.05794
accessed: 2026-09-16
access_scope: abstract
access_detail: "arXiv APIが429を返したため、Hugging FaceのPapers APIでarXivの要旨と公開日（2022-03-11）を取得して読んだ。本文は読んでいない。"
correction_status: not_checked
related_experts:
  - exp-embedding-topic-exploration
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/semantic
---

# Grootendorst（2022）：BERTopic

## 研究目的

トピックモデルをクラスタリングの課題として扱う近年の方向を発展させ、まとまりのあるトピックの表現を得る方法を提案する（要旨）。

## 対象データと研究条件

古典的なモデルとクラスタリング型のモデルを含む複数のベンチマークで評価する（要旨）。

## 分析手順の要約

事前学習済みのTransformer型言語モデルで文書の埋め込みを作り、埋め込みをクラスタリングし、クラス単位のTF-IDFでトピックの表現を作る（要旨）。

## 主要な知見

まとまりのあるトピックを生成し、さまざまなベンチマークで競争力を保つとする（要旨）。

## 適用上の注意と限界

- 査読を経ていないプレプリントである。
- [実装判断] Gurumojiの `transformer_topics` は、埋め込み、K-means、特徴語による仮ラベルで構成し、BERTopicそのものではない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert|埋め込みによるテーマ探索の専門家]]：「埋め込み→クラスタリング→語による表現」という類似の構成の先行例として記録する。結果を「BERTopicで分析した」と表示しない。

## 根拠の位置情報

要旨。

## 未確認事項

本文と評価の詳細。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-reimers-gurevych-2019-sbert]]
