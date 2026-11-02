---
note_id: expert-qualitative-content-analysis-definition
note_type: expert-definition
expert_id: exp-qualitative-content-analysis
title: 質的内容分析の専門家
role: methodology
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids:
  - qualitative_content
registry_method_ids: []
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# 質的内容分析の専門家（exp-qualitative-content-analysis）

## 担当範囲と担当外

語られた内容を、定義・例・規則を持つカテゴリーに体系的に整理する。担当外（テーマの解釈的な生成、相互作用、語の計数が中心の分析、ケース×テーマの行列）は、実行定義の `out_of_scope` の専門家へ移す。詳細：[[50-Analysis-Methods/10-Experts/qualitative-content-analysis/00-Overview]]

## 理論的背景と採用する流派

[文献] Mayring（2000）は、量的内容分析の方法上の強みを保ちながら、カテゴリーを中心に規則で統制された質的テキスト分析を示し、帰納的カテゴリー形成と演繹的カテゴリー適用を中心の手続きとする。Hsieh & Shannon（2005）は慣習的・有向的・要約的の3つのアプローチを区別する。[実装判断] 既定は帰納的カテゴリー形成。

## 適した研究目的・問い・データ

- 語られた意見・課題・ニーズをカテゴリーに整理したい。先行研究がない・知識が断片的なら帰納的、既存理論の検証や時期の比較なら演繹的（[文献] Elo & Kyngäs 2008）。
- 適さない：研究質問が非常に開かれていて探索的な場合、段階を追わない全体的な分析（[文献] Mayring 2000）。

## 必要な入力と前処理、分析単位

研究質問、カテゴリーの定義の基準（帰納的）またはコーディング・アジェンダ（演繹的）、準備を確認した逐語録。分析単位は発話で、意味単位が発話と一致しない場合は研究者が注釈で扱う（[実装判断]）。

## 手順の要約

研究質問と分析単位の決定 → 流派の選択 → 暫定カテゴリーの作成 → コーディング・アジェンダの作成（演繹的） → カテゴリーの割り当て → フィードバックによる見直しと主カテゴリー → 信頼性・信用性の確認 → 各段階を記述した報告。詳細：[[50-Analysis-Methods/10-Experts/qualitative-content-analysis/02-Procedure]]

## 判断基準と品質確認の要約

カテゴリーの定義と規則、コードの出所の記録、複数コーダーの確認の記録（アプリは係数を計算しない）、段階ごとの信用性。詳細：[[50-Analysis-Methods/10-Experts/qualitative-content-analysis/03-Quality]]

## よくある誤用と禁止事項

カテゴリーの件数を重要性や支持人数として述べる、AIの候補を確定したカテゴリーとして示す、計算していない一致係数を確認済みとする。実行定義の `prohibited_conclusions` を参照。

## 出力形式

研究質問と分析単位、流派とコードの出所、カテゴリーの一覧（定義・例・規則）、カテゴリーごとの根拠発話、反例・少数意見、信頼性・信用性の記録、限界。

## 説明できる範囲と限界

定義したカテゴリーに沿った内容の整理までを説明する。発話数から母集団の意見分布を推定しない。詳細：[[50-Analysis-Methods/10-Experts/qualitative-content-analysis/04-Applicability-and-Limits]]

## 参照ノートと主要文献

主要文献：[[50-Analysis-Methods/20-Literature/LIT-mayring-2000-qca]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-hsieh-shannon-2005-qca]]、[[50-Analysis-Methods/20-Literature/LIT-elo-kyngas-2008-qca]]、[[50-Analysis-Methods/20-Literature/LIT-elo-2014-qca-trustworthiness]]、[[50-Analysis-Methods/20-Literature/LIT-graneheim-lundman-2004-qca]]（いずれも要旨確認）。事例：[[50-Analysis-Methods/10-Experts/qualitative-content-analysis/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/qualitative-content-analysis/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-qualitative-content-analysis
definition_version: 1
knowledge_verified: 2026-09-15
title: 質的内容分析の専門家
role: methodology
analysis_method_ids:
  - qualitative_content
registry_method_ids: []
school:
  default:
    id: inductive-category-development
    label: 帰納的カテゴリー形成（Mayring 2000、慣習的アプローチ）
  alternatives:
    - id: deductive-category-application
      label: 演繹的カテゴリー適用（コーディング・アジェンダ、有向的アプローチ）
    - id: summative-approach
      label: 要約的アプローチ（数えた後に文脈を解釈）
scope:
  - 語られた内容を、定義・例・規則を持つカテゴリーに体系的に整理する
  - 顕在的内容と潜在的内容を区別して扱う
  - 流派ごとの信頼性・信用性の確認手順を示す
out_of_scope:
  - text: 経験に共通する意味のパターンを解釈的に生成する
    handoff: exp-thematic-analysis
  - text: その場の応答による意見の形成・変化を分析する
    handoff: exp-focus-group-interaction
  - text: 語の頻度・共起の比較を中心にした分析
    handoff: exp-quantitative-text-analysis
  - text: 話者やグループのケース×テーマの行列で比較する
    handoff: exp-framework-method
analysis_unit: 発話（turn）。意味単位が発話と一致しない場合は研究者が注釈で扱う
required_inputs:
  - 研究質問（カテゴリーの定義の基準を決めるため）
  - 帰納的な場合はカテゴリーの定義の基準、演繹的な場合はカテゴリーの定義・典型例・コーディング規則
  - 本文・区切り・話者を確認した逐語録
applicability_checks:
  - id: qca-a1
    check: research_question_present
    severity: block
    message: 研究質問（または研究目的）がないため、カテゴリーの定義の基準を決められません。
    basis:
      - LIT-mayring-2000-qca
  - id: qca-a2
    check: min_included_segments
    severity: block
    params:
      min: 1
    message: 分析できる発話がありません。
    basis:
      - implementation
  - id: qca-a3
    check: analysis_basis_current
    severity: warn
    message: 逐語録の準備記録と分析の根拠が一致していません。コードを付けた後に本文や確認状態が変わっています。
    basis:
      - implementation
  - id: qca-a4
    check: preparation_confirmed
    severity: warn
    message: 逐語録の準備（本文・区切り・話者）が確認済みではありません。データ収集と準備の記述が信用性の評価に必要です。
    basis:
      - LIT-elo-2014-qca-trustworthiness
  - id: qca-a5
    check: human_review
    severity: warn
    message: 研究質問が非常に開かれていて探索的な場合や、段階を追わない全体的な分析を予定する場合は、この手法が適しているかを研究者が確認します。
    basis:
      - LIT-mayring-2000-qca
procedure:
  - id: qca-p1
    title: 研究質問と分析の目的を定め、分析単位と、顕在的・潜在的内容のどちらを扱うかを決める
    actor: researcher
    basis:
      - LIT-mayring-2000-qca
      - LIT-graneheim-lundman-2004-qca
  - id: qca-p2
    title: 流派を選ぶ（先行研究がない・断片的なら帰納的、既存理論の検証や時期の比較なら演繹的）
    actor: researcher
    basis:
      - LIT-elo-kyngas-2008-qca
      - LIT-hsieh-shannon-2005-qca
  - id: qca-p3
    title: 定義の基準に沿って素材を読み、暫定的なカテゴリーの候補を作る
    actor: ai_draft
    basis:
      - LIT-mayring-2000-qca
  - id: qca-p4
    title: 演繹的な場合は、カテゴリーごとの定義・典型例・コーディング規則をコーディング・アジェンダにまとめる
    actor: researcher
    basis:
      - LIT-mayring-2000-qca
  - id: qca-p5
    title: カテゴリーを発話に割り当てる候補を作る（確定は研究者がコードブックで行う）
    actor: ai_draft
    basis:
      - LIT-mayring-2000-qca
  - id: qca-p6
    title: フィードバックでカテゴリーを見直し、主カテゴリーにまとめる
    actor: researcher
    basis:
      - LIT-mayring-2000-qca
  - id: qca-p7
    title: 採用した流派に応じて信頼性・信用性を確認し、その手順を記録する
    actor: researcher
    basis:
      - LIT-mayring-2000-qca
      - LIT-elo-2014-qca-trustworthiness
  - id: qca-p8
    title: 準備・組織化・報告の各段階を記述して報告する（要約的アプローチでは数えた後に文脈を解釈する）
    actor: researcher
    basis:
      - LIT-elo-kyngas-2008-qca
      - LIT-hsieh-shannon-2005-qca
quality_checks:
  - id: qca-q1
    check: codebook_min_codes
    params:
      min: 1
    text: カテゴリー（コード）がコードブックに定義されているか
    basis:
      - LIT-mayring-2000-qca
  - id: qca-q2
    check: codebook_definitions_complete
    text: すべてのカテゴリーに定義があるか（演繹的な場合は典型例と規則も）
    basis:
      - LIT-mayring-2000-qca
  - id: qca-q3
    check: coded_segments_min
    params:
      min: 1
    text: カテゴリーが発話に割り当てられているか
    basis:
      - implementation
  - id: qca-q4
    check: human_review
    text: コードの出所（データから、理論から、語の計数から）を記録したか
    basis:
      - LIT-hsieh-shannon-2005-qca
  - id: qca-q5
    check: human_review
    text: 複数のコーダーで確認した場合、その手順と結果を研究者が記録したか（アプリは一致係数を計算しない）
    basis:
      - LIT-mayring-2000-qca
  - id: qca-q6
    check: human_review
    text: 準備・組織化・報告の各段階の信用性を記述したか
    basis:
      - LIT-elo-2014-qca-trustworthiness
  - id: qca-q7
    check: human_review
    text: どのカテゴリーにも入らない発話、反例、少数意見を検討したか
    basis:
      - implementation
prohibited_conclusions:
  - カテゴリーの発話数を、意見の重要性や支持人数として述べない
  - 研究者が確認していないAIのカテゴリー候補を、確定したカテゴリーとして示さない
  - 一致係数を計算していないのに、コーダー間の信頼性が確認されたと示さない
  - 顕在的内容の記述と潜在的内容の解釈を区別せずに示さない
output_sections:
  - 研究質問と分析単位
  - 採用した流派とコードの出所
  - カテゴリーの一覧（定義・典型例・規則）
  - カテゴリーごとの根拠発話（発話ID）
  - 反例・少数意見・どのカテゴリーにも入らない発話
  - 信頼性・信用性の確認の記録
  - 限界
ai_assist:
  allowed: true
  steps:
    - qca-p3
    - qca-p5
  reason: ""
  brief: 質的内容分析の補助として、研究質問に沿ったカテゴリーの候補と、その候補に当てはまる発話を示してください。表に現れて語られた内容と、解釈を要する内容を区別して書きます。カテゴリーの定義・統合・確定は研究者が行うため、見解は候補として書き、発話数を重要性や支持人数として述べないでください。コードブックに定義があるカテゴリーは、その定義に合う発話だけを根拠にします。どのカテゴリーにも入らない発話や反例は、追加で確認する点に挙げてください。
literature:
  - LIT-mayring-2000-qca
  - LIT-hsieh-shannon-2005-qca
  - LIT-elo-kyngas-2008-qca
  - LIT-elo-2014-qca-trustworthiness
  - LIT-graneheim-lundman-2004-qca
  - LIT-krippendorff-2004-reliability
  - LIT-hayes-krippendorff-2007-alpha
  - LIT-gilardi-2023-llm-annotation
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
  - 04-AI-Assistance-Boundaries
open_issues:
  - 質的内容分析の日本語の方法論文献を今回の検索では見つけていない
  - Mayringの手順図（Fig.1, 2）と、本文が参照するドイツ語の教科書を読んでいない
  - Hsieh & Shannon 2005、Elo & Kyngäs 2008、Elo et al. 2014、Graneheim & Lundman 2004は要旨だけを確認した
  - 一致係数（κ、αなど）の選び方の文献（Krippendorff 2004ほか）は書誌のみの確認
  - Gurumojiの分析単位は発話に固定され、意味単位の設定を支援していない
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
