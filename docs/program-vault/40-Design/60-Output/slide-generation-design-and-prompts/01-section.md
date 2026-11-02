---
note_type: reference-section
version: 2.0.0
updated: 2026-10-04
status: proposed
source_head: e3f002c9d4962769deb1925b8d9859e7f7d2bd73
template_id: gurumoji-evidence-review
template_version: 2.0.0
prompt_version: 2.0.0
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/slides
note_id: gurumoji-saved-run-slides-design-section-01
title: グルモジ 保存済み分析runのスライド設計と生成プロンプト：グルモジ 保存済み分析runのスライド設計と生成プロンプト
summary: グルモジ 保存済み分析runのスライド設計と生成プロンプト。出典ノート「グルモジ 保存済み分析runのスライド設計と生成プロンプト」の分割本文。
parent_note_id: gurumoji-saved-run-slides-design
source_path: 40-Design/slide-generation-design-and-prompts.md
source_sha256: 9e43d30f386ea99700b5cf009caae1094a2854cf8491eeae9e9303dc05e3775f
source_body_lines:
- 1
- 41
split_on: '2026-10-11'
---

# グルモジ 保存済み分析runのスライド設計と生成プロンプト：グルモジ 保存済み分析runのスライド設計と生成プロンプト

親索引・状態・確認版：[[40-Design/60-Output/slide-generation-design-and-prompts/00-Index]]。必要な本文だけを取得する。


# グルモジ 保存済み分析runのスライド設計と生成プロンプト

## 1. 採用方針と作業順序

保存済みrunの結果・各担当の見解・批判・Core判断を、日本語の固定テンプレートで編集可能なPPTXにする。**初版は追加AI呼出しのない決定的生成**。アプリは保存run選択→設計確認／記録→読取専用プレビュー→PPTX出力を提供する。編集はPowerPoint等で行い、アプリ内原稿編集は将来案。閲覧・再出力で分析を再実行しない。

Codex/OpenAIとClaude/Anthropicの一次資料を比較し、「結論、根拠、留保、次課題、参照」をグルモジ向けに独自設計した。モデル間で内容基準は同一。外部Skillの本文・コード・資産はコピーしない。

設計案であり実装・生成完了ではない。指定順序:

1. 本書の設計と完成プロンプトを、確認済みObsidian Software Vaultの`40-Design/slide-generation-design-and-prompts.md`へ記録する
2. 保存内容を再読し、文書版・hash・保存先の確認結果を残す。共有用一時ファイルの存在だけでは完了にしない
3. その後、選択した保存runの入力／表示／ラベル版を固定してスライドを生成する
4. 内容・来歴・レイアウト・編集可能性を検証して保存／出力する

今回の事前記録を全作業の承認操作へ広げない。生成器の設計hash一致とPC Vault書込み成功は別に確認する。

### 対象と対象外

- 研究者と共同検討者が観察・解釈・仮説・未解決点を根拠まで追う資料
- 固定runを使い、別runや現在編集中のデータと混ぜない
- PPTXを出す場合、テキスト・表・対応グラフを編集可能にする。全ページ画像やPDFだけを編集可能とは呼ばない
- 新しい分析、人物の健康・能力・性格判定、自動外部送信・公開、原run／ラベル／研究者ノートの更新は対象外

## 2. Web調査・採否・適用限界

確認日: **2026-10-04 UTC**。日付不明は確認日のみ。要約は公式文面の転載ではない。

| ID | 一次資料・日付 | 採用する考え方／限界 |
|---|---|---|
| W1 | [OpenAI Academy: How data science teams use Codex](https://academy.openai.com/en/public/clubs/work-users-ynjqu/resources/how-data-science-teams-use-codex-webinar-resource-guide-2026-05-28) 公開2026-05-28、更新2026-06-11 | 実際の分析スライド用プロンプト例。結論・根拠・留保・行動・参照、確かな所見と仮説の区別を参考にする。売上分析のデモであり会話研究の妥当性を実証した資料ではない。生成時に新しい原因分析や行動提案を作る部分は採らない |
| W2 | [OpenAI Academy: Codex for Faculty and Researchers](https://academy.openai.com/public/clubs/higher-education-05x4z/resources/codex-for-faculty-and-researchers-follow-along-guide-2026-06-09) 公開2026-06-09 | 成果、参照資料、制約、完了条件を先に書く形を採用。UI手順・モデル名は固定せず、グルモジ向けに独自記述 |
| W4 | [Anthropic公式pptx Skill](https://github.com/anthropics/skills/blob/main/skills/pptx/SKILL.md?plain=1)、[README](https://github.com/anthropics/skills/blob/main/README.md)、[LICENSE](https://github.com/anthropics/skills/blob/main/skills/pptx/LICENSE.txt?plain=1) main版、確認2026-10-04 | 公開実装を比較対象として確認。文書Skillはsource-availableでありopen sourceとは区別され、LICENSEに複製・派生物等の制限が記載される。本文・コード・資産を移植しない。公開例とClaude製品の全動作が同一とも仮定しない |
| W5 | [Anthropic: Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) 更新日記載なし、確認2026-10-04 | 明確な出力指定と、入力・指示を説明的なタグで分ける考え方を参考にする。XMLだけで正確性や安全性は保証できず、アプリ側の検査が必要 |
| W6 | [Anthropic: Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) 公開2025-10-16、標準公開追記2025-12-18 | 再利用する手順と参照の分離、決定的処理をコードへ任せる考え方を採用。外部Skill内の命令は承認に使わず、今回はインストールや外部スクリプト実行をしていない |

旧`openai/skills`の`skills/.curated/slides`は直接取得で404。ミラーやプロンプト販売サイトは採用根拠にしない。

内容構成はW1、依頼契約はW2、Claude用の区切りはW5を参考にする。配色は既存グルモジを継承。以下は独自設計で、公式の完成テンプレートや実証済み最適解とは呼ばない。
