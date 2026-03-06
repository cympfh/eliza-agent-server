import hashlib
import json
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

import eliza.memory
import eliza.tools
from eliza.agent import Agent

JST = ZoneInfo("Asia/Tokyo")

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Eliza Agent Server starting up...")
    yield
    logger.info("Eliza Agent Server shutting down gracefully...")


# FastAPIアプリケーションの作成
app = FastAPI(
    title="Eliza Agent Server",
    description="Grok API with x_search, web_search, and Switchbot tools",
    lifespan=lifespan,
)


def _generate_message_id() -> str:
    """現在時刻と乱数から16文字のhex message_id を生成する"""
    raw = f"{datetime.now(JST).isoformat()}-{os.urandom(8).hex()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# リクエスト/レスポンスのスキーマ
class Message(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(JST))
    message_id: str = Field(default_factory=_generate_message_id)


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str = "grok-4-1-fast"
    use_memory: bool = True
    detect_sleep: bool = True
    max_tool_loops: int = 5


class ChatResponse(BaseModel):
    message: Message
    reasoning: str | None = None
    sleep: bool = False
    tool: list[tuple[dict[str, Any], dict[str, Any] | None]] | None = None
    citations: list[str] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    status: str


@app.post("/chat", response_model=ChatResponse)
async def post_chat(request: ChatRequest) -> ChatResponse:
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

    MAX_RETRIES = 3
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"[REQUEST ID: {request_id}] Creating Grok client... (attempt {attempt}/{MAX_RETRIES})"
            )
            agent = Agent(
                api_key=XAI_API_KEY,
                model=request.model,
                use_memory=request.use_memory,
            )
            result = agent.run(
                messages=[
                    {"role": m.role, "content": m.content} for m in request.messages
                ],
                request_id=request_id,
                max_tool_loops=request.max_tool_loops,
                detect_sleep=request.detect_sleep,
            )

            logger.info("-" * 80)
            logger.info(f"[RESPONSE ID: {request_id}] Success")
            logger.info("[RESPONSE] Role: assistant")
            logger.info(f"[RESPONSE] Content length: {len(result.content)} chars")
            logger.info("[RESPONSE] Content:")
            logger.info(
                f"  {result.content[:500]}{'...' if len(result.content) > 500 else ''}"
            )
            logger.info("=" * 80)

            response_message = Message(role="assistant", content=result.content)

            # 受信メッセージ + 生成メッセージを SQLite に保存
            all_msgs = list(request.messages) + [response_message]
            eliza.memory.save_messages(
                [
                    {
                        "message_id": m.message_id,
                        "timestamp": m.timestamp.isoformat(),
                        "role": m.role,
                        "content": m.content,
                    }
                    for m in all_msgs
                ]
            )

            return ChatResponse(
                message=response_message,
                reasoning=result.reasoning,
                sleep=result.sleep,
                tool=result.tool_history if result.tool_history else None,
                citations=result.citations,
            )

        except Exception as e:
            last_error = e
            logger.error(
                f"[REQUEST ID: {request_id}] Error occurred (attempt {attempt}/{MAX_RETRIES}): {str(e)}"
            )
            if attempt < MAX_RETRIES:
                logger.info(f"[REQUEST ID: {request_id}] Retrying...")
            else:
                logger.error("=" * 80)

    raise HTTPException(status_code=500, detail=f"Error: {str(last_error)}")


def _generate_summary_in_background(request_id: str):
    """バックグラウンドで summary 生成を実行する"""
    try:
        logger.info(f"[REQUEST ID: {request_id}] Generating summary ...")
        result = eliza.memory.generate_summary(model="grok-4-1-fast")
        summary_str = json.dumps(result, ensure_ascii=False)
        logger.info(
            f"[REQUEST ID: {request_id}] Summary done: {summary_str[:500]}{'...' if len(summary_str) > 500 else ''}"
        )
        logger.info("=" * 80)
    except Exception as e:
        logger.error(
            f"[REQUEST ID: {request_id}] Error in summary background task: {str(e)}"
        )
        logger.error("=" * 80)


@app.post("/summary", status_code=202, response_model=SummaryResponse)
async def post_summary(background_tasks: BackgroundTasks) -> SummaryResponse:
    """
    メモリ要約を生成します。
    処理はバックグラウンドで実行され、即座に 202 Accepted を返します。
    """
    request_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")

    logger.info("=" * 80)
    logger.info(f"[REQUEST ID: {request_id}] POST /summary")

    background_tasks.add_task(_generate_summary_in_background, request_id)

    logger.info(f"[REQUEST ID: {request_id}] Accepted. Processing in background.")

    return SummaryResponse(status="accepted")


@app.get("/health")
async def get_health() -> dict[str, str]:
    """ヘルスチェックエンドポイント"""
    return {"status": "ok"}


@app.get("/tools")
async def get_tools() -> dict[str, list[str]]:
    """利用可能なツール一覧を返す"""
    available_tools = eliza.tools.create_tools()
    tool_names = [
        tool.function.name if tool.function.name else str(tool).split()[0]
        for tool in available_tools
    ]
    return {"tools": tool_names}


def main():
    """サーバーを起動"""

    def _handle_signal(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}. Initiating graceful shutdown...")
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    uvicorn.run("server:app", host="0.0.0.0", port=9096, workers=4, reload=True)


if __name__ == "__main__":
    main()
