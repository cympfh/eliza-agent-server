"""スキル定義の読み込み。ツールではない。"""

import os
from pathlib import Path

from cachetools import TTLCache, cached
from jinja2 import Template

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


_CACHE_TTL = 30.0


@cached(cache=TTLCache(maxsize=4, ttl=_CACHE_TTL))
def load_skills() -> list[SkillDef]:
    """SKILL_DIR 以下の .md ファイルを読み込んでスキル一覧を返す

    スキル本文は Jinja2 テンプレートとしてレンダリングする
    """
    skills = []
    if not SKILL_DIR.exists():
        return skills
    for md_file in sorted(SKILL_DIR.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            name, description, instruction = _parse_skill_md(content)
            if name and description:
                skills.append(
                    SkillDef(
                        name=name, description=description, instruction=instruction
                    )
                )
        except Exception:
            pass
    return skills


def _parse_skill_md(content: str) -> tuple[str, str, str]:
    """frontmatter から name/description を取得し 残りを Jinja2 テンプレートとしてレンダリングして返す

    Parameters
    ----------
    content
        スキル .md ファイルの全文
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

    instruction = Template(instruction).render().strip()
    return name, description, instruction
