"""Workspace tool for Grok agent - ワークスペース内のファイル読み書き"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

WORKSPACE_ROOT = Path(
    os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Dropbox/mouse-server/eliza"))
).expanduser()
JST = ZoneInfo("Asia/Tokyo")

_DEFAULT_TAIL = 100


def _safe_workspace_dir(workspace: str) -> Path | None:
    """workspace 名から安全なディレクトリパスを返す

    Parameters
    ----------
    workspace
        ワークスペース名
    """
    if not workspace or "/" in workspace or "\\" in workspace or workspace.startswith("."):
        return None
    return (WORKSPACE_ROOT / workspace).resolve()


def _safe_file_path(workspace: str, filename: str) -> Path | None:
    """workspace 名とファイル名から安全なファイルパスを返す

    パストラバーサルを防ぐため workspace ディレクトリ配下に収まるか検証する

    Parameters
    ----------
    workspace
        ワークスペース名
    filename
        ファイル名
    """
    ws_dir = _safe_workspace_dir(workspace)
    if ws_dir is None or not filename:
        return None
    target = (ws_dir / filename).resolve()
    try:
        target.relative_to(ws_dir)
    except ValueError:
        return None
    return target


class WorkspaceListParams(BaseModel):
    pass


class WorkspaceListFilesParams(BaseModel):
    workspace: str = Field(description="ファイル一覧を取得する workspace 名")


class WorkspaceReadParams(BaseModel):
    workspace: str = Field(description="読み込むファイルがある workspace 名")
    filename: str = Field(description="読み込むファイル名")
    tail: int = Field(
        _DEFAULT_TAIL, description=f"末尾何行を返すか デフォルト {_DEFAULT_TAIL}"
    )
    full: bool = Field(False, description="True のとき全文を返す tail を無視する")


class WorkspaceWriteParams(BaseModel):
    workspace: str = Field(description="書き込むファイルがある workspace 名")
    filename: str = Field(description="書き込むファイル名")
    content: str = Field(description="書き込む内容")
    append: bool = Field(
        False, description="True のとき追記モード False のとき上書きモード"
    )


class Workspace:
    """ワークスペース内のファイルを読み書きするツール"""

    def list_workspaces(self) -> dict[str, Any]:
        """workspace の一覧を返す"""
        if not WORKSPACE_ROOT.exists():
            return {"status": "ok", "workspaces": []}
        workspaces = sorted(
            d.name for d in WORKSPACE_ROOT.iterdir() if d.is_dir() and not d.name.startswith(".")
        )
        return {"status": "ok", "workspaces": workspaces}

    def list_files(self, workspace: str) -> dict[str, Any]:
        """workspace 内のファイル一覧を返す"""
        ws_dir = _safe_workspace_dir(workspace)
        if ws_dir is None:
            return {"status": "error", "message": f"不正な workspace 名 {workspace}"}
        if not ws_dir.exists():
            return {"status": "error", "message": f"workspace が存在しません {workspace}"}
        files = sorted(f.name for f in ws_dir.iterdir() if f.is_file())
        return {"status": "ok", "workspace": workspace, "files": files}

    def read_file(
        self, workspace: str, filename: str, tail: int = _DEFAULT_TAIL, full: bool = False
    ) -> dict[str, Any]:
        """ファイルの内容を返す"""
        path = _safe_file_path(workspace, filename)
        if path is None:
            return {"status": "error", "message": "不正な workspace 名またはファイル名"}
        if not path.exists() or not path.is_file():
            return {"status": "error", "message": f"ファイルが存在しません {filename}"}
        lines = path.read_text(encoding="utf-8").splitlines()
        total = len(lines)
        if full:
            shown = lines
            truncated = False
        else:
            shown = lines[-tail:]
            truncated = total > tail
        return {
            "status": "ok",
            "workspace": workspace,
            "filename": filename,
            "total_lines": total,
            "truncated": truncated,
            "content": "\n".join(shown),
        }

    def write_file(
        self, workspace: str, filename: str, content: str, append: bool = False
    ) -> dict[str, Any]:
        """ファイルに書き込む"""
        path = _safe_file_path(workspace, filename)
        if path is None:
            return {"status": "error", "message": "不正な workspace 名またはファイル名"}
        ws_dir = path.parent
        if not ws_dir.exists():
            return {"status": "error", "message": f"workspace が存在しません {workspace}"}
        if append:
            ts = datetime.now(JST).strftime("[%Y-%m-%d %H:%M:%S]")
            body = f"{ts} {content}"
            if not body.endswith("\n"):
                body += "\n"
            with open(path, "a", encoding="utf-8") as f:
                f.write(body)
            written = len(body)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            written = len(content)
        return {
            "status": "ok",
            "workspace": workspace,
            "filename": filename,
            "mode": "append" if append else "overwrite",
            "written_chars": written,
        }

    def create_tools(self) -> list[chat_pb2.Tool]:
        """Grok agent 用のツール定義を作成"""
        return [
            tool(
                name="workspace_list",
                description=(
                    "利用可能な workspace の一覧を返します。"
                    "workspace はファイルを保存するためのディレクトリです。"
                ),
                parameters=WorkspaceListParams.model_json_schema(),
            ),
            tool(
                name="workspace_list_files",
                description=(
                    "指定した workspace 内のファイル一覧を返します。"
                    "workspace 名は workspace_list で確認できます。"
                ),
                parameters=WorkspaceListFilesParams.model_json_schema(),
            ),
            tool(
                name="workspace_read",
                description=(
                    "workspace 内のファイルを読み込みます。"
                    "デフォルトでは末尾100行を返します。"
                    "全文が必要な場合は full=true を指定します。"
                ),
                parameters=WorkspaceReadParams.model_json_schema(),
            ),
            tool(
                name="workspace_write",
                description=(
                    "workspace 内のファイルに書き込みます。"
                    "append=false で上書き append=true で追記します。"
                    "追記モードでは行頭に [YYYY-MM-DD HH:MM:SS] のタイムスタンプが自動で付きます。"
                    "既存ファイルを編集する場合は workspace_read で内容を確認してから書き込んでください。"
                ),
                parameters=WorkspaceWriteParams.model_json_schema(),
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a workspace tool by name"""
        match tool_name:
            case "workspace_list":
                return self.list_workspaces()
            case "workspace_list_files":
                return self.list_files(workspace=tool_args["workspace"])
            case "workspace_read":
                return self.read_file(
                    workspace=tool_args["workspace"],
                    filename=tool_args["filename"],
                    tail=tool_args.get("tail", _DEFAULT_TAIL),
                    full=tool_args.get("full", False),
                )
            case "workspace_write":
                return self.write_file(
                    workspace=tool_args["workspace"],
                    filename=tool_args["filename"],
                    content=tool_args["content"],
                    append=tool_args.get("append", False),
                )
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
