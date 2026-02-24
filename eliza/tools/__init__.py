"""Tools for Grok agent"""

from typing import Any

from xai_sdk import tools
from xai_sdk.proto import chat_pb2

from .alarm import Alarm
from .bash import Bash
from .browser import Browser
from .clipboard import Clipboard
from .memory import MemoryTool
from .skill import Skill
from .switchbot import Switchbot
from .tenki import Tenki
from .youtube import YouTubeSearch


def create_tools() -> list[chat_pb2.Tool]:
    """Create tools for Grok agent"""
    available_tools = [tools.x_search(), tools.web_search(), tools.code_execution()]
    try:
        switchbot = Switchbot()
        available_tools.extend(switchbot.create_tools())
    except Exception as e:
        print(f"Failed to create Switchbot tools: {e}")
    available_tools.extend(Alarm().create_tools())
    available_tools.extend(Bash().create_tools())
    available_tools.extend(Browser().create_tools())
    available_tools.extend(Tenki().create_tools())
    try:
        available_tools.extend(YouTubeSearch().create_tools())
    except Exception as e:
        print(f"Failed to create YouTubeSearch tools: {e}")
    available_tools.extend(Clipboard().create_tools())
    available_tools.extend(MemoryTool().create_tools())
    available_tools.extend(Skill().create_tools())
    return available_tools


def call(tool_name: str, tool_args: dict) -> dict[str, Any] | None:
    """Call any tool by name"""
    match tool_name:
        case _ if tool_name.startswith("switchbot_"):
            switchbot = Switchbot()
            return switchbot.call(tool_name, tool_args)
        case _ if tool_name.startswith("alarm_"):
            return Alarm().call(tool_name, tool_args)
        case _ if tool_name.startswith("bash_"):
            return Bash().call(tool_name, tool_args)
        case _ if tool_name.startswith("browser_"):
            return Browser().call(tool_name, tool_args)
        case _ if tool_name.startswith("tenki_"):
            return Tenki().call(tool_name, tool_args)
        case _ if tool_name.startswith("youtube_"):
            return YouTubeSearch().call(tool_name, tool_args)
        case _ if tool_name.startswith("clipboard_"):
            return Clipboard().call(tool_name, tool_args)
        case _ if tool_name.startswith("memory_"):
            return MemoryTool().call(tool_name, tool_args)
        case _ if tool_name.startswith("skill_"):
            return Skill().call(tool_name, tool_args)
        case _ if (
            tool_name.startswith("x_")
            or tool_name.startswith("web_")
            or tool_name.startswith("code_")
        ):
            return {
                "success": True,
                "message": "This tool is a server-side. The result is omitted.",
            }
        case _:
            return None


__all__ = [
    "Alarm",
    "Bash",
    "Browser",
    "Clipboard",
    "MemoryTool",
    "Skill",
    "Switchbot",
    "Tenki",
    "YouTubeSearch",
    "create_tools",
    "call",
]
