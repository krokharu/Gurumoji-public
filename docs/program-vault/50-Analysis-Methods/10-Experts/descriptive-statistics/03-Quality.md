---
note_id: expert-descriptive-statistics-quality
note_type: expert-quality
expert_id: exp-descriptive-statistics
title: 記述統計の専門家：判断基準と品質確認
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 記述統計の専門家：判断基準と品質確認

## 判断基準

- [実装判断] 要約値の根拠は、対象集合と表の行キーで示す。極端な発話を引用する場合は、その発話IDも付ける（[[40-Design/method-rules]] の根拠の規則）。
- [文献] 入れ子になったデータでは、観測の依存を無視した推測が誤りやすい（Aarts et al. 2014、要旨）。記述統計は推測ではないが、比較群の値を個人差や母集団の推定として読まない（[整理]）。

## アプリが判定する項目と人が確認する項目

| ID | 内容 | 判定 |
| --- | --- | --- |
| desc-q1 | 形態素に基づく変数が正式な解析によるか | コード（`morphology_engine_ready`） |
| desc-q2 | N・欠測・除外・分母の明示 | 研究者 |
| desc-q3 | 中央値と四分位の提示 | 研究者 |
| desc-q4 | 入れ子の限界の記載 | 研究者 |
