"""Browser tool - opens a URL in Vivaldi"""

import subprocess
from typing import Any

from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

VIVALDI = "/mnt/c/Users/cympf/AppData/Local/Vivaldi/Application/vivaldi.exe"


class Browser:
    """ブラウザでURLを開くツール"""

    def url_open(self, url: str) -> dict[str, Any]:
        """指定したURLをブラウザで開く

        Args:
            url: 開くURL
        """
        subprocess.Popen([VIVALDI, url])
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
                    "「開いて」「見たい」「再生して」「ブラウザで見せて」などの要求に使います。"
                    "youtube_search で動画を検索した後、ユーザーが視聴を求めている場合も必ずこのツールで先頭のURLを開くこと。"
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
