---
note_id: expert-embedding-topic-exploration-open-issues
note_type: expert-open-issues
expert_id: exp-embedding-topic-exploration
title: 埋め込みによるテーマ探索の専門家：未解決事項
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/semantic
---

# 埋め込みによるテーマ探索の専門家：未解決事項

知識の確認日：2026-09-15。

## 知識が不足している点

- multilingual-e5の技術報告（Wang et al. 2024）はプレプリントで、日本語の会話の逐語録での評価を確認していない。
- トピックの人による解釈を扱ったChang et al.（2009）の内容を読んでいない（書誌のみ）。
- Lloyd（1982）は書誌のみの確認。
- 相づちの検出と応答先の推定の妥当性を扱った文献を確認していない。

## 実装上の課題

- シルエット係数0.1、発話20件の目安は実装上の判断。
- 手動割り当てのしきい値と、上位2テーマの差が小さい境界例の目安は実装上の判断で、人手の検証をしていない。
- クラスタの併合・分割・除外の研究者の判断を記録する専用の欄はない。手動モードのテーマ定義（見出し・手がかり語・シード発話）は分析設定に保存できるが、自動・候補モードの併合・分割の記録には使えない。
