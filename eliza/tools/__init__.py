"""Tools for Grok agent"""

from typing import Any

from xai_sdk import tools
from xai_sdk.proto import chat_pb2

from .browser import Browser
from .clipboard import Clipboard
from .memory import MemoryTool
from .ready import ReadyToAnswer
from .schedule import Schedule
from .switchbot import Switchbot
from .todo import ToDo
from .workspace import Workspace
from .youtube import YouTubeSearch


def is_server_side(tool_name: str) -> bool:
    """Check if a tool is server-side (i.e., does not return a result to the agent)"""
    return (
        tool_name.startswith("x_")
        or tool_name.startswith("web_")
        or tool_name.startswith("code_")
    )


def create_tools(search: bool = True) -> list[chat_pb2.Tool]:
    """Create tools for Grok agent"""
    available_tools = (
        [tools.x_search(), tools.web_search(), tools.code_execution()] if search else []
    )
    try:
        switchbot = Switchbot()
        available_tools.extend(switchbot.create_tools())
    except Exception as e:
        print(f"Failed to create Switchbot tools: {e}")
    try:
        available_tools.extend(YouTubeSearch().create_tools())
    except Exception as e:
        print(f"Failed to create YouTubeSearch tools: {e}")
    available_tools.extend(Browser().create_tools())
    available_tools.extend(Clipboard().create_tools())
    available_tools.extend(MemoryTool().create_tools())
    available_tools.extend(ReadyToAnswer().create_tools())
    available_tools.extend(Schedule().create_tools())
    available_tools.extend(ToDo().create_tools())
    available_tools.extend(Workspace().create_tools())
    return available_tools


def call(tool_name: str, tool_args: dict) -> dict[str, Any] | None:
    """Call any tool by name"""
    match tool_name:
        case _ if tool_name.startswith("switchbot_"):
            switchbot = Switchbot()
            return switchbot.call(tool_name, tool_args)
        case _ if tool_name.startswith("browser_"):
            return Browser().call(tool_name, tool_args)
        case _ if tool_name.startswith("youtube_"):
            return YouTubeSearch().call(tool_name, tool_args)
        case _ if tool_name.startswith("clipboard_"):
            return Clipboard().call(tool_name, tool_args)
        case _ if tool_name.startswith("memory_"):
            return MemoryTool().call(tool_name, tool_args)
        case "ready_to_answer":
            return ReadyToAnswer().call(tool_name, tool_args)
        case _ if tool_name.startswith("schedule_"):
            return Schedule().call(tool_name, tool_args)
        case _ if tool_name.startswith("todo_"):
            return ToDo().call(tool_name, tool_args)
        case _ if tool_name.startswith("workspace_"):
            return Workspace().call(tool_name, tool_args)
        case _ if (
            tool_name.startswith("x_")
            or tool_name.startswith("web_")
            or tool_name.startswith("code_")
        ):
            raise ValueError("Server-side tools should not be called from the agent")
        case _:
            raise ValueError(f"Unknown tool: {tool_name}")


__all__ = [
    "create_tools",
    "call",
]
