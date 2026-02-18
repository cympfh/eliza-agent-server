"""Tenki (weather) tool for Grok agent - uses OpenWeatherMap API"""

from typing import Any

import requests
from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

APPID = "cc78d27e7519b67719a1121d90e67426"
BASE_URL = "http://api.openweathermap.org/data/2.5"


def _kelvin_to_celsius(k: float) -> float:
    return round(k - 273.15, 1)


class Tenki:
    """OpenWeatherMap を使った天気ツール"""

    def current(self, city: str) -> dict[str, Any]:
        """指定都市の現在の天気を取得する

        Args:
            city: 都市名 (例: Tokyo, Osaka, London)
        """
        resp = requests.get(
            f"{BASE_URL}/weather",
            params={"q": city, "appid": APPID},
            timeout=10,
        )
        data = resp.json()

        if data.get("cod") == "404":
            return {"error": f"City not found: {city}"}

        temp = _kelvin_to_celsius(data["main"]["temp"])
        temp_min = _kelvin_to_celsius(data["main"]["temp_min"])
        temp_max = _kelvin_to_celsius(data["main"]["temp_max"])
        weather_main = data["weather"][0]["main"]
        weather_desc = data["weather"][0]["description"]
        pressure = data["main"]["pressure"]
        humidity = data["main"]["humidity"]
        name = data["name"]
        country = data["sys"]["country"]

        return {
            "city": f"{name},{country}",
            "temperature": f"{temp}°C",
            "temp_min": f"{temp_min}°C",
            "temp_max": f"{temp_max}°C",
            "pressure": f"{pressure}hPa",
            "humidity": f"{humidity}%",
            "weather": weather_main,
            "description": weather_desc,
            "summary": (
                f"{name},{country}: {temp}°C ({temp_min}/{temp_max}°C), "
                f"{weather_main} ({weather_desc}), {pressure}hPa, 湿度{humidity}%"
            ),
        }

    def forecast(self, city: str) -> dict[str, Any]:
        """指定都市の5日間天気予報を取得する (3時間ごと)

        Args:
            city: 都市名 (例: Tokyo, Osaka, London)
        """
        resp = requests.get(
            f"{BASE_URL}/forecast",
            params={"q": city, "appid": APPID},
            timeout=10,
        )
        data = resp.json()

        if data.get("cod") == "404":
            return {"error": f"City not found: {city}"}

        city_name = f"{data['city']['name']},{data['city']['country']}"
        entries = []
        for item in data["list"]:
            dt_txt = item["dt_txt"]
            temp = _kelvin_to_celsius(item["main"]["temp"])
            weather = item["weather"][0]["main"]
            desc = item["weather"][0]["description"]
            entries.append(f"{dt_txt[5:16]}  {temp}°C  {weather} ({desc})")

        return {
            "city": city_name,
            "forecast": entries,
        }

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="tenki_current",
                description=(
                    "指定した都市の現在の天気を取得します。"
                    "「今日の天気は？」「東京の天気を教えて」などに使います。"
                    " city は英語の都市名 (例: Tokyo, Osaka, London) で指定してください。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "都市名 (英語, 例: Tokyo, Osaka, London, New York)",
                        },
                    },
                    "required": ["city"],
                },
            ),
            tool(
                name="tenki_forecast",
                description=(
                    "指定した都市の5日間天気予報 (3時間ごと) を取得します。"
                    "「今週の天気は？」「明日の天気は？」「天気予報を見せて」などに使います。"
                    " city は英語の都市名 (例: Tokyo, Osaka, London) で指定してください。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "都市名 (英語, 例: Tokyo, Osaka, London, New York)",
                        },
                    },
                    "required": ["city"],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a tenki tool by name"""
        match tool_name:
            case "tenki_current":
                return self.current(city=tool_args["city"])
            case "tenki_forecast":
                return self.forecast(city=tool_args["city"])
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
