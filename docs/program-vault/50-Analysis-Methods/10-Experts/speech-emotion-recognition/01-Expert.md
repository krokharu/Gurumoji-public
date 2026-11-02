---
note_id: expert-speech-emotion-recognition-definition
note_type: expert-definition
expert_id: exp-speech-emotion-recognition
title: 音声感情推定の専門家
role: computational
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids: []
registry_method_ids:
  - audio_emotion
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/audio
---

# 音声感情推定の専門家（exp-speech-emotion-recognition）

## 担当範囲と担当外

発話音声への感情ラベルの推定結果を、モデル・学習データ・評価条件とともに集計し、カバー率と未推定を示す。本人の感情の判定、応答の意味、発話量は担当外。詳細：[[50-Analysis-Methods/10-Experts/speech-emotion-recognition/00-Overview]]

## 理論的背景と採用する流派

[文献] 「くしなだ」はJTES（Japanese Twitter-based Emotional Speech v1.1）で学習したS3PRL向けの音声感情認識モデルで、上流は `imprt/kushinada-hubert-large`（モデルカード）。HuBERTは自己教師ありの音声表現学習の方法（Hsu et al. 2021、要旨）。[実装判断] 既存の実装（くしなだ、いざなみ、両方）に従う。

## 適した研究目的・問い・データ

音声モデルの感情ラベルの分布を、発話の文脈を確認する手がかりとして使いたい場合。音声ファイルと話者分離の結果があるデータ。

## 必要な入力と前処理、分析単位

音声ファイル、話者分離と発話区間、推定結果（モデル名、リポジトリ、fold）。分析単位は話者分離後の発話音声の区間。

## 手順の要約

モデルと条件の記録 → 切り出し・推定・集計 → 短い区間・重なり・音質・未推定の確認 → 聴取確認と、推定と手修正を区別した報告。詳細：[[50-Analysis-Methods/10-Experts/speech-emotion-recognition/02-Procedure]]

## 判断基準と品質確認の要約

カバー率、両モデルの一致・不一致の扱い、評価セットの正解率の扱い、本人の感情と断定しないこと。詳細：[[50-Analysis-Methods/10-Experts/speech-emotion-recognition/03-Quality]]

## よくある誤用と禁止事項

ラベルを本人の感情や意図とする、モデルカードの正解率をこの会話の正確さとする、ラベルから発言内容の真偽や態度を述べる。

## 出力形式

モデル・版・学習データ・評価条件、話者・ラベル別の集計、カバー率と未推定、聴取確認の記録、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/speech-emotion-recognition/04-Applicability-and-Limits]]

## 参照ノートと主要文献

実装：[[50-Analysis-Methods/02-Semantic-and-Audio/02-Audio-Emotion]]。文献：[[50-Analysis-Methods/20-Literature/RES-kushinada-hubert-jtes-er-model-card]]（公式ページ）、[[50-Analysis-Methods/20-Literature/LIT-hsu-2021-hubert]]、[[50-Analysis-Methods/20-Literature/LIT-barrett-2019-emotional-expressions]]（要旨確認）、[[50-Analysis-Methods/20-Literature/LIT-park-2022-diarization-review]]（arXiv版の本文確認）、[[50-Analysis-Methods/20-Literature/LIT-zhang-2021-cross-corpus-ser]]（コーパス間評価の総説）、Baevski et al. 2020、Kosaka et al. 2024、Schuller 2018（書誌のみ）。事例：[[50-Analysis-Methods/10-Experts/speech-emotion-recognition/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/speech-emotion-recognition/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-speech-emotion-recognition
definition_version: 1
knowledge_verified: 2026-09-15
title: 音声感情推定の専門家
role: computational
analysis_method_ids: []
registry_method_ids:
  - audio_emotion
school:
  default:
    id: jtes-ssl-classifier
    label: JTESで学習した自己教師あり音声モデルによる感情分類（くしなだ／いざなみ）
  alternatives: []
scope:
  - 発話音声への4つの主ラベル（ang・hap・sad・neu）の推定結果を集計する
  - 話者・モデル・ラベル別の件数と発話秒数、カバー率、未推定を示す
  - 両モデルを使った場合の一致・不一致を示す
out_of_scope:
  - text: 本人が経験した感情、感情の強さ、意図の判定（音声モデルの分類からは判定できない）
  - text: 応答の意味と同意・不同意
    handoff: exp-focus-group-interaction
  - text: 発話量と参加の偏り
    handoff: exp-participation-balance
analysis_unit: 話者分離後の発話音声の区間
required_inputs:
  - 音声ファイル
  - 話者分離と発話区間
  - 感情推定の結果（モデル名、リポジトリ、fold）
applicability_checks:
  - id: ser-a1
    check: emotion_coverage_min
    severity: block
    params:
      min: 1
    message: 感情推定の結果がありません（推定済みの発話がありません）。
    basis:
      - implementation
  - id: ser-a2
    check: emotion_coverage_min
    severity: warn
    params:
      min: 80
    message: 感情推定のカバー率が80%未満です。未推定の発話を0件として集計に混ぜないでください（80%は実装上の目安）。
    basis:
      - implementation
  - id: ser-a3
    check: speaker_order_confirmed
    severity: warn
    message: 話者の確認が済んでいないため、切り出した音声の話者が誤っている可能性があります。
    basis:
      - LIT-park-2022-diarization-review
  - id: ser-a4
    check: human_review
    severity: warn
    message: 録音環境、マイク、発話の重なりが、学習データ（JTES）の条件と異なることを確認します。モデルカードの正解率はJTESでの評価です。
    basis:
      - RES-kushinada-hubert-jtes-er-model-card
procedure:
  - id: ser-p1
    title: モデル（くしなだ・いざなみ）、リポジトリ、fold、学習データを記録する
    actor: code
    basis:
      - RES-kushinada-hubert-jtes-er-model-card
  - id: ser-p2
    title: 発話音声を切り出して推定し、話者・モデル・ラベル別に集計する
    actor: code
    basis:
      - RES-kushinada-hubert-jtes-er-model-card
      - LIT-hsu-2021-hubert
  - id: ser-p3
    title: 短い区間、重なり、音質の不良、未推定の発話を確認する
    actor: researcher
    basis:
      - LIT-park-2022-diarization-review
      - implementation
  - id: ser-p4
    title: 必要な箇所を聴取で確認し、推定と手修正を区別して報告する
    actor: researcher
    basis:
      - LIT-barrett-2019-emotional-expressions
      - implementation
quality_checks:
  - id: ser-q1
    check: emotion_coverage_min
    params:
      min: 80
    text: 感情推定のカバー率が目安以上か
    basis:
      - implementation
  - id: ser-q2
    check: human_review
    text: 両モデルを使った場合、一致・不一致を片方のラベルで上書きせずに示したか
    basis:
      - implementation
  - id: ser-q3
    check: human_review
    text: 評価セットの正解率を、手元の会話での推定の正確さとして示していないか
    basis:
      - RES-kushinada-hubert-jtes-er-model-card
  - id: ser-q4
    check: human_review
    text: ラベルを本人の感情と断定していないか
    basis:
      - LIT-barrett-2019-emotional-expressions
prohibited_conclusions:
  - ラベルを、本人が経験した感情、感情の強さ、意図として述べない
  - モデルカードの正解率を、この会話での推定の正確さとして述べない
  - 感情ラベルの分布から、発言内容の真偽や参加者の態度を述べない
output_sections:
  - モデル・版・学習データ・評価条件
  - 話者・ラベル別の集計
  - カバー率と未推定
  - 聴取確認の記録
  - 限界
ai_assist:
  allowed: false
  steps: []
  reason: 音声感情推定は計算系の専門家で、ラベルは音声モデルが推定し、確認は研究者が聴取で行うため、AI見解を使いません。
  brief: ""
literature:
  - RES-kushinada-hubert-jtes-er-model-card
  - LIT-hsu-2021-hubert
  - LIT-baevski-2020-wav2vec2
  - LIT-kosaka-2024-emotional-speech-recognition
  - LIT-barrett-2019-emotional-expressions
  - LIT-schuller-2018-ser
  - LIT-park-2022-diarization-review
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
open_issues:
  - JTESの論文本文と収録条件（演技か自然な発話かなど）を確認していない
  - いざなみのモデルカードを確認していない
  - Kosaka et al. 2024は題名から音声認識（文字起こし）の論文と読め、既存の手法ノートの「JTESを用いた日本語感情音声認識」という位置づけと年（2023）が確認できていない
  - 会議やグループインタビューなど複数話者の会話での日本語音声感情認識の評価を確認していない
  - Schuller 2018は書誌のみの確認
  - 80%の目安は実装上の判断
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
