"""Switchbot API tool for Grok agent"""

import base64
import hashlib
import hmac
import os
import time
import uuid
from typing import Any, Literal

import requests
from pydantic import BaseModel, Field
from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

# SwitchBot API が成功を表す statusCode
STATUS_OK = 100

# ライトのシーン定義の輝度指定
#
# None は turnOff を送って消灯する。
# "on" は turnOn を送る。輝度を指定できないデバイス (赤外線リモコンの
# DIY Light など) 用。
# int (1-100) は setBrightness を送る。消灯中の Color Bulb でも setBrightness
# だけで点灯するため turnOn は送らない (turnOn を先に送ると前回の輝度で一瞬
# 明るく点いてしまう)。
LightLevel = int | Literal["on"] | None

# ライトのシーン定義: (device_id, 表示名, LightLevel) のリスト
LightScene = list[tuple[str, str, LightLevel]]

LIGHT_OFF_SCENE: LightScene = [
    ("6055F92DD962", "light-k-a", None),
    ("6055F922E062", "light-k-c", None),
    ("6055F9236AAE", "light-c", None),
    ("6055F92C65B2", "light-w", None),
    ("68B6B3B2CCE6", "light-e", None),
    ("02-202411071358-52951738", "light-living", None),
    ("6055F933FCBA", "light-b-c", 1),
    ("6055F936FA16", "light-b-b", 1),
    ("68B6B3AFEAFE", "light-b-a", 1),
    ("686725B28D1A", "light-vrc", 30),
]

LIGHT_ON_SCENE: LightScene = [
    ("6055F92DD962", "light-k-a", None),
    ("6055F922E062", "light-k-c", None),
    ("6055F9236AAE", "light-c", None),
    ("6055F92C65B2", "light-w", None),
    ("68B6B3B2CCE6", "light-e", None),
    ("02-202411071358-52951738", "light-living", "on"),
    ("6055F933FCBA", "light-b-c", 50),
    ("6055F936FA16", "light-b-b", 50),
    ("68B6B3AFEAFE", "light-b-a", 50),
    ("686725B28D1A", "light-vrc", 60),
]


class SwitchbotEmptyParams(BaseModel):
    pass


class SwitchbotAirconOnParams(BaseModel):
    mode: Literal["heat", "cool", "strong_cool", "fan"] = Field(
        description="エアコンのモード: heat=暖房, cool=冷房, strong_cool=強冷房, fan=送風"
    )


class Switchbot:
    """Switchbot API クライアント

    API v1.1 を使う
    https://github.com/OpenWonderLabs/SwitchBotAPI
    """

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
        """Switchbot クライアントを初期化して認証する"""
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
        """エアコンをつけるコマンドを送信する

        Parameters
        ----------
        mode
            "heat" -> 暖房 (26C, fan=auto)
            "cool" -> 冷房 (24C, fan=auto)
            "strong_cool" -> 強冷房 (22C, fan=3)
            "fan" -> 送風 (25C)
        """
        device_id = "02-202010092320-98867876"
        if mode == "cool":
            parameter = "24,3,1,on"  # 実際は除湿
        elif mode == "strong_cool":
            parameter = "22,2,3,on"
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

    def _apply_light_scene(self, scene: LightScene, result: str) -> dict[str, Any]:
        """ライトのシーンを適用し、各デバイスの応答を検証する

        Parameters
        ----------
        scene
            (device_id, 表示名, level) のリスト。
            level=None なら turnOff、"on" なら turnOn、int なら setBrightness を送る
        result
            全台成功したときに result フィールドへ入れる文字列

        Returns
        -------
        dict[str, Any]
            全台成功なら status="Accepted"。
            1台でも失敗したら status="Error" と failures に失敗したデバイスの詳細
        """
        failures: list[dict[str, Any]] = []
        for device_id, name, level in scene:
            if level is None:
                command = {
                    "commandType": "command",
                    "command": "turnOff",
                    "parameter": "default",
                }
            elif level == "on":
                command = {
                    "commandType": "command",
                    "command": "turnOn",
                    "parameter": "default",
                }
            else:
                command = {
                    "commandType": "command",
                    "command": "setBrightness",
                    "parameter": level,
                }
            try:
                res = self.send_command(device_id, command)
            except Exception as e:
                failures.append(
                    {
                        "device": name,
                        "device_id": device_id,
                        "command": command["command"],
                        "error": f"{type(e).__name__}: {e}",
                    }
                )
                continue
            if res.get("statusCode") != STATUS_OK:
                failures.append(
                    {
                        "device": name,
                        "device_id": device_id,
                        "command": command["command"],
                        "statusCode": res.get("statusCode"),
                        "message": res.get("message"),
                    }
                )

        if failures:
            return {
                "status": "Error",
                "result": f"{len(failures)}/{len(scene)} 台のライト操作が失敗した",
                "failures": failures,
            }
        return {"status": "Accepted", "result": result}

    def post_light_off(self) -> dict[str, Any]:
        """家の中の全てのライトを消す

        寝る前に使う。
        light-b-a/b/c と light-vrc は常夜灯として暗く点灯したままにする。
        light-living は輝度指定できないため消灯する。
        """
        return self._apply_light_scene(LIGHT_OFF_SCENE, "All lights off")

    def post_light_on(self) -> dict[str, Any]:
        """家の中の全てのライトをつける

        light-k-a/k-c/c/w/e は点灯対象ではないため消灯する。
        light-living は輝度指定できないため turnOn で点灯する。
        """
        return self._apply_light_scene(LIGHT_ON_SCENE, "All lights on")

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        empty = SwitchbotEmptyParams.model_json_schema()

        return [
            tool(
                name="switchbot_get_room_temperature",
                description="部屋の温度と湿度を取得します。室内の現在の気温と湿度を確認したいときに使います。",
                parameters=empty,
            ),
            tool(
                name="switchbot_get_outside_temperature",
                description="家のすぐ外の温度と湿度を取得します。外の気温や湿度を確認したいときに使います。",
                parameters=empty,
            ),
            tool(
                name="switchbot_post_aircon_off",
                description="エアコンを消します。部屋が暑すぎる、寒すぎる、または外出するときなどに使います。",
                parameters=empty,
            ),
            tool(
                name="switchbot_post_aircon_on",
                description=(
                    "エアコンをつけます。mode で暖房(heat)/冷房(cool)/強冷房(strong_cool)/送風(fan) を選択できます。"
                    "部屋が寒いときは heat、暑いときは cool、本当に暑いときは strong_cool、少し蒸し暑い程度なら fan が適切"
                ),
                parameters=SwitchbotAirconOnParams.model_json_schema(),
            ),
            tool(
                name="switchbot_post_light_off",
                description=(
                    "家の中のライトを消します。寝る前や外出するときに使います。"
                    "一部のライトは常夜灯として暗く点灯したまま残ります。"
                ),
                parameters=empty,
            ),
            tool(
                name="switchbot_post_light_on",
                description="家の中の全てのライトをつけます。朝起きたときや帰宅したときに使います。",
                parameters=empty,
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
