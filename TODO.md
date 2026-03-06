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

## [x] tool calling function のループが無限ループになるのを防止する [2026-02-22 完了]

最大でも全体で3回のループで止める
`while True` → `for tool_loop in range(1, MAX_TOOL_LOOPS + 1)` に変更。
3回目のループでツールがまだ使われた場合は「これ以上ツールは使用できません」と伝えるシステムメッセージを追加してループを終了させる。
（`sample(tools=[])` はAPIが対応していなかったため、メッセージによる誘導に変更）

## [x] Switchbot/エアコン操作を完成させる [2026-02-23 14:55 完了]

switchbot_aircon_on() に引数を渡せるようにする

```
def switchbot_aircon_on(self, mode: Literal["cool", "heat", "fan"]):
    if mode == "heat":
        # 暖房をつける処理
        今ある "parameter": "26,5,1,on", で OK
    elif mode == "cool":
        # 冷房をつける処理
        "parameter": "24,2,1,on"
    elif mode == "fan":
        # 送風をつける処理
        # 普通に熱い程度なら送風でいい
        "parameter": "25,4,3,on"
```

## [x] Response に tool フィールドをオプショナルで追加 [2026-02-24 完了]

ChatResponse に `tool: list[tuple[dict, dict]] | None = None` を追加。
内容はtool呼び出しとその結果のリスト。

## [x] Skill が定義できる [2026-02-24 完了]

### Skill 定義

./skill/xxx.md, ./skill/yyy.md みたいなファイルを置いたら勝手にスキルと認識して tool として使えるようになる
./skill/video.md が既にあるので読んでみて

```
class Skill:
  name: str
  description: str
  instruction: str
```

利用可能な skill の (name, description) のリストを Grok 問い合わせの際に渡す。

```
以下はあなたが利用できる Skill のリストです。
これは tool を更に抽象化したもので、特定のタスクを実行するための手順が定義されています。

- video: 動画の検索や再生に関するスキル
- (name): (description)

Skill を使う場合は、skill_use(skill_name) を呼び出してください。
```

### Skill を使う

skill_use という tool を追加する
これは skill_name から instruction を結果として返す

```
{
  "name": "(skill_name)",
  "insturcition": "(skill_instruction)"
  "next_step": "この手順に従ってタスクを tool に分解し実行してください。"
}
```

## [x] Ctrl-C, SIGINT, SIGTERM で Graceful Shutdown する [2026-02-24 完了]

## [x] ハードコードされたプロンプトを eliza/prompt/ に切り出す [2026-02-25 完了]

- eliza/prompt/ELIZA.md: 全体のシステムプロンプト
- eliza/prompt/MEMORY_INSTRUCTION.md: memory summary の差し込みプロンプト（`{summary_str}` プレースホルダー）
- eliza/prompt/SKILL_INSTRUCTION.md: skill 一覧の差し込みプロンプト（`{skill_list}` プレースホルダー）
- eliza/prompt/SLEEP_INSTRUCTION.md: sleep 検出の差し込みプロンプト
- eliza/prompt/TOOL_LOOP_INSTRUCTION.md: tool ループ制御プロンプト（jinja2 の条件分岐で `remaining` を使用）
- jinja2 を導入し、全プロンプトテンプレートを `Template.render()` で統一

## [x] Grok 呼び出し処理を eliza/agent.py に移動する [2026-02-25 完了]

- `Agent` クラスと `AgentResponse` クラスを新規作成
- `_inject_eliza_prompt` / `_inject_memory_summary` / `_inject_skill_summary` / `_inject_sleep_instruction` をメソッドに整理
- `Agent.run()` がプロンプト差し込み・tool calling ループを一括して担う
- `server.py` の `post_chat` は `Agent.run()` を呼ぶだけに簡略化

## [x] POST /chat に detect_sleep を追加 [2026-03-03 完了]

`detect_sleep: bool=True` を `ChatRequest` のフィールドとして追加する。
このフラグが True の場合のみ `SLEEP_INSTRUCTION.md` をプロンプトに差し込む。
今は常に挿し込まれている。

## [x] Message に timestamp と message_id を追加する [2026-03-04 完了]

受け取る Message も返す Message も、両方とも timestamp と message_id を持つようにする。

```
  timestamp: datetime
  message_id: (16文字程度のhash値)
```

## [x] /memory および memory log の持ち方を見直す [2026-03-05 完了]

次のようにする

- POST /chat で受け取った messages と生成した message はこの時点で ./.memory/messages.sqlite に保存する
    - `(message_id, timestamp, role, content)` の形式で保存
    - ただし message_id で重複があったら保存しない（同じ message が複数回送られてくることがあるため）
- 今の POST /memory を廃止
- 新しく POST /summary というエンドポイントを作る
    - POST data は特に何も受け取らない
    - 次の二つを行う
        - daily summary を生成
            - ./.memory/messages.sqlite に保存されている全 message を読み込む
            - 一日ごとに分割して summary を生成
                - ./.memory/summary/2026-03-04.json で保存
                    ```json
                    {
                        "created_datetime": "2026-03-04T23:59:59 (JSTで)",
                        "num_mssages": 100,  // この日にやりとりされた messages の数
                        "messages": [message_id のリスト],
                        "summary": "この日にやりとりされた内容の要約",
                        "user_profile": {
                            "interests": ["旅行", "料理"],
                            "tendencies": ["最新の情報を求める傾向がある"]
                        }
                    }
                    ```
                - 既にこのファイルがあるときは messages を比較して、新しいものがあるときだけ生成する。同じならスキップする。
        - all summary を生成
            - daily summary のいずれかが更新された場合のみ生成する
            - ./.memory/summary/*.json を全て読み込む
                - .summary と .user_profile だけを取り出す
            - 全期間の summary を統合して生成
                - ./.memory/summary/all.json
                    ```json
                    {
                        "created_datetime": "2026-03-04T23:59:59 (JSTで)",
                        "num_mssages": num_messages の和,
                        "summary": "全期間を通しての要約",
                        "user_profile": {
                            "interests": ["旅行", "料理"],
                            "tendencies": ["最新の情報を求める傾向がある"]
                        }
                    }
                    ```

## [x] max_loop_tools を ChatRequest に追加 [2026-03-05 完了]

agent.run からは必須にする
ChatRequest で default は 5 にする

## [x] ELIZA.md プロンプト強化 [2026-03-05 完了]

最新情報・日時・天気・ニュース関連の質問は必ず検索ツールを使うよう明記、回答だけでなく実際にツールを実行することを強制する。

## [x] agent.py ループロジック強化 [2026-03-05 完了]

ツールを使わずに「検索します」「調べます」等のフレーズで終わったレスポンスを検知し、ツール使用を促すシステムメッセージを挟んでリトライする。

## [x] 最終回答を structured output 化 [2026-03-05 完了]

`AgentAnswer(BaseModel)` を導入し、最終回答を `session.parse(AgentAnswer)` で生成する。
`reasoning` と `answer` フィールドを持ち、`ChatResponse` にも `reasoning` を追加。
`AgentResponse` も BaseModel にリファクタリング。

## [x] Tool Definition も Pydantic を使う [2026-03-05 完了]

https://docs.x.ai/developers/tools/function-calling の "Defining Tools with Pydantic" 参考
各ツールファイルに `BaseModel` + `Field` でパラメータモデルを定義し、`create_tools()` 内の手書き JSON Schema dict を `ModelClass.model_json_schema()` に置き換えた。

## [x] :rocket: Agent Quality [2026-03-06 完了]

- AgentAnswer に citations を追加する
    - `citations: list[str]` を `AgentAnswer` / `AgentResponse` / `ChatResponse` に追加。
    - `Field(description=...)` で「参照した URL のリスト。なければ空リスト」と説明を付けた。
- server-side tool は無視
    - function call と見なさない
- function call があっても response.content があったら「仮説」だとして与える

## [x] deep オプションの追加 [2026-03-06 完了]

- ChatRequest に `deep: bool = False` を追加 (デフォルトは False)
- True のときに限り skill の deep_research を追加する

## [x] interact の追加 [2026-03-06 完了]

- ChatRequest に `interact: bool = False` を追加 (デフォルトは False)
- 一部のSKILLはユーザーとのやりとりを必要とするものがある
    - 一旦「次どうしますか？」と聞いて、ユーザーからのレスポンスを受け取ってから次のステップに進むようなものがある
- interact によってSKILL の説明を変えたい
- というわけで SKILL (*.md) は実は Jinja2 テンプレートだったことにする
    - SKILL を読むときは Jinja2 でレンダリングしてから解釈する
    - ここで interact という値を渡す
    - SKILL 内で `{% if interact %}ユーザーとのやりとりが必要な場合は、適宜ユーザーに質問してください。{% endif %}` みたいに条件分岐できるようにする

## [ ] docstring の整備

全てのトップクラス関数は numpydoc スタイルの docstring が必要。
簡潔な日本語で関数と引数の説明を書くこと。
Return は不要。
絶対に句読点を使わないこと
和文と英文が混在するときは半角スペースで区切ること
