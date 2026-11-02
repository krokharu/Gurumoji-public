---
note_id: expert-correlation-definition
note_type: expert-definition
expert_id: exp-correlation
title: 相関の専門家
role: computational
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids: []
registry_method_ids:
  - correlation
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 相関の専門家（exp-correlation）

## 担当範囲と担当外

発話単位の数値変数の全ペアについて、PearsonとSpearmanの相関係数・N・p値・計算不能状態を示し、探索的な関連として説明する。群の差、分布の要約、因果は担当外。詳細：[[50-Analysis-Methods/10-Experts/correlation/00-Overview]]

## 理論的背景と採用する流派

[実装判断] SciPyによるPearson・Spearman相関の既存の実装に従う。[文献] 非正規データではPearsonのrの検定が第1種の誤りを増やしうること（Bishara & Hittner 2012、要旨）、入れ子のデータは独立でないこと（Aarts et al. 2014、要旨）を、結果を探索的に扱う根拠にする。

## 適した研究目的・問い・データ

1回の会話の中の発話の性質（長さ、語数など）の関連を探索したい場合。

## 必要な入力と前処理、分析単位

発話単位の数値変数、欠測の扱い、SciPy、形態素解析の結果。分析単位は発話。

## 手順の要約

変数の対と種類の確認 → 係数・N・p値・状態の計算 → 分布・外れ値・同順位の確認 → 探索的な関連として報告。詳細：[[50-Analysis-Methods/10-Experts/correlation/02-Procedure]]

## 判断基準と品質確認の要約

歪んだ分布でのPearsonのp値の扱い、多数の対からの選択の回避、変数・種類・N・欠測の明示。詳細：[[50-Analysis-Methods/10-Experts/correlation/03-Quality]]

## よくある誤用と禁止事項

相関から因果や方向を述べる、話者内と話者間を区別せずに解釈する、発話を独立とみなせない設計でp値を一般化する。

## 出力形式

変数の対と条件、相関の表、分布の確認、探索的扱いと限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/correlation/04-Applicability-and-Limits]]

## 参照ノートと主要文献

実装：[[50-Analysis-Methods/03-Statistics/03-Correlation]]。文献：[[50-Analysis-Methods/20-Literature/LIT-bishara-hittner-2012-correlation]]、[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data]]、[[50-Analysis-Methods/20-Literature/LIT-benjamini-hochberg-1995-fdr]]（要旨確認）、Spearman 1904、Holm 1979（書誌のみ）。事例：[[50-Analysis-Methods/10-Experts/correlation/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/correlation/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-correlation
definition_version: 1
knowledge_verified: 2026-09-15
title: 相関の専門家
role: computational
analysis_method_ids: []
registry_method_ids:
  - correlation
school:
  default:
    id: exploratory-utterance-correlations
    label: 発話単位のPearson・Spearman相関（探索的）
  alternatives:
    - id: transformed-or-permutation
      label: 変換や並べ替え検定による相関の検定（未実装）
scope:
  - 発話単位の数値変数の全ペアについて、PearsonとSpearmanの相関係数、N、p値、計算不能状態を示す
  - 分布の歪み、外れ値、入れ子、多重比較の限界を示す
out_of_scope:
  - text: 群の差の検定
    handoff: exp-group-comparison-statistics
  - text: 分布の要約と度数
    handoff: exp-descriptive-statistics
  - text: 因果や方向の推定（相関からは導けない）
analysis_unit: 発話
required_inputs:
  - 発話単位の数値変数
  - 欠測の扱い
  - SciPyの利用
  - 形態素解析の結果（形態素に基づく変数のため）
applicability_checks:
  - id: cor-a1
    check: statistics_engine_ready
    severity: block
    message: SciPyを読み込めないため、相関を計算していません。
    basis:
      - implementation
  - id: cor-a2
    check: min_included_segments
    severity: warn
    params:
      min: 10
    message: 発話が10件未満です。非正規の小さな標本では、相関の検定の誤りが大きくなりうるとされます（10件は実装上の目安）。
    basis:
      - LIT-bishara-hittner-2012-correlation
      - implementation
  - id: cor-a3
    check: human_review
    severity: warn
    message: 発話が話者に入れ子になっていること、全ペアの相関に多重比較の補正がないことを確認します。
    basis:
      - LIT-aarts-2014-nested-data
      - LIT-benjamini-hochberg-1995-fdr
  - id: cor-a4
    check: morphology_engine_ready
    severity: warn
    message: 形態素解析が簡易解析（fallback）のため、形態素に基づく変数の値が正式な解析と異なります。
    basis:
      - implementation
procedure:
  - id: cor-p1
    title: 変数の対と、相関の種類（Pearson・Spearman）を確認する
    actor: researcher
    basis:
      - implementation
  - id: cor-p2
    title: 係数、N、p値、計算できない状態を計算する
    actor: code
    basis:
      - implementation
  - id: cor-p3
    title: 分布の歪み・外れ値・同順位を確認し、発話IDに戻る
    actor: researcher
    basis:
      - LIT-bishara-hittner-2012-correlation
  - id: cor-p4
    title: 探索的な関連として報告する
    actor: researcher
    basis:
      - LIT-appelbaum-2018-jars-quant
      - LIT-aarts-2014-nested-data
quality_checks:
  - id: cor-q1
    check: human_review
    text: 歪んだ分布の変数で、Pearsonのp値をそのまま解釈していないか
    basis:
      - LIT-bishara-hittner-2012-correlation
  - id: cor-q2
    check: human_review
    text: 多数の変数の対の中から、有意なものだけを取り上げていないか
    basis:
      - LIT-benjamini-hochberg-1995-fdr
  - id: cor-q3
    check: human_review
    text: 変数の対、相関の種類、N、欠測の扱いを示したか
    basis:
      - implementation
prohibited_conclusions:
  - 相関から因果や方向を述べない
  - 話者内の変化と話者間の差を区別せずに解釈しない
  - 発話を独立な観測とみなせない設計で、p値を一般化の根拠にしない
output_sections:
  - 変数の対と条件
  - 相関の表（係数・N・p値・状態）
  - 分布の確認（外れ値の発話ID）
  - 探索的扱いと限界
ai_assist:
  allowed: false
  steps: []
  reason: 相関は計算系の専門家で、係数はコードで計算するため、AI見解を使いません。
  brief: ""
literature:
  - LIT-spearman-1904-rank
  - LIT-bishara-hittner-2012-correlation
  - LIT-aarts-2014-nested-data
  - LIT-holm-1979-multiple-testing
  - LIT-benjamini-hochberg-1995-fdr
  - LIT-appelbaum-2018-jars-quant
  - RES-scipy-pearsonr
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
open_issues:
  - 変換や並べ替え検定による相関の検定は未実装
  - Spearman 1904とHolm 1979は書誌のみの確認
  - 10件の目安は実装上の判断
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
