"""ToDo tool for Grok agent - やるべきことリストの管理"""

import json
import os
from datetime import datetime
from typing import Any

from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

TODO_FILE = ".memory/todo.json"


def _load() -> list[dict]:
    if not os.path.exists(TODO_FILE):
        return []
    with open(TODO_FILE) as f:
        return json.load(f)


def _save(todos: list[dict]):
    os.makedirs(os.path.dirname(TODO_FILE), exist_ok=True)
    with open(TODO_FILE, "w") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)


class ToDo:
    """やるべきことリストを管理するツール"""

    def list_todos(self, include_done: bool = False) -> dict[str, Any]:
        """ToDoリストを返す"""
        todos = _load()
        if not include_done:
            todos = [t for t in todos if not t.get("done", False)]
        return {"status": "ok", "count": len(todos), "todos": todos}

    def add(self, title: str, note: str = "") -> dict[str, Any]:
        """ToDoを追加する"""
        todos = _load()
        new_id = max((t["id"] for t in todos), default=0) + 1
        item = {
            "id": new_id,
            "title": title,
            "note": note,
            "done": False,
            "created_at": datetime.now().isoformat(),
        }
        todos.append(item)
        _save(todos)
        return {"status": "ok", "added": item}

    def done(self, todo_id: int) -> dict[str, Any]:
        """ToDoを完了にする"""
        todos = _load()
        for t in todos:
            if t["id"] == todo_id:
                t["done"] = True
                t["done_at"] = datetime.now().isoformat()
                _save(todos)
                return {"status": "ok", "done": t}
        return {"status": "error", "message": f"ID {todo_id} のToDoが見つかりません"}

    def delete(self, todo_id: int) -> dict[str, Any]:
        """ToDoを削除する"""
        todos = _load()
        new_todos = [t for t in todos if t["id"] != todo_id]
        if len(new_todos) == len(todos):
            return {"status": "error", "message": f"ID {todo_id} のToDoが見つかりません"}
        _save(new_todos)
        return {"status": "ok", "deleted_id": todo_id}

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="todo_list",
                description=(
                    "やるべきことリスト（ToDo）を一覧表示します。"
                    "デフォルトでは未完了のものだけ返します。"
                    "include_done=true にすると完了済みも含めます。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "include_done": {
                            "type": "boolean",
                            "description": "完了済みのToDoも含めるか（デフォルト: false）",
                        },
                    },
                    "required": [],
                },
            ),
            tool(
                name="todo_add",
                description=(
                    "やるべきことリスト（ToDo）に新しいタスクを追加します。"
                    "「〇〇をToDoに追加して」「〇〇をやることリストに入れて」などに使います。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "タスクのタイトル",
                        },
                        "note": {
                            "type": "string",
                            "description": "補足メモ（任意）",
                        },
                    },
                    "required": ["title"],
                },
            ),
            tool(
                name="todo_done",
                description=(
                    "指定したIDのToDoを完了にします。"
                    "「〇〇が終わった」「〇〇を完了にして」などに使います。"
                    "IDは todo_list で確認できます。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "integer",
                            "description": "完了にするToDoのID",
                        },
                    },
                    "required": ["id"],
                },
            ),
            tool(
                name="todo_delete",
                description=(
                    "指定したIDのToDoを削除します。"
                    "「〇〇を消して」「〇〇をリストから削除して」などに使います。"
                    "IDは todo_list で確認できます。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "integer",
                            "description": "削除するToDoのID",
                        },
                    },
                    "required": ["id"],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a todo tool by name"""
        match tool_name:
            case "todo_list":
                return self.list_todos(include_done=tool_args.get("include_done", False))
            case "todo_add":
                return self.add(title=tool_args["title"], note=tool_args.get("note", ""))
            case "todo_done":
                return self.done(todo_id=tool_args["id"])
            case "todo_delete":
                return self.delete(todo_id=tool_args["id"])
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
