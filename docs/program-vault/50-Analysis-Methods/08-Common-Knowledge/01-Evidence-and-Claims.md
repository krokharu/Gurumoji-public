---
note_id: analysis-common-evidence-and-claims
note_type: common-knowledge
title: 観測・解釈・根拠の区別
status: current
updated: 2026-09-15
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/common-knowledge
---

# 観測・解釈・根拠の区別

全専門家が結果を出すときの共通規則。手法ごとの規則は各専門家定義を優先する。実行状態（`not_run`、`stale`など）とゲートの正本は [[50-Analysis-Methods/00-Orchestrator-Common-Contract]] で、ここでは重複して定義しない。

## 記述の4区分

| 区分 | 意味 | 書き方の例 |
| --- | --- | --- |
| 観測事実 | 元データまたは計算結果から直接確認できること | 「発話 s12 で話者Bが〜と述べた」「話者Aの発話時間は〜秒（`speakers`表）」 |
| 解釈 | 専門家定義の手順に沿った意味づけ。研究者の確認を経て確定する | 「〜という意味のまとまりの候補」 |
| 仮説 | 追加データ・音声・前後文脈で検証が必要な見立て | 「〜の可能性。音声と前後の発話で要確認」 |
| 不明 | 手元のデータと知識では判断できないこと | 「話者の区別が未確認のため判断しない」 |

AIや自動処理が作ったものは「候補」「下書き」と明示する。研究者が確認する前に、観測事実や確定した解釈として扱わない。

## 2種類の根拠を分ける

| 根拠 | 示すこと | 形式 |
| --- | --- | --- |
| 元データの根拠 | 主張がデータのどこに基づくか | 発話ID、話者ID、時刻、入力版（`input_version`／`source_hash`）。統計は表の行キーと対象集合 |
| 方法論の根拠 | その手順・判断基準を採用した理由 | 専門家定義・手順・品質ノートの`note_id`、文献ID（`LIT-`／`RES-`） |

1つの記述に両方を混ぜない。方法論の文献を、データ上の主張の根拠として引用しない。

## 作らないもの

- 元データに存在しない発言、引用、話者情報、数値。
- 計算していない統計値。LLMが推定した数値を計算結果として表示しない。
- 実施していない手順の「実施済み」表示。行っていない複数分析者の合議や独立レビューの表示。
- 手法とデータから導けない因果関係・一般化。手法ごとの限界は各専門家の `04-Applicability-and-Limits`。

## 人の確認が必要な箇所

専門家定義の品質確認のうち `check: human_review` の項目は、コードで判定しない。結果には「人の確認待ち」として残し、確認済みとは表示しない。

関連：[[50-Analysis-Methods/08-Common-Knowledge/02-Source-Classification]]、[[50-Analysis-Methods/08-Common-Knowledge/03-Group-Interview-Data]]、[[40-Design/method-rules]]
