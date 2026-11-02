# 公開版の開発と配布

公開先は [krokharu/Gurumoji-public](https://github.com/krokharu/Gurumoji-public) です。公開可能なアプリのコード、利用手順、実行に必要な定義を管理します。

| ブランチ | 用途 |
| --- | --- |
| `public/release` | 利用者へ配布する版・既定ブランチ |
| `public/develop` | 公開版の開発・レビュー |

利用者データ・認証情報・個人設定・内部試験資料を含めない状態を起点とし、両ブランチで同じ公開範囲を守ります。

## 開発する

```powershell
git clone --single-branch --branch public/develop https://github.com/krokharu/Gurumoji-public.git Gurumoji-public-development
cd Gurumoji-public-development
python .github/scripts/check_public_boundary.py
python scripts/bump_version.py check
```

変更は `public/develop` でレビューし、動作確認後に `public/release` へ反映します。試験は隔離した一時DB・一時Vaultで実行し、実利用者の録音・本文・属性・研究ノートを使いません。内部の試験資産や詳細設計書は公開リポジトリへ追加しません。

他の作業リポジトリから変更を移す場合は、内容を監査し、必要なコードだけを取り込みます。履歴全体をmergeすると、削除済みの資料や秘密情報も公開履歴へ入るため、公開前に到達可能な履歴を検査します。

GitHub Actionsでは両公開ブランチの履歴に対して、禁止パス・資格情報のパターン・個人の絶対パス・ノートブックの実行結果を確認し、版表記の整合も検査します。検査は実データでの動作確認やモデル品質の検証を代替しません。

Actionsの「公開範囲の読取専用検査」は手動でも実行できます。内容の読み取りと検査だけを行い、版更新・コミット・タグ・Releaseの作成権限は持ちません。

## 配布する

```powershell
git archive --format=zip --output=../gurumoji-public.zip public/release
```

Gitの追跡ファイルだけから配布物を作ります。`.gitattributes` によりGitHub管理設定とエージェント用指示をソースZIPから除外します。利用中のフォルダー全体をZIP化しないでください。

`runtime/`、認証情報、モデル、個人の `.codex/`・`.obsidian/` 設定、別リポジトリの `ObusSQL/` は配布しません。`docs/program-vault` の専門家・文献・スライド定義は実行に必要なため残し、変更時はhash・版・隣接する検証と照合します。

## バージョンの付け方

表示の正本は `src/gurumoji/app.py` の `APP_VERSION` です。READMEの版表記も一致させます。

- `β`: 画面に「Coming Soon」が残っている間は付け、なくなったら手動で外します。
- 先頭の数字: 製品版への移行時と、その後のメジャーアップデートで上げます。
- 次の数字: 通常の機能更新で上げます。
- 最後の数字: 細かい修正で上げます。

`public/release` へのpushで版を自動更新します。`feat:` を含めば通常アップデート、`docs/chore/ci/test/style` だけなら据え置き、それ以外はパッチです。`public/develop` は検査のみ実行します。

βの付け外しとメジャーアップデートはActionsの手動実行（`release` / `major` / `beta-on` / `beta-off`）で行います。画面に「Coming Soon」が残っているのにβがない場合、検査は失敗します。

版が更新されると `public/v0.46.1-beta` の形式でタグを付け、GitHub Releaseを作成します。β版のReleaseは先行リリースとして扱います。

## 不具合の報告

[Issues](https://github.com/krokharu/Gurumoji-public/issues) へ、OS・アプリの版・再現手順・期待した動作・実際の動作を記載してください。ログ等を添付する際は、個人パス、録音内容、話者名、トークンなどを除いてください。
