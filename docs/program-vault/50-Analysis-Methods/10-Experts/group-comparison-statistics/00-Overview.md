---
note_id: expert-group-comparison-statistics-overview
note_type: expert-overview
expert_id: exp-group-comparison-statistics
title: 群間比較の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 群間比較の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert]]

## この専門家が答える問い

- 比較軸（話者・役割）と、質問候補・手動コード・選択した語のクロス集計はどうなっているか（行・列・全体の百分率）。
- 探索的な検定（Pearsonのカイ二乗検定とCramér's V、一元配置分散分析とη²、Kruskal–Wallis検定とε²）で、群の違いはどの程度か。[実装判断] 計算の定義は既存の手法ノート [[50-Analysis-Methods/03-Statistics/02-Group-Statistics]] による。

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 変数どうしの関連 | [[50-Analysis-Methods/10-Experts/correlation/01-Expert\|相関]] |
| 複数回の会話の比較 | [[50-Analysis-Methods/10-Experts/cross-session-comparison/01-Expert\|会話間比較]] |
| 参加者や会話の母集団への一般化 | 発話は独立な標本ではない（[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data\|Aarts et al. 2014]]、要旨） |
| 有意差からの因果や実質的な重要性 | 検定はそれらを示さない（既存ノート） |

## 流派

| 流派 | この定義での扱い |
| --- | --- |
| 発話単位の探索的な検定（既定） | 実装済み。結果は探索的に扱う |
| 入れ子を考慮したモデル（混合ロジットモデルなど） | 未実装。カテゴリカルなデータと変量効果の扱いの文献（[[50-Analysis-Methods/20-Literature/LIT-jaeger-2008-logit-mixed\|Jaeger 2008]]、要旨）を限界の根拠にする |

## 担当する実装

- `group_statistics`（[[50-Analysis-Methods/03-Statistics/02-Group-Statistics]]）
- 検定の拡張の計画：[[40-Design/quantification-statistics-plan]]（計画であり実装済みではない）
