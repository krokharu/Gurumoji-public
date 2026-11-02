---
note_id: expert-japanese-text-preprocessing-quality
note_type: expert-quality
expert_id: exp-japanese-text-preprocessing
title: 日本語テキストの前処理の専門家：判断基準と品質確認
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 日本語テキストの前処理の専門家：判断基準と品質確認

## 判断基準

- [文献] GiNZAの精度表は、UD_Japanese-BCCWJ r2.8のテストセットで、`ja_ginza_electra` がLAS 92.3、UAS 93.7、UPOS 98.1などと示されている（公式ページ）。BCCWJは書き言葉のコーパス（Omura & Asahara 2018の題名）であり、話し言葉の逐語録の精度は別に確認する必要がある（[整理]）。
- [実装判断] 簡易解析（`fallback`）と利用不可（`unavailable`）は、通常の完了結果と混ぜない（[[50-Analysis-Methods/00-Orchestrator-Common-Contract]]）。

## アプリが判定する項目と人が確認する項目

| ID | 内容 | 判定 |
| --- | --- | --- |
| pre-q1 | 正式な解析器か | コード（`morphology_engine_ready`） |
| pre-q2 | 係り受けが利用できたか | コード（`syntax_available`） |
| pre-q3 | 条件の記録 | 研究者 |
| pre-q4 | サンプル監査 | 研究者 |
