---
note_id: expert-participation-balance-definition
note_type: expert-definition
expert_id: exp-participation-balance
title: 参加バランスの専門家
role: computational
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids: []
registry_method_ids:
  - participation
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/conversation
---

# 参加バランスの専門家（exp-participation-balance）

## 担当範囲と担当外

話者・属性群ごとの発話量と、参加の偏りの指標を記述し、確認の候補を示す。応答の意味、時間構造、検定は担当外。詳細：[[50-Analysis-Methods/10-Experts/participation-balance/00-Overview]]

## 理論的背景と採用する流派

[実装判断] Gurumojiの集計（`participation`）の定義に従う記述的な集計で、特定の文献の手法を実装したものではない。参加の分布の古典（[[50-Analysis-Methods/20-Literature/LIT-stephan-mishler-1952-participation|Stephan & Mishler 1952]]、書誌のみ）と、ターン交替の組織（[[50-Analysis-Methods/20-Literature/LIT-sacks-1974-turn-taking|Sacks et al. 1974]]、要旨）を関連文献として記録する。

## 適した研究目的・問い・データ

誰がどれだけ話したかを、解釈の前提として確認したい場合。話者ラベルと役割が登録され、時刻が有効な逐語録。

## 必要な入力と前処理、分析単位

話者ラベルと役割、有効な時刻、分母の設定（参加者のみ／全話者）。分析単位は話者と属性群。

## 手順の要約

役割と分母の決定 → 発話量の集計 → 偏りの指標 → 司会者の働きかけとグループ構成と合わせた確認。詳細：[[50-Analysis-Methods/10-Experts/participation-balance/02-Procedure]]

## 判断基準と品質確認の要約

分母・役割・除外の明示、話者分離の誤りの確認、低参加を関与の低さと解釈しないこと。詳細：[[50-Analysis-Methods/10-Experts/participation-balance/03-Quality]]

## よくある誤用と禁止事項

発話量を影響力・重要性・議論の質とする、偏りの指標を集団の成果と結び付ける、発言の少ない参加者を同意したとみなす。

## 出力形式

分母・役割・除外の条件、話者・属性群の集計表、偏りの指標、確認の候補と文脈、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/participation-balance/04-Applicability-and-Limits]]

## 参照ノートと主要文献

実装：[[50-Analysis-Methods/04-Conversation/01-Participation]]。文献：[[50-Analysis-Methods/20-Literature/LIT-gronkjaer-2011-fg-interaction]]（本文確認）、[[50-Analysis-Methods/20-Literature/LIT-park-2022-diarization-review]]（arXiv版の本文確認）、[[50-Analysis-Methods/20-Literature/LIT-woolley-2010-collective-intelligence]]（要旨確認）。事例：[[50-Analysis-Methods/10-Experts/participation-balance/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/participation-balance/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-participation-balance
definition_version: 1
knowledge_verified: 2026-09-15
title: 参加バランスの専門家
role: computational
analysis_method_ids: []
registry_method_ids:
  - participation
school:
  default:
    id: descriptive-participation-metrics
    label: 発話量と参加の偏りの記述（Gurumojiの集計）
  alternatives: []
scope:
  - 話者・属性群ごとの発話数、発話時間、割合を記述する
  - 参加の偏りの指標（Gini係数、正規化evenness、HHI、最大参加者比）を示す
  - 発言の少ない参加者や発話時間の集中を、確認の候補として示す
out_of_scope:
  - text: 応答による意見の形成と、発言の意味
    handoff: exp-focus-group-interaction
  - text: 間・重なり・話者交替の時間構造
    handoff: exp-conversation-timing
  - text: 群の差の統計的検定
    handoff: exp-group-comparison-statistics
analysis_unit: 話者（司会者・運営役を分母から除く設定あり）と属性群。値は発話の集計
required_inputs:
  - 話者ラベルと役割の登録
  - 有効な時刻
  - 分母の設定（参加者のみ、または全話者）
applicability_checks:
  - id: part-a1
    check: min_speakers
    severity: block
    params:
      min: 2
    message: 話者が1人以下のため、参加の偏りを算出できません。
    basis:
      - implementation
  - id: part-a2
    check: speaker_order_confirmed
    severity: warn
    message: 話者の確認が済んでいないため、話者ラベルの誤り（取り違え・重なり）が発話量に影響している可能性があります。
    basis:
      - LIT-park-2022-diarization-review
  - id: part-a3
    check: unknown_speaker_ratio_max
    severity: warn
    params:
      max: 0.1
    message: 話者が不明な発話が10%を超えています（10%は実装上の目安）。
    basis:
      - implementation
  - id: part-a4
    check: valid_time_ratio_min
    severity: warn
    params:
      min: 0.9
    message: 有効な時刻を持つ発話が90%未満のため、発話時間の集計が不正確です（90%は実装上の目安）。
    basis:
      - implementation
  - id: part-a5
    check: human_review
    severity: warn
    message: 司会者・観察者の役割が正しく登録され、分母から除く設定が研究の目的に合っているかを確認します。
    basis:
      - implementation
procedure:
  - id: part-p1
    title: 役割と分母（参加者のみ、または全話者）を決める
    actor: researcher
    basis:
      - implementation
  - id: part-p2
    title: 話者・属性群ごとに発話数・発話時間・割合を集計する
    actor: code
    basis:
      - implementation
  - id: part-p3
    title: 同じ話者の集合から、偏りの指標（Gini係数、正規化evenness、HHI、最大参加者比）を計算する
    actor: code
    basis:
      - implementation
  - id: part-p4
    title: 低参加や発話時間の集中の候補を、司会者の働きかけとグループ構成と合わせて読む
    actor: researcher
    basis:
      - LIT-gronkjaer-2011-fg-interaction
      - LIT-onwuegbuzie-2009-fg-analysis
quality_checks:
  - id: part-q1
    check: unknown_speaker_ratio_max
    params:
      max: 0.1
    text: 話者が不明な発話の割合が目安以下か
    basis:
      - implementation
  - id: part-q2
    check: human_review
    text: 分母と役割、除外した発話を結果と一緒に示したか
    basis:
      - implementation
  - id: part-q3
    check: human_review
    text: 低参加を、関与の低さや同意と解釈していないか
    basis:
      - LIT-gronkjaer-2011-fg-interaction
  - id: part-q4
    check: human_review
    text: 話者分離の誤りの可能性を確認したか
    basis:
      - LIT-park-2022-diarization-review
prohibited_conclusions:
  - 発話量を、影響力、重要性、満足度、議論の質の指標として述べない
  - 偏りの指標を、他の研究で示された集団の成果（集合知など）と結び付けて評価しない
  - 発言が少ない参加者を、関心が低い、または同意したと述べない
output_sections:
  - 分母・役割・除外の条件
  - 話者・属性群の集計表
  - 偏りの指標
  - 確認の候補（低参加・集中）と文脈
  - 限界
ai_assist:
  allowed: false
  steps: []
  reason: 参加バランスは計算系の専門家で、値はコードで計算し、説明は専門家定義から作るため、AI見解を使いません。
  brief: ""
literature:
  - LIT-stephan-mishler-1952-participation
  - LIT-woolley-2010-collective-intelligence
  - LIT-sacks-1974-turn-taking
  - LIT-gronkjaer-2011-fg-interaction
  - LIT-onwuegbuzie-2009-fg-analysis
  - LIT-park-2022-diarization-review
  - LIT-poliandri-2023-online-focus-groups
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
open_issues:
  - Gini係数・evenness・HHIを会話の参加の偏りに使うことの妥当性を検討した文献を確認していない
  - Stephan & Mishler 1952は書誌のみの確認
  - 10%・90%の目安は実装上の判断
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
