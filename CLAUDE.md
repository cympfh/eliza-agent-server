# CLAUDE.md

## プロジェクト概要

FastAPI + xai_sdk (Grok) を使ったパーソナル AI アシスタントサーバー。
`server.py` がエントリポイント。エージェントロジックは `eliza/agent.py`。

## ディレクトリ構造

```
eliza/
  agent.py          # Agent クラス (ツールループ・structured output)
  memory.py         # 会話ログの保存・要約
  tools/            # ツール群 (各ファイルが1つのツールカテゴリ)
  prompt/           # プロンプトテンプレート (.md, Jinja2)
skill/              # スキル定義ファイル (.md)
server.py           # FastAPI エントリポイント
```

## ツールの追加方法

1. `eliza/tools/` に新しい .py ファイルを作成する
2. xai_sdk の `@tool` デコレータで関数を定義する
3. `eliza/tools/__init__.py` の `create_tools()` と `call()` に追記する

サーバーサイドツール（xAI 側で処理される `x_search`, `web_search`, `code_execution`）は
`is_server_side()` で判定され、client 側では `call()` しない。

## スキルの追加方法

`./skill/` ディレクトリに `.md` ファイルを置くだけ。
ファイル名（拡張子なし）がスキル名になる。

スキルファイルには以下を書く:
- 利用するツール一覧
- エージェントが従うべき手順

`deep=True` のときのみ有効にしたいスキルは `deep_research.md` のように
`Skill` クラスの除外ロジックに従って管理する。

## プロンプトファイル (`eliza/prompt/`)

| ファイル | 用途 |
|---|---|
| `ELIZA.md` | system prompt (エージェントのキャラクター・基本指示) |
| `MEMORY_INSTRUCTION.md` | 会話要約をどう使うかの指示 |
| `SKILL_INSTRUCTION.md` | スキル一覧の提示方法 |
| `SKILL_FETCHED_INSTRUCTION.md` | skill_use 直後に「まだ実行していない」と釘を刺す |
| `TOOL_LOOP_INSTRUCTION.md` | ツールループ継続・終了の判断指示 |
| `TOOL_REQUIRED_INSTRUCTION.md` | ツール使用意図を示したのに呼ばなかった場合のリトライ指示 |
| `SLEEP_INSTRUCTION.md` | sleep 検出の指示 |

すべて Jinja2 テンプレートとして `_load_prompt()` で読み込まれる。

## 開発

```bash
uv sync          # 依存インストール
python server.py # 起動 (reload=True、ホットリロード有効)
```

## 注意事項

- `session.parse(AgentAnswer)` で structured output を生成している。API 不安定時に空レスポンスが返ることがある。`server.py` の MAX_RETRIES=3 でリトライしている。
- `skill_use` はスキルの手順書を取得するだけで、ツール操作の実行ではない。`SKILL_FETCHED_INSTRUCTION.md` でモデルに明示している。
