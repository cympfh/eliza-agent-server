import logging
from enum import Enum

from pydantic import BaseModel, Field
from xai_sdk import Client, chat

import eliza.tools
from eliza.models import LIGHT_MODEL

logger = logging.getLogger(__name__)


class IntentLabel(str, Enum):
    """ユーザーの意図分類ラベル"""

    Trivial = "Trivial"
    QuestionLight = "QuestionLight"
    QuestionHeavy = "QuestionHeavy"
    Operation = "Operation"


class IntentResult(BaseModel):
    label: IntentLabel = Field(
        description=(
            "ユーザーの直近の発言の意図。"
            "Trivial: 意味のない会話・挨拶・感謝など。"
            "QuestionLight: Web/X(Twitter)検索で答えられる質問。ほとんどの質問はこちら。"
            "QuestionHeavy: X(Twitter)で動画・投稿・ツイートを検索・探す場合、またはユーザーが「詳しく」「深く調べて」など明示的に深い調査を求めた場合。"
            "Operation: スキル一覧に記載された機能（YouTube動画検索・再生、エアコン操作、ToDo管理、翻訳など）や PC/スマートホーム操作など外部ツール実行が必要なタスク。"
        )
    )
    reason: str = Field(description="分類の根拠（日本語・簡潔に）")


class IntentRouter:
    def __init__(self, api_key: str):
        """意図分類ルーターを初期化する

        Parameters
        ----------
        api_key
            xAI API キー
        """
        self.api_key = api_key

    def classify(self, messages: list[dict[str, str]], request_id: str) -> IntentLabel:
        """会話履歴からユーザーの意図を分類する

        軽量モデルを使って Trivial / Question / Operation の3クラスに structured output で分類する

        Parameters
        ----------
        messages
            会話履歴 (role と content を持つ dict のリスト)
        request_id
            ログ追跡用のリクエスト ID
        """
        client = Client(api_key=self.api_key)
        session = client.chat.create(model=LIGHT_MODEL)

        skills = eliza.tools.Skill().skills()
        skill_list = "\n".join(f"  - {s.name}: {s.description}" for s in skills)

        session.append(
            chat.system(
                "あなたはユーザーの発言の意図を分類するアシスタントです。\n"
                "会話の最後のユーザー発言を以下の4種類に分類してください。\n\n"
                "- Trivial: 挨拶・雑談・感謝・相槌など意味のない会話\n"
                "- QuestionLight: Web検索やX(Twitter)検索で答えられる質問。ほとんどの質問はこれ\n"
                "- QuestionHeavy: X(Twitter)で動画・投稿・ツイートを検索・探す場合。またはユーザーが「詳しく」「深く調べて」「徹底的に」など明示的に深い調査を求めたとき\n"
                f"- Operation: 以下のスキル一覧に該当する操作、またはPC/スマートホーム機器操作など外部ツール実行が必要なタスク\n"
                f"  スキル一覧（これらに該当すれば Operation）:\n{skill_list}\n\n"
                "判断に迷ったら Operation よりも QuestionLight を優先してください。\n"
                "ただし YouTube動画・エアコン・ToDo・翻訳などスキル一覧に明示された機能は必ず Operation にしてください。\n"
            )
        )
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
            f"[REQUEST ID: {request_id}] IntentRouter: label={result.label}, reason={result.reason}"
        )
        return result.label
