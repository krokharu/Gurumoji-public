---
note_id: expert-descriptive-statistics-procedure
note_type: expert-procedure
expert_id: exp-descriptive-statistics
title: 記述統計の専門家：手順
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 記述統計の専門家：手順

計算の定義は既存の手法ノート [[50-Analysis-Methods/03-Statistics/01-Descriptive-Statistics]]（`descriptive_statistics`）による（[実装判断]）。

## 手順と各段階の確認事項

| 段階 | 内容 | 担当 | 確認事項 |
| --- | --- | --- | --- |
| desc-p1 | 対象・比較軸・欠測 | 研究者 | 比較軸（`statistics_group_by`：話者または役割）、分母、除外規則、0秒発話・形態素未取得などの欠測 |
| desc-p2 | 計算 | コード | 変数ごとにN、欠測、平均、標準偏差、中央値、最小、Q1、Q3、最大。話者・役割・質問候補の度数と割合 |
| desc-p3 | 分布の確認 | 研究者 | 発話時間や文字数は歪みやすい。極端な発話を発話IDで開いて確認する |
| desc-p4 | 報告 | 研究者 | 分析を探索的な記述として報告する（[文献] Appelbaum et al. 2018の区分、要旨） |

## 判断に迷いやすい点

- [実装判断] `characters_per_minute` は文字起こしの本文と時刻から計算した値で、音響的な発話速度ではない。
- [整理] 比較群の発話数が大きく違う場合、平均の違いは少数の長い発話に左右される。中央値と四分位を合わせて読む。

## 典型的な失敗と修正

| 失敗 | 修正 |
| --- | --- |
| 平均だけを示す | 中央値・四分位・N・欠測を合わせて示す |
| 形態素数を簡易解析のまま比べる | 解析器の状態を確認し、条件を示す |
| 平均の違いを話者の特性として述べる | 記述にとどめ、入れ子の限界を書く |

## 結果のまとめ方

対象・比較軸・欠測の条件 → 記述統計の表 → 度数の表 → 分布の確認 → 限界。
