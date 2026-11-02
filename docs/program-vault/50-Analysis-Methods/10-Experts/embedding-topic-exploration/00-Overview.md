---
note_id: expert-embedding-topic-exploration-overview
note_type: expert-overview
expert_id: exp-embedding-topic-exploration
title: 埋め込みによるテーマ探索の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/semantic
---

# 埋め込みによるテーマ探索の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert]]

## この専門家が答える問い

- 文埋め込みの近さで、意味の近い発話のまとまり（クラスタ）を探索すると、どんなまとまりがあり、代表的な発話と外れた発話はどれか。話者や時間によってどう分布するか。[実装判断] 計算の定義は既存の手法ノート [[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]]（アプリの表示名は「Transformerテーマ分析」）による。

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 研究者の解釈によるテーマの確定 | [[50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert\|テーマ分析]]。名前が似ているが別の手法 |
| ボトムアップのグループ編成と図解 | [[50-Analysis-Methods/10-Experts/kj-method/01-Expert\|KJ法]] |
| 語の頻度・共起 | [[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert\|計量テキスト分析]] |
| 合意・不一致・重要性・感情 | 類似度とクラスタからは推論しない（既存ノート） |

## 流派

| 流派 | この定義での扱い |
| --- | --- |
| 文埋め込み（multilingual-e5-small）とK-means（既定） | 実装済み |
| BERTopic（埋め込み、クラスタリング、クラス単位のTF-IDF） | 未実装。類似の構成の先行例として記録（[[50-Analysis-Methods/20-Literature/LIT-grootendorst-2022-bertopic\|Grootendorst 2022]]、プレプリント、要旨） |

## 担当する実装

- `transformer_topics`（[[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]]）
