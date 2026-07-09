import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Template
from pydantic import BaseModel, Field
from xai_sdk import Client, chat

import eliza.memory
from eliza.models import LIGHT_REASONING_EFFORT, MODEL

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent / "prompt"
JST = timezone(timedelta(hours=9))


class AgentAnswer(BaseModel):
    reasoning: str = Field(
        description="回答を導くにあたっての思考過程・推論。ユーザーには見せない"
    )
    answer: str = Field(
        description="ユーザーへの最終回答。自然な日本語で、簡潔かつ親切に答える"
    )
    citations: list[str] = Field(
        default_factory=list,
        description="参照した URL のリスト。なければ空リスト",
    )


class AgentResponse(BaseModel):
    content: str
    reasoning: str
    tool_history: list[tuple[dict[str, Any], dict[str, Any] | None]]
    citations: list[str]
    agent_name: str = ""


class TrivialAgent:
    agent_name = "trivial"

    def __init__(
        self,
        api_key: str,
    ):
        """雑談・挨拶など意味のない会話に応答するエージェントを初期化する

        ツールを呼び出さずに軽量モデルで返答する

        Parameters
        ----------
        api_key
            xAI API キー
        """
        self.api_key = api_key
        self.model = MODEL
        self.reasoning_effort = LIGHT_REASONING_EFFORT

    def _load_prompt(self, filename: str, **kwargs: Any) -> str:
        """プロンプトを読んで返す

        Parameters
        ----------
        filename
            prompt ディレクトリ内のファイル名
        **kwargs
            テンプレートに渡す変数
        """
        path = PROMPT_DIR / filename
        return Template(path.read_text(encoding="utf-8")).render(**kwargs).strip()

    def run(
        self,
        messages: list[dict[str, str]],
        request_id: str,
        query_hint: str = "",
        context: str = "vrchat",
    ) -> AgentResponse:
        """会話履歴を受け取り雑談応答を生成する

        Parameters
        ----------
        messages
            会話履歴 (role と content を持つ dict のリスト)
        request_id
            ログ追跡用のリクエスト ID
        query_hint
            IntentRouter から渡されるクエリヒント
        context
            会話の発生源 (vrchat / web / cli)
        """
        client = Client(api_key=self.api_key)
        session = client.chat.create(
            model=self.model, reasoning_effort=self.reasoning_effort
        )

        # ELIZA プロンプト差し込み
        path = PROMPT_DIR / "ELIZA.md"
        if path.exists():
            prompt = self._load_prompt(
                "ELIZA.md", agent_name=self.agent_name, context=context
            )
            if prompt:
                session.append(chat.system(prompt))
        now = datetime.now(tz=JST)
        session.append(
            chat.system(f"現在の日時（JST）: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        )

        for msg in messages:
            if msg["role"] == "system":
                session.append(chat.system(msg["content"]))
            elif msg["role"] == "user":
                session.append(chat.user(msg["content"]))
            elif msg["role"] == "assistant":
                session.append(chat.assistant(msg["content"]))

        # 直近履歴は client messages の後に挿入（常に実行）
        memory_block = eliza.memory.get_memory_context_block()
        if memory_block:
            session.append(chat.system(memory_block))

        if query_hint:
            session.append(chat.system(query_hint))

        logger.info(f"[REQUEST ID: {request_id}] TrivialAgent: generating response...")
        _, agent_answer = session.parse(AgentAnswer)

        return AgentResponse(
            content=agent_answer.answer,
            reasoning=agent_answer.reasoning,
            tool_history=[],
            citations=agent_answer.citations,
            agent_name=self.agent_name,
        )
