"""Bash tool for Grok agent - executes bash commands"""

import subprocess
from typing import Any

from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2


class Bash:
    """Bash コマンドを実行するツール"""

    def exec_date(self, format: str = "+%Y-%m-%d %H:%M:%S") -> dict[str, Any]:
        """date コマンドを実行して現在の日付と時刻を取得する"""
        result = subprocess.run(["date", format], capture_output=True, text=True)
        return {
            "status": "ok",
            "output": result.stdout.strip(),
        }

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="bash_exec_date",
                description=(
                    "date コマンドを実行して、現在の日付と時刻を取得します。"
                    "「今何時？」「今日は何日？」などの日時確認に使います。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "description": (
                                "date コマンドに渡すフォーマット文字列。"
                                "例: '+%Y-%m-%d' で日付のみ、'+%H:%M:%S' で時刻のみ。"
                                "デフォルトは '+%Y-%m-%d %H:%M:%S'。"
                            ),
                        }
                    },
                    "required": [],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a bash tool by name"""
        match tool_name:
            case "bash_exec_date":
                return self.exec_date(**tool_args)
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
