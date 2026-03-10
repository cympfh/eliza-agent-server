"""Memory module - メッセージを SQLite に記録し、要約を生成する"""

import json
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from xai_sdk import Client, chat

MEMORY_DIR = Path(".memory")
MESSAGES_DB = MEMORY_DIR / "messages.sqlite"
SUMMARY_DIR = MEMORY_DIR / "summary"
ALL_SUMMARY_FILE = SUMMARY_DIR / "all.json"
JST = ZoneInfo("Asia/Tokyo")

XAI_API_KEY = os.environ.get("XAI_API_KEY")


def _call_grok(
    system_prompt: str, user_message: str, model: str = "grok-3-fast"
) -> str:
    """Grok に問い合わせてレスポンスを返す

    Parameters
    ----------
    system_prompt
        システムプロンプト
    user_message
        ユーザーメッセージ
    model
        使用する Grok モデル名
    """
    client = Client(api_key=XAI_API_KEY)
    session = client.chat.create(model=model)
    session.append(chat.system(system_prompt))
    session.append(chat.user(user_message))
    response = session.sample()
    return response.content


def _init_db() -> None:
    """SQLite DB を初期化する

    テーブルが未作成なら作成する
    """
    MEMORY_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(MESSAGES_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                timestamp  TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                reasoning  TEXT
            )
            """
        )
        # 既存DBへの後方互換: reasoning カラムがなければ追加する
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN reasoning TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def save_messages(messages: list[dict]) -> None:
    """メッセージリストを SQLite に保存する

    重複は INSERT OR IGNORE でスキップ

    Parameters
    ----------
    messages
        {message_id, timestamp, role, content, reasoning(optional)} の dict リスト
    """
    _init_db()
    with sqlite3.connect(MESSAGES_DB) as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO messages (message_id, timestamp, role, content, reasoning) VALUES (?, ?, ?, ?, ?)",
            [
                (m["message_id"], m["timestamp"], m["role"], m["content"], m.get("reasoning"))
                for m in messages
            ],
        )
        conn.commit()


def get() -> dict | None:
    """メモリのサマリを返す

    .memory/summary/all.json の中身を dict で返す
    ファイルが存在しない場合は None を返す
    """
    if not ALL_SUMMARY_FILE.exists():
        return None
    try:
        return json.loads(ALL_SUMMARY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def grep(pattern: str, limit: int = 10) -> list[dict]:
    """メモリの検索

    日別 summary の summary テキストを正規表現で検索
    マッチした結果を新しい順で返す

    Parameters
    ----------
    pattern
        検索する正規表現パターン
    limit
        返す最大件数
    """
    if not SUMMARY_DIR.exists():
        return []

    compiled = re.compile(pattern)
    matched: list[dict] = []

    daily_files = sorted(SUMMARY_DIR.glob("[0-9-]*.json"), reverse=True)

    for daily_file in daily_files:
        try:
            data = json.loads(daily_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        summary_text = data.get("summary", "")
        if compiled.search(summary_text):
            matched.append(data)
        if len(matched) >= limit:
            break

    return matched


def generate_summary(model: str = "grok-4-1-fast") -> dict:
    """SQLite の全メッセージから日別・全期間の summary を生成して返す

    日付ごとにグループ化して各日の summary を生成しキャッシュする
    いずれかの日別 summary が更新された場合のみ全期間 summary を再生成する

    Parameters
    ----------
    model
        summary 生成に使用する Grok モデル名
    """
    _init_db()
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(MESSAGES_DB) as conn:
        rows = conn.execute(
            "SELECT message_id, timestamp, role, content, reasoning FROM messages ORDER BY timestamp ASC"
        ).fetchall()

    if not rows:
        return {}

    # 日付でグループ化
    groups: dict[str, list[dict]] = defaultdict(list)
    for message_id, timestamp, role, content, reasoning in rows:
        # timestamp は ISO形式 "2026-03-04T12:34:56+09:00" など
        date_str = timestamp[:10]  # YYYY-MM-DD
        groups[date_str].append(
            {
                "message_id": message_id,
                "timestamp": timestamp,
                "role": role,
                "content": content,
                "reasoning": reasoning,
            }
        )

    daily_summaries: list[dict] = []
    any_daily_updated = False

    for date_str, msgs in sorted(groups.items()):
        daily_file = SUMMARY_DIR / f"{date_str}.json"
        msg_ids = [m["message_id"] for m in msgs]

        # キャッシュ確認
        if daily_file.exists():
            try:
                cached = json.loads(daily_file.read_text(encoding="utf-8"))
                if cached.get("messages") == msg_ids:
                    daily_summaries.append(cached)
                    continue
            except json.JSONDecodeError:
                pass

        # 日別要約を生成
        def _fmt(m: dict) -> str:
            base = f"[{m['timestamp']}] {m['role']}: {m['content']}"
            if m.get("reasoning"):
                base += f"\n  (reasoning: {m['reasoning']})"
            return base

        messages_text = "\n".join(_fmt(m) for m in msgs)
        system_prompt = (
            "以下はある一日の会話ログです。以下のJSON形式で要約してください。"
            "JSONのみを出力し、余計な説明・コードブロックは不要です。\n"
            "ログから読み取れる情報のみ埋めてください。不明なフィールドは null または空リストにしてください。\n\n"
            "出力例:\n"
            '{"summary": "この日の会話の要約(200文字目安)", '
            '"user_profile": {'
            '"name": "田中 太郎", '
            '"age": 25, '
            '"gender": "男性", '
            '"location": {"prefecture": "東京都", "city": "渋谷区", "detail": "道玄坂付近"}, '
            '"occupation": "エンジニア", '
            '"interests": ["VRChat", "アニメ", "料理"], '
            '"tendencies": ["夜型", "最新情報を求める傾向がある"], '
            '"personal_notes": ["一人暮らし", "猫アレルギー"]}}'
        )
        raw = _call_grok(system_prompt, messages_text, model=model)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {
                "summary": raw[:500],
                "user_profile": {
                    "name": None,
                    "age": None,
                    "gender": None,
                    "location": {"prefecture": None, "city": None, "detail": None},
                    "occupation": None,
                    "interests": [],
                    "tendencies": [],
                    "personal_notes": [],
                },
            }

        _default_profile = {
            "name": None,
            "age": None,
            "gender": None,
            "location": {"prefecture": None, "city": None, "detail": None},
            "occupation": None,
            "interests": [],
            "tendencies": [],
            "personal_notes": [],
        }
        now_jst = datetime.now(JST).isoformat(timespec="seconds")
        daily_data = {
            "created_datetime": now_jst,
            "num_messages": len(msgs),
            "messages": msg_ids,
            "summary": parsed.get("summary", ""),
            "user_profile": parsed.get("user_profile", _default_profile),
        }
        daily_file.write_text(
            json.dumps(daily_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        daily_summaries.append(daily_data)
        any_daily_updated = True

    # daily が1件も更新されていなければ all はスキップ
    if not any_daily_updated:
        return get() or {}

    # 全期間 summary を生成
    all_text = "\n\n".join(
        f"[{d.get('created_datetime', '')[:10]}] {d.get('summary', '')}\nuser_profile: {json.dumps(d.get('user_profile', {}), ensure_ascii=False)}"
        for d in daily_summaries
    )
    system_prompt_all = (
        "以下は日別の会話要約です。全体を通じてユーザーの特徴・傾向・関心事・個人情報を把握し、"
        "以下のJSON形式で出力してください。JSONのみを出力し、余計な説明・コードブロックは不要です。\n"
        "複数日の情報を統合し、最も確からしい値を採用してください。不明なフィールドは null または空リストにしてください。\n\n"
        "出力例:\n"
        '{"summary": "全期間の総合要約(300文字目安)", '
        '"user_profile": {'
        '"name": "田中 太郎", '
        '"age": 25, '
        '"gender": "男性", '
        '"location": {"prefecture": "東京都", "city": "渋谷区", "detail": null}, '
        '"occupation": "エンジニア", '
        '"interests": ["VRChat", "アニメ", "料理"], '
        '"tendencies": ["夜型", "最新情報を求める傾向がある"], '
        '"personal_notes": ["一人暮らし", "猫アレルギー"]}}'
    )
    raw_all = _call_grok(system_prompt_all, all_text, model=model)
    try:
        parsed_all = json.loads(raw_all)
    except json.JSONDecodeError:
        parsed_all = {
            "summary": raw_all[:500],
            "user_profile": {
                "name": None,
                "age": None,
                "gender": None,
                "location": {"prefecture": None, "city": None, "detail": None},
                "occupation": None,
                "interests": [],
                "tendencies": [],
                "personal_notes": [],
            },
        }

    _default_profile_all = {
        "name": None,
        "age": None,
        "gender": None,
        "location": {"prefecture": None, "city": None, "detail": None},
        "occupation": None,
        "interests": [],
        "tendencies": [],
        "personal_notes": [],
    }
    total_msgs = sum(len(list(v)) for v in groups.values())
    now_jst = datetime.now(JST).isoformat(timespec="seconds")
    all_data = {
        "created_datetime": now_jst,
        "num_messages": total_msgs,
        "summary": parsed_all.get("summary", ""),
        "user_profile": parsed_all.get("user_profile", _default_profile_all),
    }
    ALL_SUMMARY_FILE.write_text(
        json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return all_data
