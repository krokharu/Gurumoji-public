---
note_id: expert-m-gta-definition
note_type: expert-definition
expert_id: exp-m-gta
title: M-GTAの専門家
role: methodology
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids:
  - mgta
registry_method_ids: []
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# M-GTAの専門家（exp-m-gta）

## 担当範囲と担当外

分析テーマと分析焦点者の視点からデータに着目し、分析ワークシートで概念を生成し、カテゴリー、結果図、ストーリーラインで変化のプロセスを説明する。頻度・類型の人数の提示、テーマの解釈的生成、小規模データの段階的理論記述は担当外。詳細：[[50-Analysis-Methods/10-Experts/m-gta/00-Overview]]

## 理論的背景と採用する流派

[文献] 修正版の基本特性として、データに基づく分析、経験的という意味での実証性、深い解釈とその意味を凝縮して名付けることの重要性が挙げられ、データの切片化はしない（木下 2007）。[実装判断] M-GTA（木下）を既定にする。

## 適した研究目的・問い・データ

ヒューマンサービス領域など、現象そのものがプロセス的な性格を持つ研究（[文献] 木下 2007、3節）。面接記録を1人分ずつ全体として読める形のデータ。

## 必要な入力と前処理、分析単位

研究テーマと、プロセスを捉える形の分析テーマ、分析焦点者、面接記録。分析単位は、分析テーマと分析焦点者に沿って着目したデータの箇所（切片化しない）で、発話IDはヴァリエーションの根拠として参照する。

## 手順の要約

分析テーマと分析焦点者の設定 → 全体を読み着目 → 概念の生成 → 分析ワークシート → 反対例・類似例の比較 → 理論的メモ → カテゴリー生成 → 理論的サンプリングと飽和化 → 結果図とストーリーライン。詳細：[[50-Analysis-Methods/10-Experts/m-gta/02-Procedure]]

## 判断基準と品質確認の要約

1概念1ワークシートと定義・ヴァリエーションの対応、反対例の検討、ストーリーラインが概念とカテゴリーだけで書かれているか、分析テーマが練られているか、飽和化の判断の根拠。詳細：[[50-Analysis-Methods/10-Experts/m-gta/03-Quality]]

## よくある誤用と禁止事項

人数や頻度を結果として示す、切片化したコーディングの結果をM-GTAの結果とする、分析焦点者の範囲を超えて一般化する。実行定義の `prohibited_conclusions` を参照。

## 出力形式

研究テーマ・分析テーマ・分析焦点者、概念の一覧（分析ワークシート）、カテゴリーと概念の関係、結果図、ストーリーライン、理論的メモと飽和化の判断、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/m-gta/04-Applicability-and-Limits]]

## 参照ノートと主要文献

主要文献：[[50-Analysis-Methods/20-Literature/LIT-kinoshita-2007-mgta]]（本文確認）、[[50-Analysis-Methods/20-Literature/RES-mgta-society-official]]（公式ページ）。応用例：[[50-Analysis-Methods/20-Literature/LIT-iseki-2023-mgta-process]]（MBC患者21人の事例。方法の一般的定義を支える主要文献ではない）。事例一覧：[[50-Analysis-Methods/10-Experts/m-gta/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/m-gta/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-m-gta
definition_version: 1
knowledge_verified: 2026-09-15
title: M-GTAの専門家
role: methodology
analysis_method_ids:
  - mgta
registry_method_ids: []
school:
  default:
    id: kinoshita-mgta
    label: 修正版グラウンデッド・セオリー・アプローチ（木下）
  alternatives:
    - id: segmenting-gta
      label: 切片化を用いる他のグラウンデッド・セオリー（この定義の対象外）
scope:
  - 分析テーマと分析焦点者の視点からデータに着目し、概念を生成する
  - 概念の関係からカテゴリーを作り、変化のプロセスを結果図とストーリーラインで説明する
  - 限定された範囲で一般化しうる理論を生成する
out_of_scope:
  - text: 共通する意味のパターンの解釈的な生成
    handoff: exp-thematic-analysis
  - text: 少量のデータの段階的なコーディングと理論記述
    handoff: exp-scat
  - text: 類型ごとの人数や頻度の提示（度数的な結果表示はこの手法では成り立たない）
analysis_unit: 分析テーマと分析焦点者に沿って着目したデータの箇所（切片化しない）。発話IDはヴァリエーションの根拠として参照する
required_inputs:
  - 研究テーマと、プロセスを捉える形の分析テーマ（研究質問として登録）
  - 分析焦点者（分析メモに記録）
  - 1人分ずつ全体として読める面接記録
applicability_checks:
  - id: mgta-a1
    check: research_question_present
    severity: block
    params:
      allow_objective: false
    message: 分析テーマ（研究質問として登録）がないため、データのどこに着目するかを決められません。
    basis:
      - LIT-kinoshita-2007-mgta
      - RES-mgta-society-official
  - id: mgta-a2
    check: human_review
    severity: warn
    message: 分析焦点者（データを解釈するときに焦点を置く人）を設定したかを研究者が確認します。Gurumojiには専用の入力欄がないため、分析メモに記録してください。
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-a3
    check: human_review
    severity: warn
    message: 対象の現象がプロセス的な性格を持つか（ヒューマンサービス領域など）を研究者が確認します。
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-a4
    check: min_included_segments
    severity: block
    params:
      min: 1
    message: 分析できる発話がありません。
    basis:
      - implementation
  - id: mgta-a5
    check: analysis_basis_current
    severity: warn
    message: 逐語録の準備記録と分析の根拠が一致していません。
    basis:
      - implementation
  - id: mgta-a6
    check: method_rationale_present
    severity: warn
    message: 手法の選定理由が未入力です。M-GTAを選んだ理由（説明したいプロセス）を記録してください。
    basis:
      - implementation
procedure:
  - id: mgta-p1
    title: 研究テーマから分析テーマを設定し、分析焦点者を決める
    actor: researcher
    basis:
      - LIT-kinoshita-2007-mgta
      - RES-mgta-society-official
  - id: mgta-p2
    title: 1人分の記録の全体に目を通し、分析テーマと分析焦点者に照らして着目する箇所を選ぶ（切片化しない）
    actor: researcher
    basis:
      - LIT-kinoshita-2007-mgta
      - RES-mgta-society-official
  - id: mgta-p3
    title: 着目した箇所の意味を幾通りか検討し、定義として採用する解釈を決めて概念を生成する
    actor: researcher
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-p4
    title: 分析ワークシート（概念名、定義、ヴァリエーション、理論的メモ）に記入し、ヴァリエーション（具体例）の候補を集める
    actor: ai_draft
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-p5
    title: 反対例・類似例の候補を探し、複数の概念を同時並行で比較する
    actor: ai_draft
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-p6
    title: 採用しなかった解釈案や疑問を理論的メモに残す
    actor: researcher
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-p7
    title: 概念間の関係からカテゴリーを生成する
    actor: researcher
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-p8
    title: 理論的サンプリングで確認し、理論的飽和化を判断する
    actor: researcher
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-p9
    title: 結果図と、概念とカテゴリーだけで書くストーリーラインをまとめる
    actor: researcher
    basis:
      - LIT-kinoshita-2007-mgta
quality_checks:
  - id: mgta-q1
    check: human_review
    text: 1概念1ワークシートで、定義とヴァリエーションが対応しているか
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-q2
    check: human_review
    text: 反対例を検討し、採用しなかった解釈案を理論的メモに残したか
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-q3
    check: human_review
    text: ストーリーラインが、生成した概念とカテゴリーだけで書かれているか
    basis:
      - LIT-kinoshita-2007-mgta
  - id: mgta-q4
    check: human_review
    text: 分析テーマが練られているか（結果がすぐ出そうな設定になっていないか）
    basis:
      - RES-mgta-society-official
  - id: mgta-q5
    check: human_review
    text: 飽和化の判断の根拠（新たな重要概念が生成されない、確認すべき問題点がない）を記録したか
    basis:
      - LIT-kinoshita-2007-mgta
prohibited_conclusions:
  - 類型ごとの人数や頻度を分析結果として示さない
  - データを切片化してコード化した結果をM-GTAの結果としない
  - 分析焦点者と分析テーマの範囲を超えて理論を一般化しない
  - AIが示した具体例や反対例の候補を、研究者が生成した概念として示さない
output_sections:
  - 研究テーマ・分析テーマ・分析焦点者
  - 概念の一覧（分析ワークシート：定義とヴァリエーション）
  - カテゴリーと概念の関係
  - 結果図
  - ストーリーライン
  - 理論的メモと飽和化の判断
  - 限界（一般化の範囲）
ai_assist:
  allowed: true
  steps:
    - mgta-p4
    - mgta-p5
  reason: ""
  brief: M-GTAの補助として、研究者が登録したコード（概念）に当てはまる具体例（ヴァリエーション）の候補と、反対例・類似例の候補を示してください。分析テーマ（研究質問）と分析焦点者の視点から読み、データを細かく切り分けて機械的にコード化しないでください。概念の生成、定義、カテゴリー、飽和化の判断は研究者が行うため、見解は候補として書きます。人数や頻度を結果として述べないでください。定義に合わない可能性がある発話は、追加で確認する点に挙げてください。
literature:
  - LIT-kinoshita-2007-mgta
  - LIT-iseki-2023-mgta-process
  - RES-mgta-society-official
  - LIT-gilardi-2023-llm-annotation
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
  - 04-AI-Assistance-Boundaries
open_issues:
  - 木下の書籍の手順の詳細（結果図の描き方、カテゴリーの生成の具体例）を読んでいない
  - M-GTAの査読付きの方法論文献を確認していない（読んだのは講演に基づく紀要論文と研究会のページ）
  - Gurumojiには分析テーマ・分析焦点者・分析ワークシートの専用の入力欄がない
  - 理論的サンプリング（追加のデータ収集）はアプリの範囲外
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
