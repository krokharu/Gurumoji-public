# Obsidian Vaultの構成

研究ノートとアプリの台帳は、役割ごとに独立したVaultへ保存します。既定のデータルートは `runtime/data` で、`MOJIOKOSI_DATA_DIR` により変更できます。

| Vault | データルート内の場所 | 用途 |
| --- | --- | --- |
| ResearchVault | `obsidian/ResearchVault` | 全文、AI仕上げ、研究メモ、解釈、分析まとめ |
| Input | `obsidian/InputVault` | 取り込み台帳、入力snapshotの来歴 |
| Visualization | `obsidian/VisualizationVault` | 図表仕様と分析結果への参照 |
| Orchestrator | `obsidian/OrchestratorVault` | 手法・実行・公開の記録 |

Obsidianで「保管庫としてフォルダーを開く」を選び、それぞれのVault自体を指定してください。親の `obsidian` フォルダーを1つのVaultとして開きません。可視化用Vaultは `open_visualization_obsidian.bat` からも開けます。

## 保存と変更の保護

分析結果は固定runとして保存し、入力版・条件・hashへ戻れるようにします。研究者が編集したアプリ生成ノートは、編集版を履歴へ保持してから更新します。研究者所有の本文・タグ・別名を強制上書きしません。ノートの欠落・公開の失敗を成功として扱いません。

「ファイル・管理」から研究メモ・解釈・コード案の差分を確認して取り込めます。原本は変更せず、解釈やコード案を自動採用しません。生成Vaultの保存先変更はpreview、バックアップ、copy-firstの既存経路を使います。ResearchVaultはこの変更対象に含めません。

Vault間の対応は会話ID・run IDなどで追跡します。同期や保存だけでAI推論・外部送信を自動開始しません。

## プログラム資料Vault

公開版の `docs/program-vault` は、アプリが読む専門家・文献・スライド定義と入口だけです。これらは削除しないでください。詳細設計・ADR・開発履歴・完全なSoftware Vaultは既存の開発資料側に保管し、公開版へ取り込みません。

公開版のブランチ運用は [DEVELOPMENT.md](DEVELOPMENT.md) を参照してください。プログラム資料の分離は、実利用データの保存先や保存形式を変更しません。

分析用の利用者Vaultと、プログラム資料のGit更新は別です。個人の `.obsidian` 設定、実runtime、移入した研究Vaultをこの分離に合わせて移動・削除する必要はありません。
