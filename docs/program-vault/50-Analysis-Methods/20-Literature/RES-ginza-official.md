---
note_id: res-ginza-official
note_type: literature
literature_id: RES-ginza-official
title: "GiNZA - Japanese NLP Library（公式README v5.2.0）"
authors:
  - Megagon Labs
year: 未確認
venue: "GiNZAの公式ドキュメント（GitHub Pages）"
source_type: official_resource
peer_review: not_peer_reviewed
peer_review_basis: "ソフトウェアの公式ドキュメントで、査読を経た資料ではない。"
doi: ""
url: https://github.com/megagonlabs/ginza/blob/v5.2.0/README.md
accessed: 2026-09-28
access_scope: official_page
access_detail: "公式ドキュメントに加え、GitHub v5.2.0 tag のREADMEとLICENSEを取得。Colab用の根拠はREADMEのライセンス、依存関係、学習データ記述に限定。"
document_version: "github-v5.2.0-readme-retrieved-2026-09-28-sha256-71652a6e50e94ee7"
document_sha256: 71652a6e50e94ee71020d16b38dd7e67a2c679149a2622a83fe9ef8615ec2dc7
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
  The versioned official repository README states that the GiNZA library and its
  Japanese Universal Dependencies models are distributed under MIT, and links the
  versioned LICENSE. Colab processing is limited to short excerpts of this README
  with our own model; dependency packages, pretrained weights, training corpora,
  and third-party text are excluded. Export is limited to paraphrased, attributed,
  source-linked claims. The project's remote_llm route remains disallowed.
correction_status: not_checked
related_experts:
  - exp-japanese-text-preprocessing
status: current
updated: 2026-09-28
tags:
  - gurumoji/literature
  - gurumoji/text
---

# GiNZAの公式ドキュメントとREADME

## 研究目的

日本語自然言語処理のライブラリGiNZAの使い方、モデル、精度、ライセンスを説明する（公式ページ）。

## 対象データと研究条件

精度の比較は、UD_Japanese-BCCWJ r2.8のテストセットで、5万ステップ学習した時点のモデルの値として示されている。

## 分析手順の要約

- 自然言語処理のフレームワークにspaCyを使い、トークン化（形態素解析）にSudachiPy、単語ベクトルにchiVeを使う。
- Transformersの事前学習モデルを使う `ja_ginza_electra` と、従来型の `ja_ginza` がある。

## 主要な知見

公式ページの精度表の例（UD_Japanese-BCCWJ r2.8）：`ja_ginza_electra` はLAS 92.3、UAS 93.7、UPOS 98.1、ENE 61.3。`ja_ginza_bert_large`（β版）はLAS 93.8、UAS 94.9、UPOS 98.3、ENE 70.8。

v5.2.0 READMEは、GiNZAの係り受け解析モデルがUD Japanese BCCWJ r2.8の一部で訓練されたと記載する。これは固有表現認識モデルの学習データ（GSK2014-AのBCCWJ版）や、`ja_ginza_electra`の事前学習コーパス（mC4由来の日本語文）とは別の記述である。

同READMEによると、固有表現認識モデルはGSK2014-Aの2019年BCCWJ版の一部で訓練され、ラベル体系には拡張固有表現階層と拡張OntoNotes 5を用いる。これは係り受け解析モデルの学習データとは区別する。

## 適用上の注意と限界

- GiNZAのライブラリと日本語UDモデルはMIT Licenseで公開され、依存するSudachi、SudachiDict、chiVe、spaCy、transformersにはそれぞれのライセンスがある。
- [整理] 精度は書き言葉のコーパス（BCCWJ）での評価であり、音声認識の誤りやフィラーを含む会話の逐語録での精度を示すものではない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/01-Expert|日本語テキスト前処理の専門家]]：使ったモデル名と版を結果に記録する。評価コーパスでの精度を、逐語録での解析の正しさとして示さない。GiNZAが使えない場合の簡易解析（`fallback`）の結果を、正式な解析結果と混ぜない（既存の実装契約と一致）。

## 根拠の位置情報

GitHub v5.2.0 tag のREADME「License」「Training Datasets」節。精度表は公式ドキュメントからの既存確認事項。

## 未確認事項

Gurumojiが実際に読み込むモデル（`ja_ginza` か `ja_ginza_electra` か）の確認。依存ソフトウェア、重み、学習データの個別ライセンスは今回のLLM許可範囲に含めない。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-matsuda-2020-ginza]]、[[50-Analysis-Methods/20-Literature/LIT-takaoka-2018-sudachi]]、[[50-Analysis-Methods/20-Literature/LIT-omura-asahara-2018-ud-japanese]]
