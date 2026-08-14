import logging
from enum import Enum

from pydantic import BaseModel, Field
from xai_sdk import Client, chat

import eliza.memory
from eliza.models import LIGHT_REASONING_EFFORT, MODEL
from eliza.skills import load_skills

logger = logging.getLogger(__name__)


class IntentLabel(str, Enum):
    """ユーザーの意図分類ラベル"""

    Trivial = "Trivial"
    Question = "Question"
    Translator = "Translator"
    FullOperation = "FullOperation"


class IntentResult(BaseModel):
    label: IntentLabel = Field(
        description=(
            "ユーザーの直近の発言の意図。"
            "Trivial: 意味のない会話・挨拶・感謝など。"
            "Question: Web/X検索または会話履歴（conversation_summary / conversation_history）で答えられる質問。ローカルツール（スキル・スマート家電等）は不要。"
            "Translator: テキストの翻訳リクエスト（「翻訳して」「訳して」「英語で言うと」など）。"
            "FullOperation: スキル一覧に記載された機能（YouTube動画検索・再生、エアコン操作、ToDo管理など）や PC/スマートホーム操作など外部ツール実行が必要なタスク。"
            "室内（家の中）の温度・湿度の取得（switchbot_get_room_temperature）も FullOperation。外の気温では代替できない。"
            "Web 検索が追加で必要な場合も含む。"
        )
    )
    reason: str = Field(description="分類の根拠（日本語・簡潔に）")
    query_hint: str = Field(
        description=(
            "次のエージェントへのヒント。ユーザーの意図・背景・推奨アクションを日本語で記述する。"
            "例: 'ユーザーは文京区の天気を尋ねています。Web検索で正確なデータを返しましょう。'"
        )
    )


class IntentRouter:
    def __init__(self, api_key: str):
        """意図分類ルーターを初期化する

        Parameters
        ----------
        api_key
            xAI API キー
        """
        self.api_key = api_key

    def classify(self, messages: list[dict[str, str]], request_id: str) -> IntentResult:
        """会話履歴からユーザーの意図を分類する

        軽量モデルを使って Trivial / Question / Translator / FullOperation の3クラスに structured output で分類する

        Parameters
        ----------
        messages
            会話履歴 (role と content を持つ dict のリスト)
        request_id
            ログ追跡用のリクエスト ID
        """
        client = Client(api_key=self.api_key)
        session = client.chat.create(model=MODEL, reasoning_effort=LIGHT_REASONING_EFFORT)

        skills = load_skills()
        skill_list = "\n".join(f"  - {s.name}: {s.description}" for s in skills)

        session.append(
            chat.system(
                "あなたはユーザーの発言の意図を分類するアシスタントです。\n"
                "会話の最後のユーザー発言を以下の4種類に分類してください。\n\n"
                "- Trivial: 挨拶・雑談・感謝・相槌など意味のない会話\n"
                "- Question: Web検索・X(Twitter)検索、または会話履歴（conversation_summary / conversation_history）で答えられる質問。ローカルツール（スキル・スマート家電等）は一切不要なもの\n"
                "web/X検索または会話履歴で回答できそうなものは Question にしてください。\n"
                "- Translator: テキストの翻訳リクエスト（「翻訳して」「訳して」「英語で言うと」など）\n"
                f"- FullOperation: 以下のスキル一覧に該当する操作: \n<skill_list>{skill_list}</skill_list>\n"
                "またはツールの直接利用で解決できるタスク（PC操作、スマートホーム操作など）\n"
                "【重要】室内（家の中）の温度・湿度の質問（「家の中は？」「部屋の温度は？」「室内の湿度は？」など）は必ず FullOperation にしてください。"
                "外の温湿度値・直前の会話内容から推定することは禁止です。switchbot_get_room_temperature ツールを呼ばなければ答えられません。\n"
                "Question 同様に Web 検索、X検索を利用することもできます。"
            )
        )

        # 直近の会話履歴（常に挿入）
        memory_block = eliza.memory.get_memory_context_block()
        if memory_block:
            session.append(chat.system(memory_block))

        for msg in messages:
            if msg["role"] == "system":
                session.append(chat.system(msg["content"]))
            elif msg["role"] == "user":
                session.append(chat.user(msg["content"]))
            elif msg["role"] == "assistant":
                session.append(chat.assistant(msg["content"]))

        logger.info(f"[REQUEST ID: {request_id}] IntentRouter: classifying intent...")
        _, result = session.parse(IntentResult)
        logger.info(
            f"[REQUEST ID: {request_id}] IntentRouter: label={result.label}, reason={result.reason}, query_hint={result.query_hint}"
        )
        return result
