---
note_id: expert-quantitative-text-analysis-quality
note_type: expert-quality
expert_id: exp-quantitative-text-analysis
title: 計量テキスト分析の専門家：判断基準と品質確認
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 計量テキスト分析の専門家：判断基準と品質確認

## 判断基準

- [文献] 誰が操作しても同じ結果になる図表を示すことで、第三者による比較・検証がしやすくなり、批判・検証に耐えるオープンさという意味での客観性が高まる（樋口 2017、2.1節、樋口 2004、p.104）。
- [文献] 自動的な方法は注意深い思考と精読の代わりにならず、問題ごとの検証が必要（Grimmer & Stewart 2013、要旨）。
- [文献] 特徴語を選ぶ統計的方法には検討と批判があり、Kilgarriff（2001、要旨）はMann-Whitneyの順位検定を提案する。

## アプリが判定する項目と人が確認する項目

| ID | 内容 | 判定 |
| --- | --- | --- |
| qta-q1 | 正式な解析器で解析されたか | コード（`morphology_engine_ready`） |
| qta-q2 | 語の選択としきい値の明示 | 研究者 |
| qta-q3 | 原文での確認 | 研究者 |
| qta-q4 | 多数の比較の探索的な扱い | 研究者（[文献] Benjamini & Hochberg 1995：多重検定では偽の発見の割合が問題になる） |
| qta-q5 | 出現率の差を検定結果としないこと | 研究者 |

## ほかの手法との違い

[整理] 要約的な質的内容分析も語を数えるが、数えた後に文脈を解釈する質的内容分析の一形態として位置づけられている（Hsieh & Shannon 2005、要旨）。計量テキスト分析は、計量的分析と質的な解釈を循環させる方法として位置づけられる（樋口 2017）。どちらの枠組みで報告するかを分析設定に記録する。
