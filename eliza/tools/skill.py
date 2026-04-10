"""Skill tool - ./skill/ ディレクトリのスキル定義を読み込んで tool として提供する"""

import os
from pathlib import Path
from typing import Any

from cachetools import TTLCache, cached
from jinja2 import Template
from pydantic import BaseModel, Field
from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

SKILL_DIR = Path(os.environ.get("SKILL_DIR", "./skill"))


class SkillDef:
    """スキル定義"""

    def __init__(self, name: str, description: str, instruction: str):
        """スキル定義を初期化する

        Parameters
        ----------
        name
            スキル名
        description
            スキルの説明
        instruction
            スキルの実行手順
        """
        self.name = name
        self.description = description
        self.instruction = instruction


_DEEP_ONLY_SKILLS = {"deep_research"}
_CACHE_TTL = 30.0


@cached(cache=TTLCache(maxsize=4, ttl=_CACHE_TTL))
def _load_skills(deep: bool = False, interact: bool = False) -> list[SkillDef]:
    """SKILL_DIR 以下の .md ファイルを読み込んでスキル一覧を返す

    スキル本文は Jinja2 テンプレートとして interact 変数を渡してレンダリングする

    Parameters
    ----------
    deep
        False のとき deep_research など deep 専用スキルを除外する
    interact
        スキルテンプレートに渡す interact フラグ
    """
    skills = []
    if not SKILL_DIR.exists():
        return skills
    for md_file in sorted(SKILL_DIR.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            name, description, instruction = _parse_skill_md(content, interact=interact)
            if name and description:
                if not deep and name in _DEEP_ONLY_SKILLS:
                    continue
                skills.append(
                    SkillDef(
                        name=name, description=description, instruction=instruction
                    )
                )
        except Exception:
            pass
    return skills


def _parse_skill_md(content: str, interact: bool = False) -> tuple[str, str, str]:
    """frontmatter から name/description を取得し 残りを Jinja2 テンプレートとしてレンダリングして返す

    Parameters
    ----------
    content
        スキル .md ファイルの全文
    interact
        テンプレートに渡す interact フラグ
    """
    name = ""
    description = ""
    instruction = content

    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            frontmatter = content[3:end].strip()
            instruction = content[end + 3 :].strip()
            for line in frontmatter.splitlines():
                if line.startswith("name:"):
                    name = line[len("name:") :].strip()
                elif line.startswith("description:"):
                    description = line[len("description:") :].strip()

    instruction = Template(instruction).render(interact=interact).strip()
    return name, description, instruction


class SkillUseParams(BaseModel):
    skill_name: str = Field(description="使用するスキルの名前")


class Skill:
    """スキルツール"""

    def __init__(self, deep: bool = False, interact: bool = False):
        """スキルツールを初期化する

        Parameters
        ----------
        deep
            True のとき deep_research など deep 専用スキルを含める
        interact
            True のとき スキルの instruction を interact モードでレンダリングする
        """
        self.deep = deep
        self.interact = interact

    def skills(self) -> list[SkillDef]:
        """利用可能なスキル一覧を返す"""
        return _load_skills(deep=self.deep, interact=self.interact)

    def skill_use(self, skill_name: str) -> dict[str, Any]:
        """スキルの instruction を返す"""
        skills = _load_skills(deep=self.deep, interact=self.interact)
        for skill in skills:
            if skill.name == skill_name:
                return {
                    "name": skill.name,
                    "instruction": skill.instruction,
                    "next_step": "これはツールの手順書になります。この手順に従い tool をあなたが実行してください",
                }
        return {"error": f"Skill '{skill_name}' not found"}

    def create_tools(self) -> list[chat_pb2.Tool]:
        """skill_use ツールを返す"""
        skills = _load_skills(deep=self.deep, interact=self.interact)
        if not skills:
            return []
        skill_list = "\n".join(f"- {s.name}" for s in skills)
        return [
            tool(
                name="skill_use",
                description=(
                    "特定のタスクを実行するための手順（Skill）を取得します。\n"
                    "以下はあなたが利用できる Skill のリストです。\n"
                    "これは tool を更に抽象化したもので、特定のタスクを実行するための手順が定義されています。\n\n"
                    f"{skill_list}\n\n"
                    "【重要】tool を直接使う前に、まずこのツールで該当する Skill がないか確認してください。\n"
                    "Skill がある場合は必ず skill_use を呼び出して手順を取得し、その手順に従って実行してください。\n"
                    "Skill を使わずに tool を直接呼び出すことは非推奨です。"
                ),
                parameters=SkillUseParams.model_json_schema(),
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a skill tool by name"""
        match tool_name:
            case "skill_use":
                return self.skill_use(skill_name=tool_args["skill_name"])
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
