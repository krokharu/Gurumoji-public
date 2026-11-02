---
note_id: expert-quantitative-text-analysis-overview
note_type: expert-overview
expert_id: exp-quantitative-text-analysis
title: 計量テキスト分析の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 計量テキスト分析の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert]]

## この専門家が答える問い

- 語の頻度・共起・特徴語から、データの全体像をつかみ、人間が詳しく読むべき箇所を探したい（データ探索）。[文献] [[50-Analysis-Methods/20-Literature/LIT-higuchi-2017-khcoder|樋口 2017]]
- 明確に区別できる比較の枠組みで、語の使われ方の違いを見て、原文に戻って解釈したい。[文献] 樋口 2017
- 理論や問題意識を、語によるコーディングの規則で操作化し、その規則を公開したい。[文献] [[50-Analysis-Methods/20-Literature/LIT-higuchi-2004-quantitative-text|樋口 2004]]

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 意見の意味を解釈的にまとめたい | [[50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert\|テーマ分析]]、[[50-Analysis-Methods/10-Experts/qualitative-content-analysis/01-Expert\|質的内容分析]] |
| 語の頻度から意見の重要性や支持人数を知りたい | 頻度はそれらの指標ではない |
| 形態素解析の精度そのもの | [[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/01-Expert\|日本語テキストの前処理]] |
| 群の差の統計的検定 | [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert\|群間比較]] |

## 流派

[文献] 従来の分析は、多変量解析で主題を探索するCorrelationalアプローチか、分析者の基準で分類するDictionary-basedアプローチのいずれかが多く、樋口（2004）は両者を区別して併用する方法を示す。

| 流派 | この定義での扱い |
| --- | --- |
| 両アプローチの併用と原文への往復（樋口） | 既定 |
| Correlationalアプローチだけ（探索のみ） | 流派として記録 |
| Dictionary-basedアプローチだけ（規則による分類） | 流派として記録。Gurumojiには規則による自動コーディングの機能がない |

## 担当する実装

- [[50-Analysis-Methods/01-Text-and-Context/05-Lexical-Frequency]]、[[50-Analysis-Methods/01-Text-and-Context/06-Cooccurrence]]、[[50-Analysis-Methods/01-Text-and-Context/02-Speaker-Characteristics]]、[[50-Analysis-Methods/01-Text-and-Context/07-KWIC]]
- [実装判断] これらはKH Coderの考え方を参照した独自実装で、KH Coderの出力ではない（[[50-Analysis-Methods/20-Literature/RES-khcoder-official]]）。
