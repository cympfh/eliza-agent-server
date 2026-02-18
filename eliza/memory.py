"""Memory module - メッセージをログに記録し、要約を生成する"""

import json
import os
import re
import subprocess
from datetime import datetime

from xai_sdk import Client, chat

MEMORY_DIR = ".memory"
LOGS_FILE = f"{MEMORY_DIR}/logs.jsonl"
SUMMARY_FILE = f"{MEMORY_DIR}/summary.txt"

XAI_API_KEY = os.environ.get("XAI_API_KEY")


def _call_grok(
    system_prompt: str, user_message: str, model: str = "grok-3-fast"
) -> str:
    """Grok に問い合わせてレスポンスを返す"""
    client = Client(api_key=XAI_API_KEY)
    session = client.chat.create(model=model)
    session.append(chat.system(system_prompt))
    session.append(chat.user(user_message))
    response = session.sample()
    return response.content


def get() -> str | None:
    """summary.txt の中身を返す。ファイルが存在しない場合は None を返す。"""
    if not os.path.exists(SUMMARY_FILE):
        return None
    with open(SUMMARY_FILE, encoding="utf-8") as f:
        return f.read()


def grep(pattern: str, limit: int = 10) -> list[dict]:
    """
    logs.jsonl を末尾から正規表現で検索し、マッチした行（dict）を最大 limit 件返す。
    結果は新しい順（ファイル末尾が先頭）。
    """
    if not os.path.exists(LOGS_FILE):
        return []

    compiled = re.compile(pattern)
    matched: list[dict] = []

    with open(LOGS_FILE, encoding="utf-8") as f:
        lines = f.readlines()

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        if compiled.search(line):
            try:
                matched.append(json.loads(line))
            except json.JSONDecodeError:
                matched.append({"raw": line})
        if len(matched) >= limit:
            break

    return matched


def append(request) -> dict:
    """
    会話履歴をメモリに追記し、要約を更新する。

    Args:
        request: ChatRequest オブジェクト (messages: list[Message] を持つ)

    Returns:
        dict with keys: summary, feedback, summary_all
    """
    os.makedirs(MEMORY_DIR, exist_ok=True)

    # Step 1: 会話履歴を1行のJSONに圧縮してlogsに追記
    now = datetime.now().isoformat(timespec="seconds")
    system_prompt_compress = (
        "与えられた会話メッセージを分析して、以下のJSON形式で1行に要約してください。"
        'フォーマット: {"summary": "何をしたかの短い説明", "feedback": "ユーザーの好みや傾向についての洞察"}'
        "JSONのみを出力し、余計な説明は不要です。"
    )
    user_message_compress = "\n".join(
        f"role: {msg.role}\ncontent: {msg.content}" for msg in request.messages
    )

    compressed = _call_grok(
        system_prompt_compress, user_message_compress, model=request.model
    )

    # JSONとして解析できるか確認、できなければそのまま使う
    try:
        parsed = json.loads(compressed)
        summary = parsed.get("summary", "")
        feedback = parsed.get("feedback", "")
    except json.JSONDecodeError:
        summary = compressed[:200]
        feedback = ""

    log_entry = json.dumps(
        {"datetime": now, "summary": summary, "feedback": feedback},
        ensure_ascii=False,
    )
    with open(LOGS_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")

    # Step 2: 直近100件のログを読んで summary.txt を更新
    result = subprocess.run(
        ["tail", "-n", "100", LOGS_FILE],
        capture_output=True,
        text=True,
    )
    recent_logs = result.stdout.strip()
    last_summary = get()

    summary_all = ""
    if recent_logs:
        system_prompt_summary = f"""
これは過去にユーザーとあなたが交わした会話のログです。
ユーザーはあなたに対して様々な質問をしてきました。
これらのログを 2000 文字程度に圧縮してください。
この目的は、過去の会話の内容を把握して、あなたがユーザーの好みや傾向を理解するためです。
---
事前情報: 直近の要約は以下の通りです:
{last_summary if last_summary else "(なし)"}
"""
        summary_all = _call_grok(
            system_prompt_summary, recent_logs, model=request.model
        )

        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            f.write(summary_all)

    return {"summary": summary, "feedback": feedback, "summary_all": summary_all}
