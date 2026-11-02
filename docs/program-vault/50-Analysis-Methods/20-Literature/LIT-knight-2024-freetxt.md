---
note_id: lit-knight-2024-freetxt
note_type: literature
literature_id: LIT-knight-2024-freetxt
title: "FreeTxt: A corpus-based bilingual free-text survey and questionnaire data analysis toolkit"
authors:
  - "Dawn Knight"
  - "Nouran Khallaf"
  - "Paul Rayson"
  - "Mahmoud El-Haj"
  - "Ignatius Ezeani"
  - "Steve Morris"
year: 2024
venue: "Applied Corpus Linguistics"
source_type: "method_article"
peer_review: "unconfirmed"
peer_review_basis: "The source note does not record evidence confirming this article's peer-review status."
doi: 10.1016/j.acorp.2024.100103
url: https://doi.org/10.1016/j.acorp.2024.100103
accessed: 2026-09-28
access_scope: abstract
access_detail: "The canonical Source snapshot below remains the verbatim abstract. Separate, hash-bound evidence-text snapshots cover selected Sections 2.2 and 3.2, 3.4, and 4 from the repository's browser-rendered Version-of-Record PDF; each hash identifies its retained snapshot, not the PDF binary."
document_version: "publisher-abstract-verbatim-snapshot-2026-09-28"
document_url: https://doi.org/10.1016/j.acorp.2024.100103
document_sha256: bfd7f51c4235cd07ea24a209c8985f2ca6e3dbcc897f47b6c86edee2e38c7e69
license_id: CC-BY-4.0
license_url: https://creativecommons.org/licenses/by/4.0/
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex GPT-6 (read-only)"
rights_reviewed_at: 2026-09-28T04:31:05Z
rights_review_basis: >-
  The journal and university repository identify the Version of Record as CC BY 4.0. The canonical Source snapshot remains the public abstract; separate selected-section evidence-text snapshots for Sections 2.2 and 3.2, 3.4, and 4 were derived from the browser-rendered PDF. Attributed paraphrased claims may use local processing, the configured Colab route, and export. Generic remote_llm processing remains disallowed. Each selected-section hash pins its retained evidence-text snapshot, not the PDF binary.
correction_status: not_checked
related_experts:
  - exp-quantitative-text-analysis
status: current
updated: 2026-09-28
tags:
  - gurumoji/literature
  - gurumoji/analysis
---


# FreeTxt：英語・ウェールズ語の自由記述を扱うツールキット

## 文献で確認したこと

要旨では、質問票や調査の自由記述を体系的に分析・可視化するための、コーパスに基づく英語・ウェールズ語対応ツールキットFreeTxtの機能を紹介している。小規模から大規模までのデータを対象に、ソフトウェア開発者、自然言語処理の専門家、コーパス言語学者、利用者が協働して開発したと報告する。

## 本文から追加確認したこと

2026-09-28にVersion of Record PDFの§2.2（PDF pp.3–4）を確認した。同節は、単語・n-gram・品詞タグ・意味タグの頻度、KWICによる検索語の出現と周辺文脈の表示、単語分布の可視化をFreeTxtの「潜在的／提案段階」の機能として挙げている。この記述は各機能の実装や評価を保証しない。

Colabへ渡したのはこの範囲を言い換えた短い抜粋である。ブラウザ表示で確認した内容から選択箇所の根拠テキストを作成し、Source version `repository-vor-section-2.2-text-extract-2026-09-28-sha256-555a0024ceb223a4` として保存した。これは原文の逐語的な書き起こしではない。SHA-256 `555a0024ceb223a47c97fdc4f52d6971e906419dc0c8b6ed79c990c3f3fa9009` は保存した根拠テキストのhashであり、PDF原本バイト列のhashではない。

§3.2では、FreeTxtの感情分析pipelineが多言語BERTモデルを使い、そのモデルページが英語テキストで約95%の精度を報告していると説明する。一方、著者らが手動で注釈したウェールズ語レビューを使った実験では約73%だった。95%はモデルページの報告、73%は著者らの実験結果という異なる根拠であり、同一条件で直接比較した数値とは扱わない。

§3.4と§4では、要約機能を抽出型と説明する。パートナーの評価では、アンケート／フィードバックデータより長文ドキュメントで有用性が高く、著者らはこれを当時の現行版の短所として記載している。これはパートナー評価についての著者報告であり、一般的な性能比較とはしない。

これらの節を言い換えた別の選択根拠テキストをSource version `repository-vor-sections-3.2-3.4-4-evidence-snapshot-2026-09-28-sha256-dffb0133c0c21751` として保存した。SHA-256 `dffb0133c0c217516e64126f639a3c13db8501ea9f5c333dc4bdf2f4fbd15d3f` はこの編集済み根拠テキストだけを指し、PDF原本バイト列のhashではない。

## 適用上の注意

§2.2の機能一覧はprovisionally include / potentially performという設計上の限定を伴う。提案された機能を実装済みと断定せず、FreeTxtの対象言語や設計目的を日本語テキストへの性能、または他の分析ツールとの優劣に一般化しない。peer-review状態と訂正状態はそれぞれ`not_verified`、`not_checked`のまま。

## 根拠の位置情報

要旨は出版社版・リポジトリ版。本文の追加確認箇所は[大学リポジトリのVersion-of-Record PDF](https://cronfa.swan.ac.uk/Record/cronfa70086/Download/70086__34939__f82a24c8c3ea49aaad5c813e2a7643c7.pdf)の§2.2（PDF pp.3–4）、§3.2、§3.4、§4。各SHA-256はブラウザ表示から作成した選択根拠テキストを指し、PDF原本のhashではない。記事のDOIは[10.1016/j.acorp.2024.100103](https://doi.org/10.1016/j.acorp.2024.100103)。
