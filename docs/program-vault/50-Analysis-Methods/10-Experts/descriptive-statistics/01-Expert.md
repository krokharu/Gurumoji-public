---
note_id: expert-descriptive-statistics-definition
note_type: expert-definition
expert_id: exp-descriptive-statistics
title: 記述統計の専門家
role: computational
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids: []
registry_method_ids:
  - descriptive_statistics
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/statistics
---

# 記述統計の専門家（exp-descriptive-statistics）

## 担当範囲と担当外

発話単位の数値変数の分布と度数を、全体と比較群ごとに記述する。検定、相関、記述量の意味づけは担当外。詳細：[[50-Analysis-Methods/10-Experts/descriptive-statistics/00-Overview]]

## 理論的背景と採用する流派

[実装判断] 記述統計はGurumojiの集計の定義（`research_analysis` の統計分析）に従う要約で、単独の文献の手法ではない。報告では分析を探索的なものとして扱う（[文献] Appelbaum et al. 2018の区分、要旨）。

## 適した研究目的・問い・データ

発話の長さや量の分布を、他の分析の前提や文脈として確認したい場合。

## 必要な入力と前処理、分析単位

除外していない発話、比較軸（話者・役割）、欠測の扱い、形態素解析の結果（形態素数・内容語数のため）。分析単位は発話。

## 手順の要約

対象・比較軸・欠測の決定 → 記述統計と度数の計算 → 分布の歪みと極端な発話の確認 → 探索的な記述として報告。詳細：[[50-Analysis-Methods/10-Experts/descriptive-statistics/02-Procedure]]

## 判断基準と品質確認の要約

Nと欠測・除外・分母の明示、中央値と四分位の提示、入れ子の限界。詳細：[[50-Analysis-Methods/10-Experts/descriptive-statistics/03-Quality]]

## よくある誤用と禁止事項

記述量を影響力や理解度とする、数値の違いに因果的な説明を加える、文字／分を音響的な発話速度とする。

## 出力形式

対象・比較軸・欠測の条件、記述統計の表、度数の表、分布の確認（極端な発話ID）、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/descriptive-statistics/04-Applicability-and-Limits]]

## 参照ノートと主要文献

実装：[[50-Analysis-Methods/03-Statistics/01-Descriptive-Statistics]]。文献：[[50-Analysis-Methods/20-Literature/LIT-appelbaum-2018-jars-quant]]、[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data]]（要旨確認）。事例：[[50-Analysis-Methods/10-Experts/descriptive-statistics/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/descriptive-statistics/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-descriptive-statistics
definition_version: 1
knowledge_verified: 2026-09-15
title: 記述統計の専門家
role: computational
analysis_method_ids: []
registry_method_ids:
  - descriptive_statistics
school:
  default:
    id: exploratory-descriptives
    label: 発話単位の記述統計と度数（Gurumojiの集計）
  alternatives: []
scope:
  - 発話時間、文字数、形態素数、内容語数、語彙多様性、文字／分の分布を記述する
  - 全体と比較群（話者・役割）ごとの記述統計と、話者・役割・質問候補の度数を示す
out_of_scope:
  - text: 群の差の統計的検定
    handoff: exp-group-comparison-statistics
  - text: 変数どうしの関連
    handoff: exp-correlation
analysis_unit: 発話（比較軸は話者または役割）
required_inputs:
  - 除外していない発話
  - 比較軸（話者または役割）
  - 欠測の扱い
  - 形態素解析の結果（形態素数・内容語数・語彙多様性のため）
applicability_checks:
  - id: desc-a1
    check: min_included_segments
    severity: block
    params:
      min: 1
    message: 集計できる発話がありません。
    basis:
      - implementation
  - id: desc-a2
    check: morphology_engine_ready
    severity: warn
    message: 形態素解析が簡易解析（fallback）のため、形態素数・内容語数・語彙多様性の値が正式な解析と異なります。
    basis:
      - implementation
  - id: desc-a3
    check: valid_time_ratio_min
    severity: warn
    params:
      min: 0.9
    message: 有効な時刻を持つ発話が90%未満のため、発話時間と文字／分の欠測が多くなります（90%は実装上の目安）。
    basis:
      - implementation
  - id: desc-a4
    check: human_review
    severity: warn
    message: 発話が話者と会話に入れ子になっていることを踏まえ、記述統計を個人差や母集団の推定として読まないことを確認します。
    basis:
      - LIT-aarts-2014-nested-data
procedure:
  - id: desc-p1
    title: 対象の発話、比較軸、欠測の扱いを決める
    actor: researcher
    basis:
      - implementation
  - id: desc-p2
    title: N、欠測、平均、標準偏差、中央値、四分位、最小・最大、度数を計算する
    actor: code
    basis:
      - implementation
  - id: desc-p3
    title: 分布の歪みと極端な発話を、発話IDで確認する
    actor: researcher
    basis:
      - implementation
  - id: desc-p4
    title: 分析を探索的な記述として報告する
    actor: researcher
    basis:
      - LIT-appelbaum-2018-jars-quant
quality_checks:
  - id: desc-q1
    check: morphology_engine_ready
    text: 形態素数・内容語数・語彙多様性が正式な解析に基づくか
    basis:
      - implementation
  - id: desc-q2
    check: human_review
    text: Nと欠測、除外規則、分母を示したか
    basis:
      - implementation
  - id: desc-q3
    check: human_review
    text: 平均だけでなく中央値と四分位を示したか
    basis:
      - implementation
  - id: desc-q4
    check: human_review
    text: 発話が話者に入れ子になっていることを限界に書いたか
    basis:
      - LIT-aarts-2014-nested-data
prohibited_conclusions:
  - 記述量を、影響力、理解度、関与の質として述べない
  - 数値の違いに因果的な説明を加えない
  - 文字／分を、音響的な発話速度として述べない
output_sections:
  - 対象・比較軸・欠測の条件
  - 記述統計の表
  - 度数の表
  - 分布の確認（極端な発話ID）
  - 限界
ai_assist:
  allowed: false
  steps: []
  reason: 記述統計は計算系の専門家で、値はコードで計算するため、AI見解を使いません。
  brief: ""
literature:
  - LIT-appelbaum-2018-jars-quant
  - LIT-aarts-2014-nested-data
  - RES-scipy-describe
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
open_issues:
  - 記述統計そのものの方法論文献は置いておらず、公式API定義と実装が主な一次資料になっている
  - Appelbaum et al. 2018は要旨だけを確認し、訂正記事の内容を読んでいない
  - 90%の目安は実装上の判断
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
