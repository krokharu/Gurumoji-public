---
note_id: expert-group-comparison-statistics-definition
note_type: expert-definition
expert_id: exp-group-comparison-statistics
title: 群間比較の専門家
role: computational
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids: []
registry_method_ids:
  - group_statistics
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 群間比較の専門家（exp-group-comparison-statistics）

## 担当範囲と担当外

比較軸（話者・役割）と質問候補・コード・語のクロス集計、探索的な検定と効果量、前提の注記を扱う。相関、複数会話の比較、母集団への一般化は担当外。詳細：[[50-Analysis-Methods/10-Experts/group-comparison-statistics/00-Overview]]

## 理論的背景と採用する流派

[実装判断] SciPyによるPearsonのカイ二乗検定、一元配置分散分析、Kruskal–Wallis検定を発話単位で計算する既存の実装に従う。[文献] 入れ子になったデータの依存を無視すると誤って有意と結論する確率が高くなりうること（Aarts et al. 2014、要旨）、多重検定では偽の発見の割合を考える必要があること（Benjamini & Hochberg 1995、要旨）を、結果を探索的に扱う根拠にする。

## 適した研究目的・問い・データ

1回の会話の中で、話者や役割によってコード・質問候補・語の現れ方が違うかを探索したい場合。

## 必要な入力と前処理、分析単位

比較の目的、比較軸、対象の変数、SciPy。分析単位は発話で、群は話者または役割。

## 手順の要約

比較の目的と群の定義 → クロス集計と検定の計算 → 期待度数・群の大きさ・分散の確認 → 入れ子と多重比較を踏まえた探索的な報告。詳細：[[50-Analysis-Methods/10-Experts/group-comparison-statistics/02-Procedure]]

## 判断基準と品質確認の要約

期待度数の小さいセルの割合、効果量・N・群数・仮定の注記、群の大きさや分散の違い、多重比較の補正がないことの明示。詳細：[[50-Analysis-Methods/10-Experts/group-comparison-statistics/03-Quality]]

## よくある誤用と禁止事項

有意差を因果や重要性とする、発話を独立な標本として一般化する、補正していない多数の検定から有意なものだけを選ぶ。

## 出力形式

比較の目的と群の定義、クロス集計、検定の表、前提の確認、探索的扱いと限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/group-comparison-statistics/04-Applicability-and-Limits]]

## 参照ノートと主要文献

実装：[[50-Analysis-Methods/03-Statistics/02-Group-Statistics]]。文献：[[50-Analysis-Methods/20-Literature/LIT-delacre-2017-welch]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-delacre-2022-correction]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data]]、[[50-Analysis-Methods/20-Literature/LIT-benjamini-hochberg-1995-fdr]]、[[50-Analysis-Methods/20-Literature/LIT-jaeger-2008-logit-mixed]]（要旨確認）、Cochran 1952・1954、Kruskal & Wallis 1952、Rasch et al. 2011、Holm 1979（書誌のみ）。事例：[[50-Analysis-Methods/10-Experts/group-comparison-statistics/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/group-comparison-statistics/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-group-comparison-statistics
definition_version: 1
knowledge_verified: 2026-09-15
title: 群間比較の専門家
role: computational
analysis_method_ids: []
registry_method_ids:
  - group_statistics
school:
  default:
    id: exploratory-utterance-tests
    label: 発話単位の探索的な検定（Pearsonのカイ二乗検定、一元配置分散分析、Kruskal–Wallis検定）
  alternatives:
    - id: nested-models
      label: 入れ子を考慮したモデル（混合ロジットモデルなど、未実装）
scope:
  - 比較軸（話者・役割）と質問候補・手動コード・選択した語のクロス集計を示す
  - 探索的な検定の統計量、p値、効果量、N、群数、仮定の注記を示す
  - 期待度数、群の大きさ、入れ子、多重比較の限界を示す
out_of_scope:
  - text: 変数どうしの関連
    handoff: exp-correlation
  - text: 複数回の会話の比較
    handoff: exp-cross-session-comparison
  - text: 語の違いの質的な解釈
    handoff: exp-quantitative-text-analysis
analysis_unit: 発話（群は話者または役割）
required_inputs:
  - 比較の目的
  - 比較軸（話者または役割）
  - 対象の変数（質問候補、手動コード、選択した語）
  - SciPyの利用
applicability_checks:
  - id: grp-a1
    check: statistics_engine_ready
    severity: block
    message: SciPyを読み込めないため、検定を計算していません。
    basis:
      - implementation
  - id: grp-a2
    check: statistics_min_groups
    severity: block
    params:
      min: 2
    message: 比較する群が2つ未満です。
    basis:
      - implementation
  - id: grp-a3
    check: chi_square_expected_cells
    severity: warn
    params:
      max_low_ratio: 0.2
    message: 期待度数5未満のセルが20%を超えるクロス集計があります。カイ二乗の近似が不正確になりえます（20%は実装上の目安）。
    basis:
      - implementation
  - id: grp-a4
    check: human_review
    severity: warn
    message: 発話は話者と会話に入れ子になっており独立な観測ではないため、検定の結果を探索的に扱うことを研究者が確認します。
    basis:
      - LIT-aarts-2014-nested-data
      - LIT-jaeger-2008-logit-mixed
  - id: grp-a5
    check: human_review
    severity: warn
    message: 多数のコードや語で検定する場合の多重比較の扱い（補正の方針か、探索的な扱いか）を決めます。
    basis:
      - LIT-benjamini-hochberg-1995-fdr
      - LIT-holm-1979-multiple-testing
  - id: grp-a6
    check: speaker_order_confirmed
    severity: warn
    message: 話者の確認が済んでいないため、話者を群にした比較に話者分離の誤りが含まれる可能性があります。
    basis:
      - LIT-park-2022-diarization-review
procedure:
  - id: grp-p1
    title: 比較の目的、群の定義、対象の変数を決める
    actor: researcher
    basis:
      - implementation
  - id: grp-p2
    title: クロス集計と検定（N、群数、統計量、p値、効果量、仮定の注記）を計算する
    actor: code
    basis:
      - implementation
  - id: grp-p3
    title: 期待度数、群の大きさ、分散の違いを確認する
    actor: researcher
    basis:
      - LIT-delacre-2017-welch
      - LIT-delacre-2022-correction
      - implementation
  - id: grp-p4
    title: 入れ子と多重比較を踏まえて、結果を探索的に報告する
    actor: researcher
    basis:
      - LIT-aarts-2014-nested-data
      - LIT-benjamini-hochberg-1995-fdr
      - LIT-appelbaum-2018-jars-quant
quality_checks:
  - id: grp-q1
    check: chi_square_expected_cells
    params:
      max_low_ratio: 0.2
    text: 期待度数5未満のセルの割合が目安以下か
    basis:
      - implementation
  - id: grp-q2
    check: human_review
    text: p値だけでなく、効果量・N・群数・仮定の注記を示したか
    basis:
      - implementation
  - id: grp-q3
    check: human_review
    text: 群の大きさや分散が大きく異なる場合に注意を付けたか（前提の検定の結果で検定を切り替えていないか）
    basis:
      - LIT-delacre-2017-welch
      - LIT-delacre-2022-correction
  - id: grp-q4
    check: human_review
    text: 多重比較の補正をしていないことを示したか
    basis:
      - LIT-benjamini-hochberg-1995-fdr
prohibited_conclusions:
  - 有意差を、因果、実質的な重要性、個人差の安定性として述べない
  - 発話を独立な標本とした検定から、会話や参加者の母集団へ一般化しない
  - 補正していない多数の検定の中から、有意なものだけを選んで結論にしない
output_sections:
  - 比較の目的と群の定義
  - クロス集計
  - 検定の表（統計量・p値・効果量・N・仮定）
  - 前提の確認（期待度数・群の大きさ）
  - 探索的扱いと限界（入れ子・多重比較）
ai_assist:
  allowed: false
  steps: []
  reason: 群間比較は計算系の専門家で、統計量はコードで計算するため、AI見解を使いません。
  brief: ""
literature:
  - LIT-cochran-1952-chi-square
  - LIT-cochran-1954-chi-square
  - LIT-kruskal-wallis-1952
  - LIT-delacre-2017-welch
  - LIT-delacre-2022-correction
  - LIT-rasch-2011-pretest
  - LIT-holm-1979-multiple-testing
  - LIT-benjamini-hochberg-1995-fdr
  - LIT-aarts-2014-nested-data
  - LIT-jaeger-2008-logit-mixed
  - LIT-appelbaum-2018-jars-quant
  - LIT-park-2022-diarization-review
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
open_issues:
  - カイ二乗検定の期待度数の基準の文献（Cochran 1952、1954）は書誌のみの確認で、20%の目安は実装上の判断
  - Welch型の検定、多重比較の補正、入れ子を考慮したモデルは未実装（計画：quantification-statistics-plan）
  - 訂正記事は確認済みだが、訂正後の追加ファイルとシミュレーションスクリプトは独立確認していない
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
