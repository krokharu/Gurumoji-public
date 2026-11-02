---
note_id: expert-kj-method-definition
note_type: expert-definition
expert_id: exp-kj-method
title: KJ法の専門家
role: methodology
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids:
  - kj
registry_method_ids: []
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# KJ法の専門家（exp-kj-method）

## 担当範囲と担当外

1ラベル1メッセージのラベルを作り、事前のカテゴリーを想定せずにボトムアップでグループ編成し、表札・空間配置・図解化・文章化で構造を示す。事前カテゴリーによる分類、自動クラスタ、概念的カテゴリーによる理論構成は担当外。詳細：[[50-Analysis-Methods/10-Experts/kj-method/00-Overview]]

## 理論的背景と採用する流派

[文献] 川喜田へのインタビューの要約は、方法論の特徴として、ありのままのデータからボトムアップで認識すること、カード記述による自由な組み合わせ、意味を重視した文章見出しの多段階使用、図解化による統合、図解化と言語化による提示と衆目評価による合意形成などを挙げる（川喜田ほか 2003、p.6）。[実装判断] 1997年版に基づく田中のクイックマニュアルの手順を既定にする。

## 適した研究目的・問い・データ

雑多な意見や観察の全体の構造を、研究者がボトムアップにまとめて図解したい研究。発話から1つのメッセージを読み取ってラベルにできるデータ。

## 必要な入力と前処理、分析単位

研究目的、文字起こし、ラベル化の方針。分析単位はラベル（1つのメッセージ）で、発話IDをラベルの通し番号に対応させる。

## 手順の要約

下準備 → ラベルづくり → ラベル拡げ → ラベル集め → 表札づくり → 第2段・第3段のグループ編成 → 空間配置 → 図解化 → 文章化 → 提示と衆目評価。詳細：[[50-Analysis-Methods/10-Experts/kj-method/02-Procedure]]

## 判断基準と品質確認の要約

1ラベル1メッセージと番号の対応、事前カテゴリーを想定しないグループ化、文章で書く表札、最小限の関係線、論理的な矛盾とデータからの逸脱の確認。詳細：[[50-Analysis-Methods/10-Experts/kj-method/03-Quality]]

## よくある誤用と禁止事項

自動クラスタやAIの分類をグループ編成として示す、事前カテゴリーに当てはめる、島の大きさを重要性とする。実行定義の `prohibited_conclusions` を参照。

## 出力形式

研究目的と使った版、ラベルの一覧（通し番号と発話ID）、グループ編成の段階と表札、図解、文章化、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/kj-method/04-Applicability-and-Limits]]

## 参照ノートと主要文献

主要文献：[[50-Analysis-Methods/20-Literature/LIT-tanaka-kj-quick-manual]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-kawakita-2003-kj-interview]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-kawakita-1967-hassoho]]、[[50-Analysis-Methods/20-Literature/LIT-scupin-1997-kj]]（書誌のみ）。事例：[[50-Analysis-Methods/10-Experts/kj-method/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/kj-method/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-kj-method
definition_version: 1
knowledge_verified: 2026-09-15
title: KJ法の専門家
role: methodology
analysis_method_ids:
  - kj
registry_method_ids: []
school:
  default:
    id: kawakita-1997-tanaka-manual
    label: KJ法（川喜田1997年版に基づく田中のクイックマニュアル）
  alternatives:
    - id: kawakita-earlier-versions
      label: 川喜田 1967・1986の版（原典未確認）
scope:
  - 1ラベル1メッセージのラベルを作り、ボトムアップにグループ編成する
  - 表札・空間配置・図解化・文章化で構造を示す
  - 図解の提示と衆目評価の記録を扱う
out_of_scope:
  - text: 事前に定めたカテゴリーに当てはめる分類
    handoff: exp-qualitative-content-analysis
  - text: 意味の近い発話の自動的なまとまり
    handoff: exp-embedding-topic-exploration
  - text: 概念的なカテゴリーによる理論の構成
    handoff: exp-m-gta
analysis_unit: ラベル（1つのメッセージ）。発話IDをラベルの通し番号に対応させる
required_inputs:
  - 研究目的（関係線を最小限にする基準）
  - 文字起こし
  - ラベル化の方針（発話の区切りとメッセージの単位が合わない場合の扱い）
applicability_checks:
  - id: kj-a1
    check: research_question_present
    severity: warn
    message: 研究目的がありません。関係線を研究目的に合わせて最小限にするための基準がありません。
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-a2
    check: min_included_segments
    severity: block
    params:
      min: 1
    message: 分析できる発話がありません。
    basis:
      - implementation
  - id: kj-a3
    check: max_included_segments
    severity: warn
    params:
      max: 400
    message: 発話が400件を超えています。1ラベル1メッセージで手作業のグループ編成を行う作業量を研究者が見積もってください（400件は実装上の目安）。
    basis:
      - implementation
  - id: kj-a4
    check: human_review
    severity: warn
    message: ラベルが1つのメッセージを読み取れる単位になっているか、発話の区切りと合わない場合の分割を研究者が確認します。
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-a5
    check: analysis_basis_current
    severity: warn
    message: 逐語録の準備記録と分析の根拠が一致していません。
    basis:
      - implementation
procedure:
  - id: kj-p0
    title: 下準備（音声データの文字起こし、道具の準備）
    actor: researcher
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-p1
    title: ラベルづくり（1ラベル1メッセージ、通し番号を元データと対応させる）
    actor: researcher
    basis:
      - LIT-tanaka-kj-quick-manual
      - LIT-kawakita-2003-kj-interview
  - id: kj-p2
    title: ラベル拡げ（ランダムな順に並べる）
    actor: researcher
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-p3
    title: ラベル集め（内容からボトムアップに小グループを作る。事前にカテゴリーを想定せず、入らないラベルはそのままにする）
    actor: researcher
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-p4
    title: 表札づくり（文章で書き、理論や専門用語に無理に当てはめない）
    actor: researcher
    basis:
      - LIT-tanaka-kj-quick-manual
      - LIT-kawakita-2003-kj-interview
  - id: kj-p5
    title: 第2段・第3段のグループ編成（解釈可能なグループ数になるまで繰り返す）
    actor: researcher
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-p6
    title: 空間配置（大グループから、解釈しやすい順に並べる）
    actor: researcher
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-p7
    title: 図解化（グループを囲み、関係線は大きいグループから研究目的に合わせて最小限に結ぶ）
    actor: researcher
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-p8
    title: 文章化（論理的な矛盾とデータからの解釈の逸脱に注意する）
    actor: researcher
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-p9
    title: 図解と文章化を他者に説明し、衆目評価の結果を記録する
    actor: researcher
    basis:
      - LIT-kawakita-2003-kj-interview
quality_checks:
  - id: kj-q1
    check: human_review
    text: 1ラベル1メッセージになっているか、ラベルと元の発話の番号が対応しているか
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-q2
    check: human_review
    text: 事前のカテゴリーを想定せずにグループ化したか、どのグループにも入らないラベルを無理に分類していないか
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-q3
    check: human_review
    text: ラベルと表札が文章で書かれ、名詞だけで終わっていないか
    basis:
      - LIT-tanaka-kj-quick-manual
      - LIT-kawakita-2003-kj-interview
  - id: kj-q4
    check: human_review
    text: 関係線が研究目的に合わせて最小限か
    basis:
      - LIT-tanaka-kj-quick-manual
  - id: kj-q5
    check: human_review
    text: 文章化で、論理的な矛盾やデータからの解釈の逸脱がないか
    basis:
      - LIT-tanaka-kj-quick-manual
prohibited_conclusions:
  - 類似度によるクラスタリングやAIの分類結果を、KJ法のグループ編成として示さない
  - 事前に用意したカテゴリーに当てはめた分類をKJ法の結果としない
  - 図解の島の大きさ（ラベル数）を意見の重要性として述べない
  - 研究者が行っていない衆目評価を、合意形成を経た結果として示さない
output_sections:
  - 研究目的と使った版
  - ラベルの一覧（通し番号と発話ID）
  - グループ編成の段階と表札
  - 図解（空間配置と関係線）
  - 文章化
  - 限界
ai_assist:
  allowed: false
  steps: []
  reason: KJ法の専門家定義では、ラベル集め・表札づくり・図解化を研究者のボトムアップな作業としており、AIによる候補の分類で置き換えないため、この手法を主手法にした場合はAI見解を生成しません。
  brief: ""
literature:
  - LIT-tanaka-kj-quick-manual
  - LIT-kawakita-2003-kj-interview
  - LIT-kawakita-1967-hassoho
  - LIT-scupin-1997-kj
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
  - 04-AI-Assistance-Boundaries
open_issues:
  - 川喜田の書籍（1967、1986、1997）の本文を読んでいない
  - KJ法の査読付きの方法論文献を確認していない（読んだのはインタビュー記事と研究会の報告論集）
  - Gurumojiにはラベル・グループ編成・図解を記録する機能がない
  - 400発話という作業量の目安は実装上の判断
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
