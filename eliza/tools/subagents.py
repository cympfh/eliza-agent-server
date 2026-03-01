"""SubAgents tool for Grok agent - ask other agents"""

import os
import subprocess
from dataclasses import dataclass
from typing import Any

import xai_sdk
import xai_sdk.chat
import xai_sdk.tools
from xai_sdk.proto import chat_pb2


@dataclass
class SubAgentResponse:
    name: str
    model: str
    answer: str


class SubAgents:
    """他のエージェントに質問するためのツール"""

    def __init__(self):
        pass

    def _ask_grok(
        self, question: str, model="grok-4-1-fast-reasoning"
    ) -> SubAgentResponse:
        """Grok agent に質問して回答を得る"""
        api_key = os.getenv("XAI_API_KEY")
        client = xai_sdk.Client(api_key=api_key)
        session = client.chat.create(
            model=model,
            tools=[
                xai_sdk.tools.x_search(),
                xai_sdk.tools.web_search(),
            ],
        )
        session.append(
            xai_sdk.chat.system(
                "You are a helpful assistant. Answer the user's question based on your knowledge and tools."
            )
        )
        session.append(xai_sdk.chat.user(question.strip()))
        response = session.sample()
        return SubAgentResponse(
            name="grok",
            model=model,
            answer=response.content.strip(),
        )

    def _ask_claudecode(
        self,
        question: str,
    ) -> SubAgentResponse:
        """Claude Code agent に質問して回答を得る"""
        cmd = [
            "claude-code",
            "-p",
            question.strip(),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        response = result.stdout.strip()
        return SubAgentResponse(
            name="claude-code",
            model="Lisa",
            answer=response,
        )

    def ask(self, question: str) -> dict[str, Any]:
        """質問して回答を得る"""
        status = "error"
        results = []
        try:
            response = self._ask_grok(question)
            status = "ok"
            results.append(
                {
                    "agent": response.name,
                    "model": response.model,
                    "answer": response.answer,
                }
            )
        except Exception as e:
            print(f"Failed to ask Grok agent: {e}")
        try:
            response = self._ask_claudecode(question)
            status = "ok"
            results.append(
                {
                    "agent": response.name,
                    "model": response.model,
                    "answer": response.answer,
                }
            )
        except Exception as e:
            print(f"Failed to ask Claude Code agent: {e}")
        return {
            "status": status,
            "results": results,
        }

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            xai_sdk.chat.tool(
                name="subagents_ask",
                description=(
                    "他の複数のエージェントに質問して回答を得ます。"
                    "同じ質問を自動的に複数のエージェントに投げ、結果をまとめて返します。"
                    "深く考える必要がある質問や、複数の視点からの回答が欲しい場合に使います。"
                    "実行には1分程度かかります。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "質問内容。エージェントに聞きたいことを具体的に書いてください。",
                        },
                    },
                    "required": ["question"],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a sub-agents tool by name"""
        match tool_name:
            case "subagents_ask":
                return self.ask(**tool_args)
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
