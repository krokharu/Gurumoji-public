---
note_id: lit-park-2022-diarization-review
note_type: literature
literature_id: LIT-park-2022-diarization-review
title: "A review of speaker diarization: Recent advances with deep learning"
authors:
  - Tae Jin Park
  - Naoyuki Kanda
  - Dimitrios Dimitriadis
  - Kyu J. Han
  - Shinji Watanabe
  - Shrikanth Narayanan
year: 2022
venue: "Computer Speech & Language, 72, 101317"
source_type: review_article
peer_review: confirmed
peer_review_basis: "Elsevierの投稿案内で査読手続きの記載を確認（2026-09-15、現在の方針）。"
doi: 10.1016/j.csl.2021.101317
url: https://doi.org/10.1016/j.csl.2021.101317
accessed: 2026-09-15
access_scope: full_text
access_detail: "arXiv版（arXiv:2101.09624）のPDFを取得し、テキスト抽出で読んだ。掲載版との同一性は確認していない。書誌はCrossref APIで確認した（72巻、2022年3月）。位置はarXiv版の節番号と頁。"
correction_status: none_found
related_experts:
  - exp-conversation-timing
  - exp-participation-balance
  - exp-focus-group-interaction
  - exp-speech-emotion-recognition
status: current
updated: 2026-09-16
tags:
  - gurumoji/literature
  - gurumoji/audio
---

# Park et al.（2022）：話者分離の総説

## 研究目的

「誰がいつ話したか」を推定する話者分離（speaker diarization）について、技術の歴史的な発展と、深層学習による最近の手法を概観する（要旨）。

## 対象データと研究条件

文献の概観であり、特定のデータの分析ではない。

## 分析手順の要約

話者分離の評価指標として、話者分離誤り率（DER）を、音声の誤検出（false alarm）、音声の検出漏れ、話者ラベルの取り違えの3つの誤りの合計を総時間で割ったものとして説明する。仮説と正解の対応付けにはハンガリアン法を使い、2006年のRT評価では0.25秒の採点除外の幅（collar）が設定されたとする（1.4.1節、arXiv版p.3）。

## 主要な知見

- 深層学習の登場で、話者分離は急速に進歩したとする（要旨）。
- 発話の重なりが大きい区間では、音声分離の技術が有望だとする（2.1.3節、arXiv版p.5）。

## 適用上の注意と限界

- arXiv版を読んだため、掲載版での修正は確認していない。
- 総説であり、Gurumojiが使う話者分離モデルの日本語会話での性能を示すものではない。

## 専門家の判断・手順に反映する内容

- [[50-Analysis-Methods/10-Experts/conversation-timing/01-Expert|会話の時間構造の専門家]]、[[50-Analysis-Methods/10-Experts/participation-balance/01-Expert|参加バランスの専門家]]：話者ラベルの誤り（取り違え、重なり区間）が、話者遷移、重なり候補、発話量の集計に直接影響する。話者の確認が済んでいない場合は警告する。
- [[50-Analysis-Methods/10-Experts/focus-group-interaction/01-Expert|フォーカスグループの相互作用分析の専門家]]：応答関係の解釈の前に、話者と順序の確認を適用条件にする。
- [[50-Analysis-Methods/10-Experts/speech-emotion-recognition/01-Expert|音声感情推定の専門家]]：発話の切り出しが話者分離に依存することを限界に含める。
- [[50-Analysis-Methods/08-Common-Knowledge/03-Group-Interview-Data|共通知識]] に反映した。

## 根拠の位置情報

arXiv版。DERの定義と評価条件：1.4.1節（p.3）。重なりと音声分離：2.1.3節（p.5）。

## 未確認事項

掲載版との差分、各手法の性能表の詳細。

## 関連ノート

[[50-Analysis-Methods/20-Literature/LIT-stivers-2009-turn-taking]]
