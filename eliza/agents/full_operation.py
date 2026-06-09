import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Template
from pydantic import BaseModel, Field
from xai_sdk import Client, chat

import eliza.memory
import eliza.tools
from eliza.models import HEAVY_REASONING_EFFORT, MODEL

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent / "prompt"
JST = timezone(timedelta(hours=9))


class AgentAnswer(BaseModel):
    reasoning: str = Field(description="回答を導くにあたっての思考過程・推論。ユーザーには見せない")
    answer: str = Field(description="ユーザーへの最終回答。自然な日本語で、簡潔かつ親切に答える")
    citations: list[str] = Field(
        default_factory=list,
        description="回答の根拠にした URL のリスト。参照した Web ページや検索結果の URL を含める。なければ空リスト。",
    )


class AgentResponse(BaseModel):
    content: str
    reasoning: str
    tool_history: list[tuple[dict[str, Any], dict[str, Any] | None]]
    citations: list[str]
    agent_name: str = ""


class FullOperationAgent:
    agent_name = "full_operation"

    def __init__(
        self,
        api_key: str,
        deep: bool = False,
        interact: bool = False,
    ):
        """ローカルツールと検索ツールを両方使えるエージェントを初期化する

        Parameters
        ----------
        api_key
            xAI API キー
        deep
            True のとき deep_research スキルを有効にする
        interact
            True のとき スキルを interact モードでレンダリングする
        """
        self.api_key = api_key
        self.model = MODEL
        self.reasoning_effort = HEAVY_REASONING_EFFORT
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

    def _inject_eliza_prompt(self, session: Any, request_id: str, context: str = "vrchat") -> None:
        """ELIZA.md の内容と現在時刻を system prompt として先頭に差し込む"""
        path = PROMPT_DIR / "ELIZA.md"
        if path.exists():
            prompt = self._load_prompt("ELIZA.md", agent_name=self.agent_name, context=context)
            if prompt:
                logger.info(f"[REQUEST ID: {request_id}] Injecting ELIZA.md as system prompt...")
                session.append(chat.system(prompt))
        now = datetime.now(tz=JST)
        session.append(chat.system(f"現在の日時（JST）: {now.strftime('%Y-%m-%d %H:%M:%S')}"))

    def _inject_memory_context(self, session: Any, request_id: str) -> None:
        """直近の会話履歴（+ summary）を system メッセージとして差し込む（常に実行）"""
        memory_block = eliza.memory.get_memory_context_block()
        if memory_block:
            logger.info(f"[REQUEST ID: {request_id}] Injecting memory context as system message...")
            session.append(chat.system(memory_block))

    def _inject_skill_summary(self, session: Any, request_id: str) -> None:
        """skill summary を system メッセージとして差し込む"""
        skills = eliza.tools.Skill(deep=self.deep, interact=self.interact).skills()
        if skills:
            logger.info(f"[REQUEST ID: {request_id}] Injecting skill summary as system message...")
            skill_list = "\n".join(f"- {s.name}: {s.description}" for s in skills)
            session.append(chat.system(self._load_prompt("SKILL_INSTRUCTION.md", skill_list=skill_list)))

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
        query_hint: str = "",
        context: str = "vrchat",
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
        query_hint
            IntentRouter から渡されるクエリヒント
        context
            会話の発生源 (vrchat / web / cli)
        """
        client = Client(api_key=self.api_key)

        available_tools = eliza.tools.create_tools(deep=self.deep, interact=self.interact, search=True)
        logger.info(f"[REQUEST ID: {request_id}] Creating chat session with {len(available_tools)} tools...")
        session = client.chat.create(
            model=self.model,
            tools=available_tools,
            reasoning_effort=self.reasoning_effort,
        )

        # プロンプト・会話履歴を順番に差し込む
        logger.info(f"[REQUEST ID: {request_id}] Appending conversation history...")
        self._inject_eliza_prompt(session, request_id, context=context)

        for msg in messages:
            if msg["role"] == "system":
                session.append(chat.system(msg["content"]))
            elif msg["role"] == "user":
                session.append(chat.user(msg["content"]))
            elif msg["role"] == "assistant":
                session.append(chat.assistant(msg["content"]))

        # 直近履歴は client messages の後に挿入（recency を高める）
        self._inject_memory_context(session, request_id)

        if query_hint:
            session.append(chat.system(query_hint))

        self._inject_skill_summary(session, request_id)

        # レスポンス生成 / tool calling ループ
        tool_history: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
        for tool_loop in range(1, max_tool_loops + 1):
            logger.info(f"[REQUEST ID: {request_id}] Generating response... (tool loop {tool_loop}/{max_tool_loops})")
            response = session.sample()
            tool_used = False

            if response.tool_calls:
                logger.info(f"[REQUEST ID: {request_id}] Tool calls detected: {len(response.tool_calls)}")
                for tool_call in response.tool_calls:
                    tool_name: str = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    logger.info(f"[REQUEST ID: {request_id}] Tool call: {tool_name} with args: {tool_args}")
                    if eliza.tools.is_server_side(tool_name):
                        continue
                    # Client-side tool calling
                    result = eliza.tools.call(tool_name, tool_args, deep=self.deep, interact=self.interact)
                    result_str = json.dumps(result, ensure_ascii=False)
                    logger.info(f"[REQUEST ID: {request_id}] Tool result: {result_str}")
                    tool_history.append(({"name": tool_name, "args": tool_args}, result))
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
                    session.append(chat.assistant(f"ここまでの仮説: {response.content}"))

                skill_just_used = any(t[0]["name"] == "skill_use" for t in tool_history[-len(response.tool_calls) :])
                if skill_just_used:
                    session.append(chat.system(self._load_prompt("SKILL_FETCHED_INSTRUCTION.md")))

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
                    session.append(chat.system(self._load_prompt("TOOL_REQUIRED_INSTRUCTION.md")))
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
                chat.system("実際にはツールを一切実行していません。実行していないことを実行したと言ってはいけません。")
            )
        _, agent_answer = session.parse(AgentAnswer)

        return AgentResponse(
            content=agent_answer.answer,
            reasoning=agent_answer.reasoning,
            tool_history=tool_history,
            citations=agent_answer.citations,
            agent_name=self.agent_name,
        )
