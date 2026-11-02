---
note_id: expert-japanese-text-preprocessing-procedure
note_type: expert-procedure
expert_id: exp-japanese-text-preprocessing
title: 日本語テキストの前処理の専門家：手順
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 日本語テキストの前処理の専門家：手順

計算の定義は既存の手法ノート [[50-Analysis-Methods/01-Text-and-Context/03-Morphology]]、[[50-Analysis-Methods/01-Text-and-Context/04-Syntax]] による（[実装判断]）。

## 手順と各段階の確認事項

| 段階 | 内容 | 担当 | 確認事項 |
| --- | --- | --- | --- |
| pre-p1 | 条件の固定 | コード | エンジン名・版・分割モード（`morph_split_mode`、既定C）・辞書・ストップ語を結果と一緒に保存する。[文献] GiNZAはSudachiPyでトークン化する（公式ページ） |
| pre-p2 | 解析と保存 | コード | GiNZAが使えれば、表層形、lemma、正規形、読み、UPOS、詳細品詞、活用、文字位置を保存し、係り受けは発話ID、文ID、語、依存関係ラベル、係り先を保存する |
| pre-p3 | 状態の伝達 | コード | GiNZAが使えなければSudachiPy単独、さらに不可能なら正規表現の簡易分割に切り替え、`fallback` とする。係り受けは `unavailable` とし、SudachiPyや正規表現から係り受けを作らない |
| pre-p4 | サンプル監査 | 研究者 | 固有名詞、口語、フィラー、誤変換、専門語をサンプルで確認し、必要ならストップ語・辞書を明示的に追加する |

## 判断に迷いやすい点

- [整理] 日本語のUDの語の単位は、利用者が読む文節や発話の単位と異なる（既存ノート）。係り受けを集計するときは、解析の行と原文を並べて確認する。
- [整理] 音声認識の句読点の付け方で文の区切りが変わり、係り受けの精度に影響する。

## 典型的な失敗と修正

| 失敗 | 修正 |
| --- | --- |
| 簡易解析の結果と正式な解析の結果を混ぜて比べる | 解析器の状態をそろえてから比べる |
| 係り受けが利用できないのに空の結果を「係り受けなし」と報告する | `unavailable` として報告する |
| ストップ語を結果を見ながら暗黙に変える | 変更を設定として記録し、版を分ける |

## 結果のまとめ方

解析器と条件 → 形態素・品詞の分布 → 係り受けの結果（利用可否） → 監査 → 限界。
