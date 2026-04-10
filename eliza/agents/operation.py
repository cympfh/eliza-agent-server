import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Template
from pydantic import BaseModel, Field
from xai_sdk import Client, chat

import eliza.memory
import eliza.tools
from eliza.models import HEAVY_MODEL

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
        description="回答の根拠にした URL のリスト。参照した Web ページや検索結果の URL を含める。なければ空リスト。",
    )


class AgentResponse(BaseModel):
    content: str
    reasoning: str
    sleep: bool
    tool_history: list[tuple[dict[str, Any], dict[str, Any] | None]]
    citations: list[str]


class Agent:
    def __init__(
        self,
        api_key: str,
        use_memory: bool = True,
        deep: bool = False,
        interact: bool = False,
    ):
        """エージェントを初期化する

        Parameters
        ----------
        api_key
            xAI API キー
        use_memory
            True のとき memory summary をプロンプトに差し込む
        deep
            True のとき deep_research スキルを有効にする
        interact
            True のとき スキルを interact モードでレンダリングする
        """
        self.api_key = api_key
        self.model = HEAVY_MODEL
        self.use_memory = use_memory
        self.deep = deep
        self.interact = interact

    def _load_prompt(self, filename: str, **kwargs: Any) -> str:
        """プロンプトを読んで返す

        prompt ディレクトリのテンプレートファイルを Jinja2 でレンダリングして返す

        Parameters
        ----------
        filename
            prompt ディレクトリ内のファイル名
        **kwargs
            テンプレートに渡す変数
        """
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
        """memory summary と直近の会話履歴を system メッセージとして差し込む"""
        if not self.use_memory:
            return
        summary = eliza.memory.get()
        recent_messages = eliza.memory.get_recent_messages(6)
        if summary or recent_messages:
            logger.info(
                f"[REQUEST ID: {request_id}] Injecting memory summary as system message..."
            )
            summary_str = json.dumps(summary, ensure_ascii=False, indent=2) if summary else ""
            session.append(
                chat.system(
                    self._load_prompt(
                        "MEMORY_INSTRUCTION.md",
                        summary_str=summary_str,
                        recent_messages=recent_messages,
                    )
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
        skills = eliza.tools.Skill(deep=self.deep, interact=self.interact).skills()
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
        query_hint: str = "",
    ) -> AgentResponse:
        """会話履歴を受け取りエージェントの応答を生成する

        Parameters
        ----------
        messages
            会話履歴 (role と content を持つ dict のリスト)
        request_id
            ログ追跡用のリクエスト ID
        max_tool_loops
            tool calling ループの最大回数
        detect_sleep
            True のとき sleep 検出プロンプトを差し込む
        query_hint
            IntentRouter から渡されるクエリヒント
        """
        client = Client(api_key=self.api_key)

        available_tools = eliza.tools.create_tools(
            deep=self.deep, interact=self.interact, search=False
        )
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

        if query_hint:
            session.append(chat.system(query_hint))

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
                    if eliza.tools.is_server_side(tool_name):
                        continue
                    # Client-side tool calling
                    result = eliza.tools.call(
                        tool_name, tool_args, deep=self.deep, interact=self.interact
                    )
                    result_str = json.dumps(result, ensure_ascii=False)
                    logger.info(f"[REQUEST ID: {request_id}] Tool result: {result_str}")
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
                if response.content:
                    session.append(
                        chat.assistant(f"ここまでの仮説: {response.content}")
                    )

                skill_just_used = any(
                    t[0]["name"] == "skill_use"
                    for t in tool_history[-len(response.tool_calls) :]
                )
                if skill_just_used:
                    session.append(
                        chat.system(self._load_prompt("SKILL_FETCHED_INSTRUCTION.md"))
                    )

                session.append(
                    chat.system(
                        self._load_prompt(
                            "TOOL_LOOP_INSTRUCTION.md",
                            remaining=remaining,
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
        executed = [t[0]["name"] for t in tool_history if t[0]["name"] != "skill_use"]
        if executed:
            session.append(chat.system(f"実際に実行したツール: {', '.join(executed)}"))
        else:
            session.append(
                chat.system(
                    "実際にはツールを一切実行していません。実行していないことを実行したと言ってはいけません。"
                )
            )
        _, agent_answer = session.parse(AgentAnswer)

        sleep = detect_sleep and "[SLEEP]" in agent_answer.answer
        return AgentResponse(
            content=agent_answer.answer,
            reasoning=agent_answer.reasoning,
            sleep=sleep,
            tool_history=tool_history,
            citations=agent_answer.citations,
        )
