import asyncio
import hashlib
import json
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

import eliza.memory
import eliza.tools
from eliza.agents.operation import Agent
from eliza.agents.question import QuestionAgent
from eliza.agents.router import IntentLabel, IntentRouter
from eliza.agents.trivial import TrivialAgent

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
    """FastAPI アプリのライフサイクル管理

    Parameters
    ----------
    app
        FastAPI アプリインスタンス
    """
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
    use_memory: bool = True
    detect_sleep: bool = True
    max_tool_loops: int = 5
    deep: bool = False
    interact: bool = False


class ChatResponse(BaseModel):
    message: Message
    reasoning: str | None = None
    sleep: bool = False
    tool: list[tuple[dict[str, Any], dict[str, Any] | None]] | None = None
    citations: list[str] = Field(default_factory=list)
    elapsed_ms: int = 0


class SummaryResponse(BaseModel):
    status: str


@app.post("/eliza/api/chat", response_model=ChatResponse)
async def post_chat(request: ChatRequest) -> ChatResponse:
    """会話履歴を受け取り次の返答を生成する

    サーバーは状態を持たず毎回の呼び出しで完全な会話履歴を受け取る

    Parameters
    ----------
    request
        チャットリクエスト (messages, model, オプション群を含む)
    """
    request_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    request_start = time.monotonic()

    # リクエストの詳細ログ
    logger.info("=" * 80)
    logger.info(f"[REQUEST ID: {request_id}] POST /chat")
    logger.info("-" * 80)
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
            messages_dicts = [
                {"role": m.role, "content": m.content} for m in request.messages
            ]

            # router で意図を分類
            intent_result = await asyncio.to_thread(
                IntentRouter(api_key=XAI_API_KEY).classify,
                messages_dicts,
                request_id,
            )
            logger.info(
                f"[REQUEST ID: {request_id}] Intent: {intent_result.label}, query_hint: {intent_result.query_hint}"
            )

            if intent_result.label == IntentLabel.Trivial:
                result = await asyncio.to_thread(
                    TrivialAgent(
                        api_key=XAI_API_KEY,
                        use_memory=request.use_memory,
                    ).run,
                    messages=messages_dicts,
                    request_id=request_id,
                    detect_sleep=request.detect_sleep,
                    query_hint=intent_result.query_hint,
                )
            elif intent_result.label == IntentLabel.Question:
                result = await asyncio.to_thread(
                    QuestionAgent(
                        api_key=XAI_API_KEY,
                        use_memory=request.use_memory,
                    ).run,
                    messages=messages_dicts,
                    request_id=request_id,
                    detect_sleep=request.detect_sleep,
                    query_hint=intent_result.query_hint,
                )
            else:
                # Operation (default)
                result = await asyncio.to_thread(
                    Agent(
                        api_key=XAI_API_KEY,
                        use_memory=request.use_memory,
                        deep=request.deep,
                        interact=request.interact,
                    ).run,
                    messages=messages_dicts,
                    request_id=request_id,
                    max_tool_loops=request.max_tool_loops,
                    detect_sleep=request.detect_sleep,
                    query_hint=intent_result.query_hint,
                )

            elapsed_ms = int((time.monotonic() - request_start) * 1000)
            logger.info("-" * 80)
            logger.info(f"[RESPONSE ID: {request_id}] Success ({elapsed_ms} ms)")
            logger.info("[RESPONSE] Role: assistant")
            logger.info(f"[RESPONSE] Content length: {len(result.content)} chars")
            logger.info("[RESPONSE] Content:")
            logger.info(f"  {result.content}")
            logger.info("[RESPONSE] Reasoning:")
            logger.info(f"  {result.reasoning}")
            logger.info("[RESPONSE] Citations:")
            if result.citations:
                for url in result.citations:
                    logger.info(f"  {url}")
            else:
                logger.info("  -- no citations --")
            logger.info("=" * 80)

            response_message = Message(role="assistant", content=result.content)

            # 受信メッセージ + 生成メッセージを SQLite に保存
            save_records = [
                {
                    "message_id": m.message_id,
                    "timestamp": m.timestamp.isoformat(),
                    "role": m.role,
                    "content": m.content,
                }
                for m in request.messages
            ] + [
                {
                    "message_id": response_message.message_id,
                    "timestamp": response_message.timestamp.isoformat(),
                    "role": response_message.role,
                    "content": response_message.content,
                    "reasoning": result.reasoning,
                }
            ]
            eliza.memory.save_messages(save_records)

            return ChatResponse(
                message=response_message,
                reasoning=result.reasoning,
                sleep=result.sleep,
                tool=result.tool_history if result.tool_history else None,
                citations=result.citations,
                elapsed_ms=elapsed_ms,
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


@app.post("/eliza/api/summary", status_code=202, response_model=SummaryResponse)
async def post_summary(background_tasks: BackgroundTasks) -> SummaryResponse:
    """メモリ要約をバックグラウンドで生成する

    処理はバックグラウンドで実行され即座に 202 Accepted を返す

    Parameters
    ----------
    background_tasks
        FastAPI の BackgroundTasks インスタンス
    """
    request_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")

    logger.info("=" * 80)
    logger.info(f"[REQUEST ID: {request_id}] POST /summary")

    background_tasks.add_task(_generate_summary_in_background, request_id)

    logger.info(f"[REQUEST ID: {request_id}] Accepted. Processing in background.")

    return SummaryResponse(status="accepted")


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
