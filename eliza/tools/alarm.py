"""Alarm tool for Grok agent - opens https://cympfh.cc/alarm/ in browser"""

import os
import subprocess
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

BROWSER_PATH = os.environ.get("BROWSER_PATH")
ALARM_BASE_URL = "https://cympfh.cc/alarm/"


class Alarm:
    """ブラウザでアラームページを開くツール"""

    def set_alarm(
        self, time: str, sound: str = "bell", auto_stop: int = 0
    ) -> dict[str, Any]:
        """指定時刻にアラームをセットする

        Args:
            time: HH:MM 形式の時刻
            sound: アラーム音 (beep/bell/chime/siren/pulse)
            auto_stop: 自動停止秒数 (0以下なら自動停止しない)
        """
        if not BROWSER_PATH:
            return {"status": "error", "message": "環境変数 BROWSER_PATH が設定されていません"}
        params = urlencode({"time": time, "sound": sound, "autoStop": auto_stop})
        url = f"{ALARM_BASE_URL}?{params}"
        subprocess.Popen([BROWSER_PATH, url])
        return {
            "status": "ok",
            "message": f"アラームをセットしました: {time} (sound={sound}, autoStop={auto_stop}s)",
            "url": url,
        }

    def set_alarm_after_minutes(
        self, minutes: int, sound: str = "bell"
    ) -> dict[str, Any]:
        """現在時刻から指定分後にアラームをセットする

        Args:
            minutes: 何分後か
            sound: アラーム音 (beep/bell/chime/siren/pulse)
        """
        target = datetime.now() + timedelta(minutes=minutes)
        time_str = target.strftime("%H:%M:%S")
        # 短時間なので autoStop=5 でOK
        return self.set_alarm(time=time_str, sound=sound, auto_stop=5)

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="alarm_set",
                description=(
                    "指定した時刻にアラームをセットします。"
                    "「朝7時に起こして」「10時にアラーム」などの絶対時刻指定に使います。"
                    " time は HH:MM 形式（24時間制）で指定してください。"
                    " sound は beep/bell/chime/siren/pulse から選べます（推奨は bell）。"
                    " 絶対時刻指定のアラームは auto_stop=0 (自動停止なし) を推奨します。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "time": {
                            "type": "string",
                            "description": "アラーム時刻 (HH:MM または HH:MM:SS 形式, 24時間制)",
                        },
                        "sound": {
                            "type": "string",
                            "enum": ["beep", "bell", "chime", "siren", "pulse"],
                            "description": "アラーム音の種類",
                        },
                        "auto_stop": {
                            "type": "integer",
                            "description": "自動停止までの秒数。0以下なら自動停止しない。絶対時刻指定には0を推奨。",
                        },
                    },
                    "required": ["time"],
                },
            ),
            tool(
                name="alarm_set_after_minutes",
                description=(
                    "現在時刻から指定した分数後にアラームをセットします。"
                    "「3分後にアラーム」「30分後に教えて」などの相対時間指定に使います。"
                    " sound は beep/bell/chime/siren/pulse から選べます（推奨は chime）。"
                    " 短時間タイマーなので自動停止(5秒)が有効になります。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "minutes": {
                            "type": "integer",
                            "description": "何分後にアラームするか",
                        },
                        "sound": {
                            "type": "string",
                            "enum": ["beep", "bell", "chime", "siren", "pulse"],
                            "description": "アラーム音の種類",
                        },
                    },
                    "required": ["minutes"],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call an alarm tool by name"""
        match tool_name:
            case "alarm_set":
                return self.set_alarm(
                    time=tool_args["time"],
                    sound=tool_args.get("sound", "bell"),
                    auto_stop=tool_args.get("auto_stop", 0),
                )
            case "alarm_set_after_minutes":
                return self.set_alarm_after_minutes(
                    minutes=tool_args["minutes"],
                    sound=tool_args.get("sound", "bell"),
                )
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
