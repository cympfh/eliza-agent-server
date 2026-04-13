---
name: aircon
description: エアコン (air conditioner) の操作を行う
---
# エアコン操作

## tools

- switchbot_post_aircon_off
    - エアコンを消す
- switchbot_post_aircon_on
    - エアコンをつける
    - 引数 `mode` でモードを指定できる
        - Enum: `cool`, `heat`, `fan`
- schedule_tool_call_after_minutes
    - 指定した分数後にツールを実行するようスケジュールする

## スキルの手順

1. ユーザーがエアコンの停止を求めているなら switchbot_post_aircon_off を呼び出して即座にスキルを終了する
2. そうでない場合、以下を実行する
3. ユーザーが求めるモードが不明の場合
    - システムプロンプトに含まれる現在時刻から季節を判断する
    - 現在の室温を switchbot_get_room_temperature で取得する
    - 季節と室温から、ユーザーが今暑いか寒いかを判断する
    - ユーザーにモードを提案だけして、スキルを終了する
4. ユーザーが求めるモードが明確な場合は、そのモードを引数にして switchbot_post_aircon_on を呼び出す
5. ユーザーが時間制限付きで依頼した場合（例:「1時間だけ冷房入れて」）
    - 今すぐ switchbot_post_aircon_on を実行する
    - schedule_tool_call_after_minutes で指定時間後に switchbot_post_aircon_off を実行するようスケジュールする
    - 例:「1時間だけ冷房」→ switchbot_post_aircon_on(mode="cool") + schedule_tool_call_after_minutes(tool_name="switchbot_post_aircon_off", tool_args={}, minutes=60)
