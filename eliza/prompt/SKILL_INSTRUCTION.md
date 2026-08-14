<skill_instruction>
該当するスキルの手順に従い、必要なツールをこのターンで全て同時に呼べ。1つずつ呼ぶな。
複数スキルが該当するならまとめて実行する。
追加のツールが不要なら、最後の実ツールと同じターンで ready_to_answer を呼べ。

{% for s in skills %}
<skill>
<name>{{ s.name }}</name>
<description>
{{ s.description }}
</description>
<instruction>
{{ s.instruction }}
</instruction>
</skill>
{% endfor %}
</skill_instruction>
