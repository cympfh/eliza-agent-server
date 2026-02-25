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

## スキルの手順

1. ユーザーがエアコンの停止を求めているなら switchbot_post_aircon_off を呼び出して即座にスキルを終了する
2. そうでない場合、以下を実行する
3. ユーザーが求めるモードが不明の場合
    - 今日の日付を bash_exec_date で取得して、現在の季節を判断する
    - 現在の室温を switchbot_get_room_temperature で取得する
    - 季節と室温から、ユーザーが今暑いか寒いかを判断する
    - ユーザーにモードを提案だけして、スキルを終了する
4. ユーザーが求めるモードが明確な場合は、そのモードを引数にして switchbot_post_aircon_on を呼び出す
