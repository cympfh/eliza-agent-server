"""Schedule tool for Grok agent - schedule tool calls for future execution"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

import eliza.tools

logger = logging.getLogger(__name__)
JST = ZoneInfo("Asia/Tokyo")

_RUNNER_INTERVAL_SECONDS = 30


class ScheduledTask(BaseModel):
    """スケジュールされたタスク"""

    task_id: str
    tool_name: str
    tool_args: dict[str, Any]
    execute_at: datetime
    status: str = "pending"


_scheduled_tasks: list[ScheduledTask] = []


class ScheduleToolCallParams(BaseModel):
    tool_name: str = Field(
        description="実行するツール名 (例: switchbot_post_aircon_off, switchbot_post_light_off)"
    )
    tool_args: dict[str, Any] = Field(
        default_factory=dict, description="ツールに渡す引数 (不要なら空の dict)"
    )
    execute_at: str = Field(
        description="実行時刻 (HH:MM 形式 24時間制, 本日のその時刻に実行する)"
    )


class ScheduleToolCallAfterMinutesParams(BaseModel):
    tool_name: str = Field(
        description="実行するツール名 (例: switchbot_post_aircon_off, switchbot_post_light_off)"
    )
    tool_args: dict[str, Any] = Field(
        default_factory=dict, description="ツールに渡す引数 (不要なら空の dict)"
    )
    minutes: int = Field(description="何分後に実行するか")


class Schedule:
    """ツール実行のスケジューラ"""

    def schedule_tool_call(
        self, tool_name: str, tool_args: dict[str, Any], execute_at: str
    ) -> dict[str, Any]:
        """指定時刻にツールを実行するようスケジュールする

        Parameters
        ----------
        tool_name
            実行するツール名
        tool_args
            ツールに渡す引数
        execute_at
            HH:MM 形式の実行時刻
        """
        now = datetime.now(JST)
        parts = execute_at.strip().split(":")
        hour, minute = int(parts[0]), int(parts[1])
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return self._register(tool_name, tool_args, target)

    def schedule_tool_call_after_minutes(
        self, tool_name: str, tool_args: dict[str, Any], minutes: int
    ) -> dict[str, Any]:
        """現在時刻から指定分後にツールを実行するようスケジュールする

        Parameters
        ----------
        tool_name
            実行するツール名
        tool_args
            ツールに渡す引数
        minutes
            何分後に実行するか
        """
        target = datetime.now(JST) + timedelta(minutes=minutes)
        return self._register(tool_name, tool_args, target)

    def _register(
        self, tool_name: str, tool_args: dict[str, Any], execute_at: datetime
    ) -> dict[str, Any]:
        """タスクを登録する

        Parameters
        ----------
        tool_name
            実行するツール名
        tool_args
            ツールに渡す引数
        execute_at
            実行予定時刻
        """
        task = ScheduledTask(
            task_id=uuid.uuid4().hex[:12],
            tool_name=tool_name,
            tool_args=tool_args,
            execute_at=execute_at,
        )
        _scheduled_tasks.append(task)
        logger.info(
            f"[SCHEDULE] Registered: {task.task_id} -> {tool_name}({tool_args}) at {execute_at.isoformat()}"
        )
        return {
            "status": "scheduled",
            "task_id": task.task_id,
            "tool_name": tool_name,
            "execute_at": execute_at.isoformat(),
        }

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="schedule_tool_call",
                description=(
                    "指定した時刻にツールを実行するようスケジュールします。"
                    "「23時にエアコンを切って」「20:00にライトを消して」のような絶対時刻指定に使います。"
                    " execute_at は HH:MM 形式（24時間制）で指定してください。"
                ),
                parameters=ScheduleToolCallParams.model_json_schema(),
            ),
            tool(
                name="schedule_tool_call_after_minutes",
                description=(
                    "現在時刻から指定した分数後にツールを実行するようスケジュールします。"
                    "「1時間後にエアコンを切って」「30分後にライトを消して」のような相対時間指定に使います。"
                ),
                parameters=ScheduleToolCallAfterMinutesParams.model_json_schema(),
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a schedule tool by name"""
        match tool_name:
            case "schedule_tool_call":
                return self.schedule_tool_call(
                    tool_name=tool_args["tool_name"],
                    tool_args=tool_args.get("tool_args", {}),
                    execute_at=tool_args["execute_at"],
                )
            case "schedule_tool_call_after_minutes":
                return self.schedule_tool_call_after_minutes(
                    tool_name=tool_args["tool_name"],
                    tool_args=tool_args.get("tool_args", {}),
                    minutes=tool_args["minutes"],
                )
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")


async def run_scheduled_tasks_loop():
    """スケジュールされたタスクを定期的にチェックし実行するバックグラウンドループ"""
    while True:
        await asyncio.sleep(_RUNNER_INTERVAL_SECONDS)
        now = datetime.now(JST)
        due_tasks = [t for t in _scheduled_tasks if t.status == "pending" and t.execute_at <= now]
        for task in due_tasks:
            task.status = "running"
            logger.info(
                f"[SCHEDULE] Executing: {task.task_id} -> {task.tool_name}({task.tool_args})"
            )
            try:
                result = await asyncio.to_thread(
                    eliza.tools.call, task.tool_name, task.tool_args
                )
                task.status = "done"
                logger.info(f"[SCHEDULE] Done: {task.task_id} -> {result}")
            except Exception as e:
                task.status = "error"
                logger.error(f"[SCHEDULE] Error: {task.task_id} -> {e}")
        # 完了・エラーのタスクをリストから除去
        _scheduled_tasks[:] = [t for t in _scheduled_tasks if t.status == "pending"]
