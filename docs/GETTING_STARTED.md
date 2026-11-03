# 利用開始ガイド

## 取得する

配布版は `public/release` です。[公開リポジトリ](https://github.com/krokharu/Gurumoji-public) の「Code → Download ZIP」から取得し、書き込みできるフォルダーへ展開します。Gitを使う場合は次を実行します。

```powershell
git clone --single-branch --branch public/release https://github.com/krokharu/Gurumoji-public.git
cd Gurumoji-public
```

## Windowsで環境を準備する

1. `setup_gui.bat` を開きます。
2. 64 bit版Python 3.10〜3.13の有無を確認します。未導入の場合は画面から導入し、セットアップ画面を開き直します。
3. アプリ用の環境を作成します。Pythonの依存関係とFFmpegはプロジェクト内に準備されます。
4. 話者分離に使うHugging Faceモデルの利用条件に同意し、read tokenを設定します。セットアップ画面のモデルページ案内と接続確認を使用します。
5. AI仕上げなどを使用する場合は、利用する接続先と必要な情報を設定します。

初回はライブラリやモデルのダウンロードに時間がかかります。必要な空き容量、ネットワーク接続、GPUの利用可否を確認してください。接続情報は `config/tokens.json` に保存されます。

## 起動して文字起こしする

1. `run.bat` を開きます。
2. ブラウザーで `http://127.0.0.1:7860` を開きます。
3. 動画・音声を選び、モデル・話者分離・AI仕上げの条件を確認して開始します。
4. 結果を元の録音と照合し、発話・時刻・話者名を必要に応じて編集します。
5. 保存と書き出しを行います。AIの仕上げや要約は元の録音と照合してください。解析機能は公開版に含みません。

AI仕上げには接続先や追加設定が必要な処理があります。[AI仕上げの設定](AI_EFFORT.md) と [データと外部通信](DATA_AND_PRIVACY.md) を確認してください。

## 更新する

更新前にバックアップを作り、処理中の作業を保存してください。Git版の `run.bat` は起動時に追跡中のブランチの更新と依存関係の更新を確認します。ローカル編集がある場合や履歴が分岐した場合、コードの自動更新はスキップされます。

手動でコードを更新する場合は、アプリを停止して次を実行します。

```powershell
git pull --ff-only origin public/release
```

ZIP版は新しいZIPを別のフォルダーへ展開して環境を準備します。利用者データの復元は [バックアップの手順](DATA_AND_PRIVACY.md#バックアップと復元) に従い、空のデータフォルダーを対象にしてください。認証情報とバックアップ対象外のデータは別途保管します。

環境の準備が済んだ後、起動時のコード更新確認とライブラリ更新を止めて起動する場合は、PowerShellで次を実行します。初回に必要な環境導入や、機能を実行する際のモデル取得・外部AI通信を停止する設定ではありません。

```powershell
$env:MOJIOKOSI_SKIP_UPDATE_CHECK = "1"
$env:MOJIOKOSI_SKIP_LIBRARY_UPDATE = "1"
.\run.bat
```

## 起動できないとき

| 状況 | 確認すること |
| --- | --- |
| Pythonが見つからない | 対応する64 bit版を導入し、セットアップ画面を開き直す |
| ライブラリ導入に失敗する | 空き容量、最初のpipエラー、ネットワーク・プロキシを確認する |
| Hugging Faceで認証・モデル取得に失敗する | 必要なモデルの利用条件への同意、read token、接続確認結果を確認する |
| GPUが使われない | セットアップ画面の処理装置・GPU状態を確認する |
| ブラウザーで開けない | 起動した画面のエラーとポートを確認し、同じアプリの重複起動がないか確認する |
| AI仕上げが使えない | 接続先、モデル、必要なAPI設定、機能のON/OFFを確認する |

Windowsの起動ログは `runtime/logs/startup-*.log` に保存されます。報告時は、ログや画面に録音内容・個人パス・トークン等が含まれないか確認し、必要な範囲だけを共有してください。

## Colabを使う

[Colabノートブック](https://colab.research.google.com/github/krokharu/Gurumoji-public/blob/public%2Frelease/notebooks/Gurumoji_Colab.ipynb) を上から順に実行します。GPU、モデルの利用条件、認証情報、Google Driveへの保存を各セルの案内に従って設定してください。Windowsの `.venv` は転用しません。アプリ用の依存関係はColab標準のPython環境から分離して導入し、Web UIも専用環境のPythonで起動します。

ランタイム上の処理やモデルが実行中の場合、取得処理は更新を拒否します。保存状態を確認し、ノートブックの終了セルで停止してから更新してください。

### 左側のシークレットにキーを設定する

Colab左側の鍵アイコンを開き、「新しいシークレットを追加」で次の名前と値を登録し、「ノートブックからのアクセス」をONにします。キーをコードへ貼り付ける必要はありません。

| 名前 | 用途・取得先 |
| --- | --- |
| `HF_TOKEN` | 話者分離に必要。[Hugging Faceでread tokenを作成](https://huggingface.co/settings/tokens) |
| `OPENAI_API_KEY` | OpenAIを使う場合だけ。[APIキーの設定](https://platform.openai.com/api-keys) |
| `GOOGLE_API_KEY` | Geminiを使う場合だけ。[Google AI Studioで発行](https://aistudio.google.com/apikey) |
| `TYPESAFE_API_KEY` | TypeSafe / JEVの校正を使う場合だけ。利用中のサービスで発行したキー |

`HUGGINGFACE_TOKEN`、`GEMINI_API_KEY` も別名として使えます。任意のキーは未登録で進められます。既定ではシークレットの値を優先し、未登録の項目はこのランタイムの既存設定を保持します。キーの変更後はセル2を再実行し、アプリも停止・起動し直します。登録を削除するだけではランタイム内の既存設定は消えないため、利用を止める場合は提供元でキーを失効させ、ランタイムを作り直してください。シークレットが利用できない場合は、セル2の `MANUAL_TOKEN_INPUT` をONにして非表示の手入力を使えます。

Hugging Faceは、[既定の話者モデルの利用条件](https://huggingface.co/pyannote/speaker-diarization-community-1)に同意したアカウントのread tokenを使います。[fine-grained tokenの説明](https://huggingface.co/docs/hub/security-tokens)も参照し、対象モデルを読み取れる権限を設定してください。旧モデルを使う場合は [speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) と [segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) の利用条件も確認します。

セル2はHugging Faceの認証と既定モデルへのアクセスを事前確認します。モデル重みのダウンロードや推論は行いません。`CHECK_HF_ACCESS` をOFFにすると事前確認を省略できますが、権限の問題は解決されません。外部AIのキーは読込状態だけを表示し、有効性・残高・利用可能なモデルは実行時に確認されます。

### エラーの分類と対処

| 表示・分類 | 確認すること |
| --- | --- |
| `SECRET_MISSING` / `SECRET_ACCESS` | 左側の名前・値・ノートブックからのアクセスを確認しセル2を再実行 |
| `SECRET_TIMEOUT` / `SECRET_READ` | Colabの画面との接続とシークレットの設定を確認 |
| `TOKEN_FILE` / `TOKEN_WRITE` | 設定を保全し、JSON形式・書込権限・空き容量を確認 |
| 401 / `AUTH_401` | キーの誤入力・失効を確認し、左側の値を更新してセル2とアプリを再起動 |
| 403 / `PERMISSION_403` | モデルの同意アカウント、トークン権限、APIのプロジェクトと提供地域を確認 |
| 400・404 / `REQUEST_400`・`MODEL_404` | モデル名・URL・要求形式・アクセス権を確認 |
| 429 / `LIMIT_429` | 回数制限なら待機。残高・利用枠不足なら提供元の利用状況・課金設定を確認 |
| `NETWORK` / `TLS` / `TIMEOUT` / `SERVICE_5XX` | 通信・証明書・提供元の稼働状況を確認 |
| `ENVIRONMENT` / `DISK_FULL` | 直前のapt/pip出力・空き容量を確認 |
| `GPU_RUNTIME` / `GPU_MEMORY` | GPU接続を確認し、小さいモデル・短いコンテキストを選ぶ |
| `DRIVE` / `LOCAL_LLM` / `APP_START` | Driveの許可、Ollamaのモデル取得、先行セルの完了をそれぞれ確認 |
| `HF_CHECK` / `HF_CHECK_FAILED` | 直前の認証・モデル利用条件の診断とモデルページを確認 |

個別の対処はノートブックにも表示します。APIの詳細は [OpenAI公式のエラー説明](https://developers.openai.com/api/docs/guides/error-codes)・[Gemini公式のエラー説明](https://ai.google.dev/gemini-api/docs/api-errors) を参照してください。

### 仕上げ用LLMの自動選択・直接指定

セル4の `LOCAL_LLM_MODEL` は `auto`（空欄も同じ）が既定です。現在の空きGPUメモリーと利用可能RAMから、音声処理用に4GiB以上のGPU余裕を残し、モデル・量子化・入力枠を選びます。目安は次のとおりです。

| ランタイムの目安 | 自動選択の候補 | 入力枠 |
| --- | --- | --- |
| T4 16GB | Qwen3 4B Instruct・Q4_K_M | 32,768 |
| L4 24GB | Qwen3 4B Instruct・Q8_0 | 32,768 |
| A100 40GB | Qwen3 30B-A3B Instruct・Q4_K_M | 32,768 |
| A100 / H100 80GB級 | Qwen3 30B-A3B Instruct・Q8_0 | 32,768 |
| CPU・小容量環境 | Qwen2.5 1.5B〜3B Instruct | 32,768 |

GPU名が同じでも、空き容量やRAMが少なければ軽いモデルを選びます。長い本文・アウトラインと生成結果に必要な枠を確保するため、自動では従来の32,768枠を維持します。複数GPUの容量は合算しません。選択理由と検出値をセル4に表示します。容量に基づく推奨であり、校正品質の実測順位や、すべての配置での動作保証ではありません。

直接指定する場合は、同じ `LOCAL_LLM_MODEL` 欄へ `qwen3:4b-instruct`、`gemma3:4b`、`hf.co/組織/モデル:量子化タグ` など、Ollamaで取得できるローカルのテキストモデル名を入力します。従来の3候補への制限はありません。タグ省略時は `:latest` を補います。`LOCAL_LLM_CONTEXT_LENGTH` は0で自動、4096〜32768で直接指定できます。Ollamaのクラウドモデルはこの設定では使いません。

取得後に文章生成への対応・モデルの入力枠上限・JSON schema応答・実際の入力枠を確認し、成功後に仕上げ用の設定へ保存します。直接指定したモデルが容量不足・JSON非対応の場合は、別モデルへ変更せずに停止します。`LLM_MODEL` はモデル名、`LLM_CONTEXT` は入力枠、`LLM_MEMORY` は空きメモリーを確認し、必要に応じて `auto` へ戻すかローカルLLMをOFFにしてください。変更後はセル4を再実行し、アプリを停止・起動し直します。

モデルのタグと配布サイズは [Qwen3](https://ollama.com/library/qwen3/tags)・[Qwen2.5 3B](https://ollama.com/library/qwen2.5:3b-instruct)・[1.5B](https://ollama.com/library/qwen2.5:1.5b-instruct)、入力枠とメモリーの関係は [Ollama公式の説明](https://docs.ollama.com/context-length) を参照してください。

旧版の環境準備で `pip check` や依存関係の衝突が表示された場合は、必要な結果を保存してからColabのランタイムを削除・再接続し、最新版のノートブックを先頭から実行してください。Google Driveに保存していない一時ファイルは、ランタイムの削除で失われます。

### 任意：下部にCPU・GPU・RAMの使用状況を表示する

ノートブックのWeb UI下にあるセル6で `ENABLE_RUNTIME_MONITOR` をONにして実行します。CPU使用率、GPU使用率とGPUメモリー使用量、RAM使用量をバーと直近60回の履歴グラフで表示します。既定はOFF、`MONITOR_INTERVAL_SECONDS` は2秒（1〜30秒で変更可）です。GPUがない・計測できない場合は0%とせず「未取得」と表示し、CPUとRAMの表示を続けます。

計測はバックグラウンドで動きます。「モニターを停止」ボタン、OFFにしてセル6を再実行、または終了セル7で停止できます。セルを再実行すると前の計測を停止するため、二重には起動しません。表示対象はColabランタイム全体で、文字起こしやLLMだけの使用率ではありません。値の履歴はメモリー内の60回分だけに保持し、計測ファイルの保存やキー・録音内容の読取は行いません。

## 追加の文字起こし・音声前処理

画面下部の「モデル」から「Haas-ja-v1.0（公式・実験的） + Nemotron 3 Diarization」を選べます。詳細設定の「文字起こし方式」からも選択できます。Haasを選ぶと日本語・GPUに切り替わり、WhisperXへ戻すときは同じ「モデル」からtiny〜large-v3を選びます。

Haas-ja-v1.0による日本語文字起こしは実験的な対応です。NVIDIA GPUと専用環境が必要です。WindowsではWSL2のUbuntu 24.04を用意し、`scripts\setup_haas_ja.bat` を実行します。Linuxでは `bash scripts/setup_haas_ja.sh` を使います。話者分離にはNemotron 3を使用し、時刻は発話区間のおおよその位置です。

RE-USE音声前処理は `scripts\setup_reuse.bat`（Linuxは `bash scripts/setup_reuse.sh`）で専用環境を準備してから選びます。NVIDIA GPUを使用し、重なった声の一部を抑える場合があります。元の音声と比較して確認してください。準備が足りないときは画面に理由を表示します。

モデルの取得にはインターネット接続が必要です。これらの追加環境は配置先ごとに準備し、別のフォルダーの仮想環境をコピーしないでください。

## 長い文字起こしを確認する

発話の編集画面は100発話ずつ表示します。「前へ」「次へ」で移動でき、本文検索や話者・感情の絞り込みは全発話が対象です。再生や発話の指定で、別のページにある発話へ移ることもできます。ページを切り替えても未保存の編集内容は保持されるので、確認後に「保存」を押してください。
