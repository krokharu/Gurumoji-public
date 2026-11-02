---
note_id: res-scipy-pearsonr
note_type: literature
literature_id: RES-scipy-pearsonr
title: "SciPy v1.18.0 stats.pearsonr API reference"
authors:
  - SciPy community
year: 2026
venue: "SciPy v1.18.0 Manual"
source_type: official_resource
peer_review: not_peer_reviewed
peer_review_basis: "統計ライブラリの公式APIマニュアルで、学術誌査読論文ではない。"
doi: ""
url: https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.pearsonr.html
accessed: 2026-09-28
access_scope: official_page
access_detail: "SciPy v1.18.0 Manualのpearsonr関数ページを取得し、関数説明とNotesを抽出。"
document_version: "scipy-v1.18.0-manual-pearsonr-retrieved-2026-09-28"
document_sha256: 9999856b875cf15abcad22654b16bd3d2801f89eef28b42a048114e93eac68c3
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
  - exp-correlation
status: current
updated: 2026-09-28
tags:
  - gurumoji/literature
  - gurumoji/statistics
---

# SciPy `stats.pearsonr` 公式APIリファレンス

## 資料の目的

SciPyのPearson積率相関係数と、その帰無仮説検定を行う関数のAPI仕様を示す。

## 対象データと分析仕様

2つの配列に対する線形関係の係数とp値を計算する。関数の既定検定は、母相関が0であるという帰無仮説のもと、独立な正規分布から標本が得られる条件を使う。

## 主要な知見

- Pearsonの係数は線形関係を表し、値域は−1から1。
- 相関が0でも独立とは限らない。非線形な依存関係を見落とす可能性がある。
- 入力が定数なら係数を定義できず、NaNと警告が返る。ほぼ定数の入力にも数値精度上の警告がある。
- SciPy v1.18.0では、`pearsonr`の`method`に`PermutationMethod`または`MonteCarloMethod`を渡し、それぞれの設定を使う置換検定またはモンテカルロ検定でp値を計算できる。
- `PearsonRResult.confidence_interval`の既定はFisher変換。`BootstrapMethod`を渡すと、設定に従って`scipy.stats.bootstrap`で信頼区間を計算する。
- 退化した再標本化では信頼限界がNaNになる場合があり、公式マニュアルは非常に小さい標本（約6観測）で典型的と説明する。この数値は一般的な最小標本数ではない。
- 片側・両側検定を指定できる。

## 適用上の注意と限界

関数の説明はソフトウェア仕様であり、データにPearson相関を使うべきかを決める研究設計の指針ではない。APIに再標本化法があることは、その方法が発話単位や話者に入れ子になったデータで妥当だと示すものではない（専門家定義に基づく適用範囲の整理）。係数だけから因果や独立性を推論しない。外れ値や非線形な関係の診断は別途行う。

## 根拠の位置情報

SciPy v1.18.0 Manual「pearsonr」Parameters `method`、Returns `confidence_interval`、Warnings、およびNotes。

## 未確認事項

プロジェクトで使用するSciPy実行版との一致、対象データでの分布・外れ値・非線形性。
