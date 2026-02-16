# Eliza Agent Server

FastAPI ベースの Grok API サーバーです。x_search、web_search、そして Switchbot API を統合したチャット機能を提供します。

## 特徴

- ✨ **ステートレス設計**: サーバーは状態を持たず、毎回完全な会話履歴を受け取ります
- 🔍 **検索ツール**: x_search（X/Twitter 検索）と web_search（Web 検索）を常に利用可能
- 🏠 **スマートホーム連携**: Switchbot デバイスの制御とシーンの実行が可能
- 🚀 **FastAPI**: 高速で使いやすい API
- 📝 **型安全**: Pydantic による完全な型チェック

## 必須環境変数

以下の環境変数を設定する必要があります：

### 必須

- **XAI_API_KEY**: xAI（Grok）の API キー
  - https://console.x.ai/ から取得
- **SWITCHBOT_API_TOKEN**: Switchbot API トークン
  - Switchbot アプリから取得
- **SWITCHBOT_API_SECRET**: Switchbot API シークレット
  - Switchbot アプリから取得

### 環境変数の設定例

```bash
export XAI_API_KEY="your-xai-api-key-here"
export SWITCHBOT_API_TOKEN="your-switchbot-token-here"
export SWITCHBOT_API_SECRET="your-switchbot-secret-here"
```

## インストール

```bash
# 依存関係のインストール
uv sync
```

## サーバーの起動

```bash
python server.py
```

サーバーは `http://0.0.0.0:9096` で起動します。

## API エンドポイント

### POST /chat

会話履歴を受け取り、次の返答を生成します。

**リクエスト:**

```json
{
  "messages": [
    {
      "role": "system",
      "content": "あなたは親切なスマートホームアシスタントです。"
    },
    {
      "role": "user",
      "content": "リビングの照明をつけて"
    }
  ],
  "model": "grok-4-1-fast"
}
```

**レスポンス:**

```json
{
  "message": {
    "role": "assistant",
    "content": "かしこまりました。リビングの照明をオンにします..."
  }
}
```

### GET /health

ヘルスチェック用エンドポイント

**レスポンス:**

```json
{
  "status": "ok"
}
```

### GET /tools

利用可能なツール一覧を返す

**レスポンス:**

```json
{
  "tools": [
    "x_search",
    "web_search",
    "code_execution",
    "get_room_temperature",
    "get_outside_temperature",
    "post_aircon_off",
    "post_aircon_on",
    "post_light_off",
    "post_light_on"
  ]
}
```

## 使用例

### curl を使った例

```bash
curl -X POST http://localhost:9096/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Switchbot のデバイス一覧を教えて"}
    ]
  }'
```

### Python を使った例

```python
import requests

response = requests.post(
    "http://localhost:9096/chat",
    json={
        "messages": [
            {"role": "user", "content": "エアコンの温度を25度に設定して"}
        ]
    }
)

print(response.json())
```

## 利用可能なツール

サーバーは以下のツールを提供します：

### 検索・実行ツール（常時有効）

1. **x_search**: X (Twitter) のリアルタイム情報を検索
2. **web_search**: Web 全体を検索
3. **code_execution**: コードを実行

### Switchbot ツール（環境変数が設定されている場合）

1. **get_room_temperature**: 室内温度を取得
2. **get_outside_temperature**: 室外温度を取得
3. **post_aircon_off**: エアコンをオフにする
4. **post_aircon_on**: エアコンをオンにする
5. **post_light_off**: 照明をオフにする
6. **post_light_on**: 照明をオンにする

これらのツールは Grok が必要に応じて自動的に使用します。

## Switchbot API について

Switchbot API の詳細は公式ドキュメントを参照してください：
https://github.com/OpenWonderLabs/SwitchBotAPI

### API トークンとシークレットの取得方法

1. Switchbot アプリを開く
2. プロフィール > 設定 > アプリバージョン を 10 回タップして開発者モードを有効化
3. 設定 > 開発者向けオプション でトークンを取得

## 技術スタック

- **FastAPI**: Web フレームワーク
- **uvicorn**: ASGI サーバー
- **xai-sdk**: Grok API クライアント
- **Pydantic**: データバリデーション
- **requests**: HTTP クライアント

## ディレクトリ構造

```
eliza-agent-server/
├── server.py              # メインサーバー
├── tools/
│   ├── __init__.py
│   └── switchbot.py       # Switchbot API クライアント
├── pyproject.toml         # プロジェクト設定
├── .python-version        # Python バージョン
└── README.md              # このファイル
```

## ライセンス

MIT
