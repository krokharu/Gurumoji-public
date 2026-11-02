---
note_id: lit-levinson-torreira-2015-timing
note_type: literature
literature_id: LIT-levinson-torreira-2015-timing
title: "Timing in turn-taking and its implications for processing models of language"
authors:
  - Stephen C. Levinson
  - Francisco Torreira
year: 2015
venue: "Frontiers in Psychology, 6, 731"
source_type: review_article
peer_review: confirmed
peer_review_basis: "Frontiersの共同型査読（Collaborative peer review）の方針を確認（2026-09-15、現在の方針）。"
doi: 10.3389/fpsyg.2015.00731
url: https://doi.org/10.3389/fpsyg.2015.00731
accessed: 2026-09-28
access_scope: full_text
access_detail: "Frontiers公式配布PDF（17頁）を取得し本文を確認。今回のA100処理には出版社公式全文HTMLから§5.2の選択箇所を固定して使用した。図・紙面レイアウトは未確認。"
document_version: "publisher-vor-frontiers-retrieved-2026-09-28-sha256-bda17c1efd9ad791"
document_url: https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2015.00731/pdf
document_sha256: bda17c1efd9ad7914fca32e9b444141b2a7c6fc5f55ffc37678b08627205dd96
processing_snapshot_sha256: 2bee897da2f719cc1ef4ed45346744a78dcacc4db5f73063da755269de3fd43d
license_id: CC-BY-4.0
license_url: https://creativecommons.org/licenses/by/4.0/
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex GPT-6 (read-only)"
rights_reviewed_at: 2026-09-28T02:42:13Z
rights_review_basis: >-
  The publisher article page identifies the article as open access under the
  Creative Commons Attribution License, and links to CC BY 4.0. Colab processing
  is limited to selected passages of the public article using our own model;
  export is limited to paraphrased, attributed, source-linked claims. No personal
  or confidential data is sent, and the project's remote_llm route remains disallowed.
correction_status: none_found
related_experts:
  - exp-conversation-timing
status: current
updated: 2026-09-28
tags:
  - gurumoji/literature
  - gurumoji/conversation
---

# Levinson & Torreira（2015）：ターン交替のタイミングと言語処理モデル

## 研究目的

会話のターン交替の仕組みに関する文献を概観し、欠けていた行動データの統計分析を加えて、言語処理の理論にとっての含意を検討する（要旨）。

## 対象データと研究条件

会話のターン交替に関する文献の概観と、会話・行動データの統計分析を扱う。ターン間隔について既存のコーパス研究を比較し、発話開始までの産出潜時と対照する。個々の研究条件は本文中の引用先に分散している。

## 分析手順の要約

本文の5.1節では、会話コーパスのターン間隔と重なりを整理し、既存研究の計測条件やコーパス差を説明する。特定の一律なしきい値を提案する論文ではない。

## 主要な知見

- ターン交替は、Sacksら（1974）が指摘した体系的な性質を持つことを示す。
- ターン間の間は短く（200ミリ秒程度）、発話の産出にかかる時間はそれより長い（600ミリ秒以上）ため、会話の参加者は相手のターンの終わりを予測して応答を事前に準備していると考えられる。
- その結果、共通の処理資源を使う産出と理解がある程度重なることになるとし、次に話す参加者の心的過程の最初のモデルを素描する（要旨）。
- NXT-Switchboardから時間情報の誤りがない348会話（約38時間）を選んだ分析では、記録された信号の77%が一方の話者だけの発話、19.2%が沈黙、3.8%が同時発話だった。沈黙を除いた発話信号では95.3%が一方の話者だけの発話だった。別の分母で見ると、話者交替（floor transfer）の30.1%は発話の重なりを伴っていた。これらの比率は同じ分母ではない。

## 適用上の注意と限界

著者らの論文は文献概観と複数の既存コーパス研究の統合であり、個々の引用研究の原データや解析を独立に再検証したものではない。会話言語、課題、測定法による差を保って読む。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/conversation-timing/01-Expert|会話の時間構造の専門家]]：[整理] 会話のターン間の間は通常きわめて短いという知見を、長い無音候補を例外的な区間として人が確認する根拠にする。ただし無音の意味（同意、熟考、不参加など）は判定しない。

## 根拠の位置情報

出版社PDF p.1（Abstract）、p.6（§5.1 Distribution of Gaps）、pp.6–7（§5.2、Figure 2：NXT-Switchboard部分標本と重なりの割合）。

## 未確認事項

個々の引用研究の原データ、測定条件、再解析。訂正履歴は未確認。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-stivers-2009-turn-taking]]、[[50-Analysis-Methods/20-Literature/LIT-sacks-1974-turn-taking]]
