---
note_id: lit-gilardi-2023-llm-annotation
note_type: literature
literature_id: LIT-gilardi-2023-llm-annotation
title: "ChatGPT outperforms crowd workers for text-annotation tasks"
authors:
  - Fabrizio Gilardi
  - Meysam Alizadeh
  - Maël Kubli
year: 2023
venue: "Proceedings of the National Academy of Sciences, 120(30), e2305016120"
source_type: journal_article
peer_review: confirmed
peer_review_basis: "PNASの編集方針で、2名以上の独立した専門家による査読を確認（2026-09-15、現在の方針）。"
doi: 10.1073/pnas.2305016120
url: https://doi.org/10.1073/pnas.2305016120
accessed: 2026-09-15
access_scope: abstract
access_detail: "Europe PMCの要旨（PMID 37463210）を読んだ。本文は読んでいない。"
license_id: CC-BY-4.0
license_url: https://creativecommons.org/licenses/by/4.0/
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex primary agent (official PNAS rights metadata review)"
rights_reviewed_at: 2026-09-26T23:10:52Z
rights_review_basis: >-
  The PNAS article page identifies the open-access article as distributed under CC BY 4.0.
  The CC license allows sharing and adaptation for any purpose with appropriate credit,
  a license link, and indication of changes. This project allowlist is limited to local
  RTX 5070 processing, user-initiated Colab A100 processing, and export of paraphrased,
  source-linked claims carrying author/title/DOI/license/change attribution. The
  remote_llm route remains blocked by project policy. Third-party material or supplements
  with separate rights are excluded. This review confirms rights metadata only; article
  body access remains as recorded above.
correction_status: none_found
related_experts:
  - exp-qualitative-content-analysis
  - exp-thematic-analysis
  - exp-framework-method
  - exp-scat
  - exp-m-gta
  - exp-focus-group-interaction
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/generative-ai
---

# Gilardi, Alizadeh & Kubli（2023）：テキスト注釈課題でのChatGPTとクラウドワーカー

## 研究目的

分類器の学習や教師なしモデルの評価に必要な、人手によるテキスト注釈を、ChatGPTで置き換えられるかを検討する（要旨）。

## 対象データと研究条件

ツイートとニュース記事の4つのサンプル（n = 6,183）。注釈課題は関連性、立場、話題、フレームの検出など（要旨）。

## 分析手順の要約

ChatGPTのゼロショットの注釈を、クラウドワーカー（MTurk）と訓練を受けた注釈者の注釈と比べた（要旨）。

## 主要な知見

- 4つのデータセット全体で、ChatGPTのゼロショットの正確さはクラウドワーカーを平均で約25ポイント上回った。
- ChatGPTの注釈者内の一致は、すべての課題でクラウドワーカーと訓練を受けた注釈者を上回った。
- 注釈1件あたりの費用は0.003ドル未満で、MTurkの約30分の1だった（要旨）。

## 適用上の注意と限界

- 対象はツイートとニュース記事の分類課題であり、日本語の会話の逐語録、質的分析の解釈、テーマの生成を検証したものではない。
- 使用したモデルは論文当時のもので、Gurumojiが接続するモデルとは異なる。
- 要旨だけを読んだ。

## 専門家の判断・手順に反映する内容

- AIによる補助を認める専門家（質的内容分析、テーマ分析、フレームワーク法、SCAT、M-GTA、フォーカスグループの相互作用分析）：[整理] 限定された分類課題でLLMの注釈が有用だった例として記録する一方、解釈を伴う質的分析での妥当性の根拠にはしない。AIの出力は候補として扱い、研究者の確認を必須にする（[[50-Analysis-Methods/08-Common-Knowledge/04-AI-Assistance-Boundaries]]）。

## 根拠の位置情報

要旨。

## 未確認事項

本文のプロンプトと評価の詳細。

## 関連ノート

[[50-Analysis-Methods/06-Generative-and-Workflow/01-AI-Insights]]
