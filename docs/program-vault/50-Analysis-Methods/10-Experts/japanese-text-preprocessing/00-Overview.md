---
note_id: expert-japanese-text-preprocessing-overview
note_type: expert-overview
expert_id: exp-japanese-text-preprocessing
title: 日本語テキストの前処理の専門家：概要
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 日本語テキストの前処理の専門家：概要

専門家定義：[[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/01-Expert]]

## この専門家が答える問い

- 逐語録の本文を、どの解析器・辞書・分割モードで形態素（表層形、原形、正規形、読み、品詞）に分け、係り受けを解析したか。解析は正式な解析器で行われたか、簡易解析（fallback）や利用不可の状態はあるか。[実装判断] 計算の定義は既存の手法ノート [[50-Analysis-Methods/01-Text-and-Context/03-Morphology]]、[[50-Analysis-Methods/01-Text-and-Context/04-Syntax]] による。

## この専門家が答えない問い

| 問い | 移す先・理由 |
| --- | --- |
| 語の頻度や共起から何が言えるか | [[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert\|計量テキスト分析]] |
| 係り受けから意味役割や意図、因果を決める | 依存関係はそれらを直接決めない（既存ノート） |

## 形態素解析と係り受けを1人の専門家にまとめた理由

[実装判断] Gurumojiでは形態素と係り受けを同じGiNZAの解析で得て、後段の分析（語彙頻度、共起、特徴語、正規化検索）に渡す。確認すべき事項（解析器と版、簡易解析への切り替え、書き言葉のコーパスで評価された精度）が共通するため、1人の前処理の専門家にまとめた。

## 流派

| 流派 | この定義での扱い |
| --- | --- |
| GiNZA（SudachiPy、Universal Dependencies） | 既定。[文献] ライブラリと日本語UDモデルはMIT License、トークン化にSudachiPyを使う（[[50-Analysis-Methods/20-Literature/RES-ginza-official\|GiNZAの公式ページ]]） |
| SudachiPy単独 | GiNZAが使えない場合。係り受けはない |
| 正規表現による簡易分割（fallback） | 最後の手段。正式な解析と混ぜない（既存ノート） |

## 担当する実装

- `morphology`、`syntax`
