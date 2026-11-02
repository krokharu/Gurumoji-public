---
note_id: lit-mayring-2000-qca
note_type: literature
literature_id: LIT-mayring-2000-qca
title: "Qualitative Content Analysis"
authors:
  - Philipp Mayring
year: 2000
venue: "Forum Qualitative Sozialforschung / Forum: Qualitative Social Research, 1(2), Art. 20"
source_type: journal_article
peer_review: confirmed
peer_review_basis: "FQSの現在の方針ページで、2名の査読者による二重盲検の査読を確認（2026-09-15）。2000年の掲載当時の手続きは未確認。"
doi: 10.17169/fqs-1.2.1089
url: https://www.qualitative-research.net/index.php/fqs/article/view/1089
accessed: 2026-09-15
access_scope: full_text
access_detail: "FQSが公開する英語版のPDFとHTMLを取得して読んだ。2026-09-27に公式PDF（10ページ）の原本hashを固定。DOIの登録機関はDataCite。"
document_version: "fqs-english-pdf-retrieved-2026-09-27-sha256-675fc4ec"
document_url: https://www.qualitative-research.net/index.php/fqs/article/download/1089/2386
document_sha256: 675fc4ecc22015000728f36f6541fd974f903bb3250f7dc70bea1381a066271f
license_id: CC-BY-4.0
license_url: https://creativecommons.org/licenses/by/4.0/
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex primary agent (official FQS article license review)"
rights_reviewed_at: 2026-09-27T04:27:17Z
rights_review_basis: >-
  The official FQS article page identifies this work as licensed under CC BY 4.0.
  The license legal code permits sharing and adaptation for any purpose with attribution,
  a license link, and indication of changes. Project routes are limited to local RTX 5070
  processing, user-initiated Colab A100 processing with our own model (not Colab
  generative AI), and export of paraphrased source-linked claims carrying author, title,
  DOI, license, and change attribution. The remote_llm route is blocked by project policy.
  Third-party material is excluded. The source note records correction_status as
  not_checked; this rights review does not verify correction history or scientific
  claims, which must be checked separately before Claim approval.
correction_status: none_found
correction_checked_at: 2026-09-27
correction_check_basis: "FQS公式記事ページに訂正記事の案内なし。DataCite DOI登録（10.17169/fqs-1.2.1089）のrelatedIdentifiersは空。公式ドメインで表題とcorrection/erratumを検索して該当する訂正記事を確認できなかった。後日の訂正がないことを保証するものではない。"
related_experts:
  - exp-qualitative-content-analysis
  - exp-thematic-analysis
status: current
updated: 2026-09-27
tags:
  - gurumoji/literature
  - gurumoji/qualitative
---

# Mayring（2000）：Qualitative Content Analysis

## 研究目的

量的内容分析の方法上の強みを保ちながら、それを質的な手続きへ広げた、規則に沿う体系的な質的テキスト分析の方法を説明する（要旨）。

## 対象データと研究条件

方法を解説する論文で、特定のデータセットの分析結果を報告するものではない。

## 分析手順の要約

- テキストをコミュニケーションのモデルの中に位置づけ、テキストのどの側面から何を推論するかという分析の目的を定める（para 4, 7）。
- 分析は規則と段階のモデルに沿って進める。カテゴリーを分析の中心に置き、分析の途中でフィードバックを通じて見直す（para 7）。
- 信頼性と妥当性の基準を持ち、コーダー間の一致を確認する。一致の目安として、Cohenのκが.7を超えれば十分とする記述がある（para 7）。
- 中心となる手続きは次の二つ（para 8）。
  - 帰納的カテゴリー形成：研究質問と理論的背景から、素材のどの側面を扱うかという定義の基準を決める。素材を読みながら暫定的なカテゴリーを段階的に作り、フィードバックで見直して主カテゴリーへまとめ、信頼性を確認する。研究質問が量的な側面を求める場合は、コード化したカテゴリーの頻度も分析できる（4.1節、para 9–12）。
  - 演繹的カテゴリー適用：理論から事前に定めた分析の側面を、方法的に統制した手順で文章箇所へ割り当てる。カテゴリーごとに、定義、典型的な文章例、コーディング規則をまとめたコーディング・アジェンダを作る（4.2節、para 13–16、Fig.3）。

## 主要な知見

実証研究の報告ではなく方法の提案である。質的内容分析を、カテゴリー体系を中心にした規則に基づく手続きとして示し、分析者が意味があると考える場合は量的な分析の段階と結び付けられるとする（para 26）。

## 適用上の注意と限界

- 研究質問が非常に開かれていて探索的であり、カテゴリーで扱うことが制約になる場合、または段階を追わない全体的な分析を予定する場合は、適していないとする（para 27）。
- 他の質的な手続きと組み合わせることはでき、手法の選択では研究質問と素材の特徴を優先するとする（para 27）。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/qualitative-content-analysis/01-Expert|質的内容分析の専門家]]：帰納的カテゴリー形成と演繹的カテゴリー適用を別の手順として保持する。演繹的な分析では、定義・例・規則を持つコーディング・アジェンダを入力の条件にする。
- 研究質問が非常に開かれている場合、または全体的な解釈を求める場合は、この手法を無条件に進めず、[[50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert|テーマ分析の専門家]]など他の手法を検討するよう示す。
- [実装判断] κ .7は本文献が示す目安として記録する。Gurumojiは一致係数を計算しないため、複数のコーダーによる確認を実施したと表示しない。

## 根拠の位置情報

FQS版の段落番号（[n]）。基本的な考え方：para 4–7。二つの手続き：para 8。帰納的カテゴリー形成：4.1節（para 9–12）。演繹的カテゴリー適用：4.2節（para 13–16）。量的な段階との接続：para 26。適さない場合：para 27。

## 未確認事項

- 手順を示す図（Fig.1, Fig.2）は画像のため、文字としては確認していない。
- 本文が参照するMayringの書籍（ドイツ語）は読んでいない。
- 2000年当時のFQSの査読手続き。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-hsieh-shannon-2005-qca]]、[[50-Analysis-Methods/20-Literature/LIT-elo-kyngas-2008-qca]]、[[50-Analysis-Methods/20-Literature/LIT-krippendorff-2004-reliability]]
