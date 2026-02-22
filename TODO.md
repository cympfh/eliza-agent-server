@CLAUDE TODO List

## [x] Grok がエラーしたら最大3回リトライするようにする [2026-02-20 完了]

## [x] logs.jsonl [2026-02-20 完了]

今は
```
{"datetime": "2026-02-18T19:04:42", "summary": "YouTubeでおさだの最新旅行動画を探すよう依頼した", "feedback": "おさだの旅行動画に興味があり、最新コンテンツを求める傾向"}
```
という形式だが、簡素で、重要な事実を取りこぼしやすい
```
{"datetime": "2026-02-18T19:04:42", "summary": "YouTubeでおさだの最新旅行動画を探すよう依頼した", "important_facts": ["ユーザーはおさだの旅行動画に興味がある", "ユーザーは最新コンテンツを求める傾向がある"], "feedback": "おさだの旅行動画に興味があり、最新コンテンツを求める傾向"}
```

important_facts を追加して。
ログ出力にも反映させる。


## [x] Sleep フラグを ChatResponse に追加する [2026-02-22 完了]

eliza-agent-app から Sleep コマンドを受け取るために、`ChatResponse` に `sleep: bool = False` フィールドを追加する。

### 仕様

- `ChatResponse` に `sleep: bool = False` を追加
- POST /chat のシステムメッセージに以下の指示を自動追記する:
  - 「ユーザーが寝ると判断した場合（例: おやすみ、寝る、などの発言や寝息と推察される内容）、レスポンスの末尾に `[SLEEP]` というマーカーを付けてください。」
- レスポンス生成後、`[SLEEP]` マーカーが含まれていれば:
  - `sleep=True` を返す
  - レスポンス本文の `[SLEEP]` マーカーはそのまま返す（ユーザーにも見せる）

### 目的

eliza-agent-app 側が `sleep=true` を受け取ったら、自動で `stop_monitoring()` を呼び出す。

## [x] Bash という tool を追加する [2026-02-22 完了]

```
class Bash:
    ...
```

"bash_exec_date" というツールを追加する.
`date` コマンドを実行して、現在の日付と時刻を取得するためのツール。
