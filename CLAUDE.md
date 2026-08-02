# CLAUDE.md

## プロジェクト概要

FastAPI + xai_sdk (Grok) を使ったパーソナル AI アシスタントサーバー。
`server.py` がエントリポイント。エージェントロジックは `eliza/agents/` 配下に分割。

## ディレクトリ構造

```
eliza/
  agents/
    router.py          # IntentRouter (意図分類のみ、ツール不使用)
    trivial.py          # TrivialAgent (雑談・挨拶、ツール不使用)
    question.py         # QuestionAgent (x_search/web_search/code_execution のみ)
    translator.py       # TranslatorAgent(TrivialAgent) (翻訳専用)
    full_operation.py   # FullOperationAgent (ツール・スキル呼び出しを行う唯一のエージェント)
  memory.py             # 会話ログの保存・要約・セッション同期
  models.py             # モデル名・reasoning effort の定数
  tools/                # ツール群 (各ファイルが1つのツールカテゴリ)
  prompt/               # プロンプトテンプレート (.md, Jinja2)
skill/                  # スキル定義ファイル (.md)
server.py               # FastAPI エントリポイント
```

## リクエストの流れ (`POST /eliza/api/chat`)

1. `IntentRouter.classify()` が軽量モデルで意図を4値分類する: `Trivial` / `Question` / `Translator` / `FullOperation`
2. ラベルに応じて対応する Agent の `run()` に振り分ける (`server.py`)
   - `Trivial` → `TrivialAgent`: 雑談・挨拶。ツール・スキル不使用
   - `Question` → `QuestionAgent`: サーバーサイドツール (`x_search`, `web_search`, `code_execution`) のみ使用
   - `Translator` → `TranslatorAgent`: 翻訳専用、ツール不使用
   - それ以外 (default) → `FullOperationAgent`: クライアントサイドツール・スキルを使う唯一のエージェント
3. 室内の温度・湿度など Switchbot 系の話題は `IntentRouter` が明示的に `FullOperation` に振る

`FullOperationAgent` (`eliza/agents/full_operation.py`) の主な定数:
- `MAX_TOOL_LOOPS`: ツールループの最大回数
- `STEP_MAX_RETRIES`: API エラー時のステップ単位リトライ回数

`server.py` の `MAX_RETRIES` はこれとは別物で、`/eliza/api/chat` 全体（意図分類〜Agent実行）のリトライ回数。

## ツールの追加方法

1. `eliza/tools/` に新しい .py ファイルを作成する
2. xai_sdk の `@tool` デコレータで関数を定義し、`create_tools()` / `call()` を持つクラスを実装する
3. `eliza/tools/__init__.py` の `create_tools()` と `call()` に追記する

サーバーサイドツール（xAI 側で処理される `x_search`, `web_search`, `code_execution`）は
`is_server_side()` で判定され、client 側では `call()` しない。これらは `QuestionAgent` と
`FullOperationAgent` から使われる。

現在のツールカテゴリ: `switchbot`, `youtube`, `browser`, `clipboard`, `memory`, `skill`,
`subagents`（他エージェント／Claude Code CLI に質問を委譲する）, `schedule`, `tenki`, `todo`, `workspace`。

## スキルの追加方法

`./skill/` ディレクトリに `.md` ファイルを置くだけ。
ファイル名（拡張子なし）がスキル名になる。

スキルファイルには以下を書く:
- 利用するツール一覧
- エージェントが従うべき手順

スキルを実際に使うのは `FullOperationAgent` のみ。`load_skill` ツールはスキルの手順書を
読み込むだけで、ツール操作の実行ではない（`SKILL_FETCHED_INSTRUCTION.md` で直後にモデルへ
念押しする）。

## プロンプトファイル (`eliza/prompt/`)

| ファイル | 用途 | 読み込み元 |
|---|---|---|
| `ELIZA.md` | system prompt (エージェントのキャラクター・基本指示) | `trivial.py`, `question.py`, `full_operation.py` |
| `MEMORY_INSTRUCTION.md` | 直近履歴＋summary を常に system として注入する指示（全リクエストで無条件） | `eliza/memory.py` の `get_memory_context_block()` 経由で `router.py`, `trivial.py`, `question.py`, `full_operation.py` |
| `SKILL_INSTRUCTION.md` | スキル一覧の提示方法 | `full_operation.py` |
| `SKILL_FETCHED_INSTRUCTION.md` | load_skill 直後に「まだ実行していない」と釘を刺す | `full_operation.py` |
| `TOOL_LOOP_INSTRUCTION.md` | ツールループ継続・終了の判断指示 | `full_operation.py` |
| `TRANSLATE_INSTRUCTION.md` | 翻訳専用の指示 | `translator.py` |

すべて Jinja2 テンプレートとして読み込まれる。

## 開発

```bash
uv sync          # 依存インストール
python server.py # 起動 (reload=True、ホットリロード有効)
```

## 注意事項

- `session.parse(AgentAnswer)` で structured output を生成している。API 不安定時に空レスポンスが返ることがある。
  `full_operation.py` の `_step_with_retry()` はステップ単位でリトライし（`STEP_MAX_RETRIES`）、
  `server.py` の `POST /eliza/api/chat` は意図分類〜Agent実行全体を `MAX_RETRIES=3` でリトライする。
- `load_skill` はスキルの手順書を読み込むだけで、ツール操作の実行ではない。`SKILL_FETCHED_INSTRUCTION.md` でモデルに明示している。
- `TODO.md` は `.gitignore` で管理対象外。`git add TODO.md` は失敗する。
