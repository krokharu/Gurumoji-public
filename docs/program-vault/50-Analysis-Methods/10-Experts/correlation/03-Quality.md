---
note_id: expert-correlation-quality
note_type: expert-quality
expert_id: exp-correlation
title: 相関の専門家：判断基準と品質確認
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 相関の専門家：判断基準と品質確認

## 判断基準

- [文献] 非正規データでは、Pearsonのrの有意性の検定の誤りが大きくなりうる（Bishara & Hittner 2012、要旨）。
- [文献] 多数の検定を行う場合は、偽の発見を考慮する必要がある（Benjamini & Hochberg 1995、要旨）。
- [文献] 入れ子のデータの依存を無視した推測は誤りやすい（Aarts et al. 2014、要旨）。

## アプリが判定する項目と人が確認する項目

相関の品質項目はすべて研究者が確認する（`cor-q1`〜`cor-q3`）。適用条件では、SciPyの利用、発話数の目安（10件）、形態素解析の状態をコードで判定する（[実装判断]）。
