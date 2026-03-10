import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Template
from pydantic import BaseModel, Field
from xai_sdk import Client, chat
from xai_sdk.tools import code_execution, web_search, x_search

import eliza.memory
from eliza.models import HEAVY_MODEL, LIGHT_MODEL

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent / "prompt"


class AgentAnswer(BaseModel):
    reasoning: str = Field(
        description="回答を導くにあたっての思考過程・推論。ユーザーには見せない"
    )
    answer: str = Field(
        description="ユーザーへの最終回答。自然な日本語で、簡潔かつ親切に答える"
    )
    citations: list[str] = Field(
        default_factory=list,
        description="回答の根拠にした URL のリスト。参照した Web ページや検索結果の URL を含める。なければ空リスト",
    )


class AgentResponse(BaseModel):
    content: str
    reasoning: str
    sleep: bool
    tool_history: list[tuple[dict[str, Any], dict[str, Any] | None]]
    citations: list[str]


class QuestionAgent:
    def __init__(
        self,
        api_key: str,
        use_memory: bool = True,
        use_heavy: bool = False,
    ):
        """検索・情報収集で質問に答えるエージェントを初期化する

        x_search / web_search / code_execution をサーバーサイドツールとして使用する

        Parameters
        ----------
        api_key
            xAI API キー
        use_memory
            True のとき memory summary をプロンプトに差し込む
        use_heavy
            True のとき重いモデル (HEAVY_MODEL) を使用する。False のとき軽量モデル (LIGHT_MODEL) を使用する
        """
        self.api_key = api_key
        self.model = HEAVY_MODEL if use_heavy else LIGHT_MODEL
        self.use_memory = use_memory

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
        detect_sleep: bool = True,
    ) -> AgentResponse:
        """会話履歴を受け取り検索ベースで質問に回答する

        サーバーサイドツールを使用するためツールループは不要

        Parameters
        ----------
        messages
            会話履歴 (role と content を持つ dict のリスト)
        request_id
            ログ追跡用のリクエスト ID
        detect_sleep
            True のとき sleep 検出プロンプトを差し込む
        """
        client = Client(api_key=self.api_key)
        session = client.chat.create(
            model=self.model,
            tools=[x_search(), web_search(), code_execution()],
        )

        # ELIZA プロンプト差し込み
        path = PROMPT_DIR / "ELIZA.md"
        if path.exists():
            prompt = path.read_text(encoding="utf-8").strip()
            if prompt:
                session.append(chat.system(prompt))

        # memory summary 差し込み
        if self.use_memory:
            summary = eliza.memory.get()
            if summary:
                summary_str = json.dumps(summary, ensure_ascii=False, indent=2)
                session.append(
                    chat.system(
                        self._load_prompt(
                            "MEMORY_INSTRUCTION.md", summary_str=summary_str
                        )
                    )
                )

        for msg in messages:
            if msg["role"] == "system":
                session.append(chat.system(msg["content"]))
            elif msg["role"] == "user":
                session.append(chat.user(msg["content"]))
            elif msg["role"] == "assistant":
                session.append(chat.assistant(msg["content"]))

        if detect_sleep:
            session.append(chat.system(self._load_prompt("SLEEP_INSTRUCTION.md")))

        logger.info(f"[REQUEST ID: {request_id}] QuestionAgent: generating response...")
        _, agent_answer = session.parse(AgentAnswer)

        sleep = detect_sleep and "[SLEEP]" in agent_answer.answer
        return AgentResponse(
            content=agent_answer.answer,
            reasoning=agent_answer.reasoning,
            sleep=sleep,
            tool_history=[],
            citations=agent_answer.citations,
        )
