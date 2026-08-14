# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `skill/temperature.md`: 室内（リビング）/ 室外（ベランダ）の温湿度取得

### Removed
- 未使用の `tools/subagents`（他エージェント委譲）と `tools/tenki`（OpenWeatherMap）を削除。天気は web_search に委譲
- ChatRequest の `interact` とドキュメント上の `deep` を削除。UI の Interact トグルも削除
- workspace スキルの interact 分岐を削除（確認プロンプトは出さない）

## [0.7.0] - 2026-05-30

### Added
- セッションのサーバーサイド永続化 (`sessions.sqlite`) と CRUD API (`GET/PUT/DELETE /eliza/api/sessions`)
- UI: セッション一覧にクラウド同期アイコンを追加（syncSessionToServer / fetchServerSessions）
- UI: 最後の assistant メッセージに「再生成」ボタンを追加（retryMessage）

(git commit: 8ca0dcc)

## [0.6.2] - 2026-05-28

### Added
- `ChatResponse` に `agent_name` フィールドを追加し、応答したエージェント名を返すように
- `index.html` のメッセージフッターに agent_name を薄く表示

### Changed
- IntentRouter: 室内温湿度の質問は必ず FullOperation に分類する制約を追加
- ELIZA.md (full_operation): 室内温湿度は `switchbot_get_room_temperature` を必ず呼ぶよう明記、外気温・tenki からの推定を禁止

(git commit: 5a26e03)

## [0.6.1] - 2026-05-28

### Changed
- QuestionAgent が会話履歴ベースの質問でも検索ツールを強制的に呼ばせようとしていた挙動を修正
- IntentRouter の Question 分類基準を明確化（web/X 検索だけでなく会話履歴でも回答可能なものは Question へ）

### Removed
- QuestionAgent 内部の検索未使用検知 + 最大10回リトライループ（_used_search と MAX_LOOP）
- それに伴う QUESTION_SEARCH_REQUIRED_INSTRUCTION.md（不要になったため削除）

(git commit: 8b27fda)

## [0.6.0] - 2026-05-27

### Added
- ブラウザ向けフル機能チャットUI (GET /) を追加
  - Tailwind + marked.js によるモダンなダークテーマ単一ファイルUI
  - 複数会話セッション管理（localStorage永続化、最初のユーザー発言があるまで保存しない設計）
  - QRコードモーダル（ヘッダー右上）で http://100.84.144.97:9096 を簡単に共有
  - ヘッダーボタンを「クリア」から「新しい会話」へ変更 + 吹き出し＋アイコン
  - 内部リファクタ: `clearHistory` → `startNewConversation`（命名の明確化）
  - 仮想welcomeメッセージ（messages配列には保存されない）、reasoning/citations/toolsの折り畳み表示、Deep/Interactトグル対応

- server.py に `/static` マウントとルート `GET /` で `static/index.html` を返すエンドポイントを追加

(git commit: 5e0df98)

## [0.5.0] - 2026-05-26

### Added
- `TranslatorAgent` を新設し、翻訳リクエストを `IntentRouter` で専用ルーティング
- 全 Agent に `agent_name` を追加し、Jinja2 テンプレート経由で `ELIZA.md` に渡す

### Changed
- 全 Agent を `grok-4.3` へ移行し、用途別に `reasoning_effort` を設定
  - IntentRouter / TrivialAgent / TranslatorAgent / memory: `none`
  - QuestionAgent: `low`
  - FullOperationAgent / SubAgents: `medium`
- `eliza/models.py` を `MODEL` + `*_REASONING_EFFORT` 定数に整理（`HEAVY_MODEL`/`LIGHT_MODEL` 廃止）
- `xai-sdk` を `>=1.12.2` に引き上げ（`none`/`medium` reasoning_effort サポート）
- スケジュールチェック間隔を 30 秒 → 5 秒に変更

(git commit: 4cccd54)

## [0.4.0] - 2026-04-13

### Added
- ツールのスケジュール実行機能 (`schedule_tool_call`, `schedule_tool_call_after_minutes`)
- サーバー lifespan にスケジュールランナー (30秒間隔の非同期バックグラウンドループ)
- アラームスキル (`skill/alarm.md`) - スケジュール + ブラウザで YouTube を開く方式

### Removed
- `alarm` ツール (`eliza/tools/alarm.py`) をスケジュール+ブラウザの組み合わせで代替

### Fixed
- `skill/aircon.md` の `bash_exec_date` 参照を修正

(git commit: e6d71f2)

## [0.3.0] - 2026-04-13

### Changed
- `FullAgent` と `OperationAgent` を `FullOperationAgent` に統合し、コードを簡略化
- 意図分類を4クラス（Trivial/Question/Operation/Full）から3クラス（Trivial/Question/FullOperation）に簡略化
- `FullOperationAgent` で検索ツールも常時有効化（`search=True`）

### Fixed
- switchbot の cool モードのパラメータを除湿の正しい値に修正（`24,2,1,on` → `24,3,1,on`）

(git commit: c6a7fa7)

## [0.2.0] - 2026-04-11

### Added
- Operation / Full エージェントへの分割（ローカル操作専用 / 検索+ローカル複合）
- 30分ごとの自動 summary 生成
- summary と一緒に直近3往復の会話履歴をプロンプトに差し込む
- `ELIZA_SECRET_KEY` による API 認証機構
- `/eliza/api/health` エンドポイント
- Skill キャッシュ（30秒 TTL、mtime による変更検知）

### Changed
- 現在時刻を `bash_exec_date` ツールではなくシステムプロンプトへ自動差し込みする方式に変更
- プロンプトテンプレートに XML タグを追加して構造化
- IntentRouter の Operation 説明から「時間の確認」を削除（誤分類対策）
- Light モデルを grok-4.20 に変更（Experimental）

### Removed
- `bash_exec_date` ツールを削除

(git commit: bb2f14d)

## [0.1.0] - 2026-03-01

### Added
- FastAPI + xai_sdk (Grok) によるパーソナル AI アシスタントサーバー初期実装
- Trivial / Question / Operation の IntentRouter による意図分類
- ツールループ付きエージェント（switchbot, youtube, alarm, browser, clipboard, todo など）
- Skill 定義（./skill/*.md）とスキルキャッシュ
- SQLite ベースのメモリ（会話ログ・デイリーサマリー）
- structured output による最終回答生成
- Docker コンテナ対応

(git commit: e5919cc)
