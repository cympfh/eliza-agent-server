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
    Question = "Question"
    Operation = "Operation"
    Full = "Full"


class IntentResult(BaseModel):
    label: IntentLabel = Field(
        description=(
            "ユーザーの直近の発言の意図。"
            "Trivial: 意味のない会話・挨拶・感謝など。"
            "Question: Web/X(Twitter)検索で答えられる質問。X(Twitter)で動画・投稿を探す場合も含む。"
            "Operation: スキル一覧に記載された機能（時間の確認、YouTube動画検索・再生、エアコン操作、ToDo管理、翻訳など）や PC/スマートホーム操作など外部ツール実行が必要なタスク。"
            "Full: 全てのツールが利用可能。ローカル操作（スマート家電・スキル等）と Web 検索の両方が同時に必要な複合タスク。非常にまれなケースのみ使用する。"
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
                "- Question: Web検索やX(Twitter)検索で答えられる質問。X(Twitter)で動画・投稿・ツイートを探す場合も含む。ほとんどの質問はこれ\n"
                f"- Operation: 以下のスキル一覧に該当する操作: \n{skill_list}\n"
                "またはツールの直接利用で解決できるタスク（PC操作、スマートホーム操作など、時刻取得、天気取得）\n"
                "- Full: ローカル操作（スマート家電・スキル等）と Web 検索の両方が同時に必要な複合タスク。非常にまれ\n\n"
                "判断に迷ったら Operation よりも Question を優先してください。\n"
                "ただし YouTube動画・エアコン・ToDo・翻訳などスキル一覧に明示された機能は必ず Operation にしてください。\n"
                "Full は「エアコンの最適温度をインターネットで調べてからエアコンをつけて」のような、検索とローカル操作が両方必要なときだけ使ってください。\n"
                "単なる操作は Operation、単なる検索は Question にしてください。\n"
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
            f"[REQUEST ID: {request_id}] IntentRouter: label={result.label}, reason={result.reason}, query_hint={result.query_hint}"
        )
        return result
