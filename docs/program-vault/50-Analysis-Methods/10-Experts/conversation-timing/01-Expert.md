---
note_id: expert-conversation-timing-definition
note_type: expert-definition
expert_id: exp-conversation-timing
title: 会話の時間構造の専門家
role: computational
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids: []
registry_method_ids:
  - conversation_dynamics
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/conversation
---

# 会話の時間構造の専門家（exp-conversation-timing）

## 担当範囲と担当外

タイムスタンプから、話者遷移、平均の間、無音の候補、重なりの候補、時間区間ごとの推移を計算し、候補として示す。無音や重なりの意味、応答の連鎖、発話量の偏りは担当外。詳細：[[50-Analysis-Methods/10-Experts/conversation-timing/00-Overview]]

## 理論的背景と採用する流派

[文献] 会話のターン交替は局所的に管理される組織として特徴づけられる（Sacks et al. 1974、要旨）。[実装判断] Gurumojiの集計（`conversation_dynamics`）はタイムスタンプからの候補抽出で、会話分析のターン交替の分析そのものではない。

## 適した研究目的・問い・データ

会話の時間的な流れを概観し、音声で確認すべき区間を探したい場合。有効な時刻を持つ逐語録。

## 必要な入力と前処理、分析単位

有効な開始・終了時刻、話者ラベル、しきい値（無音3秒、重なり0.2秒、時間区間300秒が既定）。分析単位は文字起こしのセグメントの時刻。

## 手順の要約

しきい値の決定と記録 → 遷移・無音・重なり・時間区間の計算 → 候補区間を音声と前後の発話で確認 → 件数と意味を分けて報告。詳細：[[50-Analysis-Methods/10-Experts/conversation-timing/02-Procedure]]

## 判断基準と品質確認の要約

しきい値と区間幅の明示、打ち切りと無効時刻の明示、音声での確認、有効な時刻の割合。詳細：[[50-Analysis-Methods/10-Experts/conversation-timing/03-Quality]]

## よくある誤用と禁止事項

無音を同意・熟考、重なりを遮り・対立、遷移の件数を影響関係とする、ミリ秒の差を解釈する。

## 出力形式

しきい値と時間区間の条件、遷移表、無音・重なりの候補（時刻と前後の発話ID）、時間区間の推移、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/conversation-timing/04-Applicability-and-Limits]]

## 参照ノートと主要文献

実装：[[50-Analysis-Methods/04-Conversation/02-Conversation-Dynamics]]。文献：[[50-Analysis-Methods/20-Literature/LIT-stivers-2009-turn-taking]]、[[50-Analysis-Methods/20-Literature/LIT-levinson-torreira-2015-timing]]（出版社PDF本文確認）、[[50-Analysis-Methods/20-Literature/LIT-sacks-1974-turn-taking]]（要旨確認）、[[50-Analysis-Methods/20-Literature/LIT-heldner-edlund-2010-pauses]]（要旨の一部）、[[50-Analysis-Methods/20-Literature/LIT-park-2022-diarization-review]]（arXiv版の本文確認）。事例：[[50-Analysis-Methods/10-Experts/conversation-timing/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/conversation-timing/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-conversation-timing
definition_version: 1
knowledge_verified: 2026-09-15
title: 会話の時間構造の専門家
role: computational
analysis_method_ids: []
registry_method_ids:
  - conversation_dynamics
school:
  default:
    id: timestamp-based-candidates
    label: タイムスタンプからの遷移・無音・重なりの候補抽出（Gurumojiの集計）
  alternatives: []
scope:
  - 話者遷移の表と、話者間の平均の間を計算する
  - 長い無音と発話の重なりの候補を、しきい値とともに示す
  - 時間区間ごとの発話量の推移を示す
out_of_scope:
  - text: 応答の連鎖と、同意・不同意の意味
    handoff: exp-focus-group-interaction
  - text: 発話量と参加の偏り
    handoff: exp-participation-balance
analysis_unit: 文字起こしのセグメントの開始・終了時刻
required_inputs:
  - 有効な開始・終了時刻
  - 話者ラベル
  - しきい値（無音、重なり、時間区間）
applicability_checks:
  - id: time-a1
    check: valid_time_ratio_min
    severity: block
    params:
      min: 0.5
    message: 有効な時刻を持つ発話が半数未満のため、時間構造を分析しません（50%は実装上の目安）。
    basis:
      - implementation
  - id: time-a2
    check: valid_time_ratio_min
    severity: warn
    params:
      min: 0.95
    message: 有効な時刻を持たない発話が5%を超えています。遷移・無音・重なりの候補に抜けがあります（95%は実装上の目安）。
    basis:
      - implementation
  - id: time-a3
    check: speaker_order_confirmed
    severity: warn
    message: 話者の確認が済んでいないため、話者遷移と重なりの候補に話者分離の誤りが含まれる可能性があります。
    basis:
      - LIT-park-2022-diarization-review
  - id: time-a4
    check: min_speakers
    severity: block
    params:
      min: 2
    message: 話者が1人以下のため、話者遷移を算出できません。
    basis:
      - implementation
  - id: time-a5
    check: human_review
    severity: warn
    message: 文字起こしのセグメント境界と時刻の精度を、音声で確認できるかを確認します。会話の間はミリ秒単位の現象として研究されています。
    basis:
      - LIT-stivers-2009-turn-taking
      - implementation
procedure:
  - id: time-p1
    title: しきい値（無音、重なり、時間区間）を決めて記録する
    actor: researcher
    basis:
      - implementation
  - id: time-p2
    title: 話者遷移・無音の候補・重なりの候補・時間区間の集計を計算する
    actor: code
    basis:
      - implementation
  - id: time-p3
    title: 候補の区間を音声と前後の発話で確認する
    actor: researcher
    basis:
      - LIT-heldner-edlund-2010-pauses
      - implementation
  - id: time-p4
    title: 遷移の件数と、遷移の社会的な意味を分けて報告する
    actor: researcher
    basis:
      - LIT-sacks-1974-turn-taking
quality_checks:
  - id: time-q1
    check: valid_time_ratio_min
    params:
      min: 0.95
    text: 有効な時刻を持つ発話の割合が目安以上か
    basis:
      - implementation
  - id: time-q2
    check: human_review
    text: しきい値と、要求した時間区間の幅と実際の幅を結果に示したか
    basis:
      - implementation
  - id: time-q3
    check: human_review
    text: 候補の上限による打ち切りと、0秒・無効な時刻の発話を示したか
    basis:
      - implementation
  - id: time-q4
    check: human_review
    text: 無音と重なりの候補を音声で確認したか
    basis:
      - implementation
prohibited_conclusions:
  - 無音を、同意・熟考・不参加として述べない
  - 重なりを、遮りや対立として述べない
  - 話者遷移の件数を、影響関係として述べない
  - 文字起こしの時刻から得た短い間の差を、文化差や態度として解釈しない
output_sections:
  - しきい値と時間区間の条件
  - 遷移表
  - 無音・重なりの候補（時刻と前後の発話ID）
  - 時間区間ごとの推移
  - 限界（時刻の精度・話者分離）
ai_assist:
  allowed: false
  steps: []
  reason: 会話の時間構造は計算系の専門家で、値はコードで計算するため、AI見解を使いません。
  brief: ""
literature:
  - LIT-sacks-1974-turn-taking
  - LIT-stivers-2009-turn-taking
  - LIT-levinson-torreira-2015-timing
  - LIT-heldner-edlund-2010-pauses
  - LIT-park-2022-diarization-review
  - LIT-nicholson-shrives-2022-fg-interaction
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
open_issues:
  - Heldner & Edlund 2010は要旨の一部だけを確認し、既存ノートの記述（閾値・統計処理の問題）を裏付けていない
  - 日本語の会話のターン間の間や相づちの研究を確認していない
  - 話者分離の誤りが遷移数や重なりの候補に与える影響を扱った研究を確認していない
  - 50%・95%の目安と、既定の3秒・0.2秒は実装上の判断
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
