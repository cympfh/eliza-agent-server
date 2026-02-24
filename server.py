import json
import logging
import os
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel
from xai_sdk import Client, chat

import eliza.memory
import eliza.tools

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
    use_memory: bool = True


class ChatResponse(BaseModel):
    message: Message
    sleep: bool = False
    tool: list[tuple[dict[str, Any], dict[str, Any] | None]] | None = None


class MemoryRequest(BaseModel):
    messages: list[Message]
    model: str = "grok-4-1-fast"


class MemoryAcceptedResponse(BaseModel):
    status: str
    message: str
    request_id: str


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
            # Grok クライアントの作成
            logger.info(
                f"[REQUEST ID: {request_id}] Creating Grok client... (attempt {attempt}/{MAX_RETRIES})"
            )
            client = Client(api_key=XAI_API_KEY)

            # tools を有効化してチャットセッション作成
            available_tools = eliza.tools.create_tools()
            logger.info(
                f"[REQUEST ID: {request_id}] Creating chat session with {len(available_tools)} tools..."
            )
            session = client.chat.create(
                model=request.model,
                tools=available_tools,
            )

            # 会話履歴を追加
            logger.info(f"[REQUEST ID: {request_id}] Appending conversation history...")

            # memory summary を system メッセージとして差し込む
            def _inject_memory_summary():
                if request.use_memory:
                    summary = eliza.memory.get()
                    if summary:
                        logger.info(
                            f"[REQUEST ID: {request_id}] Injecting memory summary as system message..."
                        )
                        summary_str = json.dumps(summary, ensure_ascii=False, indent=2)
                        session.append(
                            chat.system(
                                f"以下はユーザーとの過去の会話の要約です:\n{summary_str}"
                            )
                        )

            injected = False
            if request.messages[0].role != "system":
                _inject_memory_summary()
                injected = True

            for msg in request.messages:
                if msg.role == "system":
                    session.append(chat.system(msg.content))
                    if not injected:
                        _inject_memory_summary()
                        injected = True
                elif msg.role == "user":
                    session.append(chat.user(msg.content))
                elif msg.role == "assistant":
                    session.append(chat.assistant(msg.content))

            # sleep 検出のためのシステムメッセージを追加
            session.append(
                chat.system(
                    "ユーザーが寝る、または既に寝ていると判断した場合（例: おやすみ、寝る、などの発言や寝息と推察される内容）、"
                    "レスポンスの末尾に `[SLEEP]` というマーカーを付けてください。"
                )
            )

            # レスポンス生成, function calling (最大3回のループ)
            MAX_TOOL_LOOPS = 3
            tool_history: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
            for tool_loop in range(1, MAX_TOOL_LOOPS + 1):
                logger.info(
                    f"[REQUEST ID: {request_id}] Generating response... (tool loop {tool_loop}/{MAX_TOOL_LOOPS})"
                )
                response = session.sample()
                tool_used = False
                if response.tool_calls:
                    logger.info(
                        f"[REQUEST ID: {request_id}] Tool calls detected: {len(response.tool_calls)}"
                    )
                    for tool_call in response.tool_calls:
                        tool_name: str = tool_call.function.name
                        tool_args = (
                            json.loads(tool_call.function.arguments)
                            if tool_call.function.arguments
                            else {}
                        )
                        logger.info(
                            f"[REQUEST ID: {request_id}] Tool call: {tool_name} with args: {tool_args}"
                        )
                        result = eliza.tools.call(tool_name, tool_args)
                        tool_history.append(
                            ({"name": tool_name, "args": tool_args}, result)
                        )
                        if result:
                            tool_used = True
                            session.append(chat.tool_result(json.dumps(result)))
                if tool_used:
                    if tool_loop >= MAX_TOOL_LOOPS - 1:
                        logger.warning(
                            f"[REQUEST ID: {request_id}] Tool loop limit reached. Forcing final response without tools."
                        )
                        session.append(
                            chat.system(
                                "ツール呼び出しの結果は上記の通りです。これ以上ツールは使用できません。今すぐユーザーへの最終回答を生成してください。"
                            )
                        )
                    else:
                        session.append(
                            chat.system(
                                f"ツール呼び出しの結果は上記の通りです。ユーザーへの回答を生成してください。必要ならあと {MAX_TOOL_LOOPS - tool_loop - 1} 回までツールを呼び出せます。"
                            )
                        )
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

            sleep = "[SLEEP]" in response.content
            return ChatResponse(
                message=Message(role="assistant", content=response.content),
                sleep=sleep,
                tool=tool_history if tool_history else None,
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


def _process_memory_in_background(request: MemoryRequest, request_id: str):
    """
    バックグラウンドでメモリ処理を実行する関数
    """
    try:
        if not request.messages:
            logger.info(
                f"[REQUEST ID: {request_id}] messages is empty. Skipping log append, refreshing summary only."
            )
            summary_all = eliza.memory.refresh_summary(model=request.model)
            result = {
                "summary": "",
                "important_facts": [],
                "feedback": "",
                "summary_all": summary_all,
            }
        else:
            logger.info(f"[REQUEST ID: {request_id}] Calling eliza.memory.append ...")
            result = eliza.memory.append(request)
        logger.info(f"[REQUEST ID: {request_id}] Done.")
        logger.info(f"[MEMORY] summary: {result['summary']}")
        logger.info(f"[MEMORY] important_facts: {result['important_facts']}")
        logger.info(f"[MEMORY] feedback: {result['feedback']}")
        summary_all_str = json.dumps(result["summary_all"], ensure_ascii=False)
        logger.info(
            f"[MEMORY] summary_all: {summary_all_str[:1000]}{'...' if len(summary_all_str) > 1000 else ''}"
        )
        logger.info("=" * 80)
    except Exception as e:
        logger.error(
            f"[REQUEST ID: {request_id}] Error occurred in background task: {str(e)}"
        )
        logger.error("=" * 80)


@app.post("/memory", status_code=202, response_model=MemoryAcceptedResponse)
async def post_memory(
    request: MemoryRequest, background_tasks: BackgroundTasks
) -> MemoryAcceptedResponse:
    """
    会話履歴をメモリに記録します。
    処理はバックグラウンドで実行され、即座に 202 Accepted を返します。
    """
    request_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")

    logger.info("=" * 80)
    logger.info(f"[REQUEST ID: {request_id}] POST /memory")
    logger.info("-" * 80)
    logger.info(f"[REQUEST] Model: {request.model}")
    logger.info(f"[REQUEST] Number of messages: {len(request.messages)}")
    for i, msg in enumerate(request.messages):
        logger.info(
            f"  Message[{i}]: role={msg.role}, content={msg.content[:200]}{'...' if len(msg.content) > 200 else ''}"
        )
    logger.info("-" * 80)

    # バックグラウンドタスクに追加
    background_tasks.add_task(_process_memory_in_background, request, request_id)

    logger.info(f"[REQUEST ID: {request_id}] Accepted. Processing in background.")

    return MemoryAcceptedResponse(
        status="accepted",
        message="Memory processing started in background",
        request_id=request_id,
    )


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
    uvicorn.run("server:app", host="0.0.0.0", port=9096, workers=4, reload=True)


if __name__ == "__main__":
    main()
