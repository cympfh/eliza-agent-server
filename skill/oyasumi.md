---
name: oyasumi
description: ユーザーが「おやすみ」と言った場合、家の中の電灯を全て消してあげてから、優しく「おやすみなさい」と言ってあげる
---

# おやすみスキル

## tools

- switchbot_post_light_off
    - 家の中の電灯を全て消す
    - 引数不要
- ready_to_answer
    - 消灯と同じターンで呼ぶ

## 手順

ユーザーが「おやすみ」と就寝の挨拶をしたら

1. switchbot_post_light_off を呼び出して家の中の電灯を全て消す
2. 同じターンで ready_to_answer を呼ぶ
3. 優しく、あなた自身の言葉で「おやすみ」とか「良い夢見てね」とか愛を込めて挨拶を返す
