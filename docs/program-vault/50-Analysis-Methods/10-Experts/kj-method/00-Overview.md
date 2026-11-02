---
note_id: expert-kj-method-overview
note_type: expert-overview
expert_id: exp-kj-method
title: KJ法の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# KJ法の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/kj-method/01-Expert]]

## この専門家が答える問い

- 雑多な意見や観察を、1つのメッセージを持つラベルにし、事前のカテゴリーを想定せずにボトムアップでまとめ、図解と文章で構造を示したい。[文献] [[50-Analysis-Methods/20-Literature/LIT-tanaka-kj-quick-manual|田中のKJ法クイックマニュアル]]
- 図解化と言語化で提示し、他者への説明と評価（衆目評価）で合意を形成したい。[文献] [[50-Analysis-Methods/20-Literature/LIT-kawakita-2003-kj-interview|川喜田ほか 2003]]

## この専門家が答えない問い

| 問い | 移す先 |
| --- | --- |
| 事前に定めたカテゴリーに当てはめる分類 | [[50-Analysis-Methods/10-Experts/qualitative-content-analysis/01-Expert\|質的内容分析]]（演繹的カテゴリー適用） |
| 意味の近い発話の自動的なまとまり | [[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert\|埋め込みによるテーマ探索]]（KJ法の代替ではない） |
| 概念的なカテゴリーによる理論の構成 | [[50-Analysis-Methods/10-Experts/m-gta/01-Expert\|M-GTA]] |

## 流派・版

[文献] KJ法にはいくつかの流派やバージョンがあり、田中のマニュアルは川喜田（1997）の1997年版に基づく（田中、p.102）。聞き手のやまだようこは、グラウンデッド理論が概念的カテゴリーを礎石に理論を構成するのに対し、KJ法はばらばらにしたカードの意味的なエッセンスから組み立てる点で異なると解説する（川喜田ほか 2003、p.26）。

| 版 | この定義での扱い |
| --- | --- |
| 1997年版に基づく田中のクイックマニュアル | 既定（本文確認） |
| 川喜田 1967『発想法』、1986『KJ法』 | 原典未確認 |

## 関連する実装

- [実装判断] Gurumojiにはラベル、グループ編成、図解を記録する機能はない。発話IDをラベルの通し番号に対応させ、作業は研究者が行う。KJ法を主手法に選んだ場合、AI見解は生成しない（実行定義の `ai_assist`）。
