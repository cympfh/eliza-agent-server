"""Memory tool for Grok agent - 会話ログの検索"""

from typing import Any

import eliza.memory
from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2


class MemoryTool:
    """過去の会話ログを検索するツール"""

    def grep(self, pattern: str, limit: int = 10) -> dict[str, Any]:
        """正規表現で会話ログを検索する"""
        try:
            results = eliza.memory.grep(pattern, limit)
            return {
                "status": "ok",
                "pattern": pattern,
                "count": len(results),
                "results": results,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="memory_grep",
                description=(
                    "過去の会話ログを正規表現で検索します。"
                    "「以前〇〇について話したっけ？」「△△を調べたことある？」などに使います。"
                    "最新の会話から順に最大 limit 件返します。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "検索する正規表現パターン",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "返す最大件数（デフォルト: 10）",
                        },
                    },
                    "required": ["pattern"],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a memory tool by name"""
        match tool_name:
            case "memory_grep":
                return self.grep(
                    pattern=tool_args["pattern"],
                    limit=tool_args.get("limit", 10),
                )
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
