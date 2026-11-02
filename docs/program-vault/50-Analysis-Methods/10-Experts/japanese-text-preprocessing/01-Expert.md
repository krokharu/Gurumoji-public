---
note_id: expert-japanese-text-preprocessing-definition
note_type: expert-definition
expert_id: exp-japanese-text-preprocessing
title: 日本語テキストの前処理の専門家
role: preprocessing
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids: []
registry_method_ids:
  - morphology
  - syntax
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/text
---

# 日本語テキストの前処理の専門家（exp-japanese-text-preprocessing）

## 担当範囲と担当外

形態素解析と係り受け解析の条件・状態を記録し、簡易解析や利用不可の状態を後段の分析に伝える。語の頻度の解釈、係り受けからの意味の推定は担当外。詳細：[[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/00-Overview]]

## 理論的背景と採用する流派

[文献] GiNZAはspaCyをフレームワークとし、トークン化にSudachiPy、単語ベクトルにchiVeを使う。精度はUD_Japanese-BCCWJ r2.8のテストセットで示されている（GiNZAの公式ページ）。[実装判断] GiNZAを既定にし、使えない場合の切り替えを状態として記録する。

## 適した研究目的・問い・データ

語を単位にする後段の分析（計量テキスト分析、記述統計の形態素数、正規化検索）の前提として、解析の条件と状態を確認したい場合。

## 必要な入力と前処理、分析単位

除外していない本文、解析器・辞書・分割モード（既定C）・ストップ語。分析単位は形態素（トークン）と形態素間の係り受けで、発話ID・文ID・トークンIDで対応させる。

## 手順の要約

解析条件の固定 → 解析と保存 → 簡易解析・利用不可の状態の伝達 → サンプルでの解析誤りの監査。詳細：[[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/02-Procedure]]

## 判断基準と品質確認の要約

正式な解析器の使用、係り受けの利用可否の扱い、条件の記録、サンプル監査。詳細：[[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/03-Quality]]

## よくある誤用と禁止事項

形態素境界や品詞を正解ラベルとする、書き言葉での精度を逐語録での正しさとする、依存関係から意図や因果を決める。

## 出力形式

解析器と条件、形態素・品詞の分布、係り受けの結果（利用可否）、解析誤りの監査、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/04-Applicability-and-Limits]]

## 参照ノートと主要文献

実装：[[50-Analysis-Methods/01-Text-and-Context/03-Morphology]]、[[50-Analysis-Methods/01-Text-and-Context/04-Syntax]]。文献：[[50-Analysis-Methods/20-Literature/RES-ginza-official]]（公式ページ）、Matsuda 2020、Takaoka et al. 2018、Kudo et al. 2004、Omura & Asahara 2018、Nivre et al. 2020（書誌のみ）。事例：[[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-japanese-text-preprocessing
definition_version: 1
knowledge_verified: 2026-09-15
title: 日本語テキストの前処理の専門家
role: preprocessing
analysis_method_ids: []
registry_method_ids:
  - morphology
  - syntax
school:
  default:
    id: ginza-sudachi-ud
    label: GiNZA（SudachiPy、Universal Dependencies）による形態素解析と係り受け解析
  alternatives:
    - id: sudachipy-only
      label: SudachiPy単独（係り受けなし）
    - id: regex-fallback
      label: 正規表現による簡易分割（fallback、正式な解析と混ぜない）
scope:
  - 形態素（表層形、原形、正規形、読み、品詞）と係り受けの解析の条件と状態を記録する
  - 簡易解析（fallback）や利用不可の状態を後段の分析に伝える
  - 解析の誤りをサンプルで監査する手順を示す
out_of_scope:
  - text: 語の頻度・共起・特徴語の解釈
    handoff: exp-quantitative-text-analysis
  - text: 係り受けから意味役割、話者の意図、因果、談話関係を決めること（依存関係はそれらを直接決めない）
analysis_unit: 形態素（トークン）と形態素間の係り受け。発話ID・文ID・トークンIDで対応させる
required_inputs:
  - 除外していない本文
  - 解析器・辞書・分割モード（既定C）・ストップ語の設定
applicability_checks:
  - id: pre-a1
    check: morphology_engine_ready
    severity: warn
    message: 形態素解析が簡易解析（fallback）です。後段の語彙頻度・共起・特徴語・正規化検索の精度が下がります。
    basis:
      - RES-ginza-official
      - implementation
  - id: pre-a2
    check: syntax_available
    severity: warn
    message: 係り受け解析が利用できません。係り受けの結果を、空の成功として扱いません。
    basis:
      - implementation
  - id: pre-a3
    check: min_included_segments
    severity: block
    params:
      min: 1
    message: 解析できる発話がありません。
    basis:
      - implementation
  - id: pre-a4
    check: human_review
    severity: warn
    message: 口語、フィラー、固有名詞、誤変換を含む発話の解析をサンプルで確認します。精度は書き言葉のコーパスで評価されています。
    basis:
      - RES-ginza-official
      - LIT-omura-asahara-2018-ud-japanese
procedure:
  - id: pre-p1
    title: 解析器・辞書・分割モード・ストップ語を固定し、版を記録する
    actor: code
    basis:
      - RES-ginza-official
      - implementation
  - id: pre-p2
    title: 形態素と係り受けを解析し、発話ID・文ID・トークンIDと一緒に保存する
    actor: code
    basis:
      - RES-ginza-official
  - id: pre-p3
    title: 簡易解析や利用不可の状態を、後段の分析の結果に伝える
    actor: code
    basis:
      - implementation
  - id: pre-p4
    title: 解析の誤りをサンプルで監査し、必要なら辞書やストップ語を明示的に追加する
    actor: researcher
    basis:
      - implementation
quality_checks:
  - id: pre-q1
    check: morphology_engine_ready
    text: 形態素解析が正式な解析器で行われたか
    basis:
      - implementation
  - id: pre-q2
    check: syntax_available
    text: 係り受け解析が利用できたか（利用できない場合に空の成功として扱っていないか）
    basis:
      - implementation
  - id: pre-q3
    check: human_review
    text: 解析器の版、分割モード、ストップ語を結果に記録したか
    basis:
      - implementation
  - id: pre-q4
    check: human_review
    text: サンプルで解析の誤りを確認したか
    basis:
      - implementation
prohibited_conclusions:
  - 形態素境界・品詞・原形を、正解のラベルとして述べない
  - 書き言葉のコーパスで評価された精度を、逐語録での解析の正しさとして述べない
  - 依存関係から、意味役割、意図、因果を決めない
output_sections:
  - 解析器と条件
  - 形態素・品詞の分布
  - 係り受けの結果（利用可否）
  - 解析誤りの監査
  - 限界
ai_assist:
  allowed: false
  steps: []
  reason: 日本語テキストの前処理は解析器で行う前処理の専門家で、AI見解を使いません。
  brief: ""
literature:
  - RES-ginza-official
  - LIT-matsuda-2020-ginza
  - LIT-takaoka-2018-sudachi
  - LIT-kudo-2004-japanese-morphology
  - LIT-omura-asahara-2018-ud-japanese
  - LIT-nivre-2020-ud-v2
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
open_issues:
  - 話し言葉の逐語録での形態素解析・係り受け解析の精度を扱った文献を確認していない
  - Gurumojiが実際に読み込むGiNZAのモデル（ja_ginza か ja_ginza_electra か）をこの定義では確認していない
  - Matsuda 2020、Takaoka et al. 2018、Kudo et al. 2004、Omura & Asahara 2018、Nivre et al. 2020は書誌のみの確認
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
