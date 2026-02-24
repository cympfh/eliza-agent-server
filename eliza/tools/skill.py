"""Skill tool - ./skill/ ディレクトリのスキル定義を読み込んで tool として提供する"""

import os
from pathlib import Path
from typing import Any

from xai_sdk.chat import tool
from xai_sdk.proto import chat_pb2

SKILL_DIR = Path(os.environ.get("SKILL_DIR", "./skill"))


class SkillDef:
    """スキル定義"""

    def __init__(self, name: str, description: str, instruction: str):
        self.name = name
        self.description = description
        self.instruction = instruction


def _load_skills() -> list[SkillDef]:
    """SKILL_DIR 以下の .md ファイルを読み込んでスキル一覧を返す"""
    skills = []
    if not SKILL_DIR.exists():
        return skills
    for md_file in sorted(SKILL_DIR.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            name, description, instruction = _parse_skill_md(content)
            if name and description:
                skills.append(SkillDef(name=name, description=description, instruction=instruction))
        except Exception:
            pass
    return skills


def _parse_skill_md(content: str) -> tuple[str, str, str]:
    """frontmatter から name/description を取得し、残りを instruction として返す"""
    name = ""
    description = ""
    instruction = content

    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            frontmatter = content[3:end].strip()
            instruction = content[end + 3:].strip()
            for line in frontmatter.splitlines():
                if line.startswith("name:"):
                    name = line[len("name:"):].strip()
                elif line.startswith("description:"):
                    description = line[len("description:"):].strip()

    return name, description, instruction


class Skill:
    """スキルツール"""

    def skill_use(self, skill_name: str) -> dict[str, Any]:
        """スキルの instruction を返す"""
        skills = _load_skills()
        for skill in skills:
            if skill.name == skill_name:
                return {
                    "name": skill.name,
                    "instruction": skill.instruction,
                    "next_step": "この手順に従ってタスクを tool に分解し実行してください。",
                }
        return {"error": f"Skill '{skill_name}' not found"}

    def create_tools(self) -> list[chat_pb2.Tool]:
        """skill_use ツールを返す"""
        skills = _load_skills()
        if not skills:
            return []
        skill_list = "\n".join(f"- {s.name}: {s.description}" for s in skills)
        return [
            tool(
                name="skill_use",
                description=(
                    "特定のタスクを実行するための手順（Skill）を取得します。\n"
                    "以下はあなたが利用できる Skill のリストです。\n"
                    "これは tool を更に抽象化したもので、特定のタスクを実行するための手順が定義されています。\n\n"
                    f"{skill_list}\n\n"
                    "Skill を使う場合は、このツールを呼び出して手順を取得してください。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "使用するスキルの名前",
                        },
                    },
                    "required": ["skill_name"],
                },
            ),
        ]

    def call(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """Call a skill tool by name"""
        match tool_name:
            case "skill_use":
                return self.skill_use(skill_name=tool_args["skill_name"])
            case _:
                raise ValueError(f"Unknown tool: {tool_name}")
