---
note_id: expert-japanese-text-preprocessing-limits
note_type: expert-limits
expert_id: exp-japanese-text-preprocessing
title: 日本語テキストの前処理の専門家：適用条件と限界
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 日本語テキストの前処理の専門家：適用条件と限界

## 入力データの条件

| 条件 | 満たさない場合 | 根拠 |
| --- | --- | --- |
| 正式な形態素解析 | 要確認（`pre-a1`） | [文献] GiNZAの公式ページ、[実装判断] |
| 係り受けが利用できる | 要確認（`pre-a2`） | [実装判断] |
| 解析できる発話がある | 分析を始めない（`pre-a3`） | [実装判断] |
| 口語のサンプル監査 | 研究者が確認（`pre-a4`） | [文献] 精度は書き言葉のコーパスでの評価 |

## この手法の結果から言えないこと

- 形態素境界、品詞、原形が正解であること（既存ノート [[50-Analysis-Methods/01-Text-and-Context/03-Morphology]]）。
- 依存関係から、意味役割、話者の意図、因果、談話関係（既存ノート [[50-Analysis-Methods/01-Text-and-Context/04-Syntax]]）。

## グループインタビューでの注意

- [整理] 話し言葉の逐語録には、言い淀み、言い直し、相づち、途中で切れた発話が多く、書き言葉で評価された解析器の精度が下がりうる。
- [整理] テーマ分析の解説では、言い淀みなどを取り除かずに書き起こすことが推奨されている（[[50-Analysis-Methods/20-Literature/LIT-oka-2022-reflexive-ta-ja|岡ほか 2022]]）。前処理でフィラーをストップ語にすることは、手法によっては分析の材料を減らす。質的分析の本文を変更しない。
