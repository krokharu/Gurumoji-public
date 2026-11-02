---
note_id: expert-embedding-topic-exploration-quality
note_type: expert-quality
expert_id: exp-embedding-topic-exploration
title: 埋め込みによるテーマ探索の専門家：判断基準と品質確認
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/semantic
---

# 埋め込みによるテーマ探索の専門家：判断基準と品質確認

## 判断基準

- [文献] シルエットは、各クラスタのまとまりと分離の比較に基づき、どの対象がクラスタの内側によく収まり、どれがクラスタの間にあるかを示す（Rousseeuw 1987、要旨）。
- [文献] 自動テキスト分析は、問題ごとの広範な検証を必要とする（Grimmer & Stewart 2013、要旨）。
- [実装判断] 手動で定義したテーマへの割り当ては、研究者の見出しに沿った最近傍の候補である。シルエット係数は割り当て後のまとまりの記述であり、テーマの妥当性ではない。
- [整理] 文埋め込みの評価は主に英語の標準課題で行われており（Reimers & Gurevych 2019、要旨）、使用するmultilingual-e5の技術報告はプレプリント（Wang et al. 2024）である。日本語の会話の逐語録での性能は確認していない。

## アプリが判定する項目と人が確認する項目

| ID | 内容 | 判定 |
| --- | --- | --- |
| emb-q1 | シルエット係数の目安 | コード（`transformer_silhouette_min`、0.1は実装上の目安） |
| emb-q2 | モデルと条件の記録 | 研究者 |
| emb-q3 | 代表発話と外れ値の原文確認 | 研究者 |
| emb-q4 | 相づちの応答先の解釈 | 研究者 |
| emb-q5 | 手動割り当ての未割当・境界例の確認 | 研究者 |
