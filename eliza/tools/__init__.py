"""Tools for Grok agent"""

from typing import Any

from xai_sdk import tools
from xai_sdk.proto import chat_pb2

from .switchbot import Switchbot


def create_tools() -> list[chat_pb2.Tool]:
    """Create tools for Grok agent"""
    available_tools = [tools.x_search(), tools.web_search(), tools.code_execution()]
    try:
        switchbot = Switchbot()
        available_tools.extend(switchbot.create_tools())
    except Exception as e:
        print(f"Failed to create Switchbot tools: {e}")
    return available_tools


def call(tool_name: str, tool_args: dict) -> dict[str, Any] | None:
    """Call any tool by name"""
    match tool_name:
        case _ if tool_name.startswith("switchbot_"):
            switchbot = Switchbot()
            return switchbot.call(tool_name, tool_args)
        case _:
            return None


__all__ = ["Switchbot", "base_tools", "create_tools", "call"]
