---
note_id: expert-conversation-timing-quality
note_type: expert-quality
expert_id: exp-conversation-timing
title: 会話の時間構造の専門家：判断基準と品質確認
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/conversation
---

# 会話の時間構造の専門家：判断基準と品質確認

## 判断基準

- [実装判断] 候補は、しきい値とともにのみ意味を持つ。しきい値を変えた結果と比べるときは条件をそろえる。
- [文献] 話者分離の誤り（音声の見逃し、誤検出、話者の取り違え）は、遷移と重なりの候補に直接入り込む。重なりが大きい区間は話者分離の課題とされる（Park et al. 2022、1.4.1節、2.1.3節）。
- [文献] 会話のターン間の間は通常きわめて短い（Levinson & Torreira 2015、Stivers et al. 2009、いずれも要旨）。長い無音の候補は例外的な区間として確認に値するが、その意味は時間の値だけでは決まらない（[整理]）。

## アプリが判定する項目と人が確認する項目

| ID | 内容 | 判定 |
| --- | --- | --- |
| time-q1 | 有効な時刻の割合 | コード（`valid_time_ratio_min`、95%は実装上の目安） |
| time-q2 | しきい値と区間幅の明示 | 研究者 |
| time-q3 | 打ち切りと無効時刻の明示 | 研究者 |
| time-q4 | 音声での確認 | 研究者 |
