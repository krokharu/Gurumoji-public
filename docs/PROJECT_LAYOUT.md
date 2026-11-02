# フォルダー構成

公開版の両ブランチは、利用・引渡しに必要なファイルへ絞っています。

```text
Gurumoji/
├─ README.md             利用の入口
├─ run.bat               Windows起動
├─ setup_gui.bat         初回セットアップ
├─ config/               設定・依存関係
├─ src/gurumoji/         アプリ本体・画面素材
├─ scripts/              起動・導入・診断・バックアップ等
├─ notebooks/            Colab
├─ docs/                 利用・運用手順
│  └─ program-vault/     実行時の専門家・文献・スライド定義
└─ runtime/              利用者データ（Git管理外）
```

`runtime/data` にSQLite・メディア・分析結果・Obsidian Vault・台帳を保存します。`runtime/output` は文字起こし出力、`runtime/models` はモデル、`runtime/logs` はログ、`runtime/uploads` は一時アップロード、`runtime/backups` はバックアップです。

保存先は既存の `MOJIOKOSI_DATA_DIR`、`MOJIOKOSI_OUTPUT_DIR`、`MOJIOKOSI_BACKUP_DIR` で指定できます。個人のパスや資格情報をソースへ固定しません。

バックアップは画面か、アプリ停止中の `python scripts/backup_data.py create` で作成します。DB・分析結果・Vault・台帳・作業台・登録語を同じ時点で保存し、manifestでSHA-256を検証します。元メディアは既定で含めず、必要な場合だけ `--include-media` を指定します。秘密情報は別途保管してください。

## Linux配置

アプリのチェックアウト、実行データ、移入Vault、検証出力を分けます。`scripts/run_cloud.sh` はデータ・出力・バックアップの環境変数を、アプリの隣のruntimeへ設定します。一時アップロード用のアプリ内runtimeをsymlinkに置き換えないでください。

Python環境は配置先で作り、Windowsの `.venv` をコピーしません。CPU再現用の依存関係は `config/requirements-cloud-cpu.lock.txt` を参照し、起動は `bash scripts/run_cloud.sh` です。待受は既定で `127.0.0.1:7860`。認証の解除や公開bindを疎通確認の代わりに使いません。

試験・開発資料の配置と実行方法は [DEVELOPMENT.md](DEVELOPMENT.md) にまとめています。
