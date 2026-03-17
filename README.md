# Eliza Agent Server

自分専用のパーソナル AI アシスタントサーバーです。
会話するだけで、家電の操作・検索・アラームなど日常のあれこれを自然言語で頼めます。

---

## できること

### 家電・スマートホームの操作

「エアコン消して」「照明つけて」と話しかけるだけで Switchbot デバイスを制御できます。
室内・室外の温度取得にも対応しています。

### 情報検索

- **Web 検索**: 気になることをその場で調べられます (xAI サーバーサイド)
- **X (Twitter) 検索**: リアルタイムの話題もチェックできます (xAI サーバーサイド)
- **天気**: 「今日の東京の天気は？」「今週の天気予報」など世界中の都市に対応

### YouTube

キーワードで動画を検索し、結果を返します。
「開いて」と続けると、そのままブラウザで再生できます。
検索結果の先頭 URL は自動的にクリップボードにコピーされます。

### アラーム

「朝7時に起こして」「30分後にアラーム」など絶対・相対どちらの指定にも対応。

### クリップボード

「これをコピーして」「クリップボードの中身は？」で読み書きできます。

### ToDo 管理

「〇〇をやることに追加して」「今日のタスクを見せて」でタスクを管理できます。

### 過去ログ検索

「前に〇〇について話したっけ？」など、過去の会話をキーワードで検索できます。

### サブエージェント

複雑な質問に対して Grok (reasoning モード) と Claude Code の両方に並列で聞いて、
まとめて回答を返すことができます。

### スキル

`./skill/` ディレクトリに .md ファイルを置くことで、ツールを組み合わせた手順をスキルとして定義できます。
エージェントはタスクに応じて必要なスキルを参照し、ツール呼び出しに落とし込みます。

### 会話の記憶

過去の会話は自動的に要約・保存されます。
次回以降の会話では、あなたの好みや傾向を踏まえた応答が返ってきます。

---

## セットアップ

```bash
uv sync
```

必要な環境変数:

```bash
export XAI_API_KEY="..."           # Grok API キー (必須)
export SWITCHBOT_API_TOKEN="..."   # Switchbot トークン
export SWITCHBOT_API_SECRET="..."  # Switchbot シークレット
export YOUTUBE_API_KEY="..."       # YouTube Data API キー
export BROWSER_PATH="..."          # ブラウザの実行ファイルパス (アラーム・YouTube・URL 開封に必要)
export SKILL_DIR="./skill"         # スキルディレクトリのパス (省略可、デフォルト: ./skill)
export ELIZA_SECRET_KEY="..."      # API 認証キー (省略可、設定時はリクエストヘッダーに必須)
```

## 起動

```bash
python server.py
```

`http://0.0.0.0:9096` で起動します。

---

## API

### 認証

`ELIZA_SECRET_KEY` を設定している場合、すべてのリクエストに `X-Secret-Key` ヘッダーが必要です。
一致しない場合は **403 Forbidden** を返します。未設定の場合は認証スキップ。

```
X-Secret-Key: <ELIZA_SECRET_KEY の値>
```

### POST /eliza/api/chat

会話履歴を送信して返答を得ます。

```json
{
  "messages": [
    { "role": "user", "content": "エアコン消して" }
  ],
  "use_memory": true,
  "detect_sleep": true,
  "max_tool_loops": 5,
  "deep": false,
  "interact": false
}
```

| フィールド | デフォルト | 説明 |
|---|---|---|
| `use_memory` | `true` | 会話要約をプロンプトに差し込む |
| `detect_sleep` | `true` | sleep 検出を有効にする |
| `max_tool_loops` | `5` | ツール呼び出しの最大ループ数 |
| `deep` | `false` | deep_research スキルを有効にする |
| `interact` | `false` | スキルを interact モードでレンダリングする |

### POST /eliza/api/summary

過去の会話を要約してメモリに保存します（バックグラウンド実行・202 即返し）。
