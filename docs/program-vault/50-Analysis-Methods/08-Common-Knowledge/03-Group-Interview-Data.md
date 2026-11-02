---
note_id: analysis-common-group-interview-data
note_type: common-knowledge
title: グループインタビューのデータに共通する注意
status: current
updated: 2026-09-15
tags:
  - gurumoji/analysis
  - gurumoji/expert
  - gurumoji/common-knowledge
---

# グループインタビューのデータに共通する注意

Gurumojiが主に扱うグループインタビュー・会議の逐語録について、どの手法でも確認する事項。手法ごとの扱いは各専門家の `04-Applicability-and-Limits`。

## 相互作用はデータの一部である

- [文献] フォーカスグループの利点は参加者間の相互作用にあるとされる一方、結果は1人ずつの引用で報告されることが多く、個人の見解が相互作用から切り離せるかのような印象を与える、と指摘されている（[[50-Analysis-Methods/20-Literature/LIT-gronkjaer-2011-fg-interaction|Grønkjær et al. 2011]]、本文確認）。
- [文献] 集団の談話と個人の談話の違いが分析・解釈にどう影響するかについて、文献の指針は少ない（[[50-Analysis-Methods/20-Literature/LIT-kidd-parshall-2000-fg-rigor|Kidd & Parshall 2000]]、要旨確認）。相互作用データをどう分析・報告するかは論点として扱われている（[[50-Analysis-Methods/20-Literature/LIT-duggleby-2005-fg-interaction|Duggleby 2005]]、要旨確認）。
- [整理] 内容（何が語られたか）と相互作用（どう応答し合ったか）は、別の手順・別の表で扱い、同じ発話IDで照合する。既存の分析方針（`build_focus_group_analysis_plan`）の「内容分析と相互作用分析を混同しない」と一致する。

## 観測は独立ではない

- [整理] 同じ会話・同じ話者の発話は互いに独立な標本とはみなせない。入れ子になったデータの観測は独立ではなく、その依存を無視すると誤って有意と結論する確率が名目の水準より大きく高くなりうると論じる文献がある（[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data|Aarts et al. 2014]]、要旨確認。対象は神経科学の実験デザイン）。発話単位の検定・頻度比較は探索的に扱う。
- [文献] 質的研究の標本は代表性を目的に設計されていないため、「20人中13人が〜と述べた」のような数値化は意味をなさない、とフレームワーク法の文献は注意している（[[50-Analysis-Methods/20-Literature/LIT-gale-2013-framework|Gale et al. 2013]]、本文確認）。

## 司会とグループ構成の影響

- [文献] ある研究では、年齢を同質性の要因として参加者の共通性を確保しつつ、対立する意見が出る程度の多様性を持たせてグループを構成した。司会者は、参加者の言葉の選び方が他の参加者の参加に与える影響や、同質性・異質性が相互作用に与える影響を継続的に見立て、発言が得意でない参加者も含めて全員の声が聞かれるようにする必要があるとする。発言の多い参加者を事前の雑談で把握する方法（Krueger & Casey 2000）にも触れている（[[50-Analysis-Methods/20-Literature/LIT-gronkjaer-2011-fg-interaction|Grønkjær et al. 2011]]、p.18、p.25）。
- [実装判断] 発話量の少なさを、関与の低さや同意と解釈しない。司会の質問・指名・グループ構成を確認してから解釈する。

## 文字起こしと話者分離の誤り

- [文献] 話者分離の評価指標DERは、音声の誤検出、音声の見逃し、話者ラベルの取り違えの合計であり、発話の重なりが大きい区間では音声分離などの技術が検討されている（[[50-Analysis-Methods/20-Literature/LIT-park-2022-diarization-review|Park et al. 2022]]、arXiv版の1.4.1節と2.1.3節）。
- [実装判断] 話者ラベルは実在の人物と一対一とは限らない。分析準備（`transcript_preparation`）で本文・区切り・話者・順序の確認状態を見て、未確認なら相互作用や話者比較の結論を保留する。
- [文献] 再帰的テーマ分析の解説では、聞こえた音声をそのまま書き起こすことが推奨され、文法的な修正や「えー」などの言い始め、言い淀み、間、ちょっとした言い間違いなどを取り除くことは一般的に推奨しない、と紹介している（[[50-Analysis-Methods/20-Literature/LIT-oka-2022-reflexive-ta-ja|岡ほか 2022]]、p.149）。これは手法ごとの推奨であり、全手法に共通する規則ではない。

## 専門家が確認する共通項目

| 項目 | データ上の確認先 |
| --- | --- |
| 研究質問・研究目的 | 分析設定 `research_question`、会話プロフィール `objective` |
| 逐語録の準備状態 | `manual.preparation.status`、`analysis_needs_review` |
| 話者・順序の確認 | `manual.preparation.order_verified`、`unknown_speaker_turns` |
| 司会の役割 | 準備記録の役割と話者確認 |
| 時刻の有効性 | `automatic.data_quality.invalid_time_segments` |
| 除外発話 | `automatic.data_quality.excluded_segments` |

関連：[[50-Analysis-Methods/08-Common-Knowledge/01-Evidence-and-Claims]]、[[30-Data/transcript-preparation-v1]]
