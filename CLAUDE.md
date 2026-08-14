# CLAUDE.md

## プロジェクト概要

FastAPI + xai_sdk (Grok) を使ったパーソナル AI アシスタントサーバー。
`server.py` がエントリポイント。エージェントロジックは `eliza/agents/` 配下に分割。
モデル名・ reasoning effort は `eliza/models.py` の定数（現行は全エージェント同一モデル `grok-4.6`、effort だけ用途別に変える）。

## ディレクトリ構造

```
eliza/
  agents/
    router.py          # IntentRouter (意図分類のみ、ツール不使用)
    trivial.py          # TrivialAgent (雑談・挨拶、ツール不使用)
    question.py         # QuestionAgent (x_search/web_search/code_execution のみ)
    translator.py       # TranslatorAgent(TrivialAgent) (chat は run 継承、専用 API は translate)
    full_operation.py   # FullOperationAgent (ツール・スキル呼び出しを行う唯一のエージェント)
  memory.py             # 会話ログの保存・要約・セッション同期
  models.py             # モデル名・reasoning effort の定数
  skills.py             # スキル定義の読み込み（ツールではない）
  tools/                # ツール群 (各ファイルが1つのツールカテゴリ)
  prompt/               # プロンプトテンプレート (.md, Jinja2)
skill/                  # スキル定義ファイル (.md)
static/                 # ブラウザ向けチャット UI (GET /)
server.py               # FastAPI エントリポイント
```

ランタイムデータは `.memory/`（git 管理外）。メッセージ・セッションの SQLite と summary を置く。

## リクエストの流れ (`POST /eliza/api/chat`)

リクエストフィールド:
- `messages`: 会話履歴（サーバーはリクエスト単位では状態を持たず、毎回完全な履歴を受け取る）
- `interact`: スキル本文を interact モードでレンダリングするか（`FullOperationAgent` のみ使用）
- `context`: `vrchat` / `web` / `cli`。`ELIZA.md` の environment 分岐に渡す（デフォルト `vrchat`）

1. `IntentRouter.classify()` が `MODEL` + `LIGHT_REASONING_EFFORT` で意図を4値分類する: `Trivial` / `Question` / `Translator` / `FullOperation`
2. ラベルに応じて対応する Agent の `run()` に振り分ける (`server.py`)
   - `Trivial` → `TrivialAgent`: 雑談・挨拶。ツール・スキル不使用
   - `Question` → `QuestionAgent`: サーバーサイドツール (`x_search`, `web_search`, `code_execution`) のみ使用。会話履歴（memory context）だけで答えられる質問もここ
   - `Translator` → `TranslatorAgent.run()`: `TrivialAgent.run()` を継承。ツール不使用。`ELIZA.md` の `agent_name == "translator"` 分岐で翻訳する（`TRANSLATE_INSTRUCTION.md` は使わない）
   - それ以外 (default) → `FullOperationAgent`: クライアントサイドツール・スキルを使う唯一のエージェント
3. 室内の温度・湿度など Switchbot 系の話題は `IntentRouter` が明示的に `FullOperation` に振る
4. 応答後、受信メッセージ + 生成メッセージを `eliza.memory.save_messages()` で SQLite に保存する

`FullOperationAgent` (`eliza/agents/full_operation.py`) の主な定数:
- `MAX_TOOL_LOOPS = 5`: ツールループの最大回数
- `STEP_MAX_RETRIES = 3`: API エラー時のステップ単位リトライ回数
- ツールループの `sample` は `HEAVY_REASONING_EFFORT`（medium）。最終 `parse` だけ `LIGHT_REASONING_EFFORT`（low）

ツールループの約束:
- スキル手順書は `eliza/skills.py` で読み、最初から全文注入する
- 同一 `sample` で必要な `tool_calls` をまとめて出す（1ツールずつは禁止）
- ツール実行後は次の `sample` を回し、ツールなしになったら `session.parse` で最終回答する
- 最後の実ツールと同じターンで `ready_to_answer` が来たら、閉じの `sample` を飛ばして `parse` する

`server.py` の `MAX_RETRIES = 3` はこれとは別物で、`/eliza/api/chat` 全体（意図分類〜Agent実行）のリトライ回数。

## その他の API / バックグラウンド

| 経路 | 役割 |
|---|---|
| `GET /` | `static/index.html` のチャット UI |
| `GET /eliza/api/health` | ヘルスチェック |
| `POST /eliza/api/translate` | `TranslatorAgent.translate()`。`TRANSLATE_INSTRUCTION.md` を使う翻訳専用 API |
| `POST /eliza/api/summary` | メモリ要約をバックグラウンド生成（202 即返し） |
| `GET/PUT/DELETE /eliza/api/sessions` | Web UI セッションのサーバーサイド永続化 |

lifespan で動くループ:
- 30分ごとの auto summary（直近30分にやりとりがなければスキップ）
- スケジュールランナー（5秒間隔で due なツール呼び出しを実行）

## ツールの追加方法

1. `eliza/tools/` に新しい .py ファイルを作成する
2. xai_sdk の `@tool` デコレータで関数を定義し、`create_tools()` / `call()` を持つクラスを実装する
3. `eliza/tools/__init__.py` の `create_tools()` と `call()` に追記する

サーバーサイドツール（xAI 側で処理される `x_search`, `web_search`, `code_execution`）は
`is_server_side()` で判定され、client 側では `call()` しない。
`QuestionAgent` は `xai_sdk.tools` を直接渡し、`FullOperationAgent` は `eliza.tools.create_tools(search=True)` 経由で同じ3つを載せる。

現在のツールカテゴリ: `switchbot`, `youtube`, `browser`, `clipboard`, `memory`, `ready`
（`ready_to_answer`: 最終回答へ進むフラグ）,
`schedule`, `todo`, `workspace`。
スキルはツールではなく、`FullOperationAgent` が手順書全文を system に注入する。

## スキルの追加方法

`SKILL_DIR`（デフォルト `./skill`）に `.md` ファイルを置く。
スキル名はファイル名ではなく、YAML frontmatter の `name:`。`description:` も必須。
どちらが欠けるとそのファイルは読み飛ばされる。

```markdown
---
name: aircon
description: エアコンの操作を行う
---
（手順。Jinja2 テンプレート。`interact` 変数が渡る）
```

スキルファイルには以下を書く:
- 利用するツール一覧
- エージェントが従うべき手順

スキルを実際に使うのは `FullOperationAgent` のみ。`eliza/skills.py` が定義を読み、
手順書全文を system に注入する。Router には name + description だけ渡す。

## プロンプトファイル (`eliza/prompt/`)

| ファイル | 用途 | 読み込み元 |
|---|---|---|
| `ELIZA.md` | system prompt（キャラクター・`context` / `agent_name` 分岐） | `trivial.py`, `question.py`, `full_operation.py`。`translator.py` の chat 経路は `TrivialAgent.run()` 継承でここを使う |
| `MEMORY_INSTRUCTION.md` | 直近履歴＋summary を常に system として注入する指示（chat 経路は無条件） | `eliza/memory.py` の `get_memory_context_block()` 経由で `router.py`, `trivial.py`, `question.py`, `full_operation.py` |
| `SKILL_INSTRUCTION.md` | スキル手順書の全文注入 | `full_operation.py` |
| `TOOL_LOOP_INSTRUCTION.md` | ツールループ継続・終了の判断指示 | `full_operation.py` |
| `TRANSLATE_INSTRUCTION.md` | 翻訳専用 API の指示 | `translator.py` の `translate()`（`POST /eliza/api/translate`）のみ |

すべて Jinja2 テンプレートとして読み込まれる。

## 開発

```bash
uv sync          # 依存インストール
python server.py # 起動 (0.0.0.0:9096, reload=True、ホットリロード有効)
```

`Makefile` の `make serve` は `uv run ./server.py`。

## 注意事項

- `session.parse(AgentAnswer)` で structured output を生成している。API 不安定時に空レスポンスが返ることがある。
  `full_operation.py` の `_step_with_retry()` はステップ単位でリトライし（`STEP_MAX_RETRIES`）、
  `server.py` の `POST /eliza/api/chat` は意図分類〜Agent実行全体を `MAX_RETRIES=3` でリトライする。
- スキル手順書は `eliza/skills.py` 経由で `FullOperationAgent` が最初から全文注入する。
- `TODO.md` は `.gitignore` で管理対象外。`git add TODO.md` は失敗する。
