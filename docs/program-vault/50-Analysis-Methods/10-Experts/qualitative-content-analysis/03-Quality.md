---
note_id: expert-qualitative-content-analysis-quality
note_type: expert-quality
expert_id: exp-qualitative-content-analysis
title: 質的内容分析の専門家：判断基準と品質確認
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# 質的内容分析の専門家：判断基準と品質確認

## 流派ごとの判断基準

| 観点 | 帰納的カテゴリー形成 | 演繹的カテゴリー適用 | 要約的アプローチ |
| --- | --- | --- | --- |
| カテゴリーの妥当性 | 定義の基準に沿って素材の近くで作られ、フィードバックで見直されたか（[文献] Mayring 2000） | 理論から導いた定義・典型例・規則があるか（[文献] Mayring 2000） | 数えた後に文脈を解釈したか（[文献] Hsieh & Shannon 2005、要旨） |
| 一致の確認 | 主カテゴリーにまとめた後に信頼性を確認する（[文献] Mayring 2000、para 12） | コーダー間の一致を確認する。κ .7超を十分とする記述がある（[文献] Mayring 2000、para 7） | 本調査では確認していない |
| 信用性 | 準備・組織化・報告の各段階で精査する（[文献] Elo et al. 2014、要旨）。credibility・dependability・transferabilityの方策（[文献] Graneheim & Lundman 2004、要旨） | 同左 | 同左 |

[整理] 一致の確認はこの手法の流派では手順の一部だが、再帰的テーマ分析では品質の条件にしない（[[50-Analysis-Methods/10-Experts/thematic-analysis/03-Quality]]）。手法をまたいで同じ基準を当てはめない。

## アプリが判定する項目と人が確認する項目

| ID | 内容 | 判定 |
| --- | --- | --- |
| qca-q1 | カテゴリーがコードブックに定義されているか | コード（`codebook_min_codes`） |
| qca-q2 | すべてのカテゴリーに定義があるか | コード（`codebook_definitions_complete`） |
| qca-q3 | カテゴリーが発話に割り当てられているか | コード（`coded_segments_min`） |
| qca-q4 | コードの出所の記録 | 研究者 |
| qca-q5 | 複数コーダーの確認の記録 | 研究者（アプリは係数を計算しない） |
| qca-q6 | 段階ごとの信用性の記述 | 研究者 |
| qca-q7 | 反例・少数意見・未分類の発話の検討 | 研究者 |

「研究者」の項目は、アプリが確認済みと表示しない（[[50-Analysis-Methods/08-Common-Knowledge/01-Evidence-and-Claims]]）。

## 文献間で意見が分かれる点

- [整理] 信頼性の確認を係数で行うか、手順の記述で信用性を示すか。Mayring（2000）はコーダー間の一致を基準に含め、Elo et al.（2014）とGraneheim & Lundman（2004）は信用性の概念で段階ごとの精査を論じる（いずれも確認範囲の範囲で）。Gurumojiでは、研究者が採用した方法を記録させ、どちらかを強制しない（[実装判断]）。
