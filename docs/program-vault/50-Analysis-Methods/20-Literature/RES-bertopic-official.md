---
note_id: res-bertopic-official
note_type: literature
literature_id: RES-bertopic-official
title: "BERTopic algorithm documentation"
authors:
  - Maarten Grootendorst
year: 2025
venue: "BERTopic official documentation, v0.17.4"
source_type: official_resource
peer_review: not_peer_reviewed
peer_review_basis: "ソフトウェアの公式マニュアルで、査読論文ではない。"
doi: ""
url: https://github.com/MaartenGr/BERTopic/blob/v0.17.4/docs/algorithm/algorithm.md
accessed: 2026-09-28
access_scope: official_page
access_detail: "BERTopic公式GitHub v0.17.4のalgorithm.mdを取得。READMEとLICENSEも同じtagで照合。"
document_version: "github-v0.17.4-algorithm-retrieved-2026-09-28-sha256-952f766df6f0030e"
document_sha256: 952f766df6f0030ecc5db2effdf136778372825bd1e675973d78701715df35dc
license_id: MIT
license_url: https://opensource.org/license/mit/
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex GPT-6 (read-only)"
rights_reviewed_at: 2026-09-28T02:42:13Z
rights_review_basis: >-
  The official v0.17.4 repository identifies its license as MIT and contains this
  documentation file in the same tagged repository. Colab processing is limited to
  selected documentation passages using our own model; export is limited to
  attributed, source-linked paraphrased claims. The project's remote_llm route
  remains disallowed.
correction_status: not_checked
related_experts:
  - exp-embedding-topic-exploration
status: current
updated: 2026-09-28
tags:
  - gurumoji/literature
  - gurumoji/semantic
---

# BERTopic公式アルゴリズム資料

## 資料の目的

埋め込みを使ったBERTopicのトピック表現生成工程と、各段階を差し替えられる設計を説明する。

## 分析手順の要約

公式資料は、文書埋め込み、次元削減、クラスタリング、トークン化、クラス単位のTF-IDFによる重み付けという段階を示す。コード例では、それぞれにSentence Transformers、UMAP、HDBSCAN、CountVectorizer、ClassTfidfTransformerを使う。

## 主要な知見

- 埋め込み・次元削減・クラスタリング・語彙表現を別々に選べるモジュール構成。
- `c-TF-IDF`は各クラスタを1文書として集計したクラス単位の表現で、従来の文書単位TF-IDFそのものではない。公式アルゴリズム資料はクラス単位の語頻表現にL1正規化を適用し、トピックサイズの差を補正すると説明する。`ClassTfidfTransformer`にはBM25重み付けの選択肢もある。
- 出力トピックはクラスタと上位語の表現であり、分析対象に即したテーマの解釈は分析者が行う。

## 適用上の注意と限界

公式実装資料はモデルの説明であり、日本語会話データに対する埋め込み品質、短文・相づち・否定の扱い、テーマの妥当性を保証しない。埋め込みモデルやクラスタリング設定、除外された文書数を記録し、人の確認を経て解釈する。

## 根拠の位置情報

BERTopic v0.17.4公式資料「The Algorithm」「Visual Overview」「Code Overview」。

## 未確認事項

Gurumojiの埋め込み・BERTopic実行設定との一致、日本語逐語録での品質評価。
