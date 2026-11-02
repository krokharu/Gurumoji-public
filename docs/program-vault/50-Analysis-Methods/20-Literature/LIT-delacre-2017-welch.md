---
note_id: lit-delacre-2017-welch
note_type: literature
literature_id: LIT-delacre-2017-welch
title: "Why Psychologists Should by Default Use Welch’s t-test Instead of Student’s t-test"
authors:
  - Marie Delacre
  - Daniël Lakens
  - Christophe Leys
year: 2017
venue: "International Review of Social Psychology, 30(1), 92–101"
source_type: journal_article
peer_review: confirmed
peer_review_basis: "掲載誌の記事ページに「Peer Reviewed」と表示（2026-09-16に確認）。"
doi: 10.5334/irsp.82
url: https://doi.org/10.5334/irsp.82
accessed: 2026-09-16
access_scope: full_text
access_detail: "掲載誌の記事ページ（HTML、CC BY 4.0）を取得してタグを除いた本文で読んだ。記事ページに訂正記事の案内があり、訂正記事の書誌はCrossref APIで確認した。"
license_id: CC-BY-4.0
license_url: https://creativecommons.org/licenses/by/4.0/
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex primary agent (official IRSP article license review)"
rights_reviewed_at: 2026-09-27T04:24:59Z
rights_review_basis: >-
  The official International Review of Social Psychology article page identifies this
  article as CC BY 4.0. The license legal code permits sharing and adaptation for any
  purpose with attribution, a license link, and indication of changes. Project routes
  are limited to local RTX 5070 processing, user-initiated Colab A100 processing with
  our own model (not Colab generative AI), and export of paraphrased source-linked claims
  carrying author, title, DOI, license, and change attribution. The remote_llm route is
  blocked by project policy. Article-body and figure redistribution is excluded by
  project scope. The publisher identifies a separate correction article (DOI 10.5334/irsp.661).
  Its rights and content are recorded separately in
  [[50-Analysis-Methods/20-Literature/LIT-delacre-2022-correction]] and must be considered
  before any related Claim is approved.
correction_status: correction_published
related_experts:
  - exp-group-comparison-statistics
status: current
updated: 2026-09-27
tags:
  - gurumoji/literature
  - gurumoji/statistics
---

# Delacre, Lakens & Leys（2017）：Welchのt検定を既定にすべき理由

## 研究目的

独立な2群のt検定で、Studentのt検定ではなくWelchのt検定を既定として使うべき理由を論じる（要旨）。

## 対象データと研究条件

方法の論文。独立な2群の平均の比較を扱う。

## 分析手順の要約

- 分散の等質性の前提が満たされない場合の第1種の誤りの制御と、前提が満たされる場合の頑健性の損失を比べる（要旨）。
- t検定の前にLeveneの検定などで前提を確認して検定を選ぶ二段階の手順の限界を論じる（本文「Limitations of Two-Step Procedures」の節）。

## 主要な知見

- Welchのt検定は、分散が等しくない場合に第1種の誤りをStudentのt検定よりよく制御し、前提が満たされる場合も頑健性をほとんど失わないとして、既定の戦略にすべきだと論じる（要旨）。
- 分析と、あらゆる統計ソフトでWelchのt検定が使えることから、特に標本の大きさが等しくない場合はWelchのt検定を既定で使う手順を推奨する（本文、二段階の手順の限界の節の直前）。
- 一部の統計ソフトはWelchのt検定を既定で表示するとする（本文）。

## 適用上の注意と限界

- 対象は2群のt検定であり、3群以上の分散分析を直接扱った論文ではない。
- 訂正記事がある：[[50-Analysis-Methods/20-Literature/LIT-delacre-2022-correction|Delacre et al.（2022）]]。訂正の要点と未確認範囲を別ノートに記録した。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert|群間比較の専門家]]：[実装判断] Gurumojiの一元配置分散分析は分散の等質性を仮定する。群の大きさや分散が大きく異なる場合は結果に注意を付け、Leveneの検定の結果で検定を切り替える手順は採らない。Welch型の検定は現在の実装にない（計画は [[40-Design/quantification-statistics-plan]]）。

## 根拠の位置情報

記事ページの要旨、本文の「Limitations of Two-Step Procedures」の節とその直前の推奨。

## 未確認事項

訂正後の追加ファイルとシミュレーション条件の独立確認。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-rasch-2011-pretest]]、[[50-Analysis-Methods/20-Literature/LIT-kruskal-wallis-1952]]
