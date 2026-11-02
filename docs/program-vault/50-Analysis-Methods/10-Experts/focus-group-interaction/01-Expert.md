---
note_id: expert-focus-group-interaction-definition
note_type: expert-definition
expert_id: exp-focus-group-interaction
title: フォーカスグループの相互作用分析の専門家
role: methodology
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids:
  - interaction
registry_method_ids: []
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/focus-group
---

# フォーカスグループの相互作用分析の専門家（exp-focus-group-interaction）

## 担当範囲と担当外

参加者どうしの応答の連鎖（同意・不同意、補足、言い直し、意見の変化）と、司会者・グループ構成の影響を分析する。内容のカテゴリー化、発話量、時間構造は担当外。詳細：[[50-Analysis-Methods/10-Experts/focus-group-interaction/00-Overview]]

## 理論的背景と採用する流派

[文献] Grønkjær et al.（2011）は、会話分析の基本的な道具である隣接ペアと選好構造（好まれる応答＝受け入れ・同意、好まれない応答＝拒否・不同意）、説明、修復を用いて、相互作用が内容に与える影響と司会者の役割を分析する。[実装判断] この会話分析の道具による分析を既定にする。

## 適した研究目的・問い・データ

意見形成や合意・不同意の過程を問う研究。話者と発話の順序が確認された逐語録が必要。

## 必要な入力と前処理、分析単位

話者と順序を確認した逐語録、司会者の役割、研究質問。分析単位は発話の連鎖（隣接する発話の組と前後の文脈）で、根拠は複数の発話ID。

## 手順の要約

話者・順序・司会者の確認 → 内容とは別に扱う方針 → 隣接する発話の組の候補 → 選好構造・説明・修復の検討 → 不同意・少数意見・変化の記録 → 司会者と構成の影響 → 発話の連鎖と一緒に報告。詳細：[[50-Analysis-Methods/10-Experts/focus-group-interaction/02-Procedure]]

## 判断基準と品質確認の要約

根拠発話のリンク、個人の引用を相互作用から切り離さないこと、沈黙を同意としないこと、集団と個人の談話の区別。詳細：[[50-Analysis-Methods/10-Experts/focus-group-interaction/03-Quality]]

## よくある誤用と禁止事項

沈黙や相づちを同意とする、個人の引用を固定した意見として示す、話者未確認の逐語録で応答関係を確定する。実行定義の `prohibited_conclusions` を参照。

## 出力形式

研究質問と方針、話者・順序・司会者の確認状況、相互作用の所見（発話の連鎖と発話ID）、不同意・少数意見・変化、司会者と構成の影響、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/focus-group-interaction/04-Applicability-and-Limits]]

## 参照ノートと主要文献

主要文献：[[50-Analysis-Methods/20-Literature/LIT-gronkjaer-2011-fg-interaction]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-kitzinger-1994-focus-groups]]、[[50-Analysis-Methods/20-Literature/LIT-kidd-parshall-2000-fg-rigor]]、[[50-Analysis-Methods/20-Literature/LIT-onwuegbuzie-2009-fg-analysis]]。枠組みの適用例：[[50-Analysis-Methods/20-Literature/LIT-hermann-2024-fg-interaction-coding]]（本文確認）。事例一覧：[[50-Analysis-Methods/10-Experts/focus-group-interaction/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/focus-group-interaction/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-focus-group-interaction
definition_version: 1
knowledge_verified: 2026-09-15
title: フォーカスグループの相互作用分析の専門家
role: methodology
analysis_method_ids:
  - interaction
registry_method_ids: []
school:
  default:
    id: ca-informed-interaction
    label: 会話分析の道具（隣接ペア・選好構造・説明・修復）による相互作用の分析（Grønkjær et al. 2011）
  alternatives:
    - id: interaction-coding-scheme
      label: 相互作用のコーディング枠組みをテーマ分析と並行させる（Hermann et al. 2024の本文で確認した一事例）
    - id: micro-interlocutor
      label: マイクロ・インターロキュター分析（Onwuegbuzie et al. 2009、要旨のみ確認）
scope:
  - 参加者どうしの応答の連鎖（同意・不同意、補足、言い直し、意見の変化）を分析する
  - 司会者の働きかけとグループの構成が相互作用に与えた影響を検討する
  - 相互作用の所見を、根拠となる複数の発話と一緒に報告する
out_of_scope:
  - text: 語られた内容のカテゴリー化
    handoff: exp-qualitative-content-analysis
  - text: 発話量と参加の偏りの集計
    handoff: exp-participation-balance
  - text: 間・重なり・話者交替の時間的な構造
    handoff: exp-conversation-timing
analysis_unit: 発話の連鎖（隣接する発話の組と前後の文脈）。根拠は複数の発話ID
required_inputs:
  - 話者と発話の順序を確認した逐語録
  - 司会者の役割の登録
  - 研究質問
applicability_checks:
  - id: fgi-a1
    check: speaker_order_confirmed
    severity: block
    message: 話者と発話の順序が確認されていないため、応答関係を分析できません。
    basis:
      - LIT-gronkjaer-2011-fg-interaction
      - LIT-park-2022-diarization-review
  - id: fgi-a2
    check: min_participants
    severity: block
    params:
      min: 2
    message: 参加者が2人未満のため、参加者間の相互作用を分析できません。
    basis:
      - LIT-kitzinger-1994-focus-groups
  - id: fgi-a3
    check: unknown_speaker_ratio_max
    severity: warn
    params:
      max: 0.1
    message: 話者が不明な発話が10%を超えています（10%は実装上の目安）。
    basis:
      - implementation
  - id: fgi-a4
    check: research_question_present
    severity: warn
    message: 研究質問がありません。どの相互作用に注目するかの基準がありません。
    basis:
      - implementation
  - id: fgi-a5
    check: human_review
    severity: warn
    message: 司会者の質問・指名と、グループの構成（同質性・異質性）を解釈の前に確認します。
    basis:
      - LIT-gronkjaer-2011-fg-interaction
  - id: fgi-a6
    check: analysis_basis_current
    severity: warn
    message: 逐語録の準備記録と分析の根拠が一致していません。
    basis:
      - implementation
procedure:
  - id: fgi-p1
    title: 話者と順序、司会者の役割を確認する
    actor: researcher
    basis:
      - LIT-gronkjaer-2011-fg-interaction
      - LIT-park-2022-diarization-review
  - id: fgi-p2
    title: 内容の分析とは別の表で相互作用を扱う方針を決める
    actor: researcher
    basis:
      - LIT-kitzinger-1994-focus-groups
      - LIT-duggleby-2005-fg-interaction
  - id: fgi-p3
    title: 隣接する発話の組（提案と同意・不同意、質問と答え、補足、言い直し）の候補を見つける
    actor: ai_draft
    basis:
      - LIT-gronkjaer-2011-fg-interaction
  - id: fgi-p4
    title: 選好構造（好まれる応答・好まれない応答）、説明、修復の観点で応答を検討する
    actor: researcher
    basis:
      - LIT-gronkjaer-2011-fg-interaction
  - id: fgi-p5
    title: 不同意・少数意見・意見の変化の候補を、分析の資源として記録する
    actor: ai_draft
    basis:
      - LIT-gronkjaer-2011-fg-interaction
  - id: fgi-p6
    title: 司会者の働きかけとグループの構成が相互作用に与えた影響を検討する
    actor: researcher
    basis:
      - LIT-gronkjaer-2011-fg-interaction
      - LIT-morgan-1996-focus-groups
  - id: fgi-p7
    title: 相互作用の所見を、根拠となる発話の連鎖と一緒に報告する
    actor: researcher
    basis:
      - LIT-gronkjaer-2011-fg-interaction
quality_checks:
  - id: fgi-q1
    check: interaction_links_min
    params:
      min: 1
    text: 相互作用を根拠発話のリンクとして記録したか
    basis:
      - implementation
  - id: fgi-q2
    check: human_review
    text: 個人の引用を、相互作用から切り離して報告していないか
    basis:
      - LIT-gronkjaer-2011-fg-interaction
  - id: fgi-q3
    check: human_review
    text: 沈黙、発言の少なさ、相づちを同意とみなしていないか
    basis:
      - implementation
  - id: fgi-q4
    check: human_review
    text: 集団の談話を個人の意見として扱うかどうかを明示したか
    basis:
      - LIT-kidd-parshall-2000-fg-rigor
  - id: fgi-q5
    check: human_review
    text: 声色・間の長さ・重なり・表情を、音声や精密な転記なしに解釈していないか
    basis:
      - implementation
prohibited_conclusions:
  - 発言がないこと、沈黙、相づちを同意として述べない
  - 1人の発言の引用を、グループの相互作用から切り離して個人の固定した意見として示さない
  - 話者と順序が未確認の逐語録から応答関係を確定しない
  - AIが示した発話の組を、研究者が確認した相互作用として示さない
output_sections:
  - 研究質問と分析の方針（内容とは別に扱う）
  - 話者・順序・司会者の確認状況
  - 相互作用の所見（発話の連鎖と発話ID）
  - 不同意・少数意見・意見の変化
  - 司会者とグループ構成の影響
  - 限界
ai_assist:
  allowed: true
  steps:
    - fgi-p3
    - fgi-p5
  reason: ""
  brief: フォーカスグループの相互作用分析の補助として、参加者どうしの応答になっている発話の組（提案と同意・不同意、質問と答え、補足、言い直し）の候補と、不同意・少数意見・意見の変化の候補を示してください。各候補には、応答し合っている複数の発話を根拠として付けます。沈黙、発言の少なさ、相づちを同意と断定しないでください。司会者の質問と参加者の意見を区別し、応答関係の確定は研究者が行うため、見解は候補として書きます。
literature:
  - LIT-gronkjaer-2011-fg-interaction
  - LIT-kitzinger-1994-focus-groups
  - LIT-duggleby-2005-fg-interaction
  - LIT-onwuegbuzie-2009-fg-analysis
  - LIT-hermann-2024-fg-interaction-coding
  - LIT-nicholson-shrives-2022-fg-interaction
  - LIT-kidd-parshall-2000-fg-rigor
  - LIT-morgan-1996-focus-groups
  - LIT-sacks-1974-turn-taking
  - LIT-park-2022-diarization-review
  - LIT-poliandri-2023-online-focus-groups
  - LIT-gilardi-2023-llm-annotation
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
  - 04-AI-Assistance-Boundaries
open_issues:
  - Kitzinger 1994の本文を読めていない（出版社サイトが403）
  - Onwuegbuzie et al. 2009の枠組みの項目を確認していない（要旨のみ）
  - 日本語のフォーカスグループの相互作用分析の文献を確認していない
  - 非言語の情報（表情、声色）はGurumojiの逐語録にない
  - 10%の目安は実装上の判断
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
