---
name: workspace
description: ワークスペース内のファイルの読み書き メモやドキュメントの保存と参照 URLからのファイルの保存
---
# ワークスペース内のファイルを読み書きする

メモ ドキュメント ノートなどをファイルとして保存し あとから参照できる。
ファイルは workspace というディレクトリごとに分類して管理される。
画像や動画ファイルをURLから保存することもできる。

workspace は新規ファイルの作成やURLからの保存のときに自動で作成される。

## tools

- workspace_list
    - 利用可能な workspace の一覧を返す
- workspace_list_files
    - 指定した workspace 内のファイル一覧を返す
- workspace_read
    - workspace 内のファイルを読み込む
    - デフォルトで末尾100行を返す tail で行数を変えられる
    - full=true で全文を返す
- workspace_write
    - workspace 内のファイルに書き込む
    - append=false で上書き append=true で追記
    - 追記時は行頭に [YYYY-MM-DD HH:MM:SS] が自動で付く
- workspace_download
    - URLからファイルをダウンロードして workspace に保存する
    - workspace とファイル名を指定する

## スキルの手順

### 読むとき

1. workspace_list でどんな workspace があるか確認する
2. workspace_list_files で目的のファイルを探す
3. workspace_read でファイルを読む
    - まず tail で末尾を確認し 全文が必要なら full=true で読み直す

### 書くとき

1. workspace_list で workspace を確認する
2. 既存ファイルを編集する場合は workspace_read で現在の内容を確認する
3. workspace_write で書き込む
    - 新しく書き直すなら append=false
    - 末尾に追記するなら append=true

### URLからファイルを保存するとき

1. workspace_list で workspace を確認する
2. workspace_download で URL からファイルをダウンロードして保存する
    - 書き込み先の workspace とファイル名を指定する
3. ダウンロードに成功したかどうか filesize がどれくらいだったかを確認する

{% if interact %}
### ユーザーへの確認

- 上書き append のどちらか不明な場合はユーザーに確認する
- 書き込み先の workspace ファイル名が曖昧な場合はユーザーに確認する
{% endif %}
