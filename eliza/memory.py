"""Memory module - メッセージをログに記録し、要約を生成する"""

import json
import os
import re
import subprocess
from datetime import datetime

from xai_sdk import Client, chat

MEMORY_DIR = ".memory"
LOGS_FILE = f"{MEMORY_DIR}/logs.jsonl"
SUMMARY_FILE = f"{MEMORY_DIR}/summary.json"

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


def get() -> dict | None:
    """summary.json の中身を dict で返す。ファイルが存在しない場合は None を返す。"""
    if not os.path.exists(SUMMARY_FILE):
        return None
    with open(SUMMARY_FILE, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return None


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
        'フォーマット: {"summary": "何を話したかの短い説明(200文字目安)", "important_facts": ["会話から読み取れる重要な事実のリスト(各50文字目安)"], "feedback": "ユーザーの好みや傾向についての洞察(200文字目安)"}'
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
        important_facts = parsed.get("important_facts", [])
        feedback = parsed.get("feedback", "")
    except json.JSONDecodeError:
        summary = compressed[:200]
        important_facts = []
        feedback = ""

    log_entry = json.dumps(
        {"datetime": now, "summary": summary, "important_facts": important_facts, "feedback": feedback},
        ensure_ascii=False,
    )
    with open(LOGS_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")

    # Step 2: summary.json を更新
    summary_all = refresh_summary(model=request.model)

    return {"summary": summary, "important_facts": important_facts, "feedback": feedback, "summary_all": summary_all}


def refresh_summary(model: str) -> dict:
    """
    直近100件のログから summary.json を再生成して返す。
    logs.jsonl が存在しない・空の場合は空 dict を返す。
    """
    if not os.path.exists(LOGS_FILE):
        return {}

    result = subprocess.run(
        ["tail", "-n", "100", LOGS_FILE],
        capture_output=True,
        text=True,
    )
    recent_logs = result.stdout.strip()
    if not recent_logs:
        return {}

    last_summary = get()
    last_summary_str = (
        json.dumps(last_summary, ensure_ascii=False) if last_summary else "(なし)"
    )

    system_prompt_summary = f"""
これは過去にユーザーとあなたが交わした会話のログです。
今後の会話に役立つ情報だけを取捨選択し、以下のJSON形式で出力してください。JSONのみを出力し、余計な説明・コードブロックは不要です。

{{
  "recent_conversation": "直近の会話で何をしたかの短い説明",
  "user_preferences": {{
    "hobbies": ["趣味や関心事のリスト"],
    "conversation_style": "ユーザーの会話スタイルの特徴",
    "(anything as you like)": "ユーザーの好みや傾向についての洞察を自由に追加"
  }}
}}

この目的は、過去の会話の内容を把握して、次回以降の会話でユーザーの好みや傾向を活用するためです。
---
事前情報: 直近の要約は以下の通りです:
{last_summary_str}
"""
    raw = _call_grok(system_prompt_summary, recent_logs, model=model)
    try:
        summary_all = json.loads(raw)
    except json.JSONDecodeError:
        summary_all = {"recent_conversation": raw[:500], "user_preferences": {}}

    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary_all, f, ensure_ascii=False, indent=2)

    return summary_all
