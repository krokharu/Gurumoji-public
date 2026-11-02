---
note_id: expert-descriptive-statistics-limits
note_type: expert-limits
expert_id: exp-descriptive-statistics
title: 記述統計の専門家：適用条件と限界
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 記述統計の専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| 集計できる発話がある | 分析を始めない（`desc-a1`） | [実装判断] |
| 正式な形態素解析 | 要確認（`desc-a2`） | [実装判断] |
| 有効な時刻が90%以上 | 要確認（`desc-a3`） | [実装判断] |
| 入れ子の限界の理解 | 研究者が確認（`desc-a4`） | [文献] Aarts et al. 2014 |

## この手法の結果から言えないこと

- 記述量から、影響力、関与の質、理解度、会話の成功（既存ノート [[50-Analysis-Methods/03-Statistics/01-Descriptive-Statistics]]）。
- 比較群の数値の違いの原因（[整理]）。

## グループインタビューでの注意

- [整理] 司会者の発話を含めるかで、発話時間や質問候補の度数が大きく変わる。比較軸を役割にする場合は、役割の登録を確認する。
- [整理] 話者分離の誤りは話者別の記述統計に直接影響する（[[50-Analysis-Methods/20-Literature/LIT-park-2022-diarization-review|Park et al. 2022]]）。
