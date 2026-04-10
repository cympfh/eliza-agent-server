<memory_instruction>
以下はユーザーと過去にやりとりして話した内容と、ここから得られたユーザーに関する情報をまとめたものです。ユーザーのことを理解するために、これらの内容を参考にしてください。
---
{% if summary_str %}## 会話の要約
<conversation_summary>
{{ summary_str }}
</conversation_summary>
{% endif %}
{% if recent_messages %}
<conversation_history>
## 最近の会話（直近3往復）
{% for msg in recent_messages %}[{{ msg.role }}]: {{ msg.content }}{% endfor %}
</conversation_history>
{% endif %}
</memory_instruction>
