---
name: video
description: 動画の検索・再生を行う
---
# 動画の検索・再生を行う

## tools

- youtube_search
    - YouTube で動画を検索する
    - 引数 `browser_open` を True にすると、検索結果の１つ目を即座にブラウザで開いて再生する
- x_search
    - X (Twitter) で動画を検索する
    - 検索クエリに `filter:video` を追加して動画だけヒットするようにする
- web_search
    - ブラウザでインターネット検索する
- browser_url_open
    - 指定された URL をブラウザで開く

## スキルの手順

1. 検索プラットフォームを YouTube, X, web から選ぶ

一般の動画は YouTube で検索するのが最も適している。
YouTube の規約に違反するような動画を検索したい場合は X (Twitter) で検索するのが適している。
何度か検索しても目的の動画が見つからない場合は、web で検索するのが適している。

2. 検索クエリを組み立てて検索する

クエリは簡潔にすること。
例えば、YouTube で最新動画を見たい場合はクエリに「最新」を入れる代わりに、`youtube_search(order=date)` とすればよい.

5種類の検索クエリを用意して、それぞれで検索をする

3. 動画を一つに絞る

得られた全ての検索結果から、ユーザーが最も望んでいる動画を1つ選ぶ。

```
{
  "platform": "YouTube|X|web",
  "title": "動画のタイトル|投稿のテキスト|ウェブページのタイトル",
  "video_url": "動画のURL|投稿のURL|ウェブページのURL"
}
```

もしも一つも候補が見つからなかった場合は、「${platform} で検索したが動画が見つからなかった」と報告して、スキルを終了する。

4. クリップボードに動画URLをコピーする

`clipboard_copy(text=video_url)` を呼び出して、動画URLをクリップボードにコピーする。

5. 検索結果をユーザーに報告する

次のフォーマットで報告する。

```
${platform} でこんな動画を見つけました:
${title}
${video_url}
```

もしユーザーが「即座に動画を再生して」「動画を開いて」と言っているなら次 (4) に進む。
そうでないなら、スキルは一旦ここで終了する。

4. もし更にユーザーが動画を再生したいと言った場合は、検索結果から動画のURLを取得してブラウザで開く

直前のあなたの報告に動画URLが含まれているなら、そのURL を browser_url_open に渡してブラウザで開き、
スキルを実行を即座に終了する。

もし URL が不明なら再度検索に戻る。

5. もしユーザーが動画に満足しなかった場合

検索プラットフォームを変更して、検索しなおす

## よく見る動画

### 名取さな（さなちゃんねる, 個人勢 VTuber）

YouTube: https://www.youtube.com/@sana_natori
https://www.youtube.com/results?search_query=名取さな
X(Twitter): https://x.com/sana_natori

### 月ノ美兎（つきのみと, にじさんじ VTuber)

YouTube: https://www.youtube.com/@TsukinoMito
https://www.youtube.com/results?search_query=月ノ美兎

X(Twitter): https://x.com/MitoTsukino

## おさだ (osada /おさだ【海外ひとり旅】, 旅行系 YouTube)

YouTube: https://www.youtube.com/@osadalife
https://www.youtube.com/results?search_query=osadaおさだ
