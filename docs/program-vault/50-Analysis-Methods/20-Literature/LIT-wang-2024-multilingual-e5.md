---
note_id: lit-wang-2024-multilingual-e5
note_type: literature
literature_id: LIT-wang-2024-multilingual-e5
title: "Multilingual E5 Text Embeddings: A Technical Report"
authors:
  - Liang Wang
  - Nan Yang
  - Xiaolong Huang
  - Linjun Yang
  - Rangan Majumder
  - Furu Wei
year: 2024
venue: "arXiv:2402.05672"
source_type: preprint
peer_review: not_peer_reviewed
peer_review_basis: "arXivの技術報告（プレプリント）。"
doi: ""
url: https://arxiv.org/abs/2402.05672
accessed: 2026-09-16
access_scope: abstract
access_detail: "arXiv APIが429を返したため、Hugging FaceのPapers APIでarXivの要旨と公開日（2024-02-08）を取得して読んだ。本文は読んでいない。"
correction_status: not_checked
related_experts:
  - exp-embedding-topic-exploration
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/semantic
---

# Wang et al.（2024）：Multilingual E5 Text Embeddings

## 研究目的

2023年半ばに公開した多言語E5テキスト埋め込みモデルの学習方法と評価結果を報告する（要旨）。

## 対象データと研究条件

約10億の多言語のテキスト対による対照事前学習と、ラベル付きデータセットの組み合わせによる微調整（要旨）。

## 分析手順の要約

英語のE5モデルの手順に従い、small・base・largeの3つの大きさのモデルを提供する。指示で調整した埋め込みモデルも導入する（要旨）。

## 主要な知見

推論の効率と埋め込みの質の釣り合いを選べる3つのモデルを示し、指示調整モデルは同程度の大きさの英語専用の最先端モデルに匹敵する性能だとする（要旨）。

## 適用上の注意と限界

- 査読を経ていない技術報告である。
- 日本語のグループインタビューの逐語録での評価を示すものではない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert|埋め込みによるテーマ探索の専門家]]：Gurumojiが使う `intfloat/multilingual-e5-small`（384次元）の出典として、プレプリントであることを明記して記録する（既存ノート [[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]] の扱いと一致）。

## 根拠の位置情報

要旨。

## 未確認事項

本文、日本語での評価結果の有無。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-reimers-gurevych-2019-sbert]]
