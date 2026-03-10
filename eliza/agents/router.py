import logging
from enum import Enum

from pydantic import BaseModel, Field
from xai_sdk import Client, chat

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
            "QuestionLight: Web 検索とX(Twitter)検索で答えられる質問。ほとんどの質問はこちら。"
            "QuestionHeavy: Web 検索とX(Twitter)検索で答えられる質問のうち、ユーザーが「詳しく」「深く調べて」「徹底的に」など明示的に詳細・深い調査を求めた場合のみ。"
            "Operation: スマートホームや PC の操作など外部ツール実行が必要なタスク。"
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

        session.append(
            chat.system(
                "あなたはユーザーの発言の意図を分類するアシスタントです。\n"
                "会話の最後のユーザー発言を以下の4種類に分類してください。\n"
                "- Trivial: 挨拶・雑談・感謝・相槌など意味のない会話\n"
                "- QuestionLight: Web 検索とX(Twitter)検索による情報収集で答えられる質問。ほとんどの質問はこれに分類する\n"
                "- QuestionHeavy: Web 検索とX(Twitter)検索による情報収集で答えられる質問のうち、ユーザーが「詳しく」「深く調べて」「徹底的に」など明示的に詳細・深い調査を求めたときのみ\n"
                "- Operation: スマートホーム機器操作・PC 操作・アラーム設定など外部ツール実行が必要なタスク\n"
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
