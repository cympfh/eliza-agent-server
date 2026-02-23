"""Switchbot API tool for Grok agent"""

import base64
import hashlib
import hmac
import os
import time
import uuid
from typing import Any

import requests
from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2


class Switchbot:
    """Switchbot API クライアント"""

    def _auth(self):
        """認証ヘッダーを生成"""
        token = os.environ.get("SWITCHBOT_API_TOKEN")
        assert token, "SWITCHBOT_API_TOKEN is not set"
        secret = os.environ.get("SWITCHBOT_API_SECRET")
        assert secret, "SWITCHBOT_API_SECRET is not set"
        nonce = uuid.uuid4()
        t = int(round(time.time() * 1000))
        string_to_sign = bytes(f"{token}{t}{nonce}", "utf-8")
        key = bytes(secret, "utf-8")
        sign = base64.b64encode(
            hmac.new(key, msg=string_to_sign, digestmod=hashlib.sha256).digest()
        )
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "charset": "utf8",
            "t": str(t),
            "sign": str(sign, "utf-8"),
            "nonce": str(nonce),
        }

    def __init__(self):
        self._auth()

    def get(self, uri: str):
        """GET リクエスト"""
        url = f"https://api.switch-bot.com{uri}"
        return requests.get(url, headers=self.headers).json()

    def post(self, uri: str, data: dict[str, Any]):
        """POST リクエスト"""
        url = f"https://api.switch-bot.com{uri}"
        return requests.post(url, json=data, headers=self.headers).json()

    def get_devices(self) -> dict[str, Any]:
        """デバイス一覧を取得"""
        return self.get("/v1.1/devices")

    def get_status(self, device_id: str) -> dict[str, Any]:
        """デバイスのステータスを取得"""
        return self.get(f"/v1.1/devices/{device_id}/status")

    def send_command(self, device_id: str, command: dict[str, Any]) -> dict[str, Any]:
        """デバイスにコマンドを送信"""
        return self.post(f"/v1.1/devices/{device_id}/commands", command)

    def get_room_temperature(self) -> dict[str, Any]:
        """部屋の温度と湿度を取得"""
        device_id = "D641FC309593"
        return self.get_status(device_id)

    def get_outside_temperature(self) -> dict[str, Any]:
        """家のすぐ外の温度と湿度を取得"""
        device_id = "F5BD2BF834BF"
        return self.get_status(device_id)

    def post_aircon_off(self) -> dict[str, Any]:
        """エアコンを消すコマンドを送信"""
        device_id = "02-202010092320-98867876"
        command = {
            "commandType": "command",
            "command": "setAll",
            "parameter": "26,1,3,off",
        }
        return self.send_command(device_id, command)

    def post_aircon_on(self, mode: str) -> dict[str, Any]:
        """エアコンをつけるコマンドを送信

        mode:
          "heat" -> 暖房 (26C, fan=auto)
          "cool" -> 冷房 (24C, fan=auto)
          "fan"  -> 送風 (25C)
        """
        device_id = "02-202010092320-98867876"
        if mode == "cool":
            parameter = "24,2,1,on"
        elif mode == "fan":
            parameter = "25,4,3,on"
        else:
            parameter = "26,5,1,on"
        command = {
            "commandType": "command",
            "command": "setAll",
            "parameter": parameter,
        }
        return self.send_command(device_id, command)

    def post_light_off(self) -> dict[str, Any]:
        """家の中の全てのライトを消す

        寝る前に使う
        """
        # (device_id, brightness)
        devices = [
            ("6055F92DD962", 0),
            ("6055F922E062", 0),
            ("6055F9236AAE", 0),
            ("6055F92C65B2", 0),
            ("68B6B3B2CCE6", 0),
            ("6055F933FCBA", 1),
            ("6055F936FA16", 1),
            ("68B6B3AFEAFE", 1),
            ("686725B28D1A", 30),
        ]
        for device_id, brightness in devices:
            command = {
                "commandType": "command",
                "command": "setBrightness",
                "parameter": brightness,
            }
            self.send_command(device_id, command)
        return {"status": "Accepted", "result": "All lights off"}

    def post_light_on(self) -> dict[str, Any]:
        """家の中の全てのライトをつける"""
        # (device_id, brightness)
        devices = [
            ("6055F92DD962", 0),
            ("6055F922E062", 0),
            ("6055F9236AAE", 0),
            ("6055F92C65B2", 0),
            ("68B6B3B2CCE6", 0),
            ("6055F933FCBA", 50),
            ("6055F936FA16", 50),
            ("68B6B3AFEAFE", 50),
            ("686725B28D1A", 60),
        ]
        for device_id, brightness in devices:
            command = {
                "commandType": "command",
                "command": "setBrightness",
                "parameter": brightness,
            }
            self.send_command(device_id, command)
        return {"status": "Accepted", "result": "All lights on"}

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""

        return [
            tool(
                name="switchbot_get_room_temperature",
                description="部屋の温度と湿度を取得します。室内の現在の気温と湿度を確認したいときに使います。",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            tool(
                name="switchbot_get_outside_temperature",
                description="家のすぐ外の温度と湿度を取得します。外の気温や湿度を確認したいときに使います。",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            tool(
                name="switchbot_post_aircon_off",
                description="エアコンを消します。部屋が暑すぎる、寒すぎる、または外出するときなどに使います。",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            tool(
                name="switchbot_post_aircon_on",
                description=(
                    "エアコンをつけます。mode で暖房(heat)/冷房(cool)/送風(fan) を選択できます。"
                    "部屋が寒いときは heat、暑いときは cool、少し蒸し暑い程度なら fan が適切です。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["heat", "cool", "fan"],
                            "description": "エアコンのモード: heat=暖房, cool=冷房, fan=送風",
                        }
                    },
                    "required": ["mode"],
                },
            ),
            tool(
                name="switchbot_post_light_off",
                description="家の中の全てのライトを消します。寝る前や外出するときに使います。",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            tool(
                name="switchbot_post_light_on",
                description="家の中の全てのライトをつけます。朝起きたときや帰宅したときに使います。",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a switchbot tool by name"""
        match tool_name:
            case "switchbot_get_room_temperature":
                return self.get_room_temperature()
            case "switchbot_get_outside_temperature":
                return self.get_outside_temperature()
            case "switchbot_post_aircon_off":
                return self.post_aircon_off()
            case "switchbot_post_aircon_on":
                return self.post_aircon_on(mode=tool_args["mode"])
            case "switchbot_post_light_off":
                return self.post_light_off()
            case "switchbot_post_light_on":
                return self.post_light_on()
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
