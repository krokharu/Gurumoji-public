---
note_id: expert-qualitative-content-analysis-open-issues
note_type: expert-open-issues
expert_id: exp-qualitative-content-analysis
title: 質的内容分析の専門家：未解決事項
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# 質的内容分析の専門家：未解決事項

知識の確認日：2026-09-15。実行定義の `open_issues` と同じ内容を、背景とともに記録する。

## 知識が不足している点

- 質的内容分析の日本語の方法論文献を、今回の検索では見つけていない。
- Mayring（2000）の手順図（Fig.1, 2）は画像のため読めておらず、本文が参照するドイツ語の教科書も読んでいない。
- Hsieh & Shannon（2005）、Elo & Kyngäs（2008）、Elo et al.（2014）、Graneheim & Lundman（2004）は要旨だけを確認した。各段階の具体的な作業、チェックリストの項目は未確認。
- 一致係数の選び方（κ、α）の文献（[[50-Analysis-Methods/20-Literature/LIT-krippendorff-2004-reliability|Krippendorff 2004]]、[[50-Analysis-Methods/20-Literature/LIT-hayes-krippendorff-2007-alpha|Hayes & Krippendorff 2007]]）は書誌のみ。

## 文献間で意見が分かれる点

- 信頼性を係数で確認するか、段階ごとの信用性の記述で示すか（[[50-Analysis-Methods/10-Experts/qualitative-content-analysis/03-Quality]]）。

## 実装上の課題

- Gurumojiの分析単位は発話（`turn`）に固定され、意味単位の設定を支援していない。
- コードブックにコーディング規則専用の欄がない。
- コーダー間の一致の記録・計算の機能はない。
