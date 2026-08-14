"""ツールループ終了フラグ。副作用なし。"""

from typing import Any

from pydantic import BaseModel
from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

TOOL_NAME = "ready_to_answer"


class ReadyToAnswerParams(BaseModel):
    pass


class ReadyToAnswer:
    """今回の tool_calls のあと最終回答へ進むことを示すフラグ"""

    def create_tools(self) -> list[chat_pb2.Tool]:
        return [
            tool(
                name=TOOL_NAME,
                description=(
                    "今回の tool_calls で必要な操作は揃ったので、"
                    "結果を待ったあと追加のツールは不要で最終回答に進む、と宣言する。"
                    "最後の実ツールと同じターンで必ず同時に呼ぶ。"
                    "まだ次のツールが必要なら呼ぶな。"
                    "このツール自体は何も実行しない。"
                ),
                parameters=ReadyToAnswerParams.model_json_schema(),
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        if tool_name != TOOL_NAME:
            raise ValueError(f"Unknown tool: {tool_name}")
        return {"ok": True}
