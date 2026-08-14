---
name: temperature
description: 家の室内（リビング）または室外（ベランダ）の温度・湿度を取得する。「部屋の温度」「家の中は？」「外は？」「ベランダの湿度」など
---
# 温湿度の取得

## tools

- switchbot_get_room_temperature
    - 室内（リビング）の温度と湿度
    - 引数なし
- switchbot_get_outside_temperature
    - 室外（ベランダ）の温度と湿度
    - 引数なし
- ready_to_answer
    - 取得と同じターンで呼ぶ

## 手順

1. 室内・部屋・家の中なら `switchbot_get_room_temperature`
2. 外・ベランダなら `switchbot_get_outside_temperature`
3. 両方なら両方同時に呼ぶ
4. 同じターンで `ready_to_answer` を呼ぶ
5. 取得結果を報告して終了

一般の天気・予報は web_search。このスキルではない。
