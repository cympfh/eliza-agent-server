import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Template
from pydantic import BaseModel, Field
from xai_sdk import Client, chat

import eliza.memory
import eliza.tools

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompt"


class AgentAnswer(BaseModel):
    reasoning: str = Field(
        description="回答を導くにあたっての思考過程・推論。ユーザーには見せない"
    )
    answer: str = Field(
        description="ユーザーへの最終回答。自然な日本語で、簡潔かつ親切に答える"
    )


class AgentResponse(BaseModel):
    content: str
    reasoning: str
    sleep: bool
    tool_history: list[tuple[dict[str, Any], dict[str, Any] | None]]


class Agent:
    def __init__(self, api_key: str, model: str, use_memory: bool = True):
        self.api_key = api_key
        self.model = model
        self.use_memory = use_memory

    def _load_prompt(self, filename: str, **kwargs: Any) -> str:
        path = PROMPT_DIR / filename
        return Template(path.read_text(encoding="utf-8")).render(**kwargs).strip()

    def _inject_eliza_prompt(self, session: Any, request_id: str) -> None:
        """ELIZA.md の内容を system prompt として先頭に差し込む"""
        path = PROMPT_DIR / "ELIZA.md"
        if path.exists():
            prompt = path.read_text(encoding="utf-8").strip()
            if prompt:
                logger.info(
                    f"[REQUEST ID: {request_id}] Injecting ELIZA.md as system prompt..."
                )
                session.append(chat.system(prompt))

    def _inject_memory_summary(self, session: Any, request_id: str) -> None:
        """memory summary を system メッセージとして差し込む"""
        if not self.use_memory:
            return
        summary = eliza.memory.get()
        if summary:
            logger.info(
                f"[REQUEST ID: {request_id}] Injecting memory summary as system message..."
            )
            summary_str = json.dumps(summary, ensure_ascii=False, indent=2)
            session.append(
                chat.system(
                    self._load_prompt("MEMORY_INSTRUCTION.md", summary_str=summary_str)
                )
            )

    def _inject_sleep_instruction(self, session: Any, request_id: str) -> None:
        """sleep 検出のためのシステムメッセージを差し込む"""
        logger.info(
            f"[REQUEST ID: {request_id}] Injecting sleep instruction as system message..."
        )
        session.append(chat.system(self._load_prompt("SLEEP_INSTRUCTION.md")))

    def _inject_skill_summary(self, session: Any, request_id: str) -> None:
        """skill summary を system メッセージとして差し込む"""
        skills = eliza.tools.Skill().skills()
        if skills:
            logger.info(
                f"[REQUEST ID: {request_id}] Injecting skill summary as system message..."
            )
            skill_list = "\n".join(f"- {s.name}: {s.description}" for s in skills)
            session.append(
                chat.system(
                    self._load_prompt("SKILL_INSTRUCTION.md", skill_list=skill_list)
                )
            )

    _TOOL_INTENT_PATTERNS = [
        "検索します",
        "検索してみます",
        "調べます",
        "調べてみます",
        "確認します",
        "確認してみます",
        "調べますね",
        "検索しますね",
        "確認しますね",
        "探します",
        "探してみます",
        "調べてみますね",
    ]

    def _should_retry_with_tool(self, content: str) -> bool:
        """ツールを使わずにツール使用の意図を示す文言が含まれているか判定する"""
        return any(pattern in content for pattern in self._TOOL_INTENT_PATTERNS)

    def run(
        self,
        messages: list[dict[str, str]],
        request_id: str,
        max_tool_loops: int = 5,
        detect_sleep: bool = True,
    ) -> AgentResponse:
        client = Client(api_key=self.api_key)

        available_tools = eliza.tools.create_tools()
        logger.info(
            f"[REQUEST ID: {request_id}] Creating chat session with {len(available_tools)} tools..."
        )
        session = client.chat.create(model=self.model, tools=available_tools)

        # プロンプト・会話履歴を順番に差し込む
        logger.info(f"[REQUEST ID: {request_id}] Appending conversation history...")
        self._inject_eliza_prompt(session, request_id)
        self._inject_memory_summary(session, request_id)

        for msg in messages:
            if msg["role"] == "system":
                session.append(chat.system(msg["content"]))
            elif msg["role"] == "user":
                session.append(chat.user(msg["content"]))
            elif msg["role"] == "assistant":
                session.append(chat.assistant(msg["content"]))

        self._inject_skill_summary(session, request_id)
        if detect_sleep:
            self._inject_sleep_instruction(session, request_id)

        # レスポンス生成 / tool calling ループ
        tool_history: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
        for tool_loop in range(1, max_tool_loops + 1):
            logger.info(
                f"[REQUEST ID: {request_id}] Generating response... (tool loop {tool_loop}/{max_tool_loops})"
            )
            response = session.sample()
            tool_used = False

            if response.tool_calls:
                logger.info(
                    f"[REQUEST ID: {request_id}] Tool calls detected: {len(response.tool_calls)}"
                )
                for tool_call in response.tool_calls:
                    tool_name: str = tool_call.function.name
                    tool_args = (
                        json.loads(tool_call.function.arguments)
                        if tool_call.function.arguments
                        else {}
                    )
                    logger.info(
                        f"[REQUEST ID: {request_id}] Tool call: {tool_name} with args: {tool_args}"
                    )
                    result = eliza.tools.call(tool_name, tool_args)
                    result_str = json.dumps(result, ensure_ascii=False)
                    logger.info(
                        f"[REQUEST ID: {request_id}] Tool result: {result_str[:500]}{'...' if len(result_str) > 500 else ''}"
                    )
                    tool_history.append(
                        ({"name": tool_name, "args": tool_args}, result)
                    )
                    if result:
                        tool_used = True
                        session.append(chat.tool_result(json.dumps(result)))

            if tool_used:
                remaining = max_tool_loops - tool_loop - 1
                if remaining == 0:
                    logger.warning(
                        f"[REQUEST ID: {request_id}] Tool loop limit reached. Forcing final response without tools."
                    )
                session.append(
                    chat.system(
                        self._load_prompt(
                            "TOOL_LOOP_INSTRUCTION.md", remaining=remaining
                        )
                    )
                )
            elif self._should_retry_with_tool(response.content):
                remaining = max_tool_loops - tool_loop - 1
                if remaining > 0:
                    logger.info(
                        f"[REQUEST ID: {request_id}] Response mentions tool intent but no tool was called. Retrying with tool instruction..."
                    )
                    session.append(chat.assistant(response.content))
                    session.append(
                        chat.system(self._load_prompt("TOOL_REQUIRED_INSTRUCTION.md"))
                    )
                else:
                    break
            else:
                break

        # 最終回答を structured output で生成
        logger.info(f"[REQUEST ID: {request_id}] Generating final structured answer...")
        _, agent_answer = session.parse(AgentAnswer)

        sleep = detect_sleep and "[SLEEP]" in agent_answer.answer
        return AgentResponse(
            content=agent_answer.answer,
            reasoning=agent_answer.reasoning,
            sleep=sleep,
            tool_history=tool_history,
        )
