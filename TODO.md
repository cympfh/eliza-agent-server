@CLAUDE

これはあなたにお願いしたい事項の管理シートです。
完了したら, 見出しの後ろに [☑ YYYY-MM-DD] を追加してください。

1. /memory にある summary.txt を summary.json に変更する [☑ 2026-02-19]

今までは単に「会話履歴の要約」に過ぎなかったが、
今後の会話に役立てるため、会話履歴の要約に加えて、ユーザー情報（ユーザーの好み、会話スタイル）を多く含めるように指示せよ。
summary.json はそれなりにリッチな内容にする必要があると思う。
以下の JSON 形式を System prompt に例として追加してね。

```summary.json
{
  "recent_conversation": "エアコンの操作を行った。動画検索をした",
  "user_preferences": {
    "hobbies": ["旅行", "VTuber"],
    "conversation_style": "短く簡潔に指示する",
    "(anything as you like)": "...",
    "...": "..."
  }
}
```

save_memory および memory.get() の2箇所を修正する必要があると思う。

2. POST /memory で messages が空のとき、今はエラー扱いにしてるが、挙動変更する。 [☑ 2026-02-19]
空なら logs.jsonl への追加はスキップするが、logs.jsonl から summary.json への更新だけは行うこととする。
