---
note_id: expert-thematic-analysis-definition
note_type: expert-definition
expert_id: exp-thematic-analysis
title: テーマ分析の専門家
role: methodology
status: current
definition_version: 2
knowledge_verified: 2026-09-28
analysis_method_ids:
  - thematic
registry_method_ids: []
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# テーマ分析の専門家（exp-thematic-analysis）

## 担当範囲と担当外

研究質問に関わる意味のパターン（テーマ）を、研究者の解釈によって生成・見直し・定義し、報告する。自動クラスタ、カテゴリーの体系的な整理と一致の確認、相互作用は担当外。詳細：[[50-Analysis-Methods/10-Experts/thematic-analysis/00-Overview]]

## 理論的背景と採用する流派

[文献] Braun & Clarke（2006）はTAを理論的な裏付けを持つ柔軟な方法として示す。Byrne（2022、本文確認）も、分析者はテーマの捉え方、帰納的か演繹的か、意味的か潜在的か、認識論だけでなく、経験的か批判的かを検討し、その選択を研究質問に結び付けると整理する。著者らは後に自分たちのTAを再帰的TAと名付け、他の2つの形と区別する（岡ほか 2022）。[実装判断] 既定は再帰的TA。

## 適した研究目的・問い・データ

経験・考え方・意味づけのパターンを解釈的に明らかにしたい研究。データはセット全体を研究者が読み込めることが前提。テーマの頻度や代表性を示したい研究には合わない（[文献] 岡ほか 2022）。

## 必要な入力と前処理、分析単位

研究質問、分析前の理論的判断の記録（本質主義―構築主義、経験的―批判的、帰納的―演繹的、意味的―潜在的）、聞こえたとおりに書き起こした逐語録（[文献] 岡ほか 2022、p.149；Byrne 2022、PDF pp.1394–1397）。テーマは発話ごとに付く値ではなく、データセット全体を対象に、発話を根拠として参照する。

## 手順の要約

データに精通する → コーディング → 初期テーマの生成 → テーマの開発とレビュー → テーマの磨き上げ・定義と命名 → 報告書の作成（6フェーズ）。詳細：[[50-Analysis-Methods/10-Experts/thematic-analysis/02-Procedure]]

## 判断基準と品質確認の要約

15の基準のチェックリスト、5つの落とし穴。再帰的TAでは、評定者間一致・テーマの頻度・飽和を品質の根拠にしない。詳細：[[50-Analysis-Methods/10-Experts/thematic-analysis/03-Quality]]

## よくある誤用と禁止事項

インタビューガイドの質問をテーマにする、テーマが浮かび上がったと書く、発話数でテーマの重要性を示す、意味クラスタをテーマとする。実行定義の `prohibited_conclusions` を参照。

## 出力形式

研究質問と分析前の判断、TAの形、テーマの一覧（定義と名前）、テーマごとの語りとデータの抜粋（発話ID）、テーマ間の関係、品質確認の記録、限界。

## 説明できる範囲と限界

研究者の解釈として生成したテーマまでを説明する。詳細：[[50-Analysis-Methods/10-Experts/thematic-analysis/04-Applicability-and-Limits]]

## 参照ノートと主要文献

主要文献：[[50-Analysis-Methods/20-Literature/LIT-braun-clarke-2006-thematic]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-oka-2022-reflexive-ta-ja]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-braun-clarke-2021-one-size]]、[[50-Analysis-Methods/20-Literature/LIT-byrne-2022-reflexive-ta]]（本文§3.1–3.2.6確認）。事例：[[50-Analysis-Methods/10-Experts/thematic-analysis/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-28。未解決事項：[[50-Analysis-Methods/10-Experts/thematic-analysis/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-thematic-analysis
definition_version: 2
knowledge_verified: 2026-09-28
title: テーマ分析の専門家
role: methodology
analysis_method_ids:
  - thematic
registry_method_ids: []
school:
  default:
    id: reflexive-ta
    label: 再帰的テーマ分析（Braun & Clarke）
  alternatives:
    - id: codebook-ta
      label: コードブック型テーマ分析
    - id: coding-reliability-ta
      label: コーディングの信頼性型テーマ分析
scope:
  - 研究質問に関わる意味のパターン（テーマ）を研究者の解釈によって生成する
  - 意味的水準と潜在的水準のどちらでテーマを捉えるかを扱う
  - 分析前の理論的前提（本質主義／構築主義、経験的／批判的、帰納的／演繹的、意味的／潜在的）を研究質問に合わせて記録する
  - 15の基準と5つの落とし穴に沿った品質確認を示す
out_of_scope:
  - text: 埋め込みによる意味の近い発話の自動的なまとまり
    handoff: exp-embedding-topic-exploration
  - text: 定義・規則を持つカテゴリーへの整理とコーダー間の一致の確認
    handoff: exp-qualitative-content-analysis
  - text: その場の応答による意見の形成・変化
    handoff: exp-focus-group-interaction
  - text: ケース×テーマの行列による比較
    handoff: exp-framework-method
analysis_unit: データセット全体（テーマは発話ごとの値ではない）。根拠として発話IDを参照する
required_inputs:
  - 研究質問
  - 分析前の判断の記録（本質主義か構築主義か、経験的か批判的か、帰納的か演繹的か、意味的か潜在的か）
  - 聞こえたとおりに書き起こした逐語録
applicability_checks:
  - id: ta-a1
    check: research_question_present
    severity: block
    message: 研究質問（または研究目的）がないため、何をテーマとみなすかを決められません。
    basis:
      - LIT-braun-clarke-2006-thematic
  - id: ta-a2
    check: min_included_segments
    severity: block
    params:
      min: 1
    message: 分析できる発話がありません。
    basis:
      - implementation
  - id: ta-a3
    check: analysis_basis_current
    severity: warn
    message: 逐語録の準備記録と分析の根拠が一致していません。
    basis:
      - implementation
  - id: ta-a4
    check: human_review
    severity: warn
    message: 分析前の判断（本質主義か構築主義か、経験的か批判的か、帰納的か演繹的か、意味的か潜在的か）と、研究質問への適合を研究者が確認します。
    basis:
      - LIT-braun-clarke-2006-thematic
      - LIT-byrne-2022-reflexive-ta
  - id: ta-a5
    check: human_review
    severity: warn
    message: 採用するテーマ分析の形（再帰的、コードブック型、コーディングの信頼性型）を研究者が選びます。形によって品質基準が異なります。
    basis:
      - LIT-braun-clarke-2021-one-size
      - LIT-oka-2022-reflexive-ta-ja
  - id: ta-a6
    check: human_review
    severity: warn
    message: 書き起こしから言い始めの「えー」や言い淀み、間などを取り除いた本文を分析に使っていないかを確認します。
    basis:
      - LIT-oka-2022-reflexive-ta-ja
procedure:
  - id: ta-p1
    title: データに精通する（コーディングの前にデータセット全体を少なくとも1回読む）
    actor: researcher
    basis:
      - LIT-oka-2022-reflexive-ta-ja
      - LIT-braun-clarke-2006-thematic
  - id: ta-p2
    title: コーディング（研究質問に関わる特徴に初期コードを付ける）
    actor: ai_draft
    basis:
      - LIT-oka-2022-reflexive-ta-ja
      - LIT-braun-clarke-2006-thematic
  - id: ta-p3
    title: 初期テーマの生成（コードから潜在的なテーマの候補を作る）
    actor: ai_draft
    basis:
      - LIT-oka-2022-reflexive-ta-ja
  - id: ta-p4
    title: テーマの開発とレビュー（コード化したデータとデータセット全体に照らして見直す）
    actor: researcher
    basis:
      - LIT-oka-2022-reflexive-ta-ja
      - LIT-braun-clarke-2006-thematic
  - id: ta-p5
    title: テーマの磨き上げ、定義と命名
    actor: researcher
    basis:
      - LIT-oka-2022-reflexive-ta-ja
  - id: ta-p6
    title: 報告書の作成（分析の語りとデータの抜粋を織り合わせる）
    actor: researcher
    basis:
      - LIT-oka-2022-reflexive-ta-ja
quality_checks:
  - id: ta-q1
    check: human_review
    text: 15の基準のチェックリストに沿って手順を確認したか
    basis:
      - LIT-braun-clarke-2006-thematic
      - LIT-oka-2022-reflexive-ta-ja
  - id: ta-q2
    check: human_review
    text: インタビューガイドの質問をそのままテーマにしていないか
    basis:
      - LIT-braun-clarke-2006-thematic
      - LIT-oka-2022-reflexive-ta-ja
  - id: ta-q3
    check: human_review
    text: テーマが機能しているか（テーマ間の重なり、内部の一貫性、例の十分さ）
    basis:
      - LIT-braun-clarke-2006-thematic
      - LIT-oka-2022-reflexive-ta-ja
  - id: ta-q4
    check: human_review
    text: データと主張、理論や研究質問とTAの形が一致しているか
    basis:
      - LIT-braun-clarke-2006-thematic
      - LIT-oka-2022-reflexive-ta-ja
  - id: ta-q5
    check: human_review
    text: 再帰的TAで、評定者間一致・テーマの頻度・飽和を品質の根拠にしていないか
    basis:
      - LIT-oka-2022-reflexive-ta-ja
      - LIT-braun-clarke-2021-one-size
  - id: ta-q6
    check: human_review
    text: テーマが「浮かび上がった」という受け身の記述をしていないか
    basis:
      - LIT-braun-clarke-2006-thematic
      - LIT-oka-2022-reflexive-ta-ja
prohibited_conclusions:
  - テーマがデータから「浮かび上がった」と書かない（研究者の解釈として書く）
  - 再帰的TAで、テーマの発話数や話者数を重要性や代表性の根拠にしない
  - インタビューガイドの質問をテーマとして報告しない
  - Transformerの意味クラスタやAIの候補を、確定したテーマとして示さない
output_sections:
  - 研究質問と分析前の判断
  - 採用したテーマ分析の形
  - テーマの一覧（定義と名前）
  - テーマごとの分析の語りとデータの抜粋（発話ID）
  - テーマ間の関係
  - 品質確認の記録（15の基準、落とし穴）
  - 限界
ai_assist:
  allowed: true
  steps:
    - ta-p2
    - ta-p3
  reason: ""
  brief: テーマ分析（既定は再帰的テーマ分析）の補助として、研究質問に関わる初期コードの候補と、コードをまとめたテーマの候補を示してください。テーマは研究者の解釈によって生成・確定されるものなので、見解は候補として書き、「テーマが浮かび上がった」とは書きません。インタビューの質問項目をそのままテーマにしないでください。分析前の理論的判断（本質主義／構築主義、経験的／批判的、帰納的／演繹的、意味的／潜在的）と研究質問との適合は人が決めます。発話数や話者数をテーマの重要性として述べず、評定者間一致や飽和には触れません。テーマ間の重なりや、どのテーマにも合わない発話は、追加で確認する点に挙げてください。
literature:
  - LIT-braun-clarke-2006-thematic
  - LIT-oka-2022-reflexive-ta-ja
  - LIT-braun-clarke-2021-one-size
  - LIT-byrne-2022-reflexive-ta
  - LIT-hermann-2024-fg-interaction-coding
  - LIT-gilardi-2023-llm-annotation
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
  - 04-AI-Assistance-Boundaries
open_issues:
  - Braun & Clarkeの書籍を読んでおらず、最新の6フェーズの記述と2006年の論文との差を本文で確認していない
  - 岡ほか 2022で、フェーズ2とフェーズ4の具体的な問いの記述位置を特定していない
  - グループインタビューで相互作用をテーマの検討に組み込む方法（Hermann et al. 2024）は要旨だけを確認した
  - コードブック型・コーディングの信頼性型TAの手順は、この定義に含めていない（流派として記録のみ）
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
