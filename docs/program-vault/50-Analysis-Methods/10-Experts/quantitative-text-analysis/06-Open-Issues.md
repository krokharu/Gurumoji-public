---
note_id: expert-quantitative-text-analysis-open-issues
note_type: expert-open-issues
expert_id: exp-quantitative-text-analysis
title: 計量テキスト分析の専門家：未解決事項
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 計量テキスト分析の専門家：未解決事項

知識の確認日：2026-09-15。

## 知識が不足している点

- 樋口の書籍（2014『社会調査のための計量テキスト分析』）を読んでいない。
- Salton & Buckley（1988）、Callon et al.（1983）は書誌のみの確認で、TF–IDFや共語分析の定義の根拠にしていない。
- 特徴語の検定の方法（Kilgarriff 2001）の詳細は要旨の範囲。

## 文献間で意見が分かれる点

- 特徴語をどの統計量で選ぶか（Kilgarriff 2001が既存の方法を批判的に検討）。Gurumojiは出現率の差を記述するだけで、検定は行わない。

## 実装上の課題

- 辞書・コーディング規則による自動コーディングの機能がない（Dictionary-basedアプローチの段階は研究者のコードで代用）。
- 話者別特徴語の検定は未実装。
- 20発話という目安は実装上の判断。
