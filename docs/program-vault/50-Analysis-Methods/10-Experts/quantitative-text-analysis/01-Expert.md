---
note_id: expert-quantitative-text-analysis-definition
note_type: expert-definition
expert_id: exp-quantitative-text-analysis
title: 計量テキスト分析の専門家
role: methodology
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids:
  - quantitative_text
registry_method_ids:
  - lexical_frequency
  - cooccurrence
  - speaker_characteristics
  - kwic
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 計量テキスト分析の専門家（exp-quantitative-text-analysis）

## 担当範囲と担当外

語彙頻度・共起・話者別特徴語によるデータの要約と比較、文脈検索による原文への往復、概念を語で操作化する規則の記録。意見の解釈的な整理、形態素解析の精度、統計的検定は担当外。詳細：[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/00-Overview]]

## 理論的背景と採用する流派

[文献] 計量テキスト分析は、計量的分析と質的な解釈を循環的な関係として捉え、計量的分析の結果を参考にもとの文章を質的に解釈する方法とされる（樋口 2017、2.1節）。多変量解析による要約の段階と、コーディング規則で理論や問題意識を操作化する段階を区別して併用する（樋口 2004）。[実装判断] 両アプローチの併用と原文への往復を既定にする。

## 適した研究目的・問い・データ

問い、比較の枠組み、注目する概念を分析の前に具体的に設定できる研究（[文献] 樋口 2017、4節）。インタビュー記録では、質的分析の道しるべとして全体像や複数グループ間の違いをつかむ使い方がある（[文献] 樋口 2017、3.4.2節）。

## 必要な入力と前処理、分析単位

研究質問、比較の枠組み、注目する概念、形態素解析の結果（解析器・分割単位・ストップ語を固定）。分析単位は発話（文書）。

## 手順の要約

問い・比較の枠組み・注目概念の設定 → 解析条件の固定 → 頻度・共起・特徴語による要約 → 比較の枠組みでの違いの確認 → KWICで原文に戻って解釈 → 規則の記録。詳細：[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/02-Procedure]]

## 判断基準と品質確認の要約

解析条件としきい値の明示、原文での確認、多数の比較の探索的扱い、出現率の差を検定結果としないこと。詳細：[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/03-Quality]]

## よくある誤用と禁止事項

頻度を重要性や支持人数とする、特徴語の差を有意差とする、KH Coderで分析したと表示する。実行定義の `prohibited_conclusions` を参照。

## 出力形式

研究質問・比較の枠組み・注目概念、解析の条件、頻度・共起・特徴語の表、原文の確認と解釈、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/04-Applicability-and-Limits]]

## 参照ノートと主要文献

主要文献：[[50-Analysis-Methods/20-Literature/LIT-higuchi-2004-quantitative-text]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-higuchi-2017-khcoder]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-kilgarriff-2001-comparing-corpora]]、[[50-Analysis-Methods/20-Literature/LIT-grimmer-stewart-2013-text-as-data]]（要旨確認）。事例：[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/quantitative-text-analysis/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-quantitative-text-analysis
definition_version: 1
knowledge_verified: 2026-09-15
title: 計量テキスト分析の専門家
role: methodology
analysis_method_ids:
  - quantitative_text
registry_method_ids:
  - lexical_frequency
  - cooccurrence
  - speaker_characteristics
  - kwic
school:
  default:
    id: higuchi-combined-approach
    label: 計量テキスト分析（樋口：多変量による要約と規則による操作化の併用、原文への往復）
  alternatives:
    - id: correlational-only
      label: Correlationalアプローチのみ（探索）
    - id: dictionary-based-only
      label: Dictionary-basedアプローチのみ（規則による分類、Gurumojiに自動コーディングの機能はない）
scope:
  - 語彙頻度・共起・話者別特徴語でデータ全体を要約する
  - 比較の枠組みで語の使われ方の違いを見る
  - 文脈検索（KWIC）で原文に戻って解釈する
  - 概念を語で操作化する規則を記録する
out_of_scope:
  - text: 意見の意味の解釈的な整理
    handoff: exp-thematic-analysis
  - text: 定義したカテゴリーへの体系的な整理
    handoff: exp-qualitative-content-analysis
  - text: 形態素解析と係り受けの精度の確認
    handoff: exp-japanese-text-preprocessing
  - text: 群の差の統計的検定
    handoff: exp-group-comparison-statistics
analysis_unit: 発話（文書）。語はGiNZA／SudachiPyの内容語
required_inputs:
  - 研究質問
  - 比較の枠組み（明確に区別できる比較対象）
  - 注目する概念
  - 形態素解析の結果（解析器・分割単位・ストップ語を固定）
applicability_checks:
  - id: qta-a1
    check: research_question_present
    severity: warn
    message: 研究質問がありません。結果は探索としてだけ扱います（分析すれば何か意味のある結果が出るだろうという取り組み方は推奨されない）。
    basis:
      - LIT-higuchi-2017-khcoder
  - id: qta-a2
    check: comparison_axis_present
    severity: warn
    message: 比較の枠組み（比較軸・比較グループ）が設定されていません。
    basis:
      - LIT-higuchi-2017-khcoder
  - id: qta-a3
    check: morphology_engine_ready
    severity: warn
    message: 形態素解析が簡易解析（fallback）です。語の頻度・共起・特徴語の精度が下がります。
    basis:
      - RES-ginza-official
      - implementation
  - id: qta-a4
    check: min_included_segments
    severity: warn
    params:
      min: 20
    message: 発話が20件未満です。語の頻度と共起は少数の発話に左右されます（20件は実装上の目安）。
    basis:
      - implementation
  - id: qta-a5
    check: min_speakers
    severity: warn
    params:
      min: 2
    message: 話者が1人以下のため、話者別特徴語は算出されません。
    basis:
      - implementation
procedure:
  - id: qta-p1
    title: 研究質問、比較の枠組み、注目する概念を分析の前に設定する
    actor: researcher
    basis:
      - LIT-higuchi-2017-khcoder
  - id: qta-p2
    title: 形態素解析の条件（解析器、分割単位、ストップ語）を固定する
    actor: code
    basis:
      - RES-ginza-official
      - implementation
  - id: qta-p3
    title: 語彙頻度・共起・話者別特徴語を計算してデータ全体を要約する（語を手作業で逐一選ばない）
    actor: code
    basis:
      - LIT-higuchi-2004-quantitative-text
  - id: qta-p4
    title: 比較の枠組みで、明確に区別できる対象の間の語の違いを見る
    actor: researcher
    basis:
      - LIT-higuchi-2017-khcoder
  - id: qta-p5
    title: 注目した語を文脈検索（KWIC）で原文に戻って読み、質的に解釈する
    actor: researcher
    basis:
      - LIT-higuchi-2017-khcoder
  - id: qta-p6
    title: 概念を語で操作化する場合は、コーディングの規則を公開できる形で記録する
    actor: researcher
    basis:
      - LIT-higuchi-2004-quantitative-text
      - LIT-higuchi-2017-khcoder
quality_checks:
  - id: qta-q1
    check: morphology_engine_ready
    text: 形態素解析が正式な解析器で行われたか
    basis:
      - implementation
  - id: qta-q2
    check: human_review
    text: 語の選択やしきい値（最小共起数、上位語数）を結果と一緒に示したか
    basis:
      - LIT-higuchi-2004-quantitative-text
  - id: qta-q3
    check: human_review
    text: 注目した語を原文で確認したか（否定、引用、言い直し、多義）
    basis:
      - LIT-higuchi-2017-khcoder
      - LIT-grimmer-stewart-2013-text-as-data
  - id: qta-q4
    check: human_review
    text: 多数の語で比較する場合、偽の発見を含みうる探索的な結果として扱ったか
    basis:
      - LIT-benjamini-hochberg-1995-fdr
  - id: qta-q5
    check: human_review
    text: 話者別特徴語の出現率の差を、有意差や検定結果として説明していないか
    basis:
      - LIT-kilgarriff-2001-comparing-corpora
prohibited_conclusions:
  - 語の頻度や共起から、意見の重要性、支持人数、合意を述べない
  - 話者別特徴語の出現率の差を、統計的に有意な差として述べない
  - 結果を「KH Coderで分析した」と表示しない（Gurumojiの独自実装）
  - 原文を確認していない語の意味を結論にしない
output_sections:
  - 研究質問・比較の枠組み・注目する概念
  - 解析の条件（解析器・分割単位・ストップ語・しきい値）
  - 語彙頻度・共起・特徴語の表
  - 原文の確認（KWIC）と解釈
  - 限界
ai_assist:
  allowed: false
  steps: []
  reason: 計量テキスト分析の専門家定義では、計算はコードで行い、語の意味の解釈は研究者が原文に戻って行うため、この手法を主手法にした場合はAI見解を生成しません。
  brief: ""
literature:
  - LIT-higuchi-2004-quantitative-text
  - LIT-higuchi-2017-khcoder
  - RES-khcoder-official
  - LIT-salton-buckley-1988-term-weighting
  - LIT-kilgarriff-2001-comparing-corpora
  - LIT-callon-1983-coword
  - LIT-grimmer-stewart-2013-text-as-data
  - LIT-benjamini-hochberg-1995-fdr
  - RES-ginza-official
  - LIT-hsieh-shannon-2005-qca
  - LIT-knight-2024-freetxt
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
  - 04-AI-Assistance-Boundaries
open_issues:
  - 樋口の書籍（2014）を読んでいない
  - Gurumojiには辞書・コーディング規則による自動コーディングの機能がない
  - 話者別特徴語の検定（Kilgarriff 2001が検討する方法）は実装していない
  - Salton & Buckley 1988、Callon et al. 1983は書誌のみの確認
  - 20発話という目安は実装上の判断
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
