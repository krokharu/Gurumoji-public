---
note_id: expert-embedding-topic-exploration-definition
note_type: expert-definition
expert_id: exp-embedding-topic-exploration
title: 埋め込みによるテーマ探索の専門家
role: computational
status: current
definition_version: 2
knowledge_verified: 2026-09-15
analysis_method_ids: []
registry_method_ids:
  - transformer_topics
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/semantic
---

# 埋め込みによるテーマ探索の専門家（exp-embedding-topic-exploration）

## 担当範囲と担当外

文埋め込みとK-meansで意味の近い発話のまとまりを探索し、仮ラベル、代表発話、外れ値、話者分布、時間推移、相づちの候補を示す。テーマ数は自動選択のほか、候補一覧から研究者が選ぶこともできる。研究者が定義したテーマへ、意味が最も近い発話を候補として割り当てることもできる。テーマの確定、KJ法のグループ編成、語の頻度、相互作用の意味は担当外。詳細：[[50-Analysis-Methods/10-Experts/embedding-topic-exploration/00-Overview]]

## 理論的背景と採用する流派

[文献] 文埋め込みをコサイン類似度で比べ、類似検索やクラスタリングに使う考え方（Reimers & Gurevych 2019、要旨）。平均シルエット幅はクラスタリングの妥当性の評価になり、クラスタ数の選択に使える可能性があるとされる（Rousseeuw 1987、要旨）。[文献] 自動的な方法は精読の代わりにならず、問題ごとの検証が必要（Grimmer & Stewart 2013、要旨）。[実装判断] multilingual-e5-smallとK-meansの既存の実装に従う。

## 適した研究目的・問い・データ

研究者がデータを読み返す入口として、意味の近い発話のまとまりを探索したい場合。

## 必要な入力と前処理、分析単位

入力変更後に更新されたTransformerテーマ分析の結果、モデル名・版・seed。分析単位は文脈付き発話（短い断片は同じ話者の3秒以内の隣接発話で補う）。

## 手順の要約

対象の選択と文脈補完の確認 → 埋め込み・K-means・シルエットによるテーマ数の選択（または候補一覧からの選択、あるいは研究者が定義したテーマへの割り当て） → 代表発話と外れ値を原文で読み仮ラベルを見直す → 併合・分割・除外の判断と探索的な報告。詳細：[[50-Analysis-Methods/10-Experts/embedding-topic-exploration/02-Procedure]]

## 判断基準と品質確認の要約

シルエット係数の目安、モデルと条件の記録、原文の確認、相づちの応答先を賛同と読まないこと。詳細：[[50-Analysis-Methods/10-Experts/embedding-topic-exploration/03-Quality]]

## よくある誤用と禁止事項

クラスタをテーマ分析のテーマやKJ法のグループとする、類似度から合意や重要性を述べる、シルエットをテーマの妥当性とする、BERTopicと表示する、手動で定義したテーマへの割り当てを妥当性が確認された分類として示す。

## 出力形式

テーマの決め方（自動・候補から選択・手動で定義）、モデルと条件、クラスタの一覧と仮ラベル、代表発話・外れ値（発話ID）、話者分布と時間推移、未割当と境界例の件数（手動のとき）、研究者による確認の記録、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/embedding-topic-exploration/04-Applicability-and-Limits]]

## 参照ノートと主要文献

実装：[[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]]。文献：[[50-Analysis-Methods/20-Literature/LIT-reimers-gurevych-2019-sbert]]、[[50-Analysis-Methods/20-Literature/LIT-rousseeuw-1987-silhouette]]、[[50-Analysis-Methods/20-Literature/LIT-grimmer-stewart-2013-text-as-data]]（要旨確認）、[[50-Analysis-Methods/20-Literature/LIT-wang-2024-multilingual-e5]]、[[50-Analysis-Methods/20-Literature/LIT-grootendorst-2022-bertopic]]（プレプリント、要旨確認）。事例：[[50-Analysis-Methods/10-Experts/embedding-topic-exploration/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/embedding-topic-exploration/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-embedding-topic-exploration
definition_version: 2
knowledge_verified: 2026-09-15
title: 埋め込みによるテーマ探索の専門家
role: computational
analysis_method_ids: []
registry_method_ids:
  - transformer_topics
school:
  default:
    id: e5-kmeans-exploration
    label: 文埋め込み（multilingual-e5-small）とK-meansによる意味クラスタの探索（Gurumojiの実装）
  alternatives:
    - id: researcher-defined-themes
      label: 研究者が定義したテーマ（見出し・手がかり語・シード発話）への最近傍割り当て（Gurumojiの実装、探索の補助）
    - id: bertopic
      label: BERTopic（クラス単位のTF-IDFによるトピック表現、未実装）
scope:
  - 意味の近い発話のまとまり（クラスタ）を探索する
  - 研究者が選んだテーマ数で作り直し、候補ごとのsilhouetteを示す
  - 研究者が定義したテーマへ、意味が最も近い発話を候補として割り当てる
  - 仮ラベル、代表発話、外れ値、話者分布、時間推移を示す
  - 相づちとその時系列上の応答先を候補として示す
out_of_scope:
  - text: 研究者の解釈によるテーマの確定
    handoff: exp-thematic-analysis
  - text: ボトムアップのグループ編成と図解
    handoff: exp-kj-method
  - text: 語の頻度と共起
    handoff: exp-quantitative-text-analysis
  - text: 応答の連鎖と同意・不同意の意味
    handoff: exp-focus-group-interaction
analysis_unit: 文脈付き発話（短い断片は同じ話者の3秒以内の隣接発話で補う）
required_inputs:
  - 入力変更後に更新されたTransformerテーマ分析の結果
  - モデル名・リビジョン・次元・seed・候補テーマ数の記録
  - 手動で割り当てる場合は、テーマの見出しと、手がかり語またはシード発話
applicability_checks:
  - id: emb-a1
    check: transformer_result_current
    severity: block
    message: Transformerテーマ分析の結果がない、または入力の変更後に更新されていません。
    basis:
      - implementation
  - id: emb-a2
    check: transformer_silhouette_min
    severity: warn
    params:
      min: 0.1
    message: シルエット係数が0.1未満です。クラスタのまとまりと分離が弱く、区切りを人が確認する必要があります（0.1は実装上の目安）。
    basis:
      - LIT-rousseeuw-1987-silhouette
      - implementation
  - id: emb-a3
    check: min_included_segments
    severity: warn
    params:
      min: 20
    message: 発話が20件未満のため、クラスタが不安定です（20件は実装上の目安）。
    basis:
      - implementation
  - id: emb-a4
    check: human_review
    severity: warn
    message: クラスタが、話者の偏りや文字起こしの断片によって作られていないかを確認します。
    basis:
      - implementation
  - id: emb-a5
    check: speaker_order_confirmed
    severity: warn
    message: 話者の確認が済んでいないため、話者分布と相づちの応答先に話者分離の誤りが含まれる可能性があります。
    basis:
      - LIT-park-2022-diarization-review
procedure:
  - id: emb-p1
    title: 対象の発話の選択と、短い断片の文脈補完の条件を確認する
    actor: code
    basis:
      - implementation
  - id: emb-p2
    title: 文埋め込みを作り、K-meansでクラスタリングし、シルエット係数でテーマ数を選ぶ
    actor: code
    basis:
      - LIT-reimers-gurevych-2019-sbert
      - LIT-rousseeuw-1987-silhouette
      - LIT-wang-2024-multilingual-e5
      - implementation
  - id: emb-p3
    title: 各クラスタの代表発話と外れ値を原文で読み、仮ラベルを見直す
    actor: researcher
    basis:
      - LIT-grimmer-stewart-2013-text-as-data
  - id: emb-p4
    title: クラスタの併合・分割・除外を研究者が判断し、探索の結果として報告する
    actor: researcher
    basis:
      - LIT-grimmer-stewart-2013-text-as-data
  - id: emb-p5
    title: 手動で割り当てる場合は、研究者がテーマの見出しと手がかり語・シード発話を定義して保存する
    actor: researcher
    basis:
      - LIT-grimmer-stewart-2013-text-as-data
      - implementation
  - id: emb-p6
    title: 定義したテーマのベクトルへ最近傍で割り当て、未割当と境界例を研究者が原文で確認する
    actor: code
    basis:
      - implementation
quality_checks:
  - id: emb-q1
    check: transformer_silhouette_min
    params:
      min: 0.1
    text: シルエット係数が目安以上か
    basis:
      - LIT-rousseeuw-1987-silhouette
      - implementation
  - id: emb-q2
    check: human_review
    text: モデル名・リビジョン・次元・seed・候補テーマ数を記録したか
    basis:
      - implementation
  - id: emb-q3
    check: human_review
    text: 代表発話と外れ値を原文で読んだか
    basis:
      - LIT-grimmer-stewart-2013-text-as-data
  - id: emb-q4
    check: human_review
    text: 相づちの応答先を、賛同や合意と解釈していないか
    basis:
      - implementation
  - id: emb-q5
    check: human_review
    text: 手動割り当ての未割当・境界例を読み、手がかり語・シード発話・しきい値を見直したか
    basis:
      - implementation
prohibited_conclusions:
  - 意味クラスタを、テーマ分析のテーマやKJ法のグループとして示さない
  - 類似度やクラスタから、合意・不一致・重要性・感情を述べない
  - シルエット係数を、テーマの意味の妥当性の指標として述べない
  - 結果を「BERTopicで分析した」と表示しない
  - 研究者が定義したテーマへの割り当てを、テーマの妥当性が確認された結果として示さない
output_sections:
  - テーマの決め方（自動・候補から選択・手動で定義）
  - モデルと条件
  - クラスタの一覧と仮ラベル
  - 代表発話・外れ値（発話ID）
  - 話者分布と時間推移
  - 未割当と境界例の件数（手動のとき）
  - 研究者による確認の記録
  - 限界
ai_assist:
  allowed: false
  steps: []
  reason: 埋め込みによるテーマ探索は計算系の専門家で、クラスタはコードで計算し、意味の確認は研究者が原文で行うため、AI見解を使いません。
  brief: ""
literature:
  - LIT-reimers-gurevych-2019-sbert
  - LIT-lloyd-1982-kmeans
  - LIT-rousseeuw-1987-silhouette
  - LIT-wang-2024-multilingual-e5
  - LIT-grootendorst-2022-bertopic
  - LIT-chang-2009-reading-tea-leaves
  - LIT-grimmer-stewart-2013-text-as-data
  - LIT-park-2022-diarization-review
  - RES-bertopic-official
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
open_issues:
  - multilingual-e5の技術報告はプレプリントで、日本語の会話の逐語録での評価を確認していない
  - トピックの人による解釈を扱ったChang et al. 2009の内容を読んでいない（書誌のみ）
  - 相づちの検出と応答先の推定の妥当性を扱った文献を確認していない
  - 0.1・20件の目安は実装上の判断
  - 手動割り当てのしきい値と、上位2テーマの差の目安は実装上の判断で、検証していない
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
