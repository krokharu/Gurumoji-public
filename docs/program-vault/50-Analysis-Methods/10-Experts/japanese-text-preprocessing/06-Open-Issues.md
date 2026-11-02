---
note_id: expert-japanese-text-preprocessing-open-issues
note_type: expert-open-issues
expert_id: exp-japanese-text-preprocessing
title: 日本語テキストの前処理の専門家：未解決事項
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 日本語テキストの前処理の専門家：未解決事項

知識の確認日：2026-09-15。

## 知識が不足している点

- 話し言葉の逐語録での形態素解析・係り受け解析の精度を扱った文献を確認していない。
- Matsuda（2020）、Takaoka et al.（2018）、Kudo et al.（2004）、Omura & Asahara（2018）、Nivre et al.（2020）は書誌のみの確認。

## 実装上の課題

- Gurumojiが実際に読み込むGiNZAのモデル（`ja_ginza` か `ja_ginza_electra` か）を、この定義では確認していない。
- 口語向けの辞書やストップ語の既定値はない。
