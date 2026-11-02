---
note_id: expert-scat-definition
note_type: expert-definition
expert_id: exp-scat
title: SCATの専門家
role: methodology
status: current
definition_version: 1
knowledge_verified: 2026-09-15
analysis_method_ids:
  - scat
registry_method_ids: []
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/qualitative
---

# SCATの専門家（exp-scat）

## 担当範囲と担当外

セグメント化したテクストに〈1〉〜〈4〉の4段階のコードと〈5〉疑問・課題を付け、〈4〉からストーリーラインと理論記述を書く。大量データの全体像、ケース間比較、プロセスの説明理論は担当外。詳細：[[50-Analysis-Methods/10-Experts/scat/00-Overview]]

## 理論的背景と採用する流派

[文献] SCATは、明示的で定式的な手続きを持ち、1ケースのデータやアンケートの自由記述など比較的小規模のデータにも適用できる分析手法とされる（大谷 2011、p.155）。〈1〉〜〈4〉は脱文脈化、ストーリーラインは再文脈化の作業とされる（p.159）。[実装判断] 大谷（2011）の手続きを既定にする。

## 適した研究目的・問い・データ

少量のデータから、分析の過程を明示しながら構成概念と理論記述まで進めたい研究。論文化には分析の根拠となる概念的枠組みと文献の参照が必要とされる（[文献] 大谷 2011）。

## 必要な入力と前処理、分析単位

研究質問、概念的枠組みと関連文献、セグメント化したテクスト。分析単位はセグメント（一つのセグメントに大きく一つのトピック、[文献] 大谷 2011、4.2節）で、Gurumojiでは発話を目安にする。

## 手順の要約

セグメント化 → 〈1〉注目すべき語句 → 〈2〉言いかえ → 〈3〉説明する概念 → 〈4〉テーマ・構成概念 → 〈5〉疑問・課題 → ストーリーライン → 理論記述 → さらに追究すべき点・課題。詳細：[[50-Analysis-Methods/10-Experts/scat/02-Procedure]]

## 判断基準と品質確認の要約

〈4〉をすべてストーリーラインで使う（下線で確認）、〈4〉は文ではなく名詞・名詞句、理論記述は「このデータから言えること」。詳細：[[50-Analysis-Methods/10-Experts/scat/03-Quality]]

## よくある誤用と禁止事項

理論記述を普遍的な法則として示す、〈4〉を経ずにストーリーラインを書く、AIの候補をコーディングの結果とする。実行定義の `prohibited_conclusions` を参照。

## 出力形式

研究質問と概念的枠組み、〈1〉〜〈5〉のマトリクス、ストーリーライン（使った〈4〉を明示）、理論記述、さらに追究すべき点・課題、限界。

## 説明できる範囲と限界

詳細：[[50-Analysis-Methods/10-Experts/scat/04-Applicability-and-Limits]]

## 参照ノートと主要文献

主要文献：[[50-Analysis-Methods/20-Literature/LIT-otani-2011-scat]]（本文確認）、[[50-Analysis-Methods/20-Literature/RES-otani-scat-official]]（公式ページ）、[[50-Analysis-Methods/20-Literature/LIT-otani-2008-scat]]（書誌のみ）。適用例（方法の原典ではない）：[[50-Analysis-Methods/20-Literature/LIT-shimizu-2023-scat-application]]。事例一覧：[[50-Analysis-Methods/10-Experts/scat/05-Cases]]

## 知識の確認日と未解決事項

知識の確認日：2026-09-15。未解決事項：[[50-Analysis-Methods/10-Experts/scat/06-Open-Issues]]

## 実行定義

```yaml
expert_id: exp-scat
definition_version: 1
knowledge_verified: 2026-09-15
title: SCATの専門家
role: methodology
analysis_method_ids:
  - scat
registry_method_ids: []
school:
  default:
    id: otani-2011
    label: SCAT（大谷 2011の手続き）
  alternatives:
    - id: fukushi-nago-short-answers
      label: 短い自由記述が多数ある場合の活用法（福士・名郷 2011、原典未確認）
scope:
  - 小規模の質的データを〈1〉〜〈4〉の4段階でコーディングし、〈5〉疑問・課題を記録する
  - 〈4〉のテーマ・構成概念からストーリーラインと理論記述を書く
  - 分析の過程をマトリクスで示す
out_of_scope:
  - text: 大量のデータの全体像の把握
    handoff: exp-quantitative-text-analysis
  - text: 複数のケースを行列で比較する
    handoff: exp-framework-method
  - text: 変化のプロセスを説明する理論の生成
    handoff: exp-m-gta
analysis_unit: セグメント（一つのセグメントに大きく一つのトピック）。Gurumojiでは発話を目安とし、区切りは研究者が確認する
required_inputs:
  - 研究質問
  - 分析の根拠となる概念的枠組みと関連文献
  - セグメント化したテクスト
applicability_checks:
  - id: scat-a1
    check: research_question_present
    severity: warn
    message: 研究質問がありません。注目すべき語句を選ぶ視点と、概念的枠組みを決める手がかりがありません。
    basis:
      - implementation
  - id: scat-a2
    check: min_included_segments
    severity: block
    params:
      min: 1
    message: 分析できる発話がありません。
    basis:
      - implementation
  - id: scat-a3
    check: max_included_segments
    severity: warn
    params:
      max: 300
    message: 発話が300件を超えています。SCATは小規模データにも適用できる手法で、すべてのセグメントを4段階でコーディングする作業量を研究者が見積もる必要があります（300件は実装上の目安）。
    basis:
      - LIT-otani-2011-scat
      - implementation
  - id: scat-a4
    check: human_review
    severity: warn
    message: セグメントの区切りが、一つのセグメントに大きく一つのトピックになっているかを研究者が確認します。
    basis:
      - LIT-otani-2011-scat
  - id: scat-a5
    check: human_review
    severity: warn
    message: 論文化する場合、分析の根拠となる概念的枠組みと関連文献を用意したかを確認します。
    basis:
      - LIT-otani-2011-scat
  - id: scat-a6
    check: analysis_basis_current
    severity: warn
    message: 逐語録の準備記録と分析の根拠が一致していません。
    basis:
      - implementation
procedure:
  - id: scat-p1
    title: テクストをセグメント化してマトリクスに書き込む
    actor: researcher
    basis:
      - LIT-otani-2011-scat
  - id: scat-p2
    title: 〈1〉テクスト中の注目すべき語句を書き出す（全体を見て先にすべて書き出すのがよい）
    actor: ai_draft
    basis:
      - LIT-otani-2011-scat
  - id: scat-p3
    title: 〈2〉〈1〉を言いかえるテクスト外の語句を書く
    actor: researcher
    basis:
      - LIT-otani-2011-scat
  - id: scat-p4
    title: 〈3〉〈2〉を説明するテクスト外の概念を書く（背景・条件・原因・結果・影響・比較・特性・次元・変化など）
    actor: researcher
    basis:
      - LIT-otani-2011-scat
  - id: scat-p5
    title: 〈4〉前後や全体の文脈を考慮したテーマ・構成概念を書く（文ではなく名詞・名詞句）
    actor: researcher
    basis:
      - LIT-otani-2011-scat
      - RES-otani-scat-official
  - id: scat-p6
    title: 〈5〉分析の過程で得た疑問・課題を書く
    actor: ai_draft
    basis:
      - LIT-otani-2011-scat
  - id: scat-p7
    title: 〈4〉を紡いでストーリーラインを書く（使った〈4〉に下線を引いて漏れを確認する）
    actor: researcher
    basis:
      - LIT-otani-2011-scat
  - id: scat-p8
    title: ストーリーラインを断片化して理論記述を書く（このデータから言えること）
    actor: researcher
    basis:
      - LIT-otani-2011-scat
  - id: scat-p9
    title: さらに追究すべき点・課題をまとめる
    actor: researcher
    basis:
      - LIT-otani-2011-scat
quality_checks:
  - id: scat-q1
    check: human_review
    text: ストーリーラインで〈4〉のコードをすべて使ったか（下線で確認したか）
    basis:
      - LIT-otani-2011-scat
  - id: scat-q2
    check: human_review
    text: 〈4〉が文ではなく、精緻化した概念（名詞・名詞句）になっているか
    basis:
      - RES-otani-scat-official
  - id: scat-q3
    check: human_review
    text: 理論記述を、普遍的な法則ではなく、このデータから言えることとして書いたか
    basis:
      - LIT-otani-2011-scat
  - id: scat-q4
    check: human_review
    text: 関連文献を参照しながら分析を見直したか
    basis:
      - LIT-otani-2011-scat
  - id: scat-q5
    check: human_review
    text: 〈1〉〜〈5〉の分析の過程をマトリクスで示せるか
    basis:
      - LIT-otani-2011-scat
prohibited_conclusions:
  - 理論記述を、他のデータにも当てはまる普遍的な法則として示さない
  - AIが書き出した〈1〉や〈5〉の候補を、分析者が行ったコーディングとして示さない
  - 〈4〉を経ずに、テクストから直接書いたストーリーラインや理論記述をSCATの結果としない
  - 研究者が〈2〉〜〈4〉を書いていないのに、SCATを実施したと表示しない
output_sections:
  - 研究質問と概念的枠組み
  - セグメント化したテクストと〈1〉〜〈5〉のマトリクス
  - ストーリーライン（使った〈4〉を明示）
  - 理論記述
  - さらに追究すべき点・課題
  - 限界
ai_assist:
  allowed: true
  steps:
    - scat-p2
    - scat-p6
  reason: ""
  brief: SCATの補助として、〈1〉テクスト中の注目すべき語句の候補と、〈5〉分析の過程で確認すべき疑問・課題の候補だけを示してください。〈2〉〈3〉の言いかえと説明、〈4〉のテーマ・構成概念、ストーリーライン、理論記述は分析者が行うため、書かないでください。注目すべき語句は原文の語句をそのまま引用し、必ず根拠の発話を付けます。候補であることを明記し、一般化した結論を書かないでください。
literature:
  - LIT-otani-2011-scat
  - RES-otani-scat-official
  - LIT-otani-2008-scat
  - LIT-gilardi-2023-llm-annotation
common_notes:
  - 01-Evidence-and-Claims
  - 02-Source-Classification
  - 03-Group-Interview-Data
  - 04-AI-Assistance-Boundaries
open_issues:
  - 原典論文（大谷 2008）の本文を読めていない（画像のPDF）
  - 福士・名郷 2011の短い回答への活用法を読んでいない
  - SCATの公式ページのtips・pitfalls・FAQの全項目を確認していない
  - Gurumojiには〈1〉〜〈5〉のマトリクスを記録する画面がない
  - 300発話という作業量の目安は実装上の判断で、文献の基準ではない
readiness:
  literature_checked: true
  procedure_documented: true
  integrated: true
  sample_verified: true
```
