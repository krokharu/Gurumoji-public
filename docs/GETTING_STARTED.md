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
5. 保存と書き出しを行います。分析やAIの解釈は、入力した録音や研究目的に照らして採用判断を行ってください。

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

[Colabノートブック](https://colab.research.google.com/github/krokharu/Gurumoji-public/blob/public%2Frelease/notebooks/Gurumoji_Colab.ipynb) を上から順に実行します。GPU、モデルの利用条件、認証情報、Google Driveへの保存を各セルの案内に従って設定してください。Windowsの `.venv` は転用しません。

ランタイム上の処理やモデルが実行中の場合、取得処理は更新を拒否します。保存状態を確認し、ノートブックの終了セルで停止してから更新してください。
