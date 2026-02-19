"""Browser tool - opens a URL in Vivaldi"""

import os
import subprocess
from typing import Any

from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

BROWSER_PATH = os.environ.get("BROWSER_PATH")


class Browser:
    """ブラウザでURLを開くツール"""

    def url_open(self, url: str) -> dict[str, Any]:
        """指定したURLをブラウザで開く

        Args:
            url: 開くURL
        """
        if not BROWSER_PATH:
            return {"status": "error", "message": "環境変数 BROWSER_PATH が設定されていません"}
        subprocess.Popen([BROWSER_PATH, url])
        return {
            "status": "ok",
            "message": f"ブラウザでURLを開きました: {url}",
            "url": url,
        }

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="browser_url_open",
                description=(
                    "指定したURLをブラウザで開きます。"
                    "「このURLを開いて」「ブラウザで見たい」などの要求に使います。"
                    "重要：このツールはURLを直接開くため、ユーザーの意図を正確に理解して使用してください。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "開くURL",
                        },
                    },
                    "required": ["url"],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a browser tool by name"""
        match tool_name:
            case "browser_url_open":
                return self.url_open(url=tool_args["url"])
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
