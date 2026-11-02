---
note_id: analysis-common-source-classification
note_type: common-knowledge
title: 出典の区分と根拠の強さ
status: current
updated: 2026-09-15
tags:
  - gurumoji/analysis
  - gurumoji/literature
  - gurumoji/common-knowledge
---

# 出典の区分と根拠の強さ

文献ノート（[[50-Analysis-Methods/20-Literature/00-Index]]）のプロパティの意味と、専門家定義で根拠として使うときの扱い。

## 資料種別（`source_type`）

| 値 | 意味 |
| --- | --- |
| `journal_article`／`review_article` | 学術誌の論文・総説 |
| `conference_paper` | 会議録の論文 |
| `bulletin_paper` | 大学・学部等の紀要論文 |
| `serial_article`／`interview_article` | 学会誌等の連載記事・インタビュー記事 |
| `book`／`book_chapter` | 書籍・書籍の章 |
| `preprint` | arXiv等のプレプリント・技術報告 |
| `official_resource`／`model_card` | 開発者・著者・運営団体の公式ページ、モデル配布ページ |
| `report` | 研究会の報告論集など |

## 査読状態（`peer_review`）

| 値 | 判定の条件 |
| --- | --- |
| `confirmed` | 掲載誌・会議の査読方針を確認できた。根拠を `peer_review_basis` に書く |
| `not_peer_reviewed` | プレプリント、公式ページ、モデルカードなど、査読を経ない資料 |
| `unconfirmed` | 査読方針を確認していない、または記事種別（紀要・連載・インタビュー・特集等）に査読が及ぶか確認できない |

- DOIがあることだけで `confirmed` にしない。
- 特集号の論文、連載記事、インタビュー記事、紀要、依頼原稿、議論を促す短い論文など、記事の区分によって査読の適用が異なりうるものは、その区分の扱いを確認できない限り `unconfirmed` とする。
- 確認できたのは多くの場合「現在の」投稿規程であり、発表当時の手続きまでは確認していない。その点を `peer_review_basis` に書く。
- 既存の [[50-Analysis-Methods/99-Peer-Reviewed-References]] は掲載誌の種類から「査読文献」と分類していた。本調査で個別に方針を確認していない文献は、文献ノートでは `unconfirmed` とする。

## 訂正・撤回（`correction_status`）

| 値 | 意味 |
| --- | --- |
| `none_found` | CrossrefのAPIの更新情報（訂正・撤回の関連付け）に記録がなく、掲載ページでも訂正の表示を見ていない。網羅的な確認ではない |
| `correction_published` | 訂正記事・撤回の記録を確認した。本文にその書誌を書く |
| `not_checked` | Crossref以外の登録機関のDOI、DOIのない資料など、更新情報を確認していない |

訂正の内容まで読んでいない場合は、その旨を本文に書き、訂正前の記述を根拠にするときは注意を付ける。

## 確認範囲（`access_scope`）

| 値 | 意味 | 書いてよい内容 |
| --- | --- | --- |
| `full_text` | 本文を取得して読んだ | 本文で確認した手順・主張。位置は節見出しかPDFのページで示す |
| `abstract` | 要旨だけを読んだ | 要旨に書かれた範囲。手順の詳細や数値は書かない |
| `bibliographic` | 書誌情報だけを確認した | 書誌と、どの文脈で引用されているか。内容の要約は書かない |
| `official_page` | 公式ページを読んだ | ページに書かれた範囲 |

本文をツールで取得した場合は、その経路（出版社サイト、著者リポジトリ、PDFのテキスト抽出など）を `access_detail` に書く。PDFのテキスト抽出では、図表や段組みの一部を読み落とす可能性がある。

## 根拠として使うときの優先順位

1. 手法の原典・提唱者による方法論の論文（査読の有無と確認範囲を併記）
2. 査読付きの方法論論文・総説
3. 提唱者・運営団体の公式ページ
4. 紀要・連載・報告論集（査読未確認として扱う）
5. Web記事（理解の補助にとどめ、手順や基準の根拠にしない）

プレプリントは「未査読」と明示して使う。原典の書籍を読んでいない場合は、その書籍を根拠にした手順を「原典未確認」と書く。

## 更新の規則

- 文献ノートを更新すると、その文献を参照する専門家の知識hashが変わり、次回の実行で古い要約やAI見解が「更新が必要」になる（[[40-Design/method-rules]]）。
- 内容が変わっていない資料は再調査・再要約しない。再確認したときは `accessed` と調査記録を更新する。

関連：[[50-Analysis-Methods/08-Common-Knowledge/01-Evidence-and-Claims]]、[[90-Templates/literature-note]]
