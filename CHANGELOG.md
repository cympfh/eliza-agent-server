# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
