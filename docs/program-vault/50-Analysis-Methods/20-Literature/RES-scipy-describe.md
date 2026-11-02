---
note_id: res-scipy-describe
note_type: literature
literature_id: RES-scipy-describe
title: "SciPy v1.18.0 stats.describe API reference"
authors:
  - SciPy community
year: 2026
venue: "SciPy v1.18.0 Manual"
source_type: official_resource
peer_review: not_peer_reviewed
peer_review_basis: "統計ライブラリの公式APIマニュアルで、学術誌査読論文ではない。"
doi: ""
url: https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.describe.html
accessed: 2026-09-28
access_scope: official_page
access_detail: "SciPy v1.18.0 Manualのdescribe関数ページを取得し、引数と戻り値の定義を抽出。"
document_version: "scipy-v1.18.0-manual-describe-retrieved-2026-09-28"
document_sha256: 66566c9dfdc18383000a0badfd29d550f8073edfd85c2686f8162d299e84960a
license_id: BSD-3-Clause
license_url: https://opensource.org/license/bsd-3-clause
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex GPT-6 (read-only)"
rights_reviewed_at: 2026-09-28T02:42:13Z
rights_review_basis: >-
  SciPy's v1.18.0 developer guide states that code, documentation, and other
  contributor-added files are under its modified three-clause BSD license unless
  otherwise specified. Colab processing is limited to this public API documentation
  using our own model; export is limited to attributed, source-linked paraphrased
  claims. The project's remote_llm route remains disallowed.
correction_status: not_checked
related_experts:
  - exp-descriptive-statistics
status: current
updated: 2026-09-28
tags:
  - gurumoji/literature
  - gurumoji/statistics
---

# SciPy `stats.describe` 公式APIリファレンス

## 資料の目的

SciPyの`describe`関数が配列から返す基本的な記述統計と、その計算オプションを定義する。

## 主要な知見

- 戻り値は観測数、最小・最大、平均、分散、歪度、Fisherの尖度。
- 既定では分散の自由度補正`ddof=1`、歪度・尖度の補正なし、欠損値は伝播する。
- 欠損値の処理は伝播・エラー・除外から選べる。`nan_policy='omit'`では、観測数を軸スライスごとに別々に数える。`ddof`は分散のみに適用される。
- 集計軸は既定で`axis=0`。`axis=None`なら入力配列全体を対象に計算する。
- `bias=True`が既定で、`bias=False`にすると歪度と尖度に統計的バイアス補正を適用する。`bias`は分散用の`ddof`とは別の引数である。

## 適用上の注意と限界

統計量の名称と設定を報告するときは、APIの既定値を明示する。平均だけで分布を代表させず、データ型・欠損・分布形状に応じて必要な統計量を選ぶ。

## 根拠の位置情報

SciPy v1.18.0 Manual「describe」ParametersとReturns。

## 未確認事項

Gurumojiの実装におけるSciPy使用版、各画面で設定している`ddof`、歪度・尖度の表示有無。
