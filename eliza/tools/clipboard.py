"""Clipboard tool for Grok agent - uses ~/bin/clip"""

import subprocess
from typing import Any

from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

CLIP_CMD = "/home/cympfh/bin/clip"


class Clipboard:
    """クリップボードの読み書きツール"""

    def copy(self, text: str) -> dict[str, Any]:
        """テキストをクリップボードにコピーする

        Args:
            text: コピーするテキスト
        """
        result = subprocess.run(
            [CLIP_CMD],
            input=text.encode(),
            capture_output=True,
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "message": result.stderr.decode().strip(),
            }
        return {
            "status": "ok",
            "message": f"クリップボードにコピーしました ({len(text)} 文字)",
        }

    def paste(self) -> dict[str, Any]:
        """クリップボードの内容を取得する"""
        result = subprocess.run(
            [CLIP_CMD],
            capture_output=True,
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "message": result.stderr.decode().strip(),
            }
        text = result.stdout.decode()
        return {
            "status": "ok",
            "text": text,
            "length": len(text),
        }

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="clipboard_copy",
                description=(
                    "テキストをクリップボードにコピーします。"
                    "「これをコピーして」「クリップボードに保存して」などに使います。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "クリップボードにコピーするテキスト",
                        },
                    },
                    "required": ["text"],
                },
            ),
            tool(
                name="clipboard_paste",
                description=(
                    "クリップボードの内容を取得します。"
                    "「クリップボードの中身は？」「さっきコピーしたやつ見せて」などに使います。"
                ),
                parameters={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a clipboard tool by name"""
        match tool_name:
            case "clipboard_copy":
                return self.copy(text=tool_args["text"])
            case "clipboard_paste":
                return self.paste()
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
