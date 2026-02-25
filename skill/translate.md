---
name: translate
description: テキストの翻訳を行う
---

# テキストの翻訳を行う

1. ユーザーが翻訳を求めたらこのスキルを発動する
2. 明示的に翻訳の停止を求められるまで、このスキルは発動を続ける
3. ユーザーの入力を翻訳する

## 翻訳フォーマット

```
${JP_TEXT}
${ZH_TEXT}
${EN_TEXT}
```

## EXAMPLE

User: 「こんにちは、世界！」

```
こんにちは、世界！
你好，世界！
Hello, World!
```

User: 「次を翻訳して『怎么了？』」

```
いかがですか？
怎么了？
What's wrong?
```

User: 「Good night!」

```
おやすみなさい！
晚安！
Good night!
```

User: 「翻訳を停止して」

スキルを停止する
