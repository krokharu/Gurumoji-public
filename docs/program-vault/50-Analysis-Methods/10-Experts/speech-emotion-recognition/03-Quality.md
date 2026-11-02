---
note_id: expert-speech-emotion-recognition-quality
note_type: expert-quality
expert_id: exp-speech-emotion-recognition
title: 音声感情推定の専門家：判断基準と品質確認
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/audio
---

# 音声感情推定の専門家：判断基準と品質確認

## 判断基準

- [文献] モデルカードの正解率は、JTESのセッションごとの評価（session1〜5で0.7925〜0.8822、平均0.8477）である（モデルカード）。評価の条件が手元の会話と異なる場合、同じ正確さは期待できない（[整理]）。
- [文献] HuBERTの評価は英語の音声認識のベンチマークで行われている（Hsu et al. 2021、要旨）。上流の表現学習の性能は、感情ラベルの妥当性を示すものではない（[整理]）。
- [文献] 表情については、同じような表出が複数の感情カテゴリーを表し、感情以外のことを伝えることも多いとする総説がある（Barrett et al. 2019、要旨）。

## アプリが判定する項目と人が確認する項目

| ID | 内容 | 判定 |
| --- | --- | --- |
| ser-q1 | カバー率 | コード（`emotion_coverage_min`、80%は実装上の目安） |
| ser-q2 | 両モデルの一致・不一致の扱い | 研究者 |
| ser-q3 | 評価セットの正解率の扱い | 研究者 |
| ser-q4 | 本人の感情と断定していないか | 研究者 |
