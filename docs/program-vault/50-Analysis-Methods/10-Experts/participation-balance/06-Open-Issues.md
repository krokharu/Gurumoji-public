---
note_id: expert-participation-balance-open-issues
note_type: expert-open-issues
expert_id: exp-participation-balance
title: 参加バランスの専門家：未解決事項
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/conversation
---

# 参加バランスの専門家：未解決事項

知識の確認日：2026-09-15。

## 知識が不足している点

- Gini係数、evenness、HHIを会話の参加の偏りに使うことの妥当性を検討した文献を確認していない。
- Poliandri et al.（2023）はオンライン討議1事業の指標例を報告するが、発話回数や60分換算の一般的な判定基準を示してはいない。
- Stephan & Mishler（1952）は書誌のみの確認。
- Woolley et al.（2010）の測定方法と、その後の追試・批判の有無を確認していない。

## 実装上の課題

- 10%（不明な話者）、90%（有効な時刻）の目安は実装上の判断。
- 相づちと内容のある発言を分けた集計は、参加バランスの集計にはない（Transformerテーマ分析の相づち候補は別の手法）。
