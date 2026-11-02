# 任意機能: AIST音声感情分析（くしなだ / いざなみ）

この手順の設定ファイルは `config/tokens.json`、実行ファイルは `scripts/setup_emotion.bat`、モデルの保存先は `runtime/models` です。

Web UIの「音声感情分析」をONにすると、話者分離後の各発話セグメントごとに音声を切り出し、AIST公開の日本語音声感情認識モデルで感情ラベルを付与します。文字内容ではなく音声情報を使います。

## モデル

- 推奨: `くしなだ`（`imprt/kushinada-hubert-large-jtes-er`）
- 比較用: `いざなみ`（`imprt/izanami-wav2vec2-large-jtes-er`）
- 両方実行も可能ですが、処理時間とVRAM/RAM使用量が増えます。

## 初回セットアップ

Hugging Faceで次のモデルページの利用条件に同意してください。

- <https://huggingface.co/imprt/kushinada-hubert-large-jtes-er>
- <https://huggingface.co/imprt/kushinada-hubert-large>
- <https://huggingface.co/imprt/izanami-wav2vec2-large-jtes-er>
- <https://huggingface.co/imprt/izanami-wav2vec2-large>

その後、`tokens.json` の `huggingface_token` を設定した状態で、必要な場合だけ次を実行します。

```bat
scripts\setup_emotion.bat
```

`.venv`がまだない場合は`run.bat`の環境構築を自動的に呼び出します。Gitが利用可能なら
S3PRLをcloneし、Gitがない環境ではPython標準機能で固定バージョンのZIPを取得します。
そのため通常は`setup_emotion.bat`のダブルクリックだけで進行できます。初回実行には
64bit版Python 3.10～3.13、FFmpeg、インターネット接続が必要です。

このセットアップはS3PRLの感情分析ランナーに必要な最小構成だけを導入します。
音声評価・学習用パッケージまで含むS3PRLの`.[all]`は、WindowsでC++ビルドを
要求し、通常の文字起こし環境と競合するため使用しません。

セットアップの最後に、`tokens.json`のトークンを表示せず、実際のモデルファイルへ
HEADリクエストを送り、次の3区分を確認します。

1. Hugging Faceトークン認証
2. 話者分離モデル（pyannote、3リポジトリ）
3. AIST感情分析モデル（くしなだ／いざなみ、4リポジトリ）

各リポジトリを`[OK]`または`[NG]`で表示し、`[NG]`の場合は同意ページのURLを表示します。
結果を確認できるよう、成功・失敗のどちらでも最後にキー入力を待ちます。

感情分析をONにした時だけS3PRLとAISTモデルを使います。通常の文字起こし起動では読み込みません。

## 出力

感情分析をONにした場合、通常の文字起こし出力に加えて次が追加されます。

```text
入力ファイル名_感情分析.json
入力ファイル名_感情分析.csv
```

通常のJSON出力をONにした場合は、各`segments`にも`emotions`が入ります。S3PRL側の標準出力仕様上、現在保存するのは主ラベルです。確信度は取得できる場合のみ入り、取れない場合は`null`になります。
