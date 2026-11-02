---
note_id: expert-group-comparison-statistics-procedure
note_type: expert-procedure
expert_id: exp-group-comparison-statistics
title: 群間比較の専門家：手順
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 群間比較の専門家：手順

計算の定義は既存の手法ノート [[50-Analysis-Methods/03-Statistics/02-Group-Statistics]]（`group_statistics`）による（[実装判断]）。

## 手順と各段階の確認事項

| 段階 | 内容 | 担当 | 確認事項 |
| --- | --- | --- | --- |
| grp-p1 | 目的・群・変数 | 研究者 | 比較軸（`statistics_group_by`）、選択語（`crosstab_terms`）、コードブック、発話の除外。後からコード定義を変えた結果を混ぜない |
| grp-p2 | 計算 | コード | 比較軸×質問候補、比較軸×手動コード（上位50）、比較軸×選択語（上位30）のクロス集計。Pearsonのカイ二乗検定（Cramér's V、期待度数5未満のセル数）、一元配置分散分析（η²。現在は`stats.f_oneway(*samples)`を呼び、SciPy v1.18.0の既定`equal_var=True`では標準ANOVA）、Kruskal–Wallis検定（ε²） |
| grp-p3 | 前提の確認 | 研究者 | 期待度数の小さいセルの割合、群の大きさの違い。[文献] 2群のt検定について、分散が等しくない場合に第1種の誤りを制御しやすいWelchのt検定を既定にすべきとし、前提を検定してから検定を選ぶ二段階の手順の限界を論じる文献がある（Delacre et al. 2017） |
| grp-p4 | 探索的な報告 | 研究者 | [文献] 入れ子の依存を無視すると誤りの確率が高くなりうる（Aarts et al. 2014、要旨）。多重検定では偽の発見を考える（Benjamini & Hochberg 1995、要旨）。分析を探索的と区分して報告する（Appelbaum et al. 2018、要旨） |

## 判断に迷いやすい点

- [整理] Delacre et al.（2017）は2群のt検定を扱う論文で、Gurumojiの一元配置分散分析（3群以上を含む）に直接当てはまる結論ではない。群の大きさや分散の違いへの注意の根拠として使う。
- 現在の`f_oneway`呼出しは`equal_var=False`を指定せず、Welch ANOVAを選択しない。`None`と有限でない数値は呼出し前に群ごとに除外し、SciPyの`nan_policy`引数には委ねない（実装：`src/gurumoji/research_analysis.py`）。
- [文献] カテゴリカルな結果変数に分散分析を使うと、変換しても誤った結果になりうるとされる（Jaeger 2008、要旨）。コードの有無のようなカテゴリカルな変数はクロス集計とカイ二乗検定で扱い、話者の繰り返しは限界に書く（[整理]）。

## 典型的な失敗と修正

| 失敗 | 修正 |
| --- | --- |
| 多数のコード・語の検定から有意なものだけを報告する | 実施した検定の全体と、補正していないことを示す |
| 期待度数の小さい表のp値をそのまま解釈する | セルの割合を示し、探索的な値として扱う |
| 発話単位の有意差から話者や属性の一般的な違いを述べる | 1回の会話の中の探索的な記述にとどめる |

## 結果のまとめ方

比較の目的と群の定義 → クロス集計 → 検定の表 → 前提の確認 → 探索的扱いと限界。
