"""YouTube search tool for Grok agent - uses YouTube Data API v3"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

from .clipboard import Clipboard

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
BASE_URL = "https://www.googleapis.com/youtube/v3"
CACHE_DIR = Path("/tmp/eliza_youtube_cache")


def _cache_file(keyword: str, order: str) -> Path:
    key = hashlib.sha256(f"{keyword}\0{order}".encode()).hexdigest()
    return CACHE_DIR / f"search_{key}.json"


def _search(keyword: str, limit: int, order: str) -> list[dict[str, str]]:
    """YouTube API で検索"""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = _cache_file(keyword, order)

    if cache_file.exists():
        if time.time() - cache_file.stat().st_mtime < 300:
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)[:limit]
        cache_file.unlink()

    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "maxResults": 20,
        "order": order,
        "key": YOUTUBE_API_KEY,
        "safeSearch": "none",
    }
    with httpx.Client() as client:
        response = client.get(f"{BASE_URL}/search", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("items", []):
        video_id = item["id"].get("videoId")
        if not video_id:
            continue
        snippet = item["snippet"]
        results.append(
            {
                "title": snippet["title"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "channel": snippet["channelTitle"],
                "published_at": snippet["publishedAt"][:10],
            }
        )

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results[:limit]


class YouTubeSearch:
    """YouTube 検索ツール"""

    def search(
        self, keyword: str, limit: int = 5, order: str = "relevance"
    ) -> dict[str, Any]:
        """YouTube でキーワード検索して動画一覧を返す

        Args:
            keyword: 検索キーワード
            limit: 取得件数 (最大10)
            order: 並び順 (date/rating/relevance/title/videoCount/viewCount)
        """
        if not YOUTUBE_API_KEY:
            return {"error": "YOUTUBE_API_KEY is not set"}

        limit = min(limit, 10)
        results = _search(keyword, limit, order)
        if results:
            Clipboard().copy(results[0]["url"])
        return {
            "keyword": keyword,
            "count": len(results),
            "results": results,
        }

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="youtube_search",
                description=(
                    "YouTube で動画を検索します。"
                    "「おさだの最新動画探して」「〇〇のMVを見たい」などの動画検索リクエストに使います。"
                    " keyword は検索したいキーワードを指定してください。"
                    " 結果としてタイトル・URL・チャンネル名・投稿日を返します。"
                    "重要: ユーザーが「開いて」「見たい」「再生して」などブラウザで開くことを求めている場合は、"
                    "このツールで検索した後、必ず続けて browser_url_open も呼び出すこと。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "検索キーワード (例: 'ヨルシカ 音楽', 'cute cats', 'lofi hip hop')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "取得する件数 (1〜10, デフォルト5)",
                        },
                        "order": {
                            "type": "string",
                            "enum": [
                                "date",
                                "rating",
                                "relevance",
                                "title",
                                "videoCount",
                                "viewCount",
                            ],
                            "description": "並び順。date=新着順, rating=評価順, relevance=関連度順(デフォルト), title=タイトル順, videoCount=動画数順, viewCount=再生数順",
                        },
                    },
                    "required": ["keyword"],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a youtube tool by name"""
        match tool_name:
            case "youtube_search":
                return self.search(
                    keyword=tool_args["keyword"],
                    limit=tool_args.get("limit", 5),
                    order=tool_args.get("order", "relevance"),
                )
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
