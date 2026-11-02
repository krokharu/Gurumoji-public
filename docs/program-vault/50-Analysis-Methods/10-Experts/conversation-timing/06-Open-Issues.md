---
note_id: expert-conversation-timing-open-issues
note_type: expert-open-issues
expert_id: exp-conversation-timing
title: 会話の時間構造の専門家：未解決事項
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/conversation
---

# 会話の時間構造の専門家：未解決事項

知識の確認日：2026-09-15。

## 知識が不足している点

- Levinson & Torreira（2015）の出版社PDF本文は確認したが、同論文が引用する個別コーパスの計測・原データまでは独立に確認していない。
- Heldner & Edlund（2010）は要旨の一部だけを確認し、既存の手法ノートの「閾値・統計処理の方法論的問題を報告した」という記述を裏付けていない。
- 日本語の会話のターン間の間や相づちの研究を確認していない。
- 話者分離の誤りが遷移数や重なりの候補に与える影響を扱った研究を確認していない。

## 実装上の課題

- 既定のしきい値（無音3秒、重なり0.2秒）と、有効な時刻の割合の目安（50%、95%）は実装上の判断で、文献の基準ではない。
- 笑いや非言語の情報は記録されない。
