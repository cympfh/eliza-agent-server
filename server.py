import json
import logging
import os
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from xai_sdk import Client, chat, tools

from tools.switchbot import Switchbot

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 環境変数の確認
XAI_API_KEY = os.environ.get("XAI_API_KEY")
SWITCHBOT_API_TOKEN = os.environ.get("SWITCHBOT_API_TOKEN")
SWITCHBOT_API_SECRET = os.environ.get("SWITCHBOT_API_SECRET")

# FastAPIアプリケーションの作成
app = FastAPI(
    title="Eliza Agent Server",
    description="Grok API with x_search, web_search, and Switchbot tools",
)


# リクエスト/レスポンスのスキーマ
class Message(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str = "grok-4-1-fast"


class ChatResponse(BaseModel):
    message: Message


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    会話履歴を受け取り、次の返答を生成します。
    サーバーは状態を持たず、毎回の呼び出しで完全な会話履歴を受け取ります。
    """
    request_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")

    # リクエストの詳細ログ
    logger.info("=" * 80)
    logger.info(f"[REQUEST ID: {request_id}] POST /chat")
    logger.info("-" * 80)
    logger.info(f"[REQUEST] Model: {request.model}")
    logger.info(f"[REQUEST] Number of messages: {len(request.messages)}")
    logger.info("[REQUEST] Body:")
    for i, msg in enumerate(request.messages):
        logger.info(f"  Message[{i}]:")
        logger.info(f"    role: {msg.role}")
        logger.info(
            f"    content: {msg.content[:200]}{'...' if len(msg.content) > 200 else ''}"
        )
    logger.info("-" * 80)

    if not XAI_API_KEY:
        logger.error(f"[REQUEST ID: {request_id}] XAI_API_KEY is not set")
        raise HTTPException(status_code=500, detail="XAI_API_KEY is not set")

    if not request.messages:
        logger.error(f"[REQUEST ID: {request_id}] messages list cannot be empty")
        raise HTTPException(status_code=400, detail="messages list cannot be empty")

    try:
        # Grok クライアントの作成
        logger.info(f"[REQUEST ID: {request_id}] Creating Grok client...")
        client = Client(api_key=XAI_API_KEY)

        # ツール一覧を作成
        available_tools = [tools.x_search(), tools.web_search(), tools.code_execution()]

        # Switchbot ツールを追加（環境変数が設定されている場合のみ）
        if SWITCHBOT_API_TOKEN and SWITCHBOT_API_SECRET:
            logger.info(f"[REQUEST ID: {request_id}] Adding Switchbot tools...")
            try:
                switchbot = Switchbot()
                available_tools.extend(switchbot.create_tools())
            except Exception as e:
                logger.error(f"Failed to create Switchbot tools: {e}")
                raise

        # tools を有効化してチャットセッション作成
        logger.info(
            f"[REQUEST ID: {request_id}] Creating chat session with {len(available_tools)} tools..."
        )
        session = client.chat.create(
            model=request.model,
            tools=available_tools,
        )

        # 会話履歴を追加
        logger.info(f"[REQUEST ID: {request_id}] Appending conversation history...")
        for msg in request.messages:
            if msg.role == "system":
                session.append(chat.system(msg.content))
            elif msg.role == "user":
                session.append(chat.user(msg.content))
            elif msg.role == "assistant":
                session.append(chat.assistant(msg.content))

        # レスポンス生成, function calling
        while True:
            logger.info(f"[REQUEST ID: {request_id}] Generating response...")
            response = session.sample()
            if response.tool_calls:
                logger.info(
                    f"[REQUEST ID: {request_id}] Tool calls detected: {len(response.tool_calls)}"
                )
                for tool_call in response.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = (
                        json.loads(tool_call.function.arguments)
                        if tool_call.function.arguments
                        else {}
                    )
                    logger.info(
                        f"[REQUEST ID: {request_id}] Tool call: {tool_name} with args: {tool_args}"
                    )
                    match tool_name:
                        case "get_room_temperature":
                            result = json.dumps(switchbot.get_room_temperature())
                        case "get_outside_temperature":
                            result = json.dumps(switchbot.get_outside_temperature())
                        case "post_aircon_off":
                            result = json.dumps(switchbot.post_aircon_off())
                        case "post_aircon_on":
                            result = json.dumps(switchbot.post_aircon_on())
                        case "post_light_off":
                            result = json.dumps(switchbot.post_light_off())
                        case "post_light_on":
                            result = json.dumps(switchbot.post_light_on())
                        case _:
                            result = "Error: Unknown tool"

                    session.append(chat.tool_result(result))
                session.append(chat.system("ツール呼び出しの結果は上記の通りです。"))
            else:
                break

        # レスポンスの詳細ログ
        logger.info("-" * 80)
        logger.info(f"[RESPONSE ID: {request_id}] Success")
        logger.info("[RESPONSE] Role: assistant")
        logger.info(f"[RESPONSE] Content length: {len(response.content)} chars")
        logger.info("[RESPONSE] Content:")
        logger.info(
            f"  {response.content[:500]}{'...' if len(response.content) > 500 else ''}"
        )
        logger.info("=" * 80)

        return ChatResponse(message=Message(role="assistant", content=response.content))

    except Exception as e:
        logger.error(f"[REQUEST ID: {request_id}] Error occurred: {str(e)}")
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """ヘルスチェックエンドポイント"""
    return {"status": "ok"}


@app.get("/tools")
async def list_tools() -> dict[str, list[str]]:
    """利用可能なツール一覧を返す"""
    tool_list = ["x_search", "web_search", "code_execution"]
    if SWITCHBOT_API_TOKEN and SWITCHBOT_API_SECRET:
        tool_list.extend(
            [
                "get_room_temperature",
                "get_outside_temperature",
                "post_aircon_off",
                "post_aircon_on",
                "post_light_off",
                "post_light_on",
            ]
        )
    return {"tools": tool_list}


def main():
    """サーバーを起動"""
    uvicorn.run(app, host="0.0.0.0", port=9096)


if __name__ == "__main__":
    main()
