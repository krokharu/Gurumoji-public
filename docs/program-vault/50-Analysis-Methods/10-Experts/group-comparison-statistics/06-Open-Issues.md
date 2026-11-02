---
note_id: expert-group-comparison-statistics-open-issues
note_type: expert-open-issues
expert_id: exp-group-comparison-statistics
title: 群間比較の専門家：未解決事項
status: current
updated: 2026-09-28
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 群間比較の専門家：未解決事項

知識の確認日：2026-09-15。

## 知識が不足している点

- カイ二乗検定の期待度数の基準の文献（Cochran 1952、1954）、Kruskal & Wallis（1952）、Rasch et al.（2011）、Holm（1979）は書誌のみの確認。
- Delacre et al.（2017）の訂正記事（International Review of Social Psychology, 35(1), 2022）は確認済み。訂正後の追加ファイルとシミュレーションスクリプトは未確認。
- 3群以上の分散が等しくない場合の検定（Welch型の分散分析など）の方法論文献は未確認。SciPy v1.18.0の公式APIは`f_oneway(equal_var=False)`でWelch ANOVAを選べると説明するが、API記述は方法論文献の確認に代わらない。
- 実装は`stats.f_oneway(*samples)`を呼び、`equal_var`を指定していないため、SciPy v1.18.0のAPI既定では標準ANOVAを選ぶ。現在の処理でWelch ANOVAは未実装。実行環境のSciPy版は未確認。
- ANOVA入力では`None`と有限でない数値を呼出し前に除外する。SciPyの`nan_policy`指定は行っていないため、APIの既定`propagate`がこの呼出しの欠損処理を決めるわけではない。

## 実装上の課題

- Welch型の検定、多重比較の補正、入れ子を考慮したモデルは未実装（計画：[[40-Design/quantification-statistics-plan]]）。
- 期待度数の20%の目安は実装上の判断。
