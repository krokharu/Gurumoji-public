---
note_id: lit-delacre-2022-correction
note_type: literature
literature_id: LIT-delacre-2022-correction
title: "Correction: Why Psychologists Should by Default Use Welch’s t-test Instead of Student’s t-test"
authors:
  - Marie Delacre
  - Daniël Lakens
  - Christophe Leys
year: 2022
venue: "International Review of Social Psychology, 35(1), 21, 1–3"
source_type: journal_article
peer_review: unconfirmed
peer_review_basis: "Correction notice; peer-review status of this notice was not established."
doi: 10.5334/irsp.661
url: https://doi.org/10.5334/irsp.661
accessed: 2026-09-28
access_scope: full_text
access_detail: "発行元PDFの全3頁を確認。訂正内容は2頁。PDF SHA-256: 747dc11c7ca447a22ab85b33bbc83dbf871a8ea4cdb1a22e2569d67ced667260。"
document_sha256: 747dc11c7ca447a22ab85b33bbc83dbf871a8ea4cdb1a22e2569d67ced667260
document_version: official-publisher-pdf-2022-11-25
license_id: CC-BY-4.0
license_url: https://creativecommons.org/licenses/by/4.0/
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex primary agent (official publisher PDF license review)"
rights_reviewed_at: 2026-09-28T00:00:00Z
rights_review_basis: >-
  The official publisher PDF states that the article is distributed under CC BY 4.0.
  The license permits sharing and adaptation with attribution, a license link, and
  indication of changes. Project routes are limited to local processing, user-initiated
  Colab A100 processing with our own model, and export of paraphrased source-linked claims.
  The remote_llm route remains blocked by project policy.
correction_status: not_checked
related_experts:
  - exp-group-comparison-statistics
status: current
updated: 2026-09-28
tags:
  - gurumoji/literature
  - gurumoji/statistics
---

# Delacre, Lakens & Leys（2022）：Welch検定の論文に対する訂正

## 確認範囲

発行元の訂正記事全3頁を確認した。訂正の説明は2頁にあり、2017年論文とその追加ファイルの修正点を示す。

## 訂正の要点

- 著者らは、平均に基づく群比較ではWelchのt検定をStudentのt検定より優先する主張を維持している。一方、Yuenのt検定について、歪んだ分布を含む条件への結論を一般化できないと説明した。
- F比と標準偏差比の説明で、標本標準偏差と母標準偏差を混同した箇所を訂正した。標準偏差比は母標準偏差比を指す。
- StudentとWelchのt値・自由度・p値が一致する条件は、母分散が等しいことだけではなく、標本標準偏差の推定値も一致する場合だと明確にした。
- 追加ファイルのシミュレーションでは、両側指数分布の尺度指定とカイ二乗分布のスクリプトに誤りがあり、結論を修正した。著者らは、標本サイズが異なる高度に歪んだ分布への結論を一般化できないとした。

これらを2017年論文の記述と合わせて扱う。要約は訂正記事に基づくもので、追加ファイルや再実行スクリプトの独立再解析は含まない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert|群間比較の専門家]]：2017年論文に基づく候補主張を承認するときは、本訂正の条件・撤回・修正を照合する。

## 根拠の位置情報

発行元PDF、2頁。訂正記事は [DOI 10.5334/irsp.661](https://doi.org/10.5334/irsp.661) で公開。本文テキストはPDFから抽出し、改行と空白を正規化した。

## 未確認事項

訂正記事自体に後続訂正がないかは未確認。訂正後の追加ファイルとシミュレーションスクリプトも独立確認していない。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-delacre-2017-welch|Delacre et al. 2017の原論文]]
