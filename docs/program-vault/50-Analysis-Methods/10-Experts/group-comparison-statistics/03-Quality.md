---
note_id: expert-group-comparison-statistics-quality
note_type: expert-quality
expert_id: exp-group-comparison-statistics
title: 群間比較の専門家：判断基準と品質確認
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 群間比較の専門家：判断基準と品質確認

## 判断基準

- [文献] 入れ子のデザインのデータは独立とみなせず、依存を無視すると誤って有意と結論する確率が名目の水準より大きく（最大80%）なりうる（Aarts et al. 2014、要旨）。
- [文献] 偽発見率（FDR）は、すべての帰無仮説が真であれば族単位の誤り率と等しく、そうでなければ小さい。証明は独立な検定統計量の場合（Benjamini & Hochberg 1995、要旨）。
- [文献] Welchのt検定は、分散が等しくない場合に第1種の誤りを制御しやすく、前提が満たされる場合も頑健性をほとんど失わない（Delacre et al. 2017、2群の場合）。
- [実装判断] 期待度数5未満のセルが20%を超える表には注意を付ける。20%は文献の基準として確認していない（Cochranの文献は書誌のみ）。

## アプリが判定する項目と人が確認する項目

| ID | 内容 | 判定 |
| --- | --- | --- |
| grp-q1 | 期待度数5未満のセルの割合 | コード（`chi_square_expected_cells`） |
| grp-q2 | 効果量・N・群数・仮定の注記 | 研究者 |
| grp-q3 | 群の大きさ・分散の違いへの注意 | 研究者 |
| grp-q4 | 多重比較の補正がないことの明示 | 研究者 |
