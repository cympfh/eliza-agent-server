---
name: alarm
description: アラーム・タイマーをセットする
---
# アラーム・タイマー

## tools

- schedule_tool_call
    - 指定した絶対時刻にツールをスケジュール実行する
- schedule_tool_call_after_minutes
    - 指定した分数後にツールをスケジュール実行する
- browser_url_open
    - ブラウザで URL を開く

## スキルの手順

1. ユーザーが指定した時刻を解釈する
    - 「7時にアラーム」「朝7時に起こして」→ 絶対時刻 → `schedule_tool_call` を使う
    - 「3分後にアラーム」「30分後に教えて」→ 相対時間 → `schedule_tool_call_after_minutes` を使う
2. 以下の内容でスケジュールを登録する
    - tool_name: `browser_url_open`
    - tool_args: `{"url": "https://www.youtube.com/watch?v=vHHHmyihGKE"}`
    - 時刻: ユーザーの指定に応じて `execute_at` または `minutes` を設定
3. スケジュール登録結果をユーザーに報告する
    - 「{時刻}にアラームをセットしました」
